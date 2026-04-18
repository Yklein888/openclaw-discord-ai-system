# gateway/episodic_memory.py
# "What happened" memory - past task summaries with success/failure

import json
import os
import time
from typing import List, Optional

import aiohttp
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
EP_TTL = 90 * 24 * 3600
EP_MAX = 500
EP_MIN_SCORE = 0.55

_GEMINI_KEYS = [
    os.getenv(f"GEMINI_KEY_{i}", "")
    for i in range(1, 6)
    if os.getenv(f"GEMINI_KEY_{i}")
]
_idx = 0


def _next_key() -> str:
    global _idx
    if not _GEMINI_KEYS:
        return ""
    k = _GEMINI_KEYS[_idx % len(_GEMINI_KEYS)]
    _idx += 1
    return k


async def _embed(text: str) -> Optional[List[float]]:
    key = _next_key()
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


async def save_episode(
    user_id: str,
    task: str,
    outcome: str,
    success: bool,
    tools_used: List[str],
    duration: float = 0,
):
    summary = (
        f"משימה: {task[:300]}\n"
        f"תוצאה: {outcome[:400]}\n"
        f"הצלחה: {'כן' if success else 'לא'}\n"
        f"כלים: {', '.join(tools_used)}"
    )

    embed = await _embed(summary)
    if not embed:
        return

    r = aioredis.from_url(REDIS_URL)
    try:
        idx = int(time.time() * 1000)
        key = f"episode:{user_id}:{idx}"
        data = json.dumps(
            {
                "task": task[:500],
                "outcome": outcome[:500],
                "success": success,
                "tools_used": tools_used,
                "duration": duration,
                "embed": embed,
                "ts": idx,
            },
            ensure_ascii=False,
        )
        await r.set(key, data, ex=EP_TTL)

        keys = await r.keys(f"episode:{user_id}:*")
        if len(keys) > EP_MAX:
            oldest = sorted(keys)[0]
            await r.delete(oldest)
    finally:
        await r.aclose()


async def find_similar_episodes(user_id: str, task: str, top_k: int = 3) -> List[dict]:
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"episode:{user_id}:*")
        if not keys:
            return []

        q_embed = await _embed(task)
        if not q_embed:
            return []

        scores = []
        for k in keys:
            raw = await r.get(k)
            if not raw:
                continue
            try:
                ep = json.loads(raw)
                if not ep.get("embed"):
                    continue
                score = _cosine(q_embed, ep["embed"])
                if score >= EP_MIN_SCORE:
                    scores.append(
                        {
                            "task": ep["task"],
                            "outcome": ep["outcome"],
                            "success": ep["success"],
                            "tools_used": ep["tools_used"],
                            "score": round(score, 3),
                        }
                    )
            except Exception:
                continue

        scores.sort(key=lambda x: -x["score"])
        return scores[:top_k]
    finally:
        await r.aclose()


def format_episodes_for_prompt(episodes: List[dict]) -> str:
    if not episodes:
        return ""
    lines = ["## משימות דומות שביצעתי בעבר:\n"]
    for ep in episodes:
        status = "✓ הצליח" if ep["success"] else "✗ נכשל"
        lines.append(
            f"- **{ep['task'][:100]}** → {status}"
            f"\n  תוצאה: {ep['outcome'][:150]}"
            f"\n  כלים: {', '.join(ep['tools_used'])}"
        )
    lines.append("\n(השתמש בלקחים מהמשימות הללו!)")
    return "\n".join(lines)
