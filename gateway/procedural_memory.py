# gateway/procedural_memory.py
# "How to do X" memory - learned patterns from successful tasks

import json
import os
import time
from typing import List

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
PROC_TTL = 180 * 24 * 3600


async def save_pattern(user_id: str, trigger: str, steps: List[str], example: str):
    r = aioredis.from_url(REDIS_URL)
    try:
        idx = int(time.time() * 1000)
        key = f"pattern:{user_id}:{idx}"
        data = json.dumps(
            {
                "trigger": trigger,
                "steps": steps,
                "example": example,
                "success_count": 1,
                "ts": idx,
            },
            ensure_ascii=False,
        )
        await r.set(key, data, ex=PROC_TTL)
    finally:
        await r.aclose()


async def find_matching_patterns(user_id: str, current_task: str) -> List[dict]:
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"pattern:{user_id}:*")
        if not keys:
            return []

        task_lower = current_task.lower()
        matches = []

        for k in keys:
            raw = await r.get(k)
            if not raw:
                continue
            try:
                p = json.loads(raw)
                trigger_lower = p["trigger"].lower()
                trigger_words = set(trigger_lower.split())
                task_words = set(task_lower.split())
                overlap = len(trigger_words & task_words)
                if overlap >= 2:
                    matches.append(
                        {
                            "trigger": p["trigger"],
                            "steps": p["steps"],
                            "example": p["example"],
                            "success_count": p.get("success_count", 1),
                            "overlap": overlap,
                        }
                    )
            except Exception:
                continue

        matches.sort(key=lambda x: (-x["overlap"], -x["success_count"]))
        return matches[:3]
    finally:
        await r.aclose()


def format_patterns_for_prompt(patterns: List[dict]) -> str:
    if not patterns:
        return ""
    lines = ["## דפוסי פעולה מוכחים ממשימות עבר:\n"]
    for p in patterns:
        lines.append(
            f"**{p['trigger']}** (הצליח {p['success_count']}× בעבר):\n"
            + "\n".join([f"  {i + 1}. {s}" for i, s in enumerate(p["steps"])])
            + f"\n  דוגמה: `{p['example'][:150]}`"
        )
    return "\n\n".join(lines)
