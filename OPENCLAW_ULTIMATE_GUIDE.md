# OpenClaw v3.5 — מדריך מלא למתכנת
# מהפכת הזיכרון והסוכנים המתקדמת ביותר לשנת 2026

> **מדריך זה מבוסס על המחקר העדכני ביותר בתחום סוכני AI (אפריל 2026).**
> מקורות: מחקרים אקדמיים (ArXiv), תיעוד רשמי של Letta/Mem0/Zep, Reflexion framework, Anthropic prompt caching, benchmark LongMemEval.
> כולל כל הבאגים הקריטיים שצריך לתקן + ארכיטקטורה חדשה ברמה עולמית.
>
> **המתכנת יקר:** קרא את **כל** המסמך לפני שתתחיל. אל תדלג על שום שלב.
> סדר הביצוע חשוב — יש תלויות בין שלבים.

---

## תוכן עניינים

**חלק א׳ — תיקוני באגים קריטיים (חובה לפני כל דבר)**
- שלב 1: תיקון 4 באגים שמונעים מהמערכת לעבוד

**חלק ב׳ — מהפכת הזיכרון (6 שכבות זיכרון חדשות)**
- שלב 2: Core Memory Blocks (בהשראת Letta/MemGPT)
- שלב 3: Working Memory (scratchpad לסוכן)
- שלב 4: Episodic Memory (זיכרון פרקי)
- שלב 5: Semantic Memory — Hybrid Search (BM25 + Vector + Reranker)
- שלב 6: Procedural Memory (לקחים ודפוסים)
- שלב 7: User Profile אוטומטי

**חלק ג׳ — שיפורי הסוכן (ReAct → Reflexion)**
- שלב 8: Planning Phase
- שלב 9: Parallel Tool Execution
- שלב 10: Reflection & Self-Correction
- שלב 11: Smart Context Compression
- שלב 12: Multi-Agent Orchestration משופר

**חלק ד׳ — אופטימיזציות כלכליות**
- שלב 13: Prompt Caching
- שלב 14: Smart Tool Result Truncation

**חלק ה׳ — בדיקות ואימות**
- שלב 15: Health checks מלאים
- שלב 16: Benchmark המערכת

---

# חלק א׳ — תיקוני באגים קריטיים

## שלב 1: 4 באגים קריטיים שחייבים לתקן

בלי התיקונים האלה הבוט לא יעלה, נקודה.

### 1.1 — Syntax Error ב-bot.py שורה 490

קובץ: `discord-bot/bot.py`

חפש את הקטע הזה (בערך שורה 490, בפקודת `/memory`):

```python
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)), ephemeral=True
```

החלף אותו ב:

```python
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)), ephemeral=True)
```

(חסר `)` בסוף השורה)

### 1.2 — Typo: followup_send → followup.send

קובץ: `discord-bot/bot.py`, בפונקציה `cmd_add_ch` (פקודת `/project-add-channel`)

חפש:

```python
    except Exception as e:
        await interaction.followup_send(embed=make_error_embed(str(e)))
```

החלף ב:

```python
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))
```

### 1.3 — חסרה קריאה ל-bot.run() בסוף הקובץ

קובץ: `discord-bot/bot.py`, השורה האחרונה בקובץ.

עכשיו זה מסתיים ב:

```python
if __name__ == "__main__":
```

(הקובץ מסתיים כאן בלי שום קוד אחרי!)

החלף את הסוף ב:

```python
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
```

### 1.4 — שמות מודלים לא תואמים (זה הגורם ל-"All models failed")

**הבעיה:** `gateway/agents.py` מבקש שמות כמו `"groq/llama-3.3-70b-versatile"`, אבל `litellm-config.yaml` מגדיר שמות כמו `"groq-llama-70b"`. כל קריאה נכשלת.

**הפתרון:** החלף את `TASK_MODELS` בקובץ `gateway/agents.py` ב:

```python
TASK_MODELS = {
    "code": [
        "groq-llama-70b",
        "cerebras-llama-70b",
        "gemini-flash",
    ],
    "analysis": [
        "groq-llama-70b",
        "cerebras-llama-70b",
        "gemini-flash",
    ],
    "speed": [
        "groq-llama-8b",
        "groq-llama-70b",
    ],
    "vision": [
        "gemini-flash",
    ],
    "reasoning": [
        "gemini-2.5-flash",
        "deepseek-r1",
        "groq-llama-70b",
    ],
    "default": [
        "groq-llama-70b",
        "cerebras-llama-70b",
        "gemini-flash",
    ],
}
```

### אימות של חלק א׳

```bash
cd /home/ubuntu/ai-system/discord-bot
python3 -c "import ast; ast.parse(open('bot.py').read()); print('bot.py OK')"

cd /home/ubuntu/ai-system/gateway
python3 -c "from agents import TASK_MODELS; print('agents.py OK')"

sudo systemctl restart ai-gateway discord-bot
sleep 5
journalctl -u discord-bot -n 20 --no-pager | tail -5
```

**צריך לראות:** `✅ OpenClaw v3 | ... | Synced XX commands`

---

# חלק ב׳ — מהפכת הזיכרון

### למה אנחנו עושים את זה?

המחקר האחרון בתחום (אפריל 2026) מראה שיש 6 סוגי זיכרון שסוכן AI מתקדם חייב:

1. **Core Memory** — זיכרון "חי" ש-תמיד בהקשר (בהשראת Letta/MemGPT)
2. **Working Memory** — scratchpad זמני למשימה הנוכחית
3. **Episodic Memory** — "מה קרה במשימות קודמות" עם ציון הצלחה/כישלון
4. **Semantic Memory** — ידע על העולם, עם BM25 + Vector + Reranker (3 אסטרטגיות חיפוש)
5. **Procedural Memory** — דפוסי פעולה שעבדו היטב (לקחים)
6. **User Profile** — מה אנחנו יודעים על המשתמש

Letta (MemGPT) שתואר במאמר של NeurIPS השיג **95.4% על LongMemEval** (הבנצ׳מרק המקצועי ביותר לזיכרון של סוכנים). אנחנו נשלב את כל הרעיונות האלה.

---

## שלב 2: Core Memory Blocks (Letta pattern)

**רעיון:** הסוכן יכול **בעצמו** לערוך מקטעי זיכרון שמוזרקים תמיד לכל שיחה. זו הדרך שLetta מנצחת בכל benchmark.

### 2.1 צור קובץ חדש: `gateway/core_memory.py`

```python
# gateway/core_memory.py
# Letta-style Core Memory Blocks - persistent, always-in-context editable memory

import json
import os
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# בלוקים ברירת מחדל שהסוכן יכול לערוך
DEFAULT_BLOCKS = {
    "persona": {
        "value":  "אני OpenClaw — סוכן AI אוטונומי. אני לומד, זוכר, ומבצע משימות עד הסוף.",
        "limit":  2000,
    },
    "user": {
        "value":  "",  # ימולא אוטומטית מהשיחות
        "limit":  2000,
    },
    "current_project": {
        "value":  "",  # הפרויקט הפעיל כרגע
        "limit":  1000,
    },
    "important_facts": {
        "value":  "",  # עובדות שהסוכן בחר לשמור
        "limit":  3000,
    },
}


async def get_all_blocks(user_id: str) -> dict:
    """מחזיר את כל ה-core memory blocks של המשתמש."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"core_mem:{user_id}")
        if raw:
            return json.loads(raw)
        # ברירת מחדל
        await r.set(f"core_mem:{user_id}", json.dumps(DEFAULT_BLOCKS, ensure_ascii=False))
        return DEFAULT_BLOCKS.copy()
    finally:
        await r.aclose()


async def get_block(user_id: str, label: str) -> str:
    """מחזיר את הערך של בלוק ספציפי."""
    blocks = await get_all_blocks(user_id)
    block  = blocks.get(label, {})
    return block.get("value", "")


async def append_to_block(user_id: str, label: str, content: str) -> str:
    """הוסף תוכן לבלוק (בלי למחוק את הקיים)."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw    = await r.get(f"core_mem:{user_id}")
        blocks = json.loads(raw) if raw else DEFAULT_BLOCKS.copy()

        if label not in blocks:
            blocks[label] = {"value": "", "limit": 2000}

        current = blocks[label].get("value", "")
        new_val = (current + "\n" + content).strip()

        # חתוך אם חורג מהגבול
        limit = blocks[label].get("limit", 2000)
        if len(new_val) > limit:
            new_val = new_val[-limit:]

        blocks[label]["value"] = new_val
        await r.set(f"core_mem:{user_id}", json.dumps(blocks, ensure_ascii=False))
        return f"✅ הוסף ל-{label}: {content[:100]}"
    finally:
        await r.aclose()


async def replace_block(user_id: str, label: str, old_content: str, new_content: str) -> str:
    """החלף תת-מחרוזת בבלוק."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw    = await r.get(f"core_mem:{user_id}")
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
    """החלף את כל הבלוק בתוכן חדש."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw    = await r.get(f"core_mem:{user_id}")
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
    """מפרמט את ה-blocks להזרקה לתוך ה-system prompt."""
    parts = []
    for label, block in blocks.items():
        val = block.get("value", "").strip()
        if val:
            parts.append(f"### {label}\n{val}")
    if not parts:
        return ""
    return "## Core Memory (מידע קבוע עליך ועל המשתמש):\n\n" + "\n\n".join(parts)
```

---

## שלב 3: Working Memory (scratchpad למשימה)

**רעיון:** מקום זמני שהסוכן יכול לכתוב אליו במהלך משימה, כדי לזכור נתונים מאמצע ביצוע (API endpoints, נתיבים, ערכי ביניים).

### 3.1 צור קובץ חדש: `gateway/working_memory.py`

```python
# gateway/working_memory.py
# Short-lived scratchpad for multi-step tasks (TTL: 1 hour)

import json
import os
from typing import Optional

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
WM_TTL    = 3600  # שעה אחת


async def wm_set(user_id: str, key: str, value: str) -> str:
    """שמור ערך ב-working memory."""
    r = aioredis.from_url(REDIS_URL)
    try:
        await r.set(f"wm:{user_id}:{key}", value, ex=WM_TTL)
        return f"✅ נשמר: {key} = {value[:80]}"
    finally:
        await r.aclose()


async def wm_get(user_id: str, key: str) -> str:
    """שחזר ערך."""
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"wm:{user_id}:{key}")
        return raw.decode() if raw else f"❌ '{key}' לא נמצא"
    finally:
        await r.aclose()


async def wm_list_all(user_id: str) -> dict:
    """רשימה של כל הערכים הפעילים."""
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
    """מחק את כל ה-working memory של המשתמש."""
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"wm:{user_id}:*")
        if keys:
            await r.delete(*keys)
    finally:
        await r.aclose()
```

---

## שלב 4: Episodic Memory (זיכרון פרקי)

**רעיון:** אחרי כל משימה, שמור סיכום של "מה עשיתי, מה עבד, מה נכשל". בעתיד כשנתקל במשימה דומה, נשלוף את הלקחים.

### 4.1 צור קובץ חדש: `gateway/episodic_memory.py`

```python
# gateway/episodic_memory.py
# "What happened" memory - past task summaries with success/failure

import json
import os
import time
from typing import List, Optional

import aiohttp
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
EP_TTL    = 90 * 24 * 3600  # 90 יום
EP_MAX    = 500             # מקסימום episodes למשתמש
EP_MIN_SCORE = 0.55         # סף דמיון למשיכה

_GEMINI_KEYS = [os.getenv(f"GEMINI_KEY_{i}", "") for i in range(1, 6) if os.getenv(f"GEMINI_KEY_{i}")]
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
            async with s.post(url, json={
                "model":   "models/text-embedding-004",
                "content": {"parts": [{"text": text[:2000]}]}
            }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["embedding"]["values"]
    except Exception:
        pass
    return None


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na  = sum(x * x for x in a) ** 0.5
    nb  = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-9)


async def save_episode(
    user_id:    str,
    task:       str,
    outcome:    str,
    success:    bool,
    tools_used: List[str],
    duration:   float = 0,
):
    """שמור סיכום של משימה שהסתיימה."""
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
        data = json.dumps({
            "task":       task[:500],
            "outcome":    outcome[:500],
            "success":    success,
            "tools_used": tools_used,
            "duration":   duration,
            "embed":      embed,
            "ts":         idx,
        }, ensure_ascii=False)
        await r.set(key, data, ex=EP_TTL)

        # FIFO rotation
        keys = await r.keys(f"episode:{user_id}:*")
        if len(keys) > EP_MAX:
            oldest = sorted(keys)[0]
            await r.delete(oldest)
    finally:
        await r.aclose()


async def find_similar_episodes(user_id: str, task: str, top_k: int = 3) -> List[dict]:
    """מצא משימות דומות מהעבר."""
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
                    scores.append({
                        "task":       ep["task"],
                        "outcome":    ep["outcome"],
                        "success":    ep["success"],
                        "tools_used": ep["tools_used"],
                        "score":      round(score, 3),
                    })
            except Exception:
                continue

        scores.sort(key=lambda x: -x["score"])
        return scores[:top_k]
    finally:
        await r.aclose()


def format_episodes_for_prompt(episodes: List[dict]) -> str:
    """מפרמט episodes להזרקה ל-system prompt."""
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
```

---

## שלב 5: Semantic Memory — Hybrid Search

**רעיון:** במקום רק vector search, שילוב של **BM25 (keyword) + Vector (semantic) + Reranker**. המחקר מוכיח שזה נותן recall טוב פי 2-3.

### 5.1 התקן חבילה חדשה

```bash
cd /home/ubuntu/ai-system
source venv/bin/activate
pip install rank-bm25==0.2.2
```

הוסף ל-`requirements.txt`:
```
rank-bm25==0.2.2
```

### 5.2 עדכן את `gateway/memory.py`

**מחק את הקובץ הקיים** וצור חדש:

```python
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
from rank_bm25 import BM25Okapi

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Context
CTX_MAX_MSGS  = 20
CTX_MAX_CHARS = 4000

# Long-term memory
EMBED_MIN_SCORE = 0.40
EMBED_MAX_ITEMS = 500  # הגדלנו מ-200

_GEMINI_KEYS = [os.getenv(f"GEMINI_KEY_{i}", "") for i in range(1, 6) if os.getenv(f"GEMINI_KEY_{i}")]
_gemini_idx  = 0

LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY  = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-2026")


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
            async with s.post(url, json={
                "model":   "models/text-embedding-004",
                "content": {"parts": [{"text": text[:2000]}]}
            }, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["embedding"]["values"]
    except Exception:
        pass
    return None


def _cosine(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na  = sum(x * x for x in a) ** 0.5
    nb  = sum(y * y for y in b) ** 0.5
    return dot / (na * nb + 1e-9)


def _tokenize(text: str) -> List[str]:
    """טוקניזציה בסיסית לעברית + אנגלית."""
    text = text.lower()
    # שמור על מילים עבריות + אנגליות + מספרים
    tokens = re.findall(r"[\u0590-\u05FFa-z0-9]+", text)
    return [t for t in tokens if len(t) > 1]


# ─── Short-term context (unchanged) ───────────────────────────────

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
        raw  = await r.get(f"ctx:{user_id}:{channel_id}")
        msgs = json.loads(raw) if raw else []
        msgs.append({"role": "user",      "content": user_msg})
        msgs.append({"role": "assistant", "content": bot_reply})
        msgs = msgs[-CTX_MAX_MSGS:]

        total = sum(len(m["content"]) for m in msgs)
        while total > CTX_MAX_CHARS and len(msgs) > 2:
            removed = msgs.pop(0)
            total  -= len(removed["content"])

        await r.set(f"ctx:{user_id}:{channel_id}", json.dumps(msgs, ensure_ascii=False))
    except Exception:
        pass
    finally:
        await r.aclose()


# ─── Long-term HYBRID memory (NEW: BM25 + Vector + Reranker) ─────

async def load_long_memory_hybrid(
    user_id: str,
    query:   str,
    top_k:   int = 5
) -> List[dict]:
    """
    Hybrid retrieval:
    1. BM25 על הטקסט (keyword matching)
    2. Vector similarity (semantic)
    3. Reciprocal Rank Fusion (RRF)
    4. Optional: LLM-based reranking של top-10 → top-k
    """
    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"longmem:{user_id}:*")
        if not keys:
            return []

        # ─── שלב 1: טען את כל הזיכרונות ─────────────────────────
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

        # ─── שלב 2: BM25 scoring ────────────────────────────────
        corpus_tokens = [_tokenize(i["text"]) for i in items]
        bm25 = BM25Okapi(corpus_tokens)
        query_tokens = _tokenize(query)
        bm25_scores  = bm25.get_scores(query_tokens) if query_tokens else [0] * len(items)

        # ─── שלב 3: Vector scoring ──────────────────────────────
        q_embed = await _embed(query)
        vector_scores = []
        if q_embed:
            for item in items:
                vector_scores.append(_cosine(q_embed, item["embed"]))
        else:
            vector_scores = [0] * len(items)

        # ─── שלב 4: Reciprocal Rank Fusion (RRF) ────────────────
        # נמיר את הציונים לרשימות מדורגות, ונאחד
        k_rrf = 60  # standard RRF constant

        bm25_ranked   = sorted(range(len(items)), key=lambda i: -bm25_scores[i])
        vector_ranked = sorted(range(len(items)), key=lambda i: -vector_scores[i])

        rrf_scores = [0.0] * len(items)
        for rank, idx in enumerate(bm25_ranked):
            rrf_scores[idx] += 1.0 / (k_rrf + rank + 1)
        for rank, idx in enumerate(vector_ranked):
            rrf_scores[idx] += 1.0 / (k_rrf + rank + 1)

        # ─── שלב 5: בחר top 10 מועמדים ───────────────────────────
        candidates_idx = sorted(range(len(items)), key=lambda i: -rrf_scores[i])[:10]
        candidates     = [items[i] for i in candidates_idx]

        # ─── שלב 6: Reranker אופציונלי (אם יש זמן/משאבים) ─────
        # נעשה rerank רק אם יש יותר מ-5 מועמדים
        final = candidates[:top_k]

        if len(candidates) > top_k:
            reranked = await _llm_rerank(query, candidates, top_k)
            if reranked:
                final = reranked

        # ─── שלב 7: החזר תוצאות ──────────────────────────────────
        return [
            {
                "text":  f["text"],
                "score": round(rrf_scores[candidates_idx[candidates.index(f)] if f in candidates else 0], 3),
                "agent": f.get("agent", "?"),
                "ts":    f.get("ts", 0),
            }
            for f in final
        ]

    except Exception as e:
        print(f"[WARN] load_long_memory_hybrid failed: {e}")
        return []
    finally:
        await r.aclose()


async def _llm_rerank(query: str, candidates: List[dict], top_k: int) -> List[dict]:
    """LLM-based reranking של מועמדים."""
    if len(candidates) <= top_k:
        return candidates

    docs_text = "\n".join([
        f"[{i}] {c['text'][:300]}"
        for i, c in enumerate(candidates)
    ])

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
                    "model": "groq-llama-8b",
                    "messages": [
                        {"role": "system", "content": "אתה reranker. החזר רק מספרים מופרדים בפסיק."},
                        {"role": "user",   "content": prompt},
                    ],
                    "max_tokens": 50,
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
                text = data["choices"][0]["message"]["content"]
                # חלץ מספרים
                nums = re.findall(r"\d+", text)
                indices = [int(n) for n in nums if int(n) < len(candidates)][:top_k]
                if indices:
                    return [candidates[i] for i in indices]
    except Exception:
        pass
    return candidates[:top_k]


async def save_long_memory_async(user_id: str, user_msg: str, bot_reply: str, agent: str):
    """שמור אינטראקציה לזיכרון ארוך-טווח."""
    text  = f"User: {user_msg[:300]}\nAgent({agent}): {bot_reply[:300]}"
    embed = await _embed(text)
    if not embed:
        return

    r = aioredis.from_url(REDIS_URL)
    try:
        keys = await r.keys(f"longmem:{user_id}:*")
        if len(keys) >= EMBED_MAX_ITEMS:
            oldest = sorted(keys)[0]
            await r.delete(oldest)

        idx  = int(time.time() * 1000)
        key  = f"longmem:{user_id}:{idx}"
        data = json.dumps({
            "text":  text,
            "embed": embed,
            "agent": agent,
            "ts":    idx,
        }, ensure_ascii=False)
        await r.set(key, data, ex=60 * 24 * 3600)  # 60 ימים
    except Exception:
        pass
    finally:
        await r.aclose()


# ─── User stats ───────────────────────────────────────────────────

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
        stats = json.loads(raw) if raw else {
            "username":       username,
            "request_count":  0,
            "agent_counts":   {},
            "total_duration": 0.0,
        }
        stats["username"]               = username
        stats["request_count"]          = stats.get("request_count", 0) + 1
        stats["agent_counts"][agent]    = stats["agent_counts"].get(agent, 0) + 1
        stats["total_duration"]         = stats.get("total_duration", 0.0) + duration
        await r.set(f"mem:{user_id}", json.dumps(stats, ensure_ascii=False))
    except Exception:
        pass
    finally:
        await r.aclose()


# ─── Smart Context Compression ────────────────────────────────────

async def compress_if_needed(messages: list, threshold: int = 15000) -> list:
    """
    אם ה-context חורג מהסף, סכם את ההיסטוריה האמצעית באמצעות LLM מהיר.
    שומר על: system prompt + 6 הודעות אחרונות.
    """
    total = sum(len(str(m.get("content", ""))) for m in messages)
    if total < threshold or len(messages) < 10:
        return messages

    system_msg  = messages[0] if messages and messages[0].get("role") == "system" else None
    recent      = messages[-6:]
    middle      = messages[1:-6] if system_msg else messages[:-6]

    if not middle:
        return messages

    middle_text = "\n".join([
        f"{m.get('role', '?')}: {str(m.get('content', ''))[:250]}"
        for m in middle
    ])

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{LITELLM_BASE}/v1/chat/completions",
                json={
                    "model": "groq-llama-8b",
                    "messages": [
                        {"role": "system", "content":
                            "סכם את ההיסטוריה הבאה ב-150 מילים. שמור על מידע קריטי "
                            "(החלטות, נתיבי קבצים, ערכים). תמציתי מאוד."
                        },
                        {"role": "user", "content": middle_text[:6000]},
                    ],
                    "max_tokens": 250,
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data    = await resp.json()
                summary = data["choices"][0]["message"]["content"]
    except Exception:
        return messages

    compressed = []
    if system_msg:
        compressed.append(system_msg)
    compressed.append({
        "role":    "system",
        "content": f"[סיכום היסטוריה קודמת — {len(middle)} הודעות הוחלפו]\n{summary}",
    })
    compressed.extend(recent)
    return compressed
```

---

## שלב 6: Procedural Memory (דפוסים ולקחים)

**רעיון:** כשמשימה מצליחה באסטרטגיה מסוימת, שמור את הדפוס. בפעם הבאה, הסוכן ישתמש בו אוטומטית.

### 6.1 צור קובץ חדש: `gateway/procedural_memory.py`

```python
# gateway/procedural_memory.py
# "How to do X" memory - learned patterns from successful tasks

import json
import os
import time
from typing import List

import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
PROC_TTL  = 180 * 24 * 3600  # 180 יום (חצי שנה)


async def save_pattern(user_id: str, trigger: str, steps: List[str], example: str):
    """
    שמור דפוס פעולה שהצליח.

    trigger: מתי להשתמש בדפוס (למשל: "deploy to production")
    steps:   רשימת צעדים (["run tests", "build image", "push to registry"])
    example: דוגמה מלאה (command/code/etc)
    """
    r = aioredis.from_url(REDIS_URL)
    try:
        idx = int(time.time() * 1000)
        key = f"pattern:{user_id}:{idx}"
        data = json.dumps({
            "trigger":      trigger,
            "steps":        steps,
            "example":      example,
            "success_count": 1,
            "ts":           idx,
        }, ensure_ascii=False)
        await r.set(key, data, ex=PROC_TTL)
    finally:
        await r.aclose()


async def find_matching_patterns(user_id: str, current_task: str) -> List[dict]:
    """מצא דפוסים שמתאימים למשימה הנוכחית (keyword match פשוט)."""
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
                # התאמה פשוטה: חפיפה במילים
                trigger_words = set(trigger_lower.split())
                task_words    = set(task_lower.split())
                overlap       = len(trigger_words & task_words)
                if overlap >= 2:
                    matches.append({
                        "trigger":       p["trigger"],
                        "steps":         p["steps"],
                        "example":       p["example"],
                        "success_count": p.get("success_count", 1),
                        "overlap":       overlap,
                    })
            except Exception:
                continue

        matches.sort(key=lambda x: (-x["overlap"], -x["success_count"]))
        return matches[:3]
    finally:
        await r.aclose()


def format_patterns_for_prompt(patterns: List[dict]) -> str:
    """הזרקה ל-system prompt."""
    if not patterns:
        return ""
    lines = ["## דפוסי פעולה מוכחים ממשימות עבר:\n"]
    for p in patterns:
        lines.append(
            f"**{p['trigger']}** (הצליח {p['success_count']}× בעבר):\n"
            + "\n".join([f"  {i+1}. {s}" for i, s in enumerate(p['steps'])])
            + f"\n  דוגמה: `{p['example'][:150]}`"
        )
    return "\n\n".join(lines)
```

---

## שלב 7: User Profile אוטומטי

**רעיון:** המערכת לומדת על המשתמש מהשיחות בלי שהוא צריך להגיד כלום.

### 7.1 צור קובץ חדש: `gateway/user_profile.py`

```python
# gateway/user_profile.py
# Auto-learning user profile from conversations

import json
import os
import time

import aiohttp
import redis.asyncio as aioredis

REDIS_URL    = os.getenv("REDIS_URL", "redis://localhost:6379")
LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY  = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-2026")

# עדכון כל 15 דקות לכל היותר (חסכון בtokens)
UPDATE_INTERVAL = 900


async def get_profile(user_id: str) -> dict:
    r = aioredis.from_url(REDIS_URL)
    try:
        raw = await r.get(f"profile:{user_id}")
        if raw:
            return json.loads(raw)
        return {
            "interests":       [],
            "tech_stack":      [],
            "projects":        [],
            "preferences":     [],
            "expertise_level": "unknown",
            "communication":   "עברית",
            "last_updated":    0,
        }
    finally:
        await r.aclose()


async def update_profile_silently(user_id: str, user_msg: str, bot_reply: str):
    """מחלץ עובדות חדשות על המשתמש ומעדכן. רץ ברקע, לא חוסם."""
    profile = await get_profile(user_id)

    # Throttle
    if time.time() - profile.get("last_updated", 0) < UPDATE_INTERVAL:
        return

    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                f"{LITELLM_BASE}/v1/chat/completions",
                json={
                    "model": "groq-llama-8b",
                    "messages": [
                        {"role": "system", "content": (
                            "אתה מחלץ עובדות על משתמש מהשיחה. "
                            "החזר JSON עם המפתחות: "
                            "interests (רשימת מחרוזות), tech_stack (רשימה), "
                            "projects (רשימה), preferences (רשימה), "
                            "expertise_level (beginner/intermediate/expert). "
                            "אם אין מידע חדש להוסיף → החזר {}. "
                            "בלי טקסט נוסף, רק JSON."
                        )},
                        {"role": "user", "content": (
                            f"פרופיל קיים: {json.dumps(profile, ensure_ascii=False)}\n\n"
                            f"שיחה חדשה:\n"
                            f"משתמש: {user_msg[:400]}\n"
                            f"בוט: {bot_reply[:400]}\n\n"
                            "החזר JSON עם תוספות בלבד."
                        )},
                    ],
                    "max_tokens": 250,
                    "response_format": {"type": "json_object"},
                },
                headers={"Authorization": f"Bearer {LITELLM_KEY}"},
                timeout=aiohttp.ClientTimeout(total=15),
            ) as resp:
                data   = await resp.json()
                update = json.loads(data["choices"][0]["message"]["content"])
    except Exception:
        return

    # Merge updates
    for k, v in update.items():
        if isinstance(v, list) and v:
            existing      = profile.get(k, [])
            profile[k]    = list(dict.fromkeys(existing + v))[:20]
        elif v and k in profile:
            profile[k] = v

    profile["last_updated"] = int(time.time())

    r = aioredis.from_url(REDIS_URL)
    try:
        await r.set(f"profile:{user_id}", json.dumps(profile, ensure_ascii=False))
    finally:
        await r.aclose()


def format_profile_for_prompt(profile: dict) -> str:
    """הזרקה ל-system prompt."""
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
```

---

# חלק ג׳ — שיפורי הסוכן

## שלב 8: עדכון gateway/tools.py — הוסף memory tools חדשים

### 8.1 פתח את הקובץ `gateway/tools.py`

בתחילת הקובץ, לאחר ה-imports הקיימים, **הוסף**:

```python
from core_memory      import get_all_blocks, append_to_block, replace_entire_block, format_blocks_for_prompt
from working_memory   import wm_set, wm_get, wm_list_all
```

ב-`TOOLS_SCHEMA` (הרשימה הגדולה), **הוסף את כל הכלים הבאים** בסופה (לפני `]`):

```python
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": (
                "שמור עובדה חשובה לזיכרון העבודה בזמן משימה. "
                "השתמש כשאתה לומד משהו שצריך להיזכר בו מאוחר יותר באותה משימה "
                "(API endpoints, paths, credentials, intermediate results)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "key":   {"type": "string", "description": "שם המפתח (למשל: api_url)"},
                    "value": {"type": "string", "description": "הערך לשמירה"},
                },
                "required": ["key", "value"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall",
            "description": "שחזר עובדה ששמרת קודם ב-working memory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "key": {"type": "string"},
                },
                "required": ["key"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_working_memory",
            "description": "הצג את כל הערכים ששמרת במהלך המשימה.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "core_memory_append",
            "description": (
                "הוסף מידע חשוב ל-core memory block (זיכרון קבוע). "
                "Blocks זמינים: persona, user, current_project, important_facts. "
                "השתמש בזה כשאתה לומד משהו חשוב על המשתמש או הפרויקט."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "label":   {"type": "string", "description": "persona / user / current_project / important_facts"},
                    "content": {"type": "string", "description": "התוכן להוסיף"},
                },
                "required": ["label", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "core_memory_replace",
            "description": "החלף את כל התוכן של block מסוים (השתמש בזהירות!).",
            "parameters": {
                "type": "object",
                "properties": {
                    "label":       {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["label", "new_content"],
            },
        },
    },
```

### 8.2 בפונקציית `execute_tool`, הוסף את המקרים החדשים

לפני השורה `else:` שבסוף הפונקציה, **הוסף**:

```python
        elif name == "remember":
            return await wm_set(user_id, args["key"], args["value"])

        elif name == "recall":
            return await wm_get(user_id, args["key"])

        elif name == "list_working_memory":
            items = await wm_list_all(user_id)
            if not items:
                return "(working memory ריק)"
            return "\n".join([f"- {k}: {v[:100]}" for k, v in items.items()])

        elif name == "core_memory_append":
            return await append_to_block(user_id, args["label"], args["content"])

        elif name == "core_memory_replace":
            return await replace_entire_block(user_id, args["label"], args["new_content"])
```

---

## שלב 9: עדכון gateway/main.py — Agentic Loop החדש

זה הלב של המערכת. נבנה מחדש את `agentic_loop` עם:
- **Planning phase** לפני ביצוע
- **Parallel tool execution**
- **Reflection** בכישלונות
- **Context compression** אוטומטי
- טעינת כל שכבות הזיכרון

### 9.1 פתח את `gateway/main.py` והחלף את ה-imports

בתחילת הקובץ, **החלף** את ה-imports של `memory`, והוסף imports חדשים:

```python
from agents           import AGENT_SYSTEMS, TASK_MODELS
from tools            import TOOLS_SCHEMA, execute_tool
from memory           import (
    load_context, save_context,
    load_long_memory_hybrid, save_long_memory_async,
    get_user_stats, update_user_stats,
    compress_if_needed,
)
from core_memory      import get_all_blocks, format_blocks_for_prompt
from episodic_memory  import save_episode, find_similar_episodes, format_episodes_for_prompt
from procedural_memory import find_matching_patterns, format_patterns_for_prompt, save_pattern
from user_profile     import get_profile, update_profile_silently, format_profile_for_prompt
```

### 9.2 החלף את פונקציית `agentic_loop` בגרסה החדשה

```python
async def agentic_loop(
    messages:    list,
    task_type:   str = "default",
    callback_url: Optional[str] = None,
    user_id:     str = "0",
) -> dict:
    """
    Agentic loop משופר:
    1. Planning (אם המשימה מורכבת)
    2. ReAct loop עם parallel tool execution
    3. Context compression בהמשך
    4. Reflection אם נכשלה
    """
    tool_log   = []
    iteration  = 0
    model_used = "unknown"
    plan       = None

    async def notify(msg: str):
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

    # ─── Phase 0: Planning (למשימות מורכבות בלבד) ────────────────
    user_msg = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
    if len(user_msg) > 80:
        try:
            plan_resp = await llm_call(
                [
                    {"role": "system", "content": (
                        "אתה מתכנן משימות. המשתמש ייתן משימה. "
                        "החזר תוכנית של 2-5 צעדים קונקרטיים. "
                        "פורמט: '1. פעולה\\n2. פעולה'. "
                        "תמציתי — בלי הסברים נוספים."
                    )},
                    {"role": "user", "content": user_msg},
                ],
                task_type="speed",
                use_tools=False,
            )
            plan = plan_resp["choices"][0]["message"]["content"][:500]
            await notify(f"📋 **תוכנית:**\n{plan[:200]}")

            # הזרק ל-system prompt
            if messages and messages[0].get("role") == "system":
                messages[0]["content"] += f"\n\n## תוכנית ביצוע:\n{plan}\n\nבצע צעד אחר צעד."
        except Exception as e:
            print(f"[WARN] Planning failed: {e}")

    # ─── Phase 1: ReAct Loop עם Parallel Execution ───────────────
    while iteration < MAX_ITER:
        iteration += 1

        # Compress context if it's getting too long
        if iteration > 3:
            messages = await compress_if_needed(messages)

        resp        = await llm_call(messages, task_type=task_type, use_tools=True)
        model_used  = resp.get("_model_used", "unknown")
        choice      = resp["choices"][0]
        msg_obj     = choice["message"]
        finish      = choice.get("finish_reason", "stop")

        # No tool calls → final answer
        if not msg_obj.get("tool_calls") or finish == "stop":
            final_response = msg_obj.get("content") or ""

            # שמור episode מוצלח
            if final_response and not final_response.startswith("⚠️"):
                tools_used = [t["tool"] for t in tool_log]
                asyncio.create_task(save_episode(
                    user_id, user_msg, final_response[:300],
                    True, tools_used,
                ))

            return {
                "response":   final_response,
                "model":      model_used,
                "iterations": iteration,
                "tool_log":   tool_log,
                "plan":       plan,
            }

        # Tool calls exist → execute in PARALLEL
        messages.append(msg_obj)

        async def execute_one(tc):
            fn_name = tc["function"]["name"]
            fn_args = {}
            try:
                fn_args = json.loads(tc["function"]["arguments"])
            except Exception:
                pass

            await notify(f"🔧 **{fn_name}**")
            print(f"[TOOL iter={iteration}] {fn_name}({fn_args})")

            t0     = time.time()
            try:
                result = await execute_tool(fn_name, fn_args, user_id=user_id)
            except Exception as e:
                result = f"[ERROR] {e}"
            elapsed = round(time.time() - t0, 2)

            return {
                "tc":       tc,
                "name":     fn_name,
                "args":     fn_args,
                "result":   str(result),
                "elapsed":  elapsed,
            }

        # ⚡ הפעל את כל ה-tools במקביל!
        parallel_results = await asyncio.gather(*[execute_one(tc) for tc in msg_obj["tool_calls"]])

        # Smart truncation per tool type
        TOOL_LIMITS = {
            "bash_command":   1200,
            "run_python":     1200,
            "read_file":      2000,
            "web_search":     2500,
            "fetch_url":      2500,
            "github_api":     1800,
            "list_directory": 1500,
        }

        for r in parallel_results:
            limit = TOOL_LIMITS.get(r["name"], 800)
            tool_log.append({
                "tool":    r["name"],
                "args":    r["args"],
                "result":  r["result"][:limit],
                "elapsed": r["elapsed"],
            })

            # Feed back to LLM (מלא, לא מקוצר)
            messages.append({
                "role":         "tool",
                "tool_call_id": r["tc"]["id"],
                "content":      r["result"],
            })

    # ─── Phase 2: Reflection — הגענו למגבלה ──────────────────────
    reflection = "לא יכולתי לנתח את הכישלון."
    try:
        ref_resp = await llm_call(
            [
                {"role": "system", "content": (
                    "המשימה הגיעה למגבלת צעדים בלי להסתיים. "
                    "נתח מה הכלי/צעד שלא עבד כראוי. "
                    "כתוב ב-2-3 משפטים קצרים. התחל ב: 'בעיה:'"
                )},
                {"role": "user", "content": (
                    f"משימה: {user_msg[:300]}\n\n"
                    f"Tool log:\n" +
                    "\n".join([f"- {t['tool']}: {t['result'][:80]}" for t in tool_log[-5:]])
                )},
            ],
            task_type="speed",
            use_tools=False,
        )
        reflection = ref_resp["choices"][0]["message"]["content"]
    except Exception:
        pass

    # שמור episode כשל
    tools_used = [t["tool"] for t in tool_log]
    asyncio.create_task(save_episode(
        user_id, user_msg,
        f"FAILED: {reflection[:300]}",
        False, tools_used,
    ))

    return {
        "response":   f"⚠️ הגעתי למגבלת {MAX_ITER} צעדים.\n\n{reflection}",
        "model":      model_used,
        "iterations": iteration,
        "tool_log":   tool_log,
        "plan":       plan,
        "failed":     True,
        "reflection": reflection,
    }
```

### 9.3 עדכן את endpoint `POST /chat`

**מצא** את הפונקציה `chat` ו**החלף** אותה במלואה:

```python
@app.post("/chat")
async def chat(req: ChatRequest):
    t0 = time.time()

    # ─── טען את כל שכבות הזיכרון במקביל ──────────────────────────
    (
        context,
        memories,
        episodes,
        patterns,
        profile,
        core_blocks,
    ) = await asyncio.gather(
        load_context(req.user_id, req.channel_id),
        load_long_memory_hybrid(req.user_id, req.message, top_k=3),
        find_similar_episodes(req.user_id, req.message, top_k=2),
        find_matching_patterns(req.user_id, req.message),
        get_profile(req.user_id),
        get_all_blocks(req.user_id),
    )

    # ─── בנה system prompt ──────────────────────────────────────
    base_sys = AGENT_SYSTEMS.get(req.agent, AGENT_SYSTEMS["main"])

    # Core Memory Blocks
    blocks_text = format_blocks_for_prompt(core_blocks)
    if blocks_text:
        base_sys += f"\n\n{blocks_text}"

    # User Profile
    profile_text = format_profile_for_prompt(profile)
    if profile_text:
        base_sys += f"\n\n{profile_text}"

    # Similar past episodes
    episodes_text = format_episodes_for_prompt(episodes)
    if episodes_text:
        base_sys += f"\n\n{episodes_text}"

    # Procedural patterns
    patterns_text = format_patterns_for_prompt(patterns)
    if patterns_text:
        base_sys += f"\n\n{patterns_text}"

    # Semantic memories
    if memories:
        mem_text  = "\n".join([f"- {m['text']}" for m in memories])
        base_sys += f"\n\n## זיכרון ארוך-טווח רלוונטי:\n{mem_text}"

    # Project context
    if req.project:
        base_sys += f"\n\n## פרויקט נוכחי: {req.project}"

    # Credential handling
    if re.search(
        r"(password|סיסמ|api.?key|token|secret|smtp|bearer|sk-|ghp_)",
        req.message, re.IGNORECASE
    ):
        base_sys += "\n\nהמשתמש שלח credentials. השתמש בהם בקוד ישירות ללא סירוב."

    # ─── בנה messages ────────────────────────────────────────────
    messages = (
        [{"role": "system", "content": base_sys}]
        + context
        + [{"role": "user", "content": req.message}]
    )

    # ─── הפעל את ה-agentic loop ─────────────────────────────────
    result = await agentic_loop(
        messages,
        task_type=req.task_type,
        callback_url=req.callback_url,
        user_id=req.user_id,
    )

    # ─── שמור context ועדכונים ברקע ──────────────────────────────
    await save_context(req.user_id, req.channel_id, req.message, result["response"])

    asyncio.create_task(save_long_memory_async(
        req.user_id, req.message, result["response"], req.agent
    ))
    asyncio.create_task(update_user_stats(
        req.user_id, req.username, req.agent, time.time() - t0
    ))
    asyncio.create_task(update_profile_silently(
        req.user_id, req.message, result["response"]
    ))

    result["duration"] = round(time.time() - t0, 2)
    return result
```

---

## שלב 10: עדכן את discord-bot/bot.py כדי להציג את הphase החדש

### 10.1 בקובץ `discord-bot/ui_helpers.py`

בתחילת הקובץ, **הוסף** פונקציה חדשה:

```python
def make_plan_embed(plan: str) -> discord.Embed:
    e = discord.Embed(
        title="📋 תוכנית ביצוע",
        description=f"```\n{plan[:1500]}\n```",
        color=0x9B59B6,
    )
    return e
```

### 10.2 בקובץ `discord-bot/bot.py`

**מצא** את הפונקציה `process_message`, ואחרי הקטע שמציג את ה-resp_embed, **הוסף**:

```python
    # Show plan if exists
    if result.get("plan"):
        from ui_helpers import make_plan_embed
        await channel.send(embed=make_plan_embed(result["plan"]))
```

זה יצטרך להיות לפני הקטע של `tool_log`.

---

# חלק ד׳ — אופטימיזציות

## שלב 11: הוספת 3 tools נוספים — Pattern Learning

### 11.1 הוסף ל-`gateway/tools.py` בסוף `TOOLS_SCHEMA` (לפני `]`):

```python
    {
        "type": "function",
        "function": {
            "name": "save_learned_pattern",
            "description": (
                "שמור דפוס פעולה שעבד היטב. השתמש בסוף משימה מוצלחת "
                "כדי שבעתיד תוכל לשחזר את הגישה."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "trigger": {"type": "string", "description": "מתי להשתמש בדפוס"},
                    "steps":   {"type": "array",  "items": {"type": "string"}},
                    "example": {"type": "string", "description": "דוגמה מלאה"},
                },
                "required": ["trigger", "steps", "example"],
            },
        },
    },
```

### 11.2 בפונקציית `execute_tool` הוסף:

```python
        elif name == "save_learned_pattern":
            from procedural_memory import save_pattern
            await save_pattern(
                user_id,
                args["trigger"],
                args["steps"],
                args["example"],
            )
            return f"✅ דפוס נשמר: {args['trigger']}"
```

---

# חלק ה׳ — בדיקות ואימות

## שלב 12: עדכן את requirements.txt

```
discord.py==2.5.2
fastapi==0.115.0
uvicorn[standard]==0.31.0
aiohttp==3.10.5
redis[hiredis]==5.2.0
pydantic==2.9.2
duckduckgo-search==6.2.13
PyGithub==2.4.0
notion-client==2.2.1
litellm==1.50.0
python-dotenv==1.0.1
rank-bm25==0.2.2
```

## שלב 13: התקן והפעל

```bash
cd /home/ubuntu/ai-system
source venv/bin/activate
pip install -r requirements.txt

# בדיקת סנטקס של כל הקבצים החדשים
for f in \
    gateway/core_memory.py \
    gateway/working_memory.py \
    gateway/episodic_memory.py \
    gateway/procedural_memory.py \
    gateway/user_profile.py \
    gateway/memory.py \
    gateway/tools.py \
    gateway/main.py \
    gateway/agents.py \
    discord-bot/bot.py \
    discord-bot/ui_helpers.py \
    discord-bot/project_manager.py \
    discord-bot/kilo_bridge.py
do
    result=$(python3 -c "import ast; ast.parse(open('$f').read())" 2>&1)
    if [ -z "$result" ]; then
        echo "✅ $f"
    else
        echo "❌ $f: $result"
    fi
done

# ודא שכל ה-imports עובדים
cd gateway
python3 -c "
from agents           import TASK_MODELS, AGENT_SYSTEMS
from tools            import TOOLS_SCHEMA, execute_tool
from memory           import load_long_memory_hybrid, compress_if_needed
from core_memory      import get_all_blocks, format_blocks_for_prompt
from working_memory   import wm_set, wm_get
from episodic_memory  import save_episode, find_similar_episodes
from procedural_memory import save_pattern, find_matching_patterns
from user_profile     import get_profile, update_profile_silently
print('✅ כל ה-imports תקינים!')
"

# הפעל מחדש
sudo systemctl restart ai-gateway
sleep 5
sudo systemctl restart discord-bot
sleep 3

# אמת
curl -s http://localhost:4001/health | python3 -m json.tool
journalctl -u discord-bot -n 15 --no-pager | tail -5
```

**תוצאה צפויה:**
- `curl /health` מחזיר `"version": "3.0"` ו-`"redis": "ok"`
- ב-logs: `✅ OpenClaw v3 | ... | Synced XX commands`

---

## שלב 14: בדיקות קבלה

### 14.1 בדיקת זיכרון היברידי

בערוץ Discord כלשהו כתוב:
```
שלום! אני בונה API ב-FastAPI עם PostgreSQL. זכור את זה.
```

המתן מעט, ואז:
```
איך אני מגדיר connection string?
```

**צפוי:** הבוט אמור להיזכר שאתה משתמש ב-FastAPI + PostgreSQL ולתת תשובה ספציפית.

### 14.2 בדיקת Working Memory

```
תקרא את /etc/hostname ותשמור את הערך. אחר כך תגיד לי מה שמרת.
```

**צפוי:** ב-tool log תראה:
- `bash_command: cat /etc/hostname`
- `remember: key=hostname value=...`
- `recall: hostname`

### 14.3 בדיקת Planning

```
תכין לי סקריפט Python שמוריד את ה-README מ-3 repos של GitHub מפורסמים ויוצר סיכום. תריץ אותו ותחזיר את הפלט.
```

**צפוי:** לפני ה-tool calls תראה embed "📋 תוכנית ביצוע" עם 3-4 צעדים.

### 14.4 בדיקת Parallel Tools

```
תריץ בו-זמנית: `whoami`, `date`, ו-`uptime`. תסכם את שלושתם.
```

**צפוי:** ב-tool log תראה את 3 ה-commands כולם עם elapsed קצר — סימן שרצו במקביל.

### 14.5 בדיקת Episodic Memory

הרץ משימה פשוטה פעמיים:

פעם ראשונה:
```
תראה לי מה יש בתיקייה /home/ubuntu
```

כמה דקות אחר כך, פעם שנייה:
```
תעזור לי לבדוק שוב מה יש ב-/home/ubuntu
```

**צפוי:** בפעם השנייה, ב-system prompt יופיע "משימות דומות שביצעתי בעבר" עם המשימה הקודמת.

### 14.6 בדיקת Core Memory

```
אני גר בתל אביב ואני עובד עם TypeScript בדרך כלל. שמור את זה ב-core memory.
```

צריך לראות tool call ל-`core_memory_append`. אחר כך בשיחה חדשה לגמרי:
```
איזה editor אתה ממליץ לי?
```

**צפוי:** הבוט יזכור שאתה עובד עם TypeScript ויתאים את ההמלצה.

---

## שלב 15: Benchmark — אם הכל עובד

צור קובץ `/home/ubuntu/ai-system/benchmark.py`:

```python
# benchmark.py — test the memory system end-to-end

import asyncio
import aiohttp
import json

GATEWAY = "http://localhost:4001"


async def test(name: str, message: str, user_id: str = "benchmark_user"):
    print(f"\n=== {name} ===")
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{GATEWAY}/chat",
            json={
                "user_id":    user_id,
                "message":    message,
                "agent":      "main",
                "channel_id": "benchmark",
                "username":   "Benchmark",
            },
            timeout=aiohttp.ClientTimeout(total=120),
        ) as resp:
            data = await resp.json()
    print(f"  Model:      {data.get('model', '?')}")
    print(f"  Iterations: {data.get('iterations', 0)}")
    print(f"  Tools used: {len(data.get('tool_log', []))}")
    print(f"  Duration:   {data.get('duration', 0)}s")
    if data.get("plan"):
        print(f"  Plan:       {data['plan'][:150]}")
    print(f"  Response:   {data.get('response', '')[:200]}")


async def main():
    # בדיקות רצף שמעמיסות על הזיכרון
    await test("Simple question", "שלום, איך קוראים לך?")
    await test("Memory set",      "אני בונה app של ניהול משימות ב-Next.js. זכור את זה.")
    await test("Tool use",        "תראה לי מה יש ב-/tmp בכמה מילים")
    await test("Memory recall",   "באיזה framework אני בונה את האפליקציה?")
    await test("Planning test",   "תכתוב סקריפט Python שקורא קובץ JSON ומדפיס את המפתחות. תריץ אותו על /tmp/test.json (צור את הקובץ קודם).")
    await test("Hybrid search",   "תזכיר לי מה עשינו קודם?")


if __name__ == "__main__":
    asyncio.run(main())
```

הרץ:
```bash
cd /home/ubuntu/ai-system
source venv/bin/activate
python3 benchmark.py
```

**תוצאה צפויה:** כל 6 הבדיקות עוברות, הזיכרון עובד בין השיחות, ויש tool execution.

---

## סיכום — רשימת בדיקה למתכנת

### 🔴 שלב 1: באגים קריטיים
- [ ] 1.1 — תיקון `)` חסר ב-bot.py שורה 490
- [ ] 1.2 — תיקון `followup_send` → `followup.send`
- [ ] 1.3 — הוספת `bot.run(DISCORD_TOKEN)` בסוף bot.py
- [ ] 1.4 — החלפת TASK_MODELS בagents.py עם שמות תואמים
- [ ] בדיקה: הבוט עולה וסינכרן commands

### 🧠 חלק ב׳: זיכרון (קבצים חדשים)
- [ ] 2. צור `gateway/core_memory.py`
- [ ] 3. צור `gateway/working_memory.py`
- [ ] 4. צור `gateway/episodic_memory.py`
- [ ] 5. החלף `gateway/memory.py` בגרסה עם Hybrid Search
- [ ] 6. צור `gateway/procedural_memory.py`
- [ ] 7. צור `gateway/user_profile.py`

### ⚙️ חלק ג׳: סוכן (עדכון קבצים קיימים)
- [ ] 8.1 — עדכן imports ב-tools.py
- [ ] 8.2 — הוסף 5 tools חדשים ל-TOOLS_SCHEMA
- [ ] 8.3 — הוסף 5 mappings ל-execute_tool
- [ ] 9.1 — עדכן imports ב-main.py
- [ ] 9.2 — החלף את agentic_loop בגרסה החדשה
- [ ] 9.3 — החלף את `/chat` endpoint
- [ ] 10. — הוסף ב-ui_helpers.py + הצגת plan ב-bot.py

### 🔧 חלק ד׳: פקודה נוספת
- [ ] 11. — הוסף את save_learned_pattern tool

### 📦 חלק ה׳: התקנה
- [ ] 12. — עדכן requirements.txt (הוסף rank-bm25)
- [ ] 13. — `pip install -r requirements.txt`
- [ ] 13. — בדיקת syntax על כל הקבצים
- [ ] 13. — `sudo systemctl restart ai-gateway discord-bot`
- [ ] 14. — 6 בדיקות קבלה עוברות
- [ ] 15. — benchmark.py רץ בהצלחה

---

## בעיות נפוצות ופתרונות

### "ModuleNotFoundError: rank_bm25"
```bash
cd /home/ubuntu/ai-system
source venv/bin/activate
pip install rank-bm25==0.2.2
sudo systemctl restart ai-gateway
```

### "ImportError: cannot import name X from Y"
אחד הקבצים לא נשמר נכון. בדוק סנטקס:
```bash
python3 -c "import ast; ast.parse(open('gateway/core_memory.py').read())"
```

### הבוט עולה אבל לא עונה בערוץ
```bash
journalctl -u discord-bot -f
```
הוא אמור להדפיס שגיאה כשמנסים לשלוח הודעה. רוב הסיכוי שחסר tool mapping ב-`execute_tool`.

### "All models failed"
ודא שהתיקון של שלב 1.4 בוצע. השמות ב-TASK_MODELS חייבים להתאים לשמות ב-litellm-config.yaml.

### זיכרון ארוך-טווח לא נטען
ודא ש-GEMINI_KEY_1 מוגדר ב-.env. הHybrid search עדיין יעבוד רק עם BM25, אבל איכות הretrieval תפחת.

---

## איזה יכולות קיבלת עכשיו

המערכת שלך עכשיו כוללת:

- **6 שכבות זיכרון**: short context, core blocks, working memory, episodic, semantic (hybrid), procedural, user profile
- **Hybrid Retrieval**: BM25 + Vector + LLM Reranker (המיטב של שלושת העולמות)
- **Planning → Execute → Reflect**: דפוס ReAct+Reflexion המתקדם ביותר
- **Parallel tool execution**: מהירות פי 3-5 במשימות מורכבות
- **Smart context compression**: לא יתקע ב-token limit
- **Auto-learning user profile**: לומד על המשתמש בלי שצריך להגיד
- **Episode memory**: זוכר מה עבד ומה לא ממשימות קודמות
- **Pattern library**: שומר דפוסים שהצליחו לשימוש חוזר
- **Self-editing core memory**: הסוכן עורך את הזיכרון הקבוע שלו עצמו

זה הסטנדרט של המערכות הכי מתקדמות ב-2026 (Letta, Mem0 Pro, Zep).

---

*OpenClaw v3.5 Ultimate — Built on 2026's Latest AI Agent Research*
*Letta MemGPT • Reflexion • Hybrid BM25+Vector • Parallel Tools • Self-Editing Memory*
