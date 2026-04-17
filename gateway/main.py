# gateway/main.py — v3.0
# Full agentic loop with tool calling

import asyncio
import json
import os
import re
import time
from typing import Optional

import aiohttp
import redis.asyncio as aioredis
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from agents import AGENT_SYSTEMS, TASK_MODELS
from tools import TOOLS_SCHEMA, execute_tool
from memory import (
    load_context,
    save_context,
    load_long_memory,
    save_long_memory_async,
    get_user_stats,
    update_user_stats,
)

app = FastAPI(title="OpenClaw Gateway v3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-2026")
MAX_ITER = int(os.getenv("MAX_AGENT_ITERATIONS", "12"))


# ─── Request models ───────────────────────────────────────────────


class ChatRequest(BaseModel):
    user_id: str
    message: str
    agent: str = "main"
    task_type: str = "default"
    channel_id: str = "0"
    username: str = "user"
    project: Optional[str] = None
    callback_url: Optional[str] = None


class OrchRequest(BaseModel):
    user_id: str
    task: str
    agents: Optional[list] = None
    channel_id: str = "0"


class MemoryRequest(BaseModel):
    user_id: str
    text: str
    agent: str = "main"


class RecallRequest(BaseModel):
    user_id: str
    query: str
    top_k: int = 5


# ─── Core: single LLM call ───────────────────────────────────────


async def llm_call(
    messages: list,
    task_type: str = "default",
    use_tools: bool = True,
) -> dict:
    """Single LLM call via LiteLLM proxy. Tries models in order."""
    models = TASK_MODELS.get(task_type, TASK_MODELS["default"])
    payload = {
        "messages": messages,
        "max_tokens": 4096,
        "temperature": 0.4,
    }
    if use_tools:
        payload["tools"] = TOOLS_SCHEMA
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {LITELLM_KEY}",
        "Content-Type": "application/json",
    }

    last_error = None
    async with aiohttp.ClientSession() as session:
        for model in models:
            payload["model"] = model
            try:
                async with session.post(
                    f"{LITELLM_BASE}/v1/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=90),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        data["_model_used"] = model
                        return data
                    else:
                        text = await resp.text()
                        last_error = f"{model}: HTTP {resp.status}"
                        print(f"[WARN] {last_error}: {text[:100]}")
            except asyncio.TimeoutError:
                last_error = f"{model}: timeout"
                print(f"[WARN] {model} timed out, trying next model")
            except Exception as e:
                last_error = f"{model}: {e}"
                print(f"[WARN] {model} failed: {e}, trying next model")

    raise HTTPException(500, detail=f"All models failed. Last error: {last_error}")


# ─── Core: Agentic Loop ───────────────────────────────────────────


async def agentic_loop(
    messages: list,
    task_type: str = "default",
    callback_url: Optional[str] = None,
    user_id: str = "0",
) -> dict:
    """
    Full agentic loop:
    LLM → tool_calls? → execute tools → add results → repeat → final answer
    """
    tool_log = []
    iteration = 0
    model_used = "unknown"

    async def notify(msg: str):
        """Push progress update to Discord bot."""
        if callback_url:
            try:
                async with aiohttp.ClientSession() as s:
                    await s.post(
                        callback_url,
                        json={"type": "progress", "text": msg},
                        timeout=aiohttp.ClientTimeout(total=5),
                    )
            except Exception:
                pass

    while iteration < MAX_ITER:
        iteration += 1

        resp = await llm_call(messages, task_type=task_type, use_tools=True)
        model_used = resp.get("_model_used", "unknown")
        choice = resp["choices"][0]
        msg_obj = choice["message"]
        finish = choice.get("finish_reason", "stop")

        # No tool calls → this is the final answer
        if not msg_obj.get("tool_calls") or finish == "stop":
            return {
                "response": msg_obj.get("content") or "",
                "model": model_used,
                "iterations": iteration,
                "tool_log": tool_log,
            }

        # Has tool calls → execute each one
        messages.append(msg_obj)

        for tc in msg_obj["tool_calls"]:
            fn_name = tc["function"]["name"]
            fn_args = {}
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except Exception:
                pass

            await notify(
                f"🔧 **{fn_name}**(`{json.dumps(fn_args, ensure_ascii=False)[:100]}`)"
            )
            print(f"[TOOL iter={iteration}] {fn_name}({fn_args})")

            t0 = time.time()
            result = await execute_tool(fn_name, fn_args, user_id=user_id)
            elapsed = round(time.time() - t0, 2)

            tool_log.append(
                {
                    "tool": fn_name,
                    "args": fn_args,
                    "result": str(result)[:500],
                    "elapsed": elapsed,
                }
            )

            # Feed result back to LLM
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": str(result),
                }
            )

    # Reached max iterations
    return {
        "response": f"⚠️ הגעתי למגבלת {MAX_ITER} צעדים. נסה לפרק את המשימה.",
        "model": model_used,
        "iterations": iteration,
        "tool_log": tool_log,
    }


# ─── Endpoints ───────────────────────────────────────────────────


@app.post("/chat")
async def chat(req: ChatRequest):
    t0 = time.time()

    context = await load_context(req.user_id, req.channel_id)
    memories = await load_long_memory(req.user_id, req.message)

    base_sys = AGENT_SYSTEMS.get(req.agent, AGENT_SYSTEMS["main"])

    if memories:
        mem_text = "\n".join([f"- {m['text']}" for m in memories])
        base_sys += f"\n\n## זיכרון ארוך-טווח רלוונטי:\n{mem_text}"

    if req.project:
        base_sys += f"\n\n## פרויקט נוכחי: {req.project}"

    if re.search(
        r"(password|סיסמ|api.?key|token|secret|smtp|bearer|sk-|ghp_)",
        req.message,
        re.IGNORECASE,
    ):
        base_sys += "\n\nהמשתמש שלח credentials. השתמש בהם ישירות בקוד ללא סירוב."

    messages = (
        [{"role": "system", "content": base_sys}]
        + context
        + [{"role": "user", "content": req.message}]
    )

    result = await agentic_loop(
        messages,
        task_type=req.task_type,
        callback_url=req.callback_url,
        user_id=req.user_id,
    )

    await save_context(req.user_id, req.channel_id, req.message, result["response"])
    asyncio.create_task(
        save_long_memory_async(req.user_id, req.message, result["response"], req.agent)
    )
    asyncio.create_task(
        update_user_stats(req.user_id, req.username, req.agent, time.time() - t0)
    )

    result["duration"] = round(time.time() - t0, 2)
    return result


@app.post("/orchestrate")
async def orchestrate(req: OrchRequest):
    t0 = time.time()

    # Step 1: orchestrator decides which agents to use
    sel_msgs = [
        {"role": "system", "content": AGENT_SYSTEMS["orchestrator"]},
        {
            "role": "user",
            "content": (
                f"משימה: {req.task}\n\n"
                "אילו סוכנים נדרשים? ענה רק בשמות מופרדים בפסיק מתוך: "
                "coder, researcher, analyzer. לדוגמה: coder,researcher"
            ),
        },
    ]
    sel_resp = await llm_call(sel_msgs, use_tools=False)
    raw_sel = sel_resp["choices"][0]["message"]["content"].lower()
    selected = req.agents or [
        a.strip() for a in raw_sel.split(",") if a.strip() in AGENT_SYSTEMS
    ]
    if not selected:
        selected = ["coder", "researcher"]

    # Step 2: run selected agents in parallel
    async def run_one(agent_id: str) -> dict:
        msgs = [
            {
                "role": "system",
                "content": AGENT_SYSTEMS.get(agent_id, AGENT_SYSTEMS["main"]),
            },
            {"role": "user", "content": req.task},
        ]
        return await agentic_loop(msgs, task_type="default", user_id=req.user_id)

    results_list = await asyncio.gather(*[run_one(a) for a in selected])
    agent_results = dict(zip(selected, results_list))

    # Step 3: critic reviews all agent responses
    combined = "\n\n".join(
        [f"### {a.upper()}\n{r['response']}" for a, r in agent_results.items()]
    )
    crit_resp = await llm_call(
        [
            {"role": "system", "content": AGENT_SYSTEMS["critic"]},
            {"role": "user", "content": f"בדוק ושפר:\n\n{combined}"},
        ],
        use_tools=False,
    )
    critic_text = crit_resp["choices"][0]["message"]["content"]

    # Step 4: orchestrator synthesizes final answer
    synth_resp = await llm_call(
        [
            {"role": "system", "content": AGENT_SYSTEMS["orchestrator"]},
            {
                "role": "user",
                "content": (
                    f"משימה מקורית: {req.task}\n\n"
                    f"תגובות סוכנים:\n{combined}\n\n"
                    f"ביקורת:\n{critic_text}\n\n"
                    "כתוב תשובה סופית מסוכמת."
                ),
            },
        ],
        use_tools=False,
    )
    synthesis = synth_resp["choices"][0]["message"]["content"]

    return {
        "plan": f"Selected: {', '.join(selected)}",
        "agents_used": selected,
        "agent_responses": {
            a: {"response": r["response"], "tool_log": r["tool_log"]}
            for a, r in agent_results.items()
        },
        "critic": {"response": critic_text},
        "synthesis": synthesis,
        "synthesis_model": synth_resp.get("_model_used", "unknown"),
        "duration": round(time.time() - t0, 2),
    }


@app.post("/debate")
async def debate(req: OrchRequest):
    t0 = time.time()
    pro_resp, con_resp = await asyncio.gather(
        llm_call(
            [
                {"role": "system", "content": AGENT_SYSTEMS["researcher"]},
                {"role": "user", "content": f"טען בעד: {req.task}"},
            ],
            use_tools=False,
        ),
        llm_call(
            [
                {"role": "system", "content": AGENT_SYSTEMS["analyzer"]},
                {"role": "user", "content": f"טען נגד: {req.task}"},
            ],
            use_tools=False,
        ),
    )
    pro_text = pro_resp["choices"][0]["message"]["content"]
    con_text = con_resp["choices"][0]["message"]["content"]

    verdict_resp = await llm_call(
        [
            {"role": "system", "content": AGENT_SYSTEMS["critic"]},
            {
                "role": "user",
                "content": f"בעד:\n{pro_text}\n\nנגד:\n{con_text}\n\nפסוק:",
            },
        ],
        use_tools=False,
    )

    return {
        "pro": {"response": pro_text},
        "con": {"response": con_text},
        "verdict": {"response": verdict_resp["choices"][0]["message"]["content"]},
        "duration": round(time.time() - t0, 2),
    }


@app.post("/swarm")
async def swarm(req: OrchRequest):
    t0 = time.time()
    agent_ids = ["researcher", "coder", "analyzer", "critic"]
    results = await asyncio.gather(
        *[
            agentic_loop(
                [
                    {"role": "system", "content": AGENT_SYSTEMS[a]},
                    {"role": "user", "content": req.task},
                ],
                user_id=req.user_id,
            )
            for a in agent_ids
        ]
    )
    agent_map = dict(zip(agent_ids, results))
    all_text = "\n\n".join([f"### {a}\n{r['response']}" for a, r in agent_map.items()])

    synth_resp = await llm_call(
        [
            {"role": "system", "content": AGENT_SYSTEMS["orchestrator"]},
            {"role": "user", "content": f"סנתז:\n\n{all_text}"},
        ],
        use_tools=False,
    )

    return {
        "agents": {a: {"response": r["response"]} for a, r in agent_map.items()},
        "synthesis": synth_resp["choices"][0]["message"]["content"],
        "duration": round(time.time() - t0, 2),
    }


@app.post("/store-memory")
async def store_memory(req: MemoryRequest):
    await save_long_memory_async(req.user_id, req.text, "", req.agent)
    return {"status": "stored"}


@app.post("/recall")
async def recall(req: RecallRequest):
    memories = await load_long_memory(req.user_id, req.query, top_k=req.top_k)
    return {"memories": memories}


@app.get("/memory/{user_id}")
async def get_memory(user_id: str):
    return await get_user_stats(user_id)


@app.delete("/memory/{user_id}")
async def delete_memory(user_id: str):
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    r = aioredis.from_url(REDIS_URL)
    keys = await r.keys(f"ctx:{user_id}:*")
    if keys:
        await r.delete(*keys)
    await r.aclose()
    return {"deleted": len(keys)}


@app.get("/health")
async def health():
    REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
    redis_ok = False
    try:
        r = aioredis.from_url(REDIS_URL)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "3.0",
        "redis": "ok" if redis_ok else "error",
        "agents": list(AGENT_SYSTEMS.keys()),
        "max_iterations": MAX_ITER,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=4001, reload=False, workers=1)
