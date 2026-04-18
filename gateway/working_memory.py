# gateway/working_memory.py
# Short-lived scratchpad for multi-step tasks (TTL: 1 hour)

import json
import os
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WM_TTL = 3600


async def wm_set(user_id: str, key: str, value: str) -> str:
    r = aioredis.from_url(REDIS_URL)
    try:
        await r.set(f"wm:{user_id}:{key}", value, ex=WM_TTL)
        return f"✅ נשמר: {key} = {value[:80]}"
    finally:
        await r.aclose()


async def wm_get(user_id: str, key: str) -> str:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"wm:{user_id}:{key}")
        return raw.decode() if raw else f"❌ '{key}' לא נמצא"
    finally:
        await r.aclose()


async def wm_list_all(user_id: str) -> dict:
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"wm:{user_id}:*")
        result = {}
        for k in keys:
            val = await r.get(k)
            if val:
                key_name = k.decode().split(":", 2)[2]
                result[key_name] = val.decode()
        return result
    finally:
        await r.aclose()


async def wm_clear(user_id: str):
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"wm:{user_id}:*")
        if keys:
            await r.delete(*keys)
    finally:
        await r.aclose()
