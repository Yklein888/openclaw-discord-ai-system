# gateway/memory.py
# Memory management: short-term context + long-term semantic memory

import asyncio
import json
import os
import time
from typing import List, Optional

import aiohttp
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
EMBED_MIN_SCORE = 0.40
EMBED_MAX_ITEMS = 200
CTX_MAX_MSGS = 20
CTX_MAX_CHARS = 4000

# סיבוב בין Gemini keys לטעינת embeddings
_GEMINI_KEYS = [os.getenv(f"GEMINI_KEY_{i}", "") for i in range(1, 6)]
_GEMINI_KEYS = [k for k in _GEMINI_KEYS if k]  # הסר ריקים
_gemini_idx = 0


def _next_gemini_key() -> str:
    global _gemini_idx
    if not _GEMINI_KEYS:
        return ""
    key = _GEMINI_KEYS[_gemini_idx % len(_GEMINI_KEYS)]
    _gemini_idx += 1
    return key


async def _embed(text: str) -> Optional[List[float]]:
    """Creates a 768-dim embedding vector using Gemini API."""
    key = _next_gemini_key()
    if not key:
        return None
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"text-embedding-004:embedContent?key={key}"
    )
    payload = {
        "model": "models/text-embedding-004",
        "content": {"parts": [{"text": text[:2000]}]},
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                url, json=payload, timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["embedding"]["values"]
    except Exception:
        pass
    return None


def _cosine(a: List[float], b: List[float]) -> float:
    """Cosine similarity between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-9)


async def load_context(user_id: str, channel_id: str) -> list:
    """Load per-channel conversation context from Redis."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"ctx:{user_id}:{channel_id}")
        if not raw:
            return []
        msgs = json.loads(raw)
        return msgs[-CTX_MAX_MSGS:]
    except Exception:
        return []
    finally:
        await r.aclose()


async def save_context(user_id: str, channel_id: str, user_msg: str, bot_reply: str):
    """Save updated conversation context to Redis."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"ctx:{user_id}:{channel_id}")
        msgs = json.loads(raw) if raw else []
        msgs.append({"role": "user", "content": user_msg})
        msgs.append({"role": "assistant", "content": bot_reply})
        # trim to max messages
        msgs = msgs[-CTX_MAX_MSGS:]
        # trim to max chars
        total = sum(len(m["content"]) for m in msgs)
        while total > CTX_MAX_CHARS and len(msgs) > 2:
            removed = msgs.pop(0)
            total -= len(removed["content"])
        await r.set(f"ctx:{user_id}:{channel_id}", json.dumps(msgs, ensure_ascii=False))
    except Exception:
        pass
    finally:
        await r.aclose()


async def load_long_memory(user_id: str, query: str, top_k: int = 3) -> list:
    """Search long-term semantic memory for relevant context."""
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"longmem:{user_id}:*")
        if not keys:
            return []

        q_embed = await _embed(query)
        if not q_embed:
            return []

        scores = []
        for key in keys:
            raw = await r.get(key)
            if not raw:
                continue
            try:
                item = json.loads(raw)
                embed = item.get("embed")
                if not embed:
                    continue
                score = _cosine(q_embed, embed)
                if score >= EMBED_MIN_SCORE:
                    scores.append(
                        {
                            "text": item["text"],
                            "score": round(score, 3),
                            "agent": item.get("agent", "?"),
                            "timestamp": item.get("ts", 0),
                        }
                    )
            except Exception:
                continue

        scores.sort(key=lambda x: -x["score"])
        return scores[:top_k]

    except Exception:
        return []
    finally:
        await r.aclose()


async def save_long_memory_async(
    user_id: str, user_msg: str, bot_reply: str, agent: str
):
    """Save interaction to long-term semantic memory (async, non-blocking)."""
    text = f"User: {user_msg}\nAgent({agent}): {bot_reply}"[:500]
    embed = await _embed(text)
    if not embed:
        return

    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"longmem:{user_id}:*")
        # FIFO rotation: delete oldest if over limit
        if len(keys) >= EMBED_MAX_ITEMS:
            oldest = sorted(keys)[0]
            await r.delete(oldest)

        idx = int(time.time() * 1000)
        key = f"longmem:{user_id}:{idx}"
        data = json.dumps(
            {"text": text, "embed": embed, "agent": agent, "ts": idx},
            ensure_ascii=False,
        )
        await r.set(key, data, ex=30 * 24 * 3600)  # 30 days TTL
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
