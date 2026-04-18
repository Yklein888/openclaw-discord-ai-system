# gateway/core_memory.py
# Letta-style Core Memory Blocks - persistent, always-in-context editable memory

import json
import os
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

DEFAULT_BLOCKS = {
    "persona": {
        "value": "אני OpenClaw — סוכן AI אוטונומי. אני לומד, זוכר, ומבצע משימות עד הסוף.",
        "limit": 2000,
    },
    "user": {
        "value": "",
        "limit": 2000,
    },
    "current_project": {
        "value": "",
        "limit": 1000,
    },
    "important_facts": {
        "value": "",
        "limit": 3000,
    },
}


async def get_all_blocks(user_id: str) -> dict:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"core_mem:{user_id}")
        if raw:
            return json.loads(raw)
        await r.set(
            f"core_mem:{user_id}", json.dumps(DEFAULT_BLOCKS, ensure_ascii=False)
        )
        return DEFAULT_BLOCKS.copy()
    finally:
        await r.aclose()


async def get_block(user_id: str, label: str) -> str:
    blocks = await get_all_blocks(user_id)
    block = blocks.get(label, {})
    return block.get("value", "")


async def append_to_block(user_id: str, label: str, content: str) -> str:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"core_mem:{user_id}")
        blocks = json.loads(raw) if raw else DEFAULT_BLOCKS.copy()

        if label not in blocks:
            blocks[label] = {"value": "", "limit": 2000}

        current = blocks[label].get("value", "")
        new_val = (current + "\n" + content).strip()

        limit = blocks[label].get("limit", 2000)
        if len(new_val) > limit:
            new_val = new_val[-limit:]

        blocks[label]["value"] = new_val
        await r.set(f"core_mem:{user_id}", json.dumps(blocks, ensure_ascii=False))
        return f"✅ הוסף ל-{label}: {content[:100]}"
    finally:
        await r.aclose()


async def replace_block(
    user_id: str, label: str, old_content: str, new_content: str
) -> str:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"core_mem:{user_id}")
        blocks = json.loads(raw) if raw else DEFAULT_BLOCKS.copy()

        if label not in blocks:
            return f"❌ בלוק {label} לא קיים"

        current = blocks[label].get("value", "")
        if old_content not in current:
            return f"⚠️ הטקסט '{old_content[:50]}' לא נמצא ב-{label}"

        new_val = current.replace(old_content, new_content)
        blocks[label]["value"] = new_val
        await r.set(f"core_mem:{user_id}", json.dumps(blocks, ensure_ascii=False))
        return f"✅ עדכנתי את {label}"
    finally:
        await r.aclose()


async def replace_entire_block(user_id: str, label: str, new_content: str) -> str:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"core_mem:{user_id}")
        blocks = json.loads(raw) if raw else DEFAULT_BLOCKS.copy()

        if label not in blocks:
            blocks[label] = {"value": "", "limit": 2000}

        limit = blocks[label].get("limit", 2000)
        blocks[label]["value"] = new_content[:limit]
        await r.set(f"core_mem:{user_id}", json.dumps(blocks, ensure_ascii=False))
        return f"✅ החלפתי את {label}"
    finally:
        await r.aclose()


def format_blocks_for_prompt(blocks: dict) -> str:
    parts = []
    for label, block in blocks.items():
        val = block.get("value", "").strip()
        if val:
            parts.append(f"### {label}\n{val}")
    if not parts:
        return ""
    return "## Core Memory (מידע קבוע עליך ועל המשתמש):\n\n" + "\n\n".join(parts)
