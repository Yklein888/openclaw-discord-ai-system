# gateway/memory.py
# Hybrid semantic memory: BM25 + Vector + Reranker

import asyncio
import json
import os
import re
import time
from typing import List, Optional

import aiohttp
import redis.asyncio as aioredis

try:
    from rank_bm25 import BM25Okapi

    BM25_AVAILABLE = True
except ImportError:
    BM25_AVAILABLE = False

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

CTX_MAX_MSGS = 20
CTX_MAX_CHARS = 4000

EMBED_MIN_SCORE = 0.40
EMBED_MAX_ITEMS = 500

_GEMINI_KEYS = [
    os.getenv(f"GEMINI_KEY_{i}", "")
    for i in range(1, 6)
    if os.getenv(f"GEMINI_KEY_{i}")
]
_gemini_idx = 0

LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-2026")


def _next_gemini_key() -> str:
    global _gemini_idx
    if not _GEMINI_KEYS:
        return ""
    k = _GEMINI_KEYS[_gemini_idx % len(_GEMINI_KEYS)]
    _gemini_idx += 1
    return k


async def _embed(text: str) -> Optional[List[float]]:
    key = _next_gemini_key()
    if not key:
        return None
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"text-embedding-004:embedContent?key={key}"
    )
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                url,
                json={
                    "model": "models/text-embedding-004",
                    "content": {"parts": [{"text": text[:2000]}]},
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["embedding"]["values"]
    except Exception:
        pass
    return None


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-9)


def _tokenize(text: str) -> List[str]:
    text = text.lower()
    tokens = re.findall(r"[\u0590-\u05FFa-z0-9]+", text)
    return [t for t in tokens if len(t) > 1]


async def load_context(user_id: str, channel_id: str) -> list:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"ctx:{user_id}:{channel_id}")
        if not raw:
            return []
        return json.loads(raw)[-CTX_MAX_MSGS:]
    except Exception:
        return []
    finally:
        await r.aclose()


async def save_context(user_id: str, channel_id: str, user_msg: str, bot_reply: str):
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"ctx:{user_id}:{channel_id}")
        msgs = json.loads(raw) if raw else []
        msgs.append({"role": "user", "content": user_msg})
        msgs.append({"role": "assistant", "content": bot_reply})
        msgs = msgs[-CTX_MAX_MSGS:]

        total = sum(len(m["content"]) for m in msgs)
        while total > CTX_MAX_CHARS and len(msgs) > 2:
            removed = msgs.pop(0)
            total -= len(removed["content"])

        await r.set(f"ctx:{user_id}:{channel_id}", json.dumps(msgs, ensure_ascii=False))
    except Exception:
        pass
    finally:
        await r.aclose()


async def load_long_memory_hybrid(
    user_id: str, query: str, top_k: int = 5
) -> List[dict]:
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"longmem:{user_id}:*")
        if not keys:
            return []

        items = []
        for k in keys:
            raw = await r.get(k)
            if not raw:
                continue
            try:
                item = json.loads(raw)
                if item.get("text") and item.get("embed"):
                    items.append(item)
            except Exception:
                continue

        if not items:
            return []

        if BM25_AVAILABLE:
            corpus_tokens = [_tokenize(i["text"]) for i in items]
            bm25 = BM25Okapi(corpus_tokens)
            query_tokens = _tokenize(query)
            bm25_scores = (
                bm25.get_scores(query_tokens) if query_tokens else [0] * len(items)
            )
        else:
            bm25_scores = [0] * len(items)

        q_embed = await _embed(query)
        vector_scores = []
        if q_embed:
            for item in items:
                vector_scores.append(_cosine(q_embed, item["embed"]))
        else:
            vector_scores = [0] * len(items)

        if BM25_AVAILABLE and any(s > 0 for s in bm25_scores):
            k_rrf = 60
            bm25_ranked = sorted(range(len(items)), key=lambda i: -bm25_scores[i])
            vector_ranked = sorted(range(len(items)), key=lambda i: -vector_scores[i])

            rrf_scores = [0.0] * len(items)
            for rank, idx in enumerate(bm25_ranked):
                rrf_scores[idx] += 1.0 / (k_rrf + rank + 1)
            for rank, idx in enumerate(vector_ranked):
                rrf_scores[idx] += 1.0 / (k_rrf + rank + 1)

            candidates_idx = sorted(range(len(items)), key=lambda i: -rrf_scores[i])[
                :10
            ]
        else:
            candidates_idx = sorted(range(len(items)), key=lambda i: -vector_scores[i])[
                :10
            ]

        candidates = [items[i] for i in candidates_idx]

        final = candidates[:top_k]

        if len(candidates) > top_k:
            reranked = await _llm_rerank(query, candidates, top_k)
            if reranked:
                final = reranked

        return [
            {
                "text": f["text"],
                "score": round(vector_scores[items.index(f)], 3) if f in items else 0,
                "agent": f.get("agent", "?"),
                "ts": f.get("ts", 0),
            }
            for f in final
        ]

    except Exception as e:
        print(f"[WARN] load_long_memory_hybrid failed: {e}")
        return []
    finally:
        await r.aclose()


async def _llm_rerank(query: str, candidates: List[dict], top_k: int) -> List[dict]:
    if len(candidates) <= top_k:
        return candidates

    docs_text = "\n".join(
        [f"[{i}] {c['text'][:300]}" for i, c in enumerate(candidates)]
    )

    prompt = (
        f"השאילתה: {query}\n\n"
        f"מסמכים:\n{docs_text}\n\n"
        f"החזר רק את המספרים של {top_k} המסמכים הכי רלוונטיים, מופרדים בפסיק. "
        f"לדוגמה: 3,1,7,0,2"
    )

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{LITELLM_BASE}/v1/chat/completions",
                json={
                    "model": "groq/llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "אתה reranker. החזר רק מספרים מופרדים בפסיק.",
                        },
                        {"role": "user", "content": prompt},
                    ],
                    "max_tokens": 50,
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                text = data["choices"][0]["message"]["content"]
                nums = re.findall(r"\d+", text)
                indices = [int(n) for n in nums if int(n) < len(candidates)][:top_k]
                if indices:
                    return [candidates[i] for i in indices]
    except Exception:
        pass
    return candidates[:top_k]


async def load_long_memory(user_id: str, query: str, top_k: int = 3) -> list:
    return await load_long_memory_hybrid(user_id, query, top_k)


async def save_long_memory_async(
    user_id: str, user_msg: str, bot_reply: str, agent: str
):
    text = f"User: {user_msg[:300]}\nAgent({agent}): {bot_reply[:300]}"
    embed = await _embed(text)
    if not embed:
        return

    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"longmem:{user_id}:*")
        if len(keys) >= EMBED_MAX_ITEMS:
            oldest = sorted(keys)[0]
            await r.delete(oldest)

        idx = int(time.time() * 1000)
        key = f"longmem:{user_id}:{idx}"
        data = json.dumps(
            {
                "text": text,
                "embed": embed,
                "agent": agent,
                "ts": idx,
            },
            ensure_ascii=False,
        )
        await r.set(key, data, ex=60 * 24 * 3600)
    except Exception:
        pass
    finally:
        await r.aclose()


async def get_user_stats(user_id: str) -> dict:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"mem:{user_id}")
        return json.loads(raw) if raw else {}
    except Exception:
        return {}
    finally:
        await r.aclose()


async def update_user_stats(user_id: str, username: str, agent: str, duration: float):
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"mem:{user_id}")
        stats = (
            json.loads(raw)
            if raw
            else {
                "username": username,
                "request_count": 0,
                "agent_counts": {},
                "total_duration": 0.0,
            }
        )
        stats["username"] = username
        stats["request_count"] = stats.get("request_count", 0) + 1
        stats["agent_counts"][agent] = stats["agent_counts"].get(agent, 0) + 1
        stats["total_duration"] = stats.get("total_duration", 0.0) + duration
        await r.set(f"mem:{user_id}", json.dumps(stats, ensure_ascii=False))
    except Exception:
        pass
    finally:
        await r.aclose()


async def compress_if_needed(messages: list, threshold: int = 15000) -> list:
    total = sum(len(str(m.get("content", ""))) for m in messages)
    if total < threshold or len(messages) < 10:
        return messages

    system_msg = (
        messages[0] if messages and messages[0].get("role") == "system" else None
    )
    recent = messages[-6:]
    middle = messages[1:-6] if system_msg else messages[:-6]

    if not middle:
        return messages

    middle_text = "\n".join(
        [f"{m.get('role', '?')}: {str(m.get('content', ''))[:250]}" for m in middle]
    )

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{LITELLM_BASE}/v1/chat/completions",
                json={
                    "model": "groq/llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": "סכם את ההיסטוריה הבאה ב-150 מילים. שמור על מידע קריטי "
                            "(החלטות, נתיבי קבצים, ערכים). תמציתי מאוד.",
                        },
                        {"role": "user", "content": middle_text[:6000]},
                    ],
                    "max_tokens": 250,
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                summary = data["choices"][0]["message"]["content"]
    except Exception:
        return messages

    compressed = []
    if system_msg:
        compressed.append(system_msg)
    compressed.append(
        {
            "role": "system",
            "content": f"[סיכום היסטוריה קודמת — {len(middle)} הודעות הוחלפו]\n{summary}",
        }
    )
    compressed.extend(recent)
    return compressed
