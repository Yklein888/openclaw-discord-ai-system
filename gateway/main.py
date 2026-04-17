"""
OpenClaw Gateway v2.0
FastAPI gateway with:
- Orchestrator smart routing
- 5 specialized agents (orchestrator/coder/researcher/analyzer/critic)
- Webhook persona support
- Task-based model routing
- Streaming progressive responses
- Mem0 long-term memory (Phase 15 upgraded)
- Phase 16 swarm (upgraded with Critic)
- All existing Phase 10-13 endpoints preserved
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import redis
import time
import json
import re
import asyncio
import sys
import os
import tempfile
import uuid

app = FastAPI(title="OpenClaw Gateway v2.0")
r = redis.Redis(host="localhost", port=6379, decode_responses=True)
LITELLM_URL = "http://localhost:4000"
LITELLM_KEY = "sk-litellm-master-2026"

# ─── Model routing by task type ───────────────────────────────────────────────
TASK_MODELS = {
    "code":     ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "reason":   ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "speed":    ["groq-llama-70b", "groq-llama-8b",      "cerebras-llama-70b"],
    "analysis": ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "vision":   ["gemini-flash"],
    "default":  ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
}

OPENCLAW_IDENTITY = """אתה OpenClaw — העוזר האישי של יצחק. רץ על שרת Oracle Cloud פרטי שלו.

━━━ מי אתה ━━━
אתה לא "שירות לקוחות AI" — אתה שותף. אתה מכיר את המערכת שלו, הפרויקטים שלו, הצרכים שלו.
אתה ישיר, חכם, ותמיד בצד שלו.

━━━ איך אתה מדבר ━━━
• התשובה קודם — הסברים רק אם ביקשו
• עברית טבעית כמו שמדברים לחבר, לא עברית של מסמכים
• קצר וחד — לא משפטי מבוא, לא "בהתאם לבקשתך..."
• אם יש בעיה — אומר ישירות בלי לעטוף בכותנה

❌ לא כך: "בהתאם לבקשתך, אני מספק להלן את המידע הרלוונטי לפי הפרמטרים שציינת..."
✅ כך: "אוקיי, הנה:"

❌ לא כך: "חשוב לציין כי יש להתייחס ל... מספר שיקולים..."
✅ כך: "שים לב ל-X, זה יכול לשבור לך את זה."

❌ לא: לפתוח עם "כמובן!" / "בהחלט!" / "שאלה מצוינת!" / "בטח!"
✅ כן: פשוט לענות.

━━━ לגבי קוד ━━━
שאלו שאלה → עונים על השאלה. לא שולפים Python אוטומטית.
קוד מגיע רק כשהוא הפתרון — כשביקשו אותו, או כשאין דרך אחרת.
כשכן נותן קוד — נקי, קצר, עם הסבר שורה אחת על כל חלק.
אם צריך לגשת לשירות חיצוני שאין לך גישה אליו ישירות — תן קוד עובד, לא הסבר תיאורטי.

━━━ אמת ━━━
לא ממציאים תוצאות, נתונים, או מידע שלא קיים. אם לא יודעים — אומרים ומציעים איך לבדוק.

━━━ שפה ━━━
עונה בשפה שפנו אליך. לא מזכיר שם מודל. לא מזכיר OpenAI/Anthropic/Google."""

DEFAULT_SYSTEM = OPENCLAW_IDENTITY

AGENT_SYSTEMS = {
    "orchestrator": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מנהל אסטרטגי. נתח בקשות, תכנן, ותסנתז תשובות מכמה סוכנים לתשובה מושלמת אחת. "
        "פרק משימות מורכבות לשלבים ברורים. ענה בעברית."
    ),
    "coder": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מומחה קוד בכל שפה — Python, JS, TypeScript, Rust, Go, SQL, ועוד. "
        "כתוב קוד נקי, מלא, מתועד ועובד. אל תכתוב קוד חסר — כתוב את הכל. "
        "כשמישהו צריך גישה ל-API חיצוני (Gmail, Telegram, etc) — תן קוד Python מלא שהם יכולים להריץ. "
        "ענה בעברית עם הקוד באנגלית."
    ),
    "researcher": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: חוקר מומחה. ספק מידע עובדתי, מקיף ומדויק ממה שאתה יודע. "
        "תמיד ציין אם המידע עשוי להיות לא עדכני ואתה יכול להציע לחפש באינטרנט. "
        "ענה בעברית בצורה מסודרת עם כותרות ונקודות."
    ),
    "analyzer": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מנתח אסטרטגי. נתח כל בקשה לעומק: יתרונות, חסרונות, סיכונים, הזדמנויות. "
        "השתמש בנתונים ולוגיקה. תן המלצה ברורה בסוף. ענה בעברית."
    ),
    "critic": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מבקר מומחה. בדוק שגיאות לוגיות, חורים, בעיות איכות, ואיך לשפר. "
        "היה ישיר וספציפי. ציין גם מה טוב. ענה בעברית."
    ),
}

# ─── Pydantic models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str
    message: str
    system_prompt: Optional[str] = None
    username: Optional[str] = None
    agent: Optional[str] = "main"
    task_type: Optional[str] = "default"
    channel_id: Optional[str] = "global"
    image_url: Optional[str] = None   # ← Phase 17: multimodal image support

class VisionRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    image_url: str
    text: Optional[str] = ""

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5

class CodeRequest(BaseModel):
    code: str
    timeout: Optional[int] = 10

class OrchestratorRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    task: str
    agents: Optional[List[str]] = None  # None = auto-decide

class SwarmRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    task: str

class RecallRequest(BaseModel):
    user_id: str
    query: str
    top_k: Optional[int] = 5

class StoreMemoryRequest(BaseModel):
    user_id: str
    text: str
    agent: Optional[str] = "main"

class NotionAddRequest(BaseModel):
    text: str
    title: Optional[str] = None
    database_id: Optional[str] = None

class DebateRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    topic: str

# ─── LLM call helper ──────────────────────────────────────────────────────────

async def llm_call(messages: list, task_type: str = "default", timeout: int = 45) -> dict:
    """Call LiteLLM with automatic model fallback based on task type."""
    models = TASK_MODELS.get(task_type, TASK_MODELS["default"])
    for model in models:
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                res = await client.post(
                    f"{LITELLM_URL}/chat/completions",
                    headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                    json={"model": model, "messages": messages}
                )
                data = res.json()
                content = data["choices"][0]["message"]["content"]
                return {"response": content, "model": model, "success": True}
        except Exception:
            continue
    return {"response": "שגיאה: כל המודלים נכשלו", "model": "none", "success": False}

async def agent_call(role: str, prompt: str, task_type: str = "default") -> dict:
    """Call a specific agent role."""
    system = AGENT_SYSTEMS.get(role, DEFAULT_SYSTEM)
    msgs = [
        {"role": "system", "content": system},
        {"role": "user", "content": prompt}
    ]
    result = await llm_call(msgs, task_type)
    return {"role": role, **result}

# ─── Context & Memory ─────────────────────────────────────────────────────────

def get_context(user_id: str, channel_id: str = "global") -> list:
    raw = r.get(f"ctx:{user_id}:{channel_id}")
    if not raw:
        return []
    try:
        return json.loads(raw)
    except Exception:
        return []

def save_context(user_id: str, messages: list, channel_id: str = "global"):
    while len(messages) > 20:
        messages.pop(0)
    serialized = json.dumps(messages, ensure_ascii=False)
    while len(serialized) > 3000 and messages:
        messages.pop(0)
        serialized = json.dumps(messages, ensure_ascii=False)
    r.set(f"ctx:{user_id}:{channel_id}", serialized)

HEBREW_CHARS = re.compile(r"[\u0590-\u05FF]")
ARABIC_CHARS = re.compile(r"[\u0600-\u06FF]")
LATIN_CHARS  = re.compile(r"[a-zA-Z]")

def detect_language(text: str) -> str:
    heb = len(HEBREW_CHARS.findall(text))
    ara = len(ARABIC_CHARS.findall(text))
    lat = len(LATIN_CHARS.findall(text))
    if heb >= lat and heb >= ara:
        return "he"
    if ara >= lat:
        return "ar"
    return "en"

def get_memory(user_id: str) -> dict:
    raw = r.get(f"mem:{user_id}")
    if not raw:
        return {"username": "Unknown", "language": "he", "request_count": 0,
                "agent_counts": {}, "total_duration": 0.0, "total_tokens_est": 0}
    try:
        return json.loads(raw)
    except Exception:
        return {}

def save_memory(user_id: str, mem: dict):
    r.set(f"mem:{user_id}", json.dumps(mem, ensure_ascii=False))

def update_memory(user_id: str, username: str, message: str, agent: str, duration: float, response: str):
    mem = get_memory(user_id)
    if username:
        mem["username"] = username
    detected = detect_language(message)
    if mem.get("language") != detected:
        lang_streak_key = f"mem:langstreak:{user_id}"
        streak = r.get(lang_streak_key)
        current_streak_lang, count = (streak.split(":") if streak else (detected, "0"))
        if current_streak_lang == detected:
            count = int(count) + 1
        else:
            current_streak_lang, count = detected, 1
        r.setex(lang_streak_key, 3600, f"{current_streak_lang}:{count}")
        if int(count) >= 3:
            mem["language"] = detected
    else:
        r.delete(f"mem:langstreak:{user_id}")
    mem["request_count"] = mem.get("request_count", 0) + 1
    agents = mem.get("agent_counts", {})
    agents[agent] = agents.get(agent, 0) + 1
    mem["agent_counts"] = agents
    mem["total_duration"] = round(mem.get("total_duration", 0.0) + duration, 2)
    mem["total_tokens_est"] = mem.get("total_tokens_est", 0) + len(message) // 4 + len(response) // 4
    save_memory(user_id, mem)

# ─── Phase 18: Qdrant Semantic Memory ────────────────────────────────────────

try:
    from qdrant_client import QdrantClient
    from qdrant_client.models import Distance, VectorParams, PointStruct, Filter, FieldCondition, MatchValue
    QDRANT_AVAILABLE = True
except ImportError:
    QDRANT_AVAILABLE = False

GEMINI_EMBED_KEYS = [
    os.getenv("GEMINI_KEY_1", ""),
    os.getenv("GEMINI_KEY_2", ""),
    os.getenv("GEMINI_KEY_3", ""),
    os.getenv("GEMINI_KEY_4", ""),
    os.getenv("GEMINI_KEY_5", ""),
]

QDRANT_URL = "http://localhost:6333"
QDRANT_COLLECTION = "openclaw_memory"
VECTOR_SIZE = 768
_qdrant: "QdrantClient" = None

def get_qdrant():
    global _qdrant
    if not QDRANT_AVAILABLE:
        return None
    if _qdrant is None:
        try:
            _qdrant = QdrantClient(url=QDRANT_URL, timeout=10)
            _qdrant.get_collection(QDRANT_COLLECTION)
        except Exception:
            try:
                _qdrant.create_collection(
                    QDRANT_COLLECTION,
                    vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE)
                )
            except Exception:
                _qdrant = None
    return _qdrant

async def get_embedding(text: str) -> list:
    for key in GEMINI_EMBED_KEYS:
        if not key:
            continue
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                res = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/text-embedding-004:embedContent?key={key}",
                    json={"model": "models/text-embedding-004",
                          "content": {"parts": [{"text": text[:2000]}]}}
                )
                if res.status_code == 200:
                    return res.json()["embedding"]["values"]
        except Exception:
            continue
    return []

async def store_long_memory(user_id: str, text: str, agent: str = "main"):
    emb = await get_embedding(text)
    if not emb:
        return
    qd = get_qdrant()
    if qd:
        try:
            qd.upsert(
                collection_name=QDRANT_COLLECTION,
                points=[PointStruct(
                    id=str(int(time.time() * 1000000)),
                    vector=emb,
                    payload={
                        "user_id": user_id,
                        "text": text[:600],
                        "agent": agent,
                        "timestamp": time.time()
                    }
                )]
            )
        except Exception:
            pass

async def search_long_memory(user_id: str, query: str, top_k: int = 3) -> list:
    qemb = await get_embedding(query)
    if not qemb:
        return []
    qd = get_qdrant()
    if not qd:
        return []
    try:
        results = qd.search(
            collection_name=QDRANT_COLLECTION,
            query_vector=qemb,
            query_filter=Filter(
                must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))]
            ),
            limit=top_k,
            score_threshold=0.40
        )
        return [(r.score, r.payload.get("text",""), r.payload.get("agent",""), r.payload.get("timestamp",0))
                for r in results]
    except Exception:
        return []

# ─── CORE CHAT ────────────────────────────────────────────────────────────────

# patterns that indicate the user is sharing credentials/sensitive data
import re as _re
_CREDENTIAL_PATTERNS = _re.compile(
    r'(password|סיסמ|passwd|api.?key|token|secret|credentials|app.password|smtp|imap|'
    r'@gmail|@yahoo|@hotmail|bearer|Authorization|sk-|ghp_|AIza|MTQ)',
    _re.IGNORECASE
)

CREDENTIAL_BOOST = (
    "\n\n[הבעלים שיתף credentials/סיסמא/מפתח] "
    "השתמש בהם ישירות בקוד Python שתכתוב. "
    "אל תגיד שאתה לא יכול לקבל סיסמאות — פשוט השתמש בהם בקוד. "
    "כתוב קוד Python מלא ועובד שמשתמש במה שנשלח."
)

@app.post("/chat")
async def chat(req: ChatRequest):
    start = time.time()
    context = get_context(req.user_id, req.channel_id or "global")
    system = req.system_prompt or AGENT_SYSTEMS.get(req.agent, DEFAULT_SYSTEM)

    # Boost: if message contains credentials, add explicit instruction
    if _CREDENTIAL_PATTERNS.search(req.message):
        system = system + CREDENTIAL_BOOST

    # Inject relevant long-term memories
    try:
        memories = await search_long_memory(req.user_id, req.message, top_k=3)
        if memories:
            mem_lines = "\n".join(f"- {m[1]}" for m in memories)
            system = system + f"\n\n[זיכרונות רלוונטיים:]\n{mem_lines}"
    except Exception:
        pass

    messages = [{"role": "system", "content": system}]
    messages += context

    # Phase 17: multimodal — if image_url provided, use vision-capable model
    if req.image_url:
        user_content = [
            {"type": "image_url", "image_url": {"url": req.image_url}},
            {"type": "text", "text": req.message or "תאר את התמונה הזו בפירוט."}
        ]
        messages.append({"role": "user", "content": user_content})
        result = await llm_call(messages, "vision")
    else:
        messages.append({"role": "user", "content": req.message})
        result = await llm_call(messages, req.task_type or "default")

    if not result["success"]:
        return {"response": result["response"], "model": "none", "duration": 0}

    context.append({"role": "user", "content": req.message})
    context.append({"role": "assistant", "content": result["response"]})
    save_context(req.user_id, context, req.channel_id or "global")

    duration = round(time.time() - start, 2)
    agent = req.agent or (req.user_id.split(":")[0] if ":" in req.user_id else "main")
    update_memory(req.user_id, req.username or "", req.message, agent, duration, result["response"])

    mem_text = f"שאלה: {req.message[:300]} | תשובה: {result['response'][:300]}"
    asyncio.create_task(store_long_memory(req.user_id, mem_text, agent))

    return {"response": result["response"], "model": result["model"], "duration": duration}

# ─── STREAMING CHAT (Phase 17) ───────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming chat endpoint — returns SSE chunks.
    Bot reads these and progressively edits Discord message (typewriter effect).
    Format: data: {"content": "...", "model": "..."}\n\n
            data: [DONE]\n\n
    """
    start = time.time()
    context = get_context(req.user_id, req.channel_id or "global")
    system  = req.system_prompt or AGENT_SYSTEMS.get(req.agent, DEFAULT_SYSTEM)

    if _CREDENTIAL_PATTERNS.search(req.message):
        system = system + CREDENTIAL_BOOST

    try:
        memories = await search_long_memory(req.user_id, req.message, top_k=3)
        if memories:
            mem_lines = "\n".join(f"- {m[1]}" for m in memories)
            system = system + f"\n\n[זיכרונות רלוונטיים:]\n{mem_lines}"
    except Exception:
        pass

    messages = [{"role": "system", "content": system}]
    messages += context

    if req.image_url:
        user_content = [
            {"type": "image_url", "image_url": {"url": req.image_url}},
            {"type": "text", "text": req.message or "תאר את התמונה הזו בפירוט."}
        ]
        messages.append({"role": "user", "content": user_content})
        task_type = "vision"
    else:
        messages.append({"role": "user", "content": req.message})
        task_type = req.task_type or "default"

    models = TASK_MODELS.get(task_type, TASK_MODELS["default"])

    async def event_stream():
        full_response = ""
        used_model = "none"

        for model in models:
            try:
                async with httpx.AsyncClient(timeout=60) as client:
                    async with client.stream(
                        "POST",
                        f"{LITELLM_URL}/chat/completions",
                        headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                        json={"model": model, "messages": messages, "stream": True}
                    ) as response:
                        if response.status_code != 200:
                            continue
                        used_model = model
                        async for line in response.aiter_lines():
                            if not line.startswith("data: "):
                                continue
                            raw = line[6:].strip()
                            if raw == "[DONE]":
                                break
                            try:
                                chunk = json.loads(raw)
                                delta = chunk["choices"][0]["delta"].get("content", "")
                                if delta:
                                    full_response += delta
                                    yield f"data: {json.dumps({'content': delta, 'model': model}, ensure_ascii=False)}\n\n"
                            except Exception:
                                continue

                # Save context + memory after streaming done
                context.append({"role": "user", "content": req.message})
                context.append({"role": "assistant", "content": full_response})
                save_context(req.user_id, context, req.channel_id or "global")
                duration = round(time.time() - start, 2)
                agent = req.agent or "main"
                update_memory(req.user_id, req.username or "", req.message, agent, duration, full_response)
                mem_text = f"שאלה: {req.message[:300]} | תשובה: {full_response[:300]}"
                asyncio.create_task(store_long_memory(req.user_id, mem_text, agent))

                yield f"data: {json.dumps({'done': True, 'model': used_model, 'duration': duration}, ensure_ascii=False)}\n\n"
                return
            except Exception:
                continue

        yield f"data: {json.dumps({'error': 'כל המודלים נכשלו'})}\n\n"

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"}
    )


# ─── ORCHESTRATOR (Smart multi-agent routing) ─────────────────────────────────

@app.post("/orchestrate")
async def orchestrate(req: OrchestratorRequest):
    """
    Smart orchestrator: analyzes the task and decides which agents to use.
    Runs agents in parallel, passes results to Critic, then synthesizes.
    Supports webhook persona output (each agent has its own response).
    """
    start = time.time()

    # Step 1: Orchestrator decides which agents to use
    if req.agents:
        selected_agents = req.agents
        plan = f"Using specified agents: {', '.join(selected_agents)}"
    else:
        plan_result = await agent_call(
            "orchestrator",
            f"""משימה: {req.task}

החלט אילו סוכנים נדרשים (מבין: coder, researcher, analyzer, critic).
ענה ONLY ברשימת שמות מופרדים בפסיק, כגון: coder,researcher
אין להוסיף טקסט אחר.""",
            "speed"
        )
        raw_agents = plan_result["response"].strip().lower()
        selected_agents = [a.strip() for a in raw_agents.split(",")
                          if a.strip() in ["coder", "researcher", "analyzer", "critic"]]
        if not selected_agents:
            selected_agents = ["researcher", "coder"]
        plan = f"Orchestrator selected: {', '.join(selected_agents)}"

    # Step 2: Run selected agents in parallel
    agent_tasks = []
    for ag in selected_agents:
        task_type = "code" if ag == "coder" else "analysis" if ag == "analyzer" else "default"
        agent_tasks.append(agent_call(ag, req.task, task_type))

    agent_results_list = await asyncio.gather(*agent_tasks)
    agent_results = {r["role"]: r for r in agent_results_list}

    # Step 3: Critic reviews (always runs)
    combined_for_critic = "\n\n".join(
        f"**{ag}:** {res['response'][:500]}"
        for ag, res in agent_results.items()
    )
    critic_result = await agent_call(
        "critic",
        f"משימה מקורית: {req.task}\n\nתשובות הסוכנים:\n{combined_for_critic}\n\nציין שגיאות, חורים ושיפורים.",
        "analysis"
    )

    # Step 4: Synthesizer creates final response
    synthesis_prompt = (
        f"משימה: {req.task}\n\n"
        + "\n\n".join(f"**{ag}:**\n{res['response'][:600]}" for ag, res in agent_results.items())
        + f"\n\n**ביקורת:**\n{critic_result['response'][:400]}\n\n"
        + "שלב הכל לתשובה מושלמת, מסודרת ומקיפה בעברית."
    )
    synthesis = await agent_call("orchestrator", synthesis_prompt, "default")

    duration = round(time.time() - start, 2)
    update_memory(req.user_id, req.username or "", req.task, "orchestrator", duration, synthesis["response"])
    asyncio.create_task(store_long_memory(
        req.user_id, f"Orchestrated: {req.task[:200]} → {synthesis['response'][:200]}", "orchestrator"
    ))

    return {
        "plan": plan,
        "agents_used": selected_agents,
        "agent_responses": {
            ag: {"response": res["response"], "model": res["model"]}
            for ag, res in agent_results.items()
        },
        "critic": {"response": critic_result["response"], "model": critic_result["model"]},
        "synthesis": synthesis["response"],
        "synthesis_model": synthesis["model"],
        "duration": duration,
    }

# ─── DEBATE ───────────────────────────────────────────────────────────────────

@app.post("/debate")
async def debate(req: DebateRequest):
    """Two agents argue opposite sides, synthesizer picks the winner."""
    start = time.time()

    pro, con = await asyncio.gather(
        agent_call("researcher",
                   f"טען בחוזקה בעד: {req.topic}. 3 טיעונים חזקים.",
                   "default"),
        agent_call("analyzer",
                   f"טען בחוזקה נגד: {req.topic}. 3 טיעונים חזקים.",
                   "analysis"),
    )

    synthesis = await agent_call(
        "critic",
        f"נושא: {req.topic}\n\n"
        f"**עמדה בעד:**\n{pro['response']}\n\n"
        f"**עמדה נגד:**\n{con['response']}\n\n"
        f"נתח את שני הצדדים בצורה אובייקטיבית ותן המלצה מנומקת.",
        "analysis"
    )

    duration = round(time.time() - start, 2)
    return {
        "pro": {"response": pro["response"], "model": pro["model"]},
        "con": {"response": con["response"], "model": con["model"]},
        "verdict": {"response": synthesis["response"], "model": synthesis["model"]},
        "duration": duration,
    }

# ─── SWARM (Phase 16 — upgraded with Critic) ──────────────────────────────────

@app.post("/swarm")
async def swarm(req: SwarmRequest):
    start = time.time()

    researcher, coder, analyzer = await asyncio.gather(
        agent_call("researcher", f"חקור ותן מידע מקיף על: {req.task}"),
        agent_call("coder",      f"ספק פתרון טכני/קוד עבור: {req.task}", "code"),
        agent_call("analyzer",   f"נתח לעומק (יתרונות/חסרונות/המלצות): {req.task}", "analysis"),
    )

    # Critic reviews the parallel results
    critic = await agent_call(
        "critic",
        f"משימה: {req.task}\n\n"
        f"חוקר: {researcher['response'][:400]}\n"
        f"מתכנת: {coder['response'][:400]}\n"
        f"מנתח: {analyzer['response'][:400]}\n\n"
        f"הצבע על שגיאות ושיפורים.",
        "analysis"
    )

    synthesis_prompt = (
        f"משימה: {req.task}\n\n"
        f"**חוקר:**\n{researcher['response'][:600]}\n\n"
        f"**מתכנת:**\n{coder['response'][:600]}\n\n"
        f"**מנתח:**\n{analyzer['response'][:600]}\n\n"
        f"**ביקורת:**\n{critic['response'][:400]}\n\n"
        "שלב הכל לתשובה מושלמת אחת בעברית."
    )
    synthesis = await agent_call("orchestrator", synthesis_prompt)

    duration = round(time.time() - start, 2)
    update_memory(req.user_id, req.username or "", req.task, "swarm", duration, synthesis["response"])
    asyncio.create_task(store_long_memory(
        req.user_id, f"Swarm: {req.task[:200]} → {synthesis['response'][:200]}", "swarm"
    ))

    return {
        "agents": {
            "researcher": {"response": researcher["response"], "model": researcher["model"]},
            "coder":      {"response": coder["response"],      "model": coder["model"]},
            "analyzer":   {"response": analyzer["response"],   "model": analyzer["model"]},
            "critic":     {"response": critic["response"],     "model": critic["model"]},
        },
        "synthesis": synthesis["response"],
        "model": synthesis["model"],
        "duration": duration,
    }

# ─── VISION ───────────────────────────────────────────────────────────────────

@app.post("/vision")
async def vision(req: VisionRequest):
    start = time.time()
    text = req.text or "תאר את התמונה הזו בפירוט."
    messages = [
        {"role": "system", "content": DEFAULT_SYSTEM},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": req.image_url}},
            {"type": "text",      "text": text}
        ]}
    ]
    result = await llm_call(messages, "vision")
    duration = round(time.time() - start, 2)
    update_memory(req.user_id, req.username or "", f"[image] {text}", "vision", duration, result["response"])
    return {"response": result["response"], "model": "gemini-flash-vision", "duration": duration}

# ─── SEARCH (Phase 10) ────────────────────────────────────────────────────────

@app.post("/search")
async def web_search(req: SearchRequest):
    start = time.time()
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for item in ddgs.text(req.query, max_results=req.max_results):
                results.append({
                    "title": item.get("title", ""),
                    "url":   item.get("href", ""),
                    "body":  item.get("body", "")[:300]
                })
        return {"results": results, "count": len(results), "duration": round(time.time()-start,2)}
    except Exception as e:
        return {"results": [], "count": 0, "error": str(e), "duration": 0}

# ─── CODE RUNNER (Phase 11) ───────────────────────────────────────────────────

BLOCKED_PATTERNS = [
    "os.system", "subprocess", "shutil.rmtree",
    "open('/etc", "open('/root", "open('/home",
    "socket", "ftplib", "smtplib",
    "__import__", "importlib", "exec(", "eval(",
]

def is_code_safe(code: str):
    for pattern in BLOCKED_PATTERNS:
        if pattern.lower() in code.lower():
            return False, f"blocked: `{pattern}`"
    return True, ""

@app.post("/run-code")
async def run_code(req: CodeRequest):
    start = time.time()
    safe, reason = is_code_safe(req.code)
    if not safe:
        return {"success": False, "output": f"❌ קוד חסום ({reason})", "duration": 0}

    timeout = min(req.timeout or 10, 15)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(req.code)
        tmp_path = f.name

    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable, tmp_path,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        )
        try:
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            return {"success": False, "output": f"⏱ Timeout ({timeout}s)", "duration": timeout}

        out = stdout.decode("utf-8", errors="replace").strip()
        err = stderr.decode("utf-8", errors="replace").strip()
        duration = round(time.time() - start, 2)

        if proc.returncode != 0:
            return {"success": False, "output": (out + "\n" + err).strip()[:2000],
                    "exit_code": proc.returncode, "duration": duration}
        return {"success": True, "output": out[:2000] or "(no output)", "exit_code": 0, "duration": duration}
    finally:
        os.unlink(tmp_path)

# ─── MEMORY ENDPOINTS (Phase 8 + 15) ─────────────────────────────────────────

@app.get("/memory/{user_id}")
async def get_user_memory(user_id: str):
    mem = get_memory(user_id)
    ctx_keys = r.keys(f"ctx:{user_id}:*")
    req_count = mem.get("request_count", 0)
    avg_duration = round(mem.get("total_duration", 0) / req_count, 2) if req_count else 0
    agents = mem.get("agent_counts", {})
    fav_agent = max(agents, key=agents.get) if agents else "none"
    return {
        "user_id": user_id, "username": mem.get("username", "Unknown"),
        "language": mem.get("language", "he"), "request_count": req_count,
        "favorite_agent": fav_agent, "agent_counts": agents,
        "avg_duration": avg_duration, "total_duration": mem.get("total_duration", 0),
        "total_tokens_est": mem.get("total_tokens_est", 0), "context_messages": len(ctx_keys)
    }

@app.delete("/memory/{user_id}")
async def reset_user_memory(user_id: str):
    ctx_keys = r.keys(f"ctx:{user_id}:*")
    keys_to_del = [f"mem:{user_id}", f"mem:langstreak:{user_id}"] + list(ctx_keys)
    if keys_to_del:
        r.delete(*keys_to_del)
    return {"status": "reset", "user_id": user_id}

@app.delete("/memory")
async def reset_all_memory():
    keys = r.keys("mem:*") + r.keys("ctx:*")
    if keys:
        r.delete(*keys)
    return {"status": "all_reset", "keys_deleted": len(keys)}

@app.post("/recall")
async def recall(req: RecallRequest):
    memories = await search_long_memory(req.user_id, req.query, top_k=req.top_k or 5)
    return {
        "memories": [{"text": m[1], "score": round(m[0], 3), "agent": m[2], "timestamp": m[3]} for m in memories],
        "count": len(memories)
    }

@app.post("/store-memory")
async def store_memory_endpoint(req: StoreMemoryRequest):
    await store_long_memory(req.user_id, req.text, req.agent)
    return {"status": "stored"}

@app.delete("/long-memory/{user_id}")
async def clear_long_memory(user_id: str):
    qd = get_qdrant()
    count = 0
    if qd:
        try:
            qd.delete(
                collection_name=QDRANT_COLLECTION,
                points_selector=Filter(must=[FieldCondition(key="user_id", match=MatchValue(value=user_id))])
            )
            count = 1
        except Exception:
            pass
    return {"status": "cleared", "user_id": user_id, "qdrant": count > 0}

# ─── GITHUB (Phase 12) ────────────────────────────────────────────────────────

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")

@app.get("/github/repo/{owner}/{repo_name}")
async def github_repo_info(owner: str, repo_name: str):
    try:
        from github import Github
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")
        return {"name": repo.full_name, "description": repo.description or "",
                "stars": repo.stargazers_count, "forks": repo.forks_count,
                "open_issues": repo.open_issues_count, "language": repo.language or "N/A",
                "default_branch": repo.default_branch, "url": repo.html_url,
                "updated_at": str(repo.updated_at), "private": repo.private}
    except Exception as e:
        return {"error": str(e)}

@app.get("/github/prs/{owner}/{repo_name}")
async def github_prs(owner: str, repo_name: str, state: str = "open"):
    try:
        from github import Github
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")
        pulls = list(repo.get_pulls(state=state, sort="updated")[:10])
        return {"repo": repo.full_name, "state": state, "count": len(pulls),
                "prs": [{"number": pr.number, "title": pr.title, "user": pr.user.login,
                          "url": pr.html_url, "created_at": str(pr.created_at)[:10]} for pr in pulls]}
    except Exception as e:
        return {"error": str(e)}

@app.get("/github/commits/{owner}/{repo_name}")
async def github_commits(owner: str, repo_name: str):
    try:
        from github import Github
        g = Github(GITHUB_TOKEN)
        repo = g.get_repo(f"{owner}/{repo_name}")
        commits = list(repo.get_commits()[:5])
        return {"repo": repo.full_name, "commits": [
            {"sha": c.sha[:7], "message": c.commit.message.split("\n")[0][:80],
             "author": c.commit.author.name, "date": str(c.commit.author.date)[:10],
             "url": c.html_url} for c in commits]}
    except Exception as e:
        return {"error": str(e)}

# ─── NOTION (Phase 13) ────────────────────────────────────────────────────────

NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_INBOX_DB = os.getenv("NOTION_INBOX_DB", "")

@app.post("/notion/add")
async def notion_add(req: NotionAddRequest):
    try:
        from notion_client import Client
        notion = Client(auth=NOTION_TOKEN)
        db_id = req.database_id or NOTION_INBOX_DB
        title = req.title or req.text[:60]
        page = notion.pages.create(
            parent={"database_id": db_id},
            properties={"Name": {"title": [{"text": {"content": title}}]}},
            children=[{"object": "block", "type": "paragraph",
                        "paragraph": {"rich_text": [{"type": "text", "text": {"content": req.text[:2000]}}]}}]
        )
        return {"status": "created", "page_id": page["id"], "url": page.get("url", "")}
    except Exception as e:
        return {"error": str(e)}

@app.get("/notion/list")
async def notion_list():
    try:
        from notion_client import Client
        notion = Client(auth=NOTION_TOKEN)
        results = notion.databases.query(
            database_id=NOTION_INBOX_DB,
            sorts=[{"timestamp": "last_edited_time", "direction": "descending"}],
            page_size=8
        )
        pages = []
        for p in results.get("results", []):
            props = p.get("properties", {})
            title_val = ""
            for key in ["Name", "title", "Title", "name"]:
                if key in props:
                    rich = props[key].get("title", [])
                    if rich:
                        title_val = rich[0].get("plain_text", "")
                        break
            pages.append({"title": title_val or "(no title)", "id": p["id"],
                           "url": p.get("url", ""), "edited": p.get("last_edited_time", "")[:10]})
        return {"pages": pages, "count": len(pages)}
    except Exception as e:
        return {"error": str(e)}

@app.get("/notion/search")
async def notion_search(q: str):
    try:
        from notion_client import Client
        notion = Client(auth=NOTION_TOKEN)
        results = notion.search(query=q, page_size=5)
        pages = []
        for p in results.get("results", []):
            props = p.get("properties", {})
            title_val = ""
            for key in ["Name", "title", "Title", "name"]:
                if key in props:
                    rich = props[key].get("title", [])
                    if rich:
                        title_val = rich[0].get("plain_text", "")
                        break
            pages.append({"title": title_val or "(no title)", "id": p["id"],
                           "url": p.get("url", ""), "type": p.get("object", "")})
        return {"results": pages, "count": len(pages)}
    except Exception as e:
        return {"error": str(e)}

# ─── HEALTH & STATS ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    redis_ok = False
    try:
        r.ping()
        redis_ok = True
    except Exception:
        pass
    return {
        "status": "ok",
        "version": "2.0",
        "redis": "ok" if redis_ok else "error",
        "agents": list(AGENT_SYSTEMS.keys()),
        "task_models": list(TASK_MODELS.keys()),
    }

@app.get("/stats/{user_id}")
async def stats(user_id: str):
    return await get_user_memory(user_id)

@app.get("/agents")
async def list_agents():
    return {
        "agents": [
            {"name": name, "system_preview": sys[:80], "emoji": {
                "orchestrator": "🧭", "coder": "💻", "researcher": "🔍",
                "analyzer": "📊", "critic": "⚖️"
            }.get(name, "🤖")}
            for name, sys in AGENT_SYSTEMS.items()
        ]
    }

# Route endpoint for smart agent routing
@app.post("/route")
async def route_message(req: dict):
    try:
        from agent_workflow import route_message as route
        result = route(req.get("message", ""), req.get("user_id", ""))
        return result
    except Exception as e:
        return {"error": str(e)}
