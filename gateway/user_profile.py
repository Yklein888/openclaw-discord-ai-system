# gateway/user_profile.py
# Auto-learning user profile from conversations

import json
import os
import time

import aiohttp
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-2026")

UPDATE_INTERVAL = 900


async def get_profile(user_id: str) -> dict:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"profile:{user_id}")
        if raw:
            return json.loads(raw)
        return {
            "interests": [],
            "tech_stack": [],
            "projects": [],
            "preferences": [],
            "expertise_level": "unknown",
            "communication": "עברית",
            "last_updated": 0,
        }
    finally:
        await r.aclose()


async def update_profile_silently(user_id: str, user_msg: str, bot_reply: str):
    profile = await get_profile(user_id)

    if time.time() - profile.get("last_updated", 0) < UPDATE_INTERVAL:
        return

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{LITELLM_BASE}/v1/chat/completions",
                json={
                    "model": "groq/llama-3.1-8b-instant",
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "אתה מחלץ עובדות על משתמש מהשיחה. "
                                "החזר JSON עם המפתחות: "
                                "interests (רשימת מחרוזות), tech_stack (רשימה), "
                                "projects (רשימה), preferences (רשימה), "
                                "expertise_level (beginner/intermediate/expert). "
                                "אם אין מידע חדש להוסיף → החזר {}. "
                                "בלי טקסט נוסף, רק JSON."
                            ),
                        },
                        {
                            "role": "user",
                            "content": (
                                f"פרופיל קיים: {json.dumps(profile, ensure_ascii=False)}\n\n"
                                f"שיחה חדשה:\n"
                                f"משתמש: {user_msg[:400]}\n"
                                f"בוט: {bot_reply[:400]}\n\n"
                                "החזר JSON עם תוספות בלבד."
                            ),
                        },
                    ],
                    "max_tokens": 250,
                    "response_format": {"type": "json_object"},
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data = await resp.json()
                update = json.loads(data["choices"][0]["message"]["content"])
    except Exception:
        return

    for k, v in update.items():
        if isinstance(v, list) and v:
            existing = profile.get(k, [])
            profile[k] = list(dict.fromkeys(existing + v))[:20]
        elif v and k in profile:
            profile[k] = v

    profile["last_updated"] = int(time.time())

    r = aioredis.from_url(REDIS_URL)
    try:
        await r.set(f"profile:{user_id}", json.dumps(profile, ensure_ascii=False))
    finally:
        await r.aclose()


def format_profile_for_prompt(profile: dict) -> str:
    parts = []
    if profile.get("tech_stack"):
        parts.append(f"Tech stack: {', '.join(profile['tech_stack'][:10])}")
    if profile.get("projects"):
        parts.append(f"Projects: {', '.join(profile['projects'][:5])}")
    if profile.get("expertise_level") and profile["expertise_level"] != "unknown":
        parts.append(f"רמה: {profile['expertise_level']}")
    if profile.get("preferences"):
        parts.append(f"העדפות: {', '.join(profile['preferences'][:5])}")

    if not parts:
        return ""
    return "## פרופיל משתמש (למד מהשיחות):\n" + "\n".join([f"- {p}" for p in parts])
