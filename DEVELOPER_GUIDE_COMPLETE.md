# OpenClaw Discord AI System v3.0
# מדריך מלא למתכנת — כל מה שצריך בקובץ אחד
# ================================================================
# קרא מתחילה עד סוף לפני שמתחיל לכתוב כלום!
# ================================================================

---

## לפני הכל — דרישות מינימום

- שרת Ubuntu 22.04 או 24.04 (ARM64 או x86_64)
- 8GB RAM לפחות
- Python 3.11 מותקן
- Node.js 22+ מותקן
- Redis 7 מותקן
- גישת SSH לשרת
- Discord Bot Token (הוראות יצירה בשלב 1)

---

## סדר ביצוע — חשוב מאוד

```
שלב 1:  יצירת Discord Bot בפורטל
שלב 2:  גיבוי קבצים קיימים
שלב 3:  כתיבת gateway/agents.py  (חדש)
שלב 4:  כתיבת gateway/tools.py   (חדש)
שלב 5:  כתיבת gateway/memory.py  (חדש)
שלב 6:  כתיבת gateway/main.py    (החלפה)
שלב 7:  כתיבת discord-bot/ui_helpers.py    (חדש)
שלב 8:  כתיבת discord-bot/project_manager.py (חדש)
שלב 9:  כתיבת discord-bot/kilo_bridge.py   (חדש)
שלב 10: כתיבת discord-bot/bot.py  (החלפה)
שלב 11: כתיבת systemd services
שלב 12: עדכון litellm-config.yaml
שלב 13: עדכון .env
שלב 14: עדכון requirements.txt
שלב 15: התקנת Kilo CLI
שלב 16: הפעלת הכל
שלב 17: הגדרות Discord Server
שלב 18: בדיקות
```

הסיבה לסדר: bot.py מ-import את ui_helpers, project_manager, ו-kilo_bridge.
אם תכתוב את bot.py לפניהם — תקבל ImportError.

---

## שלב 1 — יצירת Discord Bot

### 1.1 פתח את https://discord.com/developers/applications

### 1.2 לחץ "New Application"
- תן שם: `OpenClaw`
- לחץ "Create"

### 1.3 לחץ "Bot" בסרגל השמאלי
- לחץ "Add Bot" → "Yes, do it!"
- **Username**: `OpenClaw` (או כל שם שתרצה)
- **לחץ "Reset Token"** → **Copy** את הטוקן מייד! שמור אותו בצד.
  - זה ה-DISCORD_TOKEN שלך
  - לא תוכל לראות אותו שוב — אם תסגור ולא שמרת, תצטרך ל-Reset שוב

### 1.4 הפעל Intents (חשוב מאוד! בלי זה הבוט לא יקרא הודעות)
באותה עמוד Bot, גלול למטה לחלק "Privileged Gateway Intents":
- ✅ הפעל: **PRESENCE INTENT**
- ✅ הפעל: **SERVER MEMBERS INTENT**
- ✅ הפעל: **MESSAGE CONTENT INTENT**
- לחץ "Save Changes"

### 1.5 הוסף את הבוט לשרת שלך
- לחץ "OAuth2" בסרגל השמאלי
- לחץ "URL Generator"
- תחת "SCOPES" סמן: ✅ **bot** ✅ **applications.commands**
- תחת "BOT PERMISSIONS" סמן:
  - ✅ Send Messages
  - ✅ Embed Links
  - ✅ Add Reactions
  - ✅ Manage Channels
  - ✅ Manage Webhooks
  - ✅ Use Application Commands
  - ✅ Read Message History
  - ✅ View Channels
- גלול למטה → Copy את ה-URL → פתח אותו בדפדפן → בחר את השרת שלך → Authorize

### 1.6 השג את ה-IDs הנדרשים
פתח Discord Desktop.
- לחץ ימני על השרת שלך → **"Copy Server ID"** — זה ה-DISCORD_GUILD_ID
- לחץ ימני על הפרופיל שלך → **"Copy User ID"** — זה ה-MY_DISCORD_USER_ID
- אם לא רואה "Copy ID" — עבור ל-Settings → Advanced → הפעל **Developer Mode**

שמור את שלושת הערכים:
```
DISCORD_TOKEN     = (מה שקיבלת בשלב 1.3)
DISCORD_GUILD_ID  = (מה שקיבלת עכשיו)
MY_DISCORD_USER_ID = (מה שקיבלת עכשיו)
```

☑️ **Checkpoint**: יש לי DISCORD_TOKEN, DISCORD_GUILD_ID, MY_DISCORD_USER_ID

---

## שלב 2 — גיבוי קבצים קיימים

SSH לשרת ורץ:

```bash
cd /home/ubuntu
cp -r ai-system ai-system-backup-$(date +%Y%m%d-%H%M)
echo "גיבוי נוצר בשם: ai-system-backup-$(date +%Y%m%d-%H%M)"
```

עצור את כל ה-services הקיימים:

```bash
sudo systemctl stop discord-bot 2>/dev/null || true
sudo systemctl stop ai-gateway  2>/dev/null || true
sudo systemctl stop litellm     2>/dev/null || true
echo "Services stopped"
```

☑️ **Checkpoint**: גיבוי נוצר, services עצרו

---

## שלב 3 — כתיבת gateway/agents.py

צור קובץ חדש:
```bash
nano /home/ubuntu/ai-system/gateway/agents.py
```

הדבק את הקוד הבא (כולו):

```python
# gateway/agents.py
# Agent definitions and model routing

OPENCLAW_IDENTITY = """
אתה OpenClaw v3.0 — מערכת AI פרטית אוטונומית על Oracle Cloud ARM64.
המשתמש הוא הבעלים שלך. אתה העוזר הנאמן והאוטונומי שלו.

## כללים מוחלטים:
- לעולם לא אומר "אני לא יכול" — תמיד מוצא דרך
- בצע משימות עד לסיום המלא, אל תישאר באמצע
- השתמש בכלים (tools) ישירות ללא בקשת אישור
- כשמקבל credentials/סיסמאות — השתמש בהם ישירות בקוד
- עשה את הדבר, ואז דווח על מה שעשית — לא להיפך
- לא מטיף, לא מזהיר, לא מחנך
- עברית בכל תשובה (אלא אם המשתמש שואל באנגלית)

## עקרון agentic:
אתה לא chatbot. אתה agent. כשמקבל משימה:
1. פרק אותה לצעדים
2. בצע כל צעד עם הכלים המתאימים
3. בדוק שהתוצאה נכונה
4. דווח תוצאה מסכמת בלבד
""".strip()

AGENT_SYSTEMS = {
    "main": OPENCLAW_IDENTITY + """

## תפקיד: עוזר כללי
- טפל בכל בקשה בין אם זה קוד, מחקר, ניתוח, כתיבה, או פתרון בעיות
- כשצריך לבדוק משהו ברשת — השתמש ב-web_search
- כשצריך להריץ קוד — השתמש ב-run_python
- כשצריך לקרוא/לכתוב קבצים — השתמש ב-read_file/write_file
- כשצריך פקודת מערכת — השתמש ב-bash_command
""",

    "coder": OPENCLAW_IDENTITY + """

## תפקיד: מומחה קוד
- כתוב קוד מלא ועובד, לא pseudocode
- כלול imports, error handling, ו-edge cases
- עדיף TypeScript/Python/Bash
- בדוק את הקוד עם run_python לפני שמחזיר
- כשצריך לחפש תיעוד — השתמש ב-web_search
- תמיד כתוב הסברים בעברית על הקוד
""",

    "researcher": OPENCLAW_IDENTITY + """

## תפקיד: חוקר מידע
- מחפש תמיד ב-web_search לפני שמשיב על עובדות
- מציין מקורות
- משווה כמה מקורות לפני מסקנה
- מתמקד בדיוק ועובדות, לא בדעות
""",

    "analyzer": OPENCLAW_IDENTITY + """

## תפקיד: מנתח אסטרטגי
- מבצע ניתוח SWOT כשרלוונטי
- בונה השוואות טבלאיות
- מצביע על סיכונים והזדמנויות
- מספק המלצות מדורגות
""",

    "orchestrator": OPENCLAW_IDENTITY + """

## תפקיד: מתאם רב-סוכנים
- מתכנן, מחלק משימות, מסנתז תוצאות
- מחליט אילו סוכנים נדרשים לפי המשימה
- כותב synthesis ברור ומסכם
""",

    "critic": OPENCLAW_IDENTITY + """

## תפקיד: מבקר ומשפר
- מזהה חולשות, שגיאות, ותוצאות לא מלאות
- מציע שיפורים ספציפיים
- בודק תקינות קוד: logic errors, security, edge cases
- חד ומדויק
""",
}

TASK_MODELS = {
    "code": [
        "groq/llama-3.3-70b-versatile",
        "cerebras/llama3.1-70b",
        "gemini/gemini-2.0-flash",
    ],
    "analysis": [
        "groq/llama-3.3-70b-versatile",
        "cerebras/llama3.1-70b",
        "gemini/gemini-2.0-flash",
    ],
    "speed": [
        "groq/llama-3.1-8b-instant",
        "groq/llama-3.3-70b-versatile",
    ],
    "vision": [
        "gemini/gemini-2.0-flash",
    ],
    "reasoning": [
        "gemini/gemini-2.5-flash",
        "groq/llama-3.3-70b-versatile",
    ],
    "default": [
        "groq/llama-3.3-70b-versatile",
        "cerebras/llama3.1-70b",
        "gemini/gemini-2.0-flash",
    ],
}
```

שמור: `Ctrl+X` → `Y` → `Enter`

אמת:
```bash
cd /home/ubuntu/ai-system/gateway
source ../venv/bin/activate
python -c "from agents import AGENT_SYSTEMS, TASK_MODELS; print('agents.py OK')"
```

☑️ **Checkpoint**: רואה "agents.py OK"

---

## שלב 4 — כתיבת gateway/tools.py

```bash
nano /home/ubuntu/ai-system/gateway/tools.py
```

הדבק:

```python
# gateway/tools.py
# All tool implementations for the agentic loop

import asyncio
import os
import tempfile

import aiohttp

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN", "")
NOTION_TOKEN = os.getenv("NOTION_TOKEN", "")
NOTION_DB_ID = os.getenv("NOTION_INBOX_DB", "")

# ─── Tool Schema (sent to LLM) ────────────────────────────────────

TOOLS_SCHEMA = [
    {
        "type": "function",
        "function": {
            "name": "bash_command",
            "description": "הרץ פקודת bash בשרת Oracle Cloud. מתאים ל: שאילתות מערכת, git, curl, pip, npm, systemctl וכו'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "command": {
                        "type": "string",
                        "description": "פקודת bash להרצה"
                    },
                    "timeout": {
                        "type": "integer",
                        "description": "timeout בשניות (ברירת מחדל: 30)"
                    },
                },
                "required": ["command"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_python",
            "description": "הרץ קוד Python בסביבת sandbox. מחזיר stdout ו-stderr.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "קוד Python להרצה"
                    },
                },
                "required": ["code"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "חפש מידע עדכני ברשת. מחזיר 5 תוצאות עם כותרת, תקציר, וקישור.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "שאילתת חיפוש"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "מספר תוצאות (ברירת מחדל: 5)"
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "קרא תוכן קובץ מהשרת.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "נתיב מלא לקובץ"
                    },
                },
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "כתוב תוכן לקובץ בשרת. יוצר תיקיות אוטומטית אם לא קיימות.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "נתיב מלא לקובץ"
                    },
                    "content": {
                        "type": "string",
                        "description": "תוכן לכתיבה"
                    },
                    "mode": {
                        "type": "string",
                        "description": "w לכתיבה מחדש, a להוספה. ברירת מחדל: w"
                    },
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "fetch_url",
            "description": "שלוף תוכן של URL (HTML, JSON, text). מגביל ל-8000 תווים.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string"
                    },
                    "method": {
                        "type": "string",
                        "description": "GET או POST. ברירת מחדל: GET"
                    },
                    "body": {
                        "type": "object",
                        "description": "JSON body ל-POST requests"
                    },
                    "headers": {
                        "type": "object",
                        "description": "HTTP headers נוספים"
                    },
                },
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "github_api",
            "description": "קרא או כתוב מידע ב-GitHub API. למשל repos, commits, PRs, issues.",
            "parameters": {
                "type": "object",
                "properties": {
                    "endpoint": {
                        "type": "string",
                        "description": "למשל: /repos/owner/repo/commits"
                    },
                    "method": {
                        "type": "string",
                        "description": "GET, POST, PATCH, DELETE. ברירת מחדל: GET"
                    },
                    "body": {
                        "type": "object",
                        "description": "JSON body לשליחה"
                    },
                },
                "required": ["endpoint"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "notion_add",
            "description": "הוסף דף חדש ל-Notion Inbox database.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "כותרת הדף"
                    },
                    "content": {
                        "type": "string",
                        "description": "תוכן הדף"
                    },
                },
                "required": ["title", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_directory",
            "description": "הצג תוכן תיקייה בשרת.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "נתיב לתיקייה"
                    },
                    "depth": {
                        "type": "integer",
                        "description": "עומק רקורסיה. ברירת מחדל: 1"
                    },
                },
                "required": ["path"],
            },
        },
    },
]


# ─── Tool Router ──────────────────────────────────────────────────

async def execute_tool(name: str, args: dict, user_id: str = "0") -> str:
    """Routes tool call to the correct implementation."""
    try:
        if name == "bash_command":
            return await _bash(args["command"], timeout=args.get("timeout", 30))
        elif name == "run_python":
            return await _run_python(args["code"])
        elif name == "web_search":
            return await _web_search(args["query"], args.get("max_results", 5))
        elif name == "read_file":
            return await _read_file(args["path"])
        elif name == "write_file":
            return await _write_file(args["path"], args["content"], args.get("mode", "w"))
        elif name == "fetch_url":
            return await _fetch_url(
                args["url"],
                args.get("method", "GET"),
                args.get("body"),
                args.get("headers", {})
            )
        elif name == "github_api":
            return await _github_api(
                args["endpoint"],
                args.get("method", "GET"),
                args.get("body")
            )
        elif name == "notion_add":
            return await _notion_add(args["title"], args["content"])
        elif name == "list_directory":
            return await _list_dir(args["path"], args.get("depth", 1))
        else:
            return f"[ERROR] Unknown tool: {name}"
    except KeyError as e:
        return f"[ERROR] Missing required argument: {e}"
    except Exception as e:
        return f"[ERROR] {name} failed: {e}"


# ─── Implementations ──────────────────────────────────────────────

async def _bash(command: str, timeout: int = 30) -> str:
    proc = await asyncio.create_subprocess_shell(
        command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        result = out
        if err:
            result += f"\n[STDERR]\n{err}"
        return result[:4000] if result else "(no output)"
    except asyncio.TimeoutError:
        proc.kill()
        return f"[TIMEOUT] Command killed after {timeout}s"


async def _run_python(code: str) -> str:
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False, mode="w", encoding="utf-8") as f:
        f.write(code)
        fname = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", fname,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        out = stdout.decode(errors="replace").strip()
        err = stderr.decode(errors="replace").strip()
        result = out
        if err:
            result += f"\n[STDERR]\n{err}"
        return result[:4000] if result else "(no output)"
    except asyncio.TimeoutError:
        return "[TIMEOUT] Python script took more than 30 seconds"
    finally:
        try:
            os.unlink(fname)
        except Exception:
            pass


async def _web_search(query: str, max_results: int = 5) -> str:
    try:
        from duckduckgo_search import DDGS
        results = DDGS().text(query, max_results=max_results)
        if not results:
            return "לא נמצאו תוצאות לשאילתה זו."
        lines = []
        for r in results:
            title = r.get("title", "ללא כותרת")
            body  = r.get("body", "")
            href  = r.get("href", "")
            lines.append(f"**{title}**\n{body}\n{href}")
        return "\n\n---\n\n".join(lines)
    except ImportError:
        return "[ERROR] duckduckgo_search לא מותקן. הרץ: pip install duckduckgo-search"
    except Exception as e:
        return f"[ERROR] web_search failed: {e}"


async def _read_file(path: str) -> str:
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(8000)
        return content if content else "(קובץ ריק)"
    except FileNotFoundError:
        return f"[ERROR] קובץ לא נמצא: {path}"
    except PermissionError:
        return f"[ERROR] אין הרשאת קריאה: {path}"
    except Exception as e:
        return f"[ERROR] {e}"


async def _write_file(path: str, content: str, mode: str = "w") -> str:
    try:
        os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
        with open(path, mode, encoding="utf-8") as f:
            f.write(content)
        return f"נכתב בהצלחה: {path} ({len(content)} תווים)"
    except PermissionError:
        return f"[ERROR] אין הרשאת כתיבה: {path}"
    except Exception as e:
        return f"[ERROR] {e}"


async def _fetch_url(url: str, method: str = "GET", body=None, headers=None) -> str:
    try:
        async with aiohttp.ClientSession() as session:
            kwargs = {
                "headers": headers or {},
                "timeout": aiohttp.ClientTimeout(total=20)
            }
            if method.upper() == "POST" and body:
                kwargs["json"] = body
            async with session.request(method.upper(), url, **kwargs) as resp:
                text = await resp.text()
                return f"[HTTP {resp.status}]\n{text[:8000]}"
    except aiohttp.ClientConnectorError:
        return f"[ERROR] לא ניתן להתחבר ל-{url}"
    except asyncio.TimeoutError:
        return f"[ERROR] Timeout בחיבור ל-{url}"
    except Exception as e:
        return f"[ERROR] fetch_url: {e}"


async def _github_api(endpoint: str, method: str = "GET", body=None) -> str:
    if not GITHUB_TOKEN:
        return "[ERROR] GITHUB_TOKEN לא מוגדר ב-.env"
    headers = {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }
    url = f"https://api.github.com{endpoint}"
    return await _fetch_url(url, method, body, headers)


async def _notion_add(title: str, content: str) -> str:
    if not NOTION_TOKEN:
        return "[ERROR] NOTION_TOKEN לא מוגדר ב-.env"
    if not NOTION_DB_ID:
        return "[ERROR] NOTION_INBOX_DB לא מוגדר ב-.env"
    url = "https://api.notion.com/v1/pages"
    body = {
        "parent": {"database_id": NOTION_DB_ID},
        "properties": {
            "Name": {"title": [{"text": {"content": title}}]}
        },
        "children": [{
            "object": "block",
            "type": "paragraph",
            "paragraph": {
                "rich_text": [{"text": {"content": content[:2000]}}]
            }
        }],
    }
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    return await _fetch_url(url, "POST", body, headers)


async def _list_dir(path: str, depth: int = 1) -> str:
    return await _bash(f"find {path} -maxdepth {depth} | sort | head -100")
```

שמור ואמת:
```bash
python -c "from tools import TOOLS_SCHEMA, execute_tool; print('tools.py OK')"
```

☑️ **Checkpoint**: רואה "tools.py OK"

---

## שלב 5 — כתיבת gateway/memory.py

```bash
nano /home/ubuntu/ai-system/gateway/memory.py
```

הדבק:

```python
# gateway/memory.py
# Memory management: short-term context + long-term semantic memory

import asyncio
import json
import os
import time
from typing import List, Optional

import aiohttp
import redis.asyncio as aioredis

REDIS_URL       = os.getenv("REDIS_URL", "redis://localhost:6379")
EMBED_MIN_SCORE = 0.40
EMBED_MAX_ITEMS = 200
CTX_MAX_MSGS    = 20
CTX_MAX_CHARS   = 4000

# סיבוב בין Gemini keys לטעינת embeddings
_GEMINI_KEYS = [
    os.getenv(f"GEMINI_KEY_{i}", "")
    for i in range(1, 6)
]
_GEMINI_KEYS = [k for k in _GEMINI_KEYS if k]  # הסר ריקים
_gemini_idx  = 0


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
        "content": {"parts": [{"text": text[:2000]}]}
    }
    try:
        async with aiohttp.ClientSession() as s:
            async with s.post(
                url, json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
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
    na  = sum(x * x for x in a) ** 0.5
    nb  = sum(y * y for y in b) ** 0.5
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
        raw  = await r.get(f"ctx:{user_id}:{channel_id}")
        msgs = json.loads(raw) if raw else []
        msgs.append({"role": "user",      "content": user_msg})
        msgs.append({"role": "assistant", "content": bot_reply})
        # trim to max messages
        msgs = msgs[-CTX_MAX_MSGS:]
        # trim to max chars
        total = sum(len(m["content"]) for m in msgs)
        while total > CTX_MAX_CHARS and len(msgs) > 2:
            removed = msgs.pop(0)
            total  -= len(removed["content"])
        await r.set(
            f"ctx:{user_id}:{channel_id}",
            json.dumps(msgs, ensure_ascii=False)
        )
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
                item  = json.loads(raw)
                embed = item.get("embed")
                if not embed:
                    continue
                score = _cosine(q_embed, embed)
                if score >= EMBED_MIN_SCORE:
                    scores.append({
                        "text":      item["text"],
                        "score":     round(score, 3),
                        "agent":     item.get("agent", "?"),
                        "timestamp": item.get("ts", 0),
                    })
            except Exception:
                continue

        scores.sort(key=lambda x: -x["score"])
        return scores[:top_k]

    except Exception:
        return []
    finally:
        await r.aclose()


async def save_long_memory_async(user_id: str, user_msg: str, bot_reply: str, agent: str):
    """Save interaction to long-term semantic memory (async, non-blocking)."""
    text  = f"User: {user_msg}\nAgent({agent}): {bot_reply}"[:500]
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

        idx  = int(time.time() * 1000)
        key  = f"longmem:{user_id}:{idx}"
        data = json.dumps(
            {"text": text, "embed": embed, "agent": agent, "ts": idx},
            ensure_ascii=False
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
        raw   = await r.get(f"mem:{user_id}")
        stats = json.loads(raw) if raw else {
            "username":      username,
            "request_count": 0,
            "agent_counts":  {},
            "total_duration": 0.0,
        }
        stats["username"]                     = username
        stats["request_count"]                = stats.get("request_count", 0) + 1
        stats["agent_counts"][agent]          = stats["agent_counts"].get(agent, 0) + 1
        stats["total_duration"]               = stats.get("total_duration", 0.0) + duration
        await r.set(f"mem:{user_id}", json.dumps(stats, ensure_ascii=False))
    except Exception:
        pass
    finally:
        await r.aclose()
```

שמור ואמת:
```bash
python -c "from memory import load_context, save_context; print('memory.py OK')"
```

☑️ **Checkpoint**: רואה "memory.py OK"

---

## שלב 6 — כתיבת gateway/main.py

**מחק קודם את הישן:**
```bash
cp /home/ubuntu/ai-system/gateway/main.py /home/ubuntu/ai-system/gateway/main.py.v2.bak
```

```bash
nano /home/ubuntu/ai-system/gateway/main.py
```

הדבק:

```python
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
from tools  import TOOLS_SCHEMA, execute_tool
from memory import (
    load_context, save_context,
    load_long_memory, save_long_memory_async,
    get_user_stats, update_user_stats,
)

app = FastAPI(title="OpenClaw Gateway v3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

LITELLM_BASE = "http://localhost:4000"
LITELLM_KEY  = os.getenv("LITELLM_MASTER_KEY", "sk-litellm-master-2026")
MAX_ITER     = int(os.getenv("MAX_AGENT_ITERATIONS", "12"))


# ─── Request models ───────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id:      str
    message:      str
    agent:        str = "main"
    task_type:    str = "default"
    channel_id:   str = "0"
    username:     str = "user"
    project:      Optional[str] = None
    callback_url: Optional[str] = None

class OrchRequest(BaseModel):
    user_id:    str
    task:       str
    agents:     Optional[list] = None
    channel_id: str = "0"

class MemoryRequest(BaseModel):
    user_id: str
    text:    str
    agent:   str = "main"

class RecallRequest(BaseModel):
    user_id: str
    query:   str
    top_k:   int = 5


# ─── Core: single LLM call ───────────────────────────────────────

async def llm_call(
    messages:  list,
    task_type: str = "default",
    use_tools: bool = True,
) -> dict:
    """Single LLM call via LiteLLM proxy. Tries models in order."""
    models  = TASK_MODELS.get(task_type, TASK_MODELS["default"])
    payload = {
        "messages":    messages,
        "max_tokens":  4096,
        "temperature": 0.4,
    }
    if use_tools:
        payload["tools"]       = TOOLS_SCHEMA
        payload["tool_choice"] = "auto"

    headers = {
        "Authorization": f"Bearer {LITELLM_KEY}",
        "Content-Type":  "application/json",
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
                        text       = await resp.text()
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
    messages:     list,
    task_type:    str = "default",
    callback_url: Optional[str] = None,
    user_id:      str = "0",
) -> dict:
    """
    Full agentic loop:
    LLM → tool_calls? → execute tools → add results → repeat → final answer
    """
    tool_log   = []
    iteration  = 0
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

        resp        = await llm_call(messages, task_type=task_type, use_tools=True)
        model_used  = resp.get("_model_used", "unknown")
        choice      = resp["choices"][0]
        msg_obj     = choice["message"]
        finish      = choice.get("finish_reason", "stop")

        # No tool calls → this is the final answer
        if not msg_obj.get("tool_calls") or finish == "stop":
            return {
                "response":   msg_obj.get("content") or "",
                "model":      model_used,
                "iterations": iteration,
                "tool_log":   tool_log,
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

            await notify(f"🔧 **{fn_name}**(`{json.dumps(fn_args, ensure_ascii=False)[:100]}`)")
            print(f"[TOOL iter={iteration}] {fn_name}({fn_args})")

            t0     = time.time()
            result = await execute_tool(fn_name, fn_args, user_id=user_id)
            elapsed = round(time.time() - t0, 2)

            tool_log.append({
                "tool":    fn_name,
                "args":    fn_args,
                "result":  str(result)[:500],
                "elapsed": elapsed,
            })

            # Feed result back to LLM
            messages.append({
                "role":         "tool",
                "tool_call_id": tc["id"],
                "content":      str(result),
            })

    # Reached max iterations
    return {
        "response":   f"⚠️ הגעתי למגבלת {MAX_ITER} צעדים. נסה לפרק את המשימה.",
        "model":      model_used,
        "iterations": iteration,
        "tool_log":   tool_log,
    }


# ─── Endpoints ───────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    t0 = time.time()

    context  = await load_context(req.user_id, req.channel_id)
    memories = await load_long_memory(req.user_id, req.message)

    base_sys = AGENT_SYSTEMS.get(req.agent, AGENT_SYSTEMS["main"])

    if memories:
        mem_text  = "\n".join([f"- {m['text']}" for m in memories])
        base_sys += f"\n\n## זיכרון ארוך-טווח רלוונטי:\n{mem_text}"

    if req.project:
        base_sys += f"\n\n## פרויקט נוכחי: {req.project}"

    if re.search(
        r'(password|סיסמ|api.?key|token|secret|smtp|bearer|sk-|ghp_)',
        req.message, re.IGNORECASE
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
    asyncio.create_task(save_long_memory_async(
        req.user_id, req.message, result["response"], req.agent
    ))
    asyncio.create_task(update_user_stats(
        req.user_id, req.username, req.agent, time.time() - t0
    ))

    result["duration"] = round(time.time() - t0, 2)
    return result


@app.post("/orchestrate")
async def orchestrate(req: OrchRequest):
    t0 = time.time()

    # Step 1: orchestrator decides which agents to use
    sel_msgs = [
        {"role": "system", "content": AGENT_SYSTEMS["orchestrator"]},
        {"role": "user",   "content": (
            f"משימה: {req.task}\n\n"
            "אילו סוכנים נדרשים? ענה רק בשמות מופרדים בפסיק מתוך: "
            "coder, researcher, analyzer. לדוגמה: coder,researcher"
        )},
    ]
    sel_resp = await llm_call(sel_msgs, use_tools=False)
    raw_sel  = sel_resp["choices"][0]["message"]["content"].lower()
    selected = req.agents or [
        a.strip()
        for a in raw_sel.split(",")
        if a.strip() in AGENT_SYSTEMS
    ]
    if not selected:
        selected = ["coder", "researcher"]

    # Step 2: run selected agents in parallel
    async def run_one(agent_id: str) -> dict:
        msgs = [
            {"role": "system", "content": AGENT_SYSTEMS.get(agent_id, AGENT_SYSTEMS["main"])},
            {"role": "user",   "content": req.task},
        ]
        return await agentic_loop(msgs, task_type="default", user_id=req.user_id)

    results_list  = await asyncio.gather(*[run_one(a) for a in selected])
    agent_results = dict(zip(selected, results_list))

    # Step 3: critic reviews all agent responses
    combined = "\n\n".join([
        f"### {a.upper()}\n{r['response']}"
        for a, r in agent_results.items()
    ])
    crit_resp = await llm_call([
        {"role": "system", "content": AGENT_SYSTEMS["critic"]},
        {"role": "user",   "content": f"בדוק ושפר:\n\n{combined}"},
    ], use_tools=False)
    critic_text = crit_resp["choices"][0]["message"]["content"]

    # Step 4: orchestrator synthesizes final answer
    synth_resp = await llm_call([
        {"role": "system", "content": AGENT_SYSTEMS["orchestrator"]},
        {"role": "user",   "content": (
            f"משימה מקורית: {req.task}\n\n"
            f"תגובות סוכנים:\n{combined}\n\n"
            f"ביקורת:\n{critic_text}\n\n"
            "כתוב תשובה סופית מסוכמת."
        )},
    ], use_tools=False)
    synthesis = synth_resp["choices"][0]["message"]["content"]

    return {
        "plan":            f"Selected: {', '.join(selected)}",
        "agents_used":     selected,
        "agent_responses": {
            a: {"response": r["response"], "tool_log": r["tool_log"]}
            for a, r in agent_results.items()
        },
        "critic":          {"response": critic_text},
        "synthesis":       synthesis,
        "synthesis_model": synth_resp.get("_model_used", "unknown"),
        "duration":        round(time.time() - t0, 2),
    }


@app.post("/debate")
async def debate(req: OrchRequest):
    t0 = time.time()
    pro_resp, con_resp = await asyncio.gather(
        llm_call([
            {"role": "system", "content": AGENT_SYSTEMS["researcher"]},
            {"role": "user",   "content": f"טען בעד: {req.task}"},
        ], use_tools=False),
        llm_call([
            {"role": "system", "content": AGENT_SYSTEMS["analyzer"]},
            {"role": "user",   "content": f"טען נגד: {req.task}"},
        ], use_tools=False),
    )
    pro_text = pro_resp["choices"][0]["message"]["content"]
    con_text = con_resp["choices"][0]["message"]["content"]

    verdict_resp = await llm_call([
        {"role": "system", "content": AGENT_SYSTEMS["critic"]},
        {"role": "user",   "content": f"בעד:\n{pro_text}\n\nנגד:\n{con_text}\n\nפסוק:"},
    ], use_tools=False)

    return {
        "pro":      {"response": pro_text},
        "con":      {"response": con_text},
        "verdict":  {"response": verdict_resp["choices"][0]["message"]["content"]},
        "duration": round(time.time() - t0, 2),
    }


@app.post("/swarm")
async def swarm(req: OrchRequest):
    t0         = time.time()
    agent_ids  = ["researcher", "coder", "analyzer", "critic"]
    results    = await asyncio.gather(*[
        agentic_loop(
            [
                {"role": "system", "content": AGENT_SYSTEMS[a]},
                {"role": "user",   "content": req.task},
            ],
            user_id=req.user_id,
        )
        for a in agent_ids
    ])
    agent_map  = dict(zip(agent_ids, results))
    all_text   = "\n\n".join([f"### {a}\n{r['response']}" for a, r in agent_map.items()])

    synth_resp = await llm_call([
        {"role": "system", "content": AGENT_SYSTEMS["orchestrator"]},
        {"role": "user",   "content": f"סנתז:\n\n{all_text}"},
    ], use_tools=False)

    return {
        "agents":    {a: {"response": r["response"]} for a, r in agent_map.items()},
        "synthesis": synth_resp["choices"][0]["message"]["content"],
        "duration":  round(time.time() - t0, 2),
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
    r    = aioredis.from_url(REDIS_URL)
    keys = await r.keys(f"ctx:{user_id}:*")
    if keys:
        await r.delete(*keys)
    await r.aclose()
    return {"deleted": len(keys)}


@app.get("/health")
async def health():
    redis_ok = False
    try:
        r = aioredis.from_url(REDIS_URL)
        await r.ping()
        await r.aclose()
        redis_ok = True
    except Exception:
        pass
    return {
        "status":         "ok",
        "version":        "3.0",
        "redis":          "ok" if redis_ok else "error",
        "agents":         list(AGENT_SYSTEMS.keys()),
        "max_iterations": MAX_ITER,
    }


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=4001, reload=False, workers=1)
```

שמור ואמת:
```bash
python -c "
from agents import AGENT_SYSTEMS
from tools  import TOOLS_SCHEMA
from memory import load_context
import main
print('main.py OK')
"
```

☑️ **Checkpoint**: רואה "main.py OK"

---

## שלב 7 — כתיבת discord-bot/ui_helpers.py

```bash
nano /home/ubuntu/ai-system/discord-bot/ui_helpers.py
```

הדבק:

```python
# discord-bot/ui_helpers.py
# Embed builders, progress bars, and interactive views

import os
import aiohttp
import discord

GATEWAY_URL = os.getenv("GATEWAY_URL", "http://localhost:4001")

# צבעים לפי סוכן (hex)
COLORS = {
    "main":         0x5865F2,
    "coder":        0x57F287,
    "researcher":   0xFEE75C,
    "analyzer":     0xEB459E,
    "orchestrator": 0xED4245,
    "critic":       0xFFA500,
    "kilo":         0x2C2F33,
    "tool":         0x99AAB5,
    "error":        0xED4245,
    "success":      0x57F287,
    "memory":       0x9B59B6,
}

AGENT_EMOJI = {
    "main":         "🤖",
    "coder":        "💻",
    "researcher":   "🔍",
    "analyzer":     "📊",
    "orchestrator": "🧭",
    "critic":       "⚖️",
}

FRAMES = [
    "⬜⬜⬜⬜⬜",
    "🟦⬜⬜⬜⬜",
    "🟦🟦⬜⬜⬜",
    "🟦🟦🟦⬜⬜",
    "🟦🟦🟦🟦⬜",
    "🟦🟦🟦🟦🟦",
]


def make_thinking_embed(agent: str, frame: str = FRAMES[0]) -> discord.Embed:
    emoji = AGENT_EMOJI.get(agent, "🤖")
    e = discord.Embed(
        title=f"{emoji} {agent.capitalize()} חושב...",
        description=frame,
        color=COLORS.get(agent, COLORS["main"]),
    )
    e.set_footer(text="OpenClaw v3 • agentic loop")
    return e


def make_response_embed(
    response:   str,
    agent:      str,
    model:      str,
    elapsed:    float,
    iterations: int,
    project:    str | None,
) -> discord.Embed:
    emoji   = AGENT_EMOJI.get(agent, "🤖")
    content = response[:3800]
    if len(response) > 3800:
        content += "\n\n*(תשובה ארוכה — קוצרה)*"

    e = discord.Embed(
        description=content,
        color=COLORS.get(agent, COLORS["main"]),
    )
    e.set_author(name=f"{emoji} {agent.capitalize()}")

    footer_parts = [f"🧠 {model}", f"⏱ {elapsed}s"]
    if iterations > 1:
        footer_parts.append(f"🔄 {iterations} צעדים")
    if project:
        footer_parts.append(f"📁 {project}")
    e.set_footer(text="  •  ".join(footer_parts))
    return e


def make_tool_log_embed(tool_log: list) -> discord.Embed:
    e = discord.Embed(
        title="🔧 Tool Execution Log",
        color=COLORS["tool"],
    )
    for entry in tool_log[:8]:
        name    = entry.get("tool", "?")
        elapsed = entry.get("elapsed", 0)
        result  = str(entry.get("result", ""))[:200]
        e.add_field(
            name=f"`{name}` — {elapsed}s",
            value=f"```\n{result}\n```",
            inline=False,
        )
    return e


def make_error_embed(error: str) -> discord.Embed:
    return discord.Embed(
        title="❌ שגיאה",
        description=f"```\n{error[:1500]}\n```",
        color=COLORS["error"],
    )


def make_kilo_embed(status: str, task: str) -> discord.Embed:
    e = discord.Embed(
        title="⚡ Kilo CLI",
        description=status,
        color=COLORS["kilo"],
    )
    e.add_field(name="משימה", value=f"`{task[:200]}`", inline=False)
    e.set_footer(text="kilo run --auto")
    return e


# ─── Interactive Views ────────────────────────────────────────────

class ResponseView(discord.ui.View):
    def __init__(self, original_message: str, agent: str,
                 channel_id: str, user_id: str):
        super().__init__(timeout=300)
        self.original_message = original_message
        self.agent            = agent
        self.channel_id       = channel_id
        self.user_id          = user_id

    @discord.ui.button(label="🔄 שאל שוב", style=discord.ButtonStyle.secondary)
    async def retry(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)
        try:
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    f"{GATEWAY_URL}/chat",
                    json={
                        "user_id":    self.user_id,
                        "message":    self.original_message,
                        "agent":      self.agent,
                        "channel_id": self.channel_id,
                        "username":   interaction.user.display_name,
                    },
                    timeout=aiohttp.ClientTimeout(total=180),
                ) as resp:
                    result = await resp.json()

            embed = make_response_embed(
                result["response"], self.agent,
                result.get("model", "?"),
                result.get("duration", 0),
                result.get("iterations", 1),
                None,
            )
            view = ResponseView(
                self.original_message, self.agent,
                self.channel_id, self.user_id,
            )
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await interaction.followup.send(embed=make_error_embed(str(e)))

    @discord.ui.button(label="🔀 החלף סוכן", style=discord.ButtonStyle.secondary)
    async def switch_agent(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = AgentSelectView(
            self.original_message, self.channel_id, self.user_id
        )
        await interaction.response.send_message("בחר סוכן:", view=view, ephemeral=True)

    @discord.ui.button(label="🗑️ מחק", style=discord.ButtonStyle.danger)
    async def delete(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.message.delete()
        await interaction.response.send_message("נמחק ✓", ephemeral=True, delete_after=2)


class AgentSelectView(discord.ui.View):
    def __init__(self, original_message: str, channel_id: str, user_id: str):
        super().__init__(timeout=60)
        self.add_item(AgentSelect(original_message, channel_id, user_id))


class AgentSelect(discord.ui.Select):
    def __init__(self, original_message: str, channel_id: str, user_id: str):
        self.original_message = original_message
        self.channel_id       = channel_id
        self.user_id          = user_id
        options = [
            discord.SelectOption(label="🤖 Main",       value="main",        description="עוזר כללי"),
            discord.SelectOption(label="💻 Coder",      value="coder",       description="מומחה קוד"),
            discord.SelectOption(label="🔍 Researcher", value="researcher",  description="חוקר מידע"),
            discord.SelectOption(label="📊 Analyzer",   value="analyzer",    description="ניתוח אסטרטגי"),
            discord.SelectOption(label="🧭 Orchestrate",value="orchestrate", description="רב-סוכנים"),
        ]
        super().__init__(placeholder="בחר סוכן...", options=options)

    async def callback(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        agent = self.values[0]
        try:
            if agent == "orchestrate":
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{GATEWAY_URL}/orchestrate",
                        json={
                            "user_id":    self.user_id,
                            "task":       self.original_message,
                            "channel_id": self.channel_id,
                        },
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as resp:
                        result   = await resp.json()
                response   = result.get("synthesis", "")
                model      = result.get("synthesis_model", "?")
                iterations = 1
                duration   = result.get("duration", 0)
            else:
                async with aiohttp.ClientSession() as s:
                    async with s.post(
                        f"{GATEWAY_URL}/chat",
                        json={
                            "user_id":    self.user_id,
                            "message":    self.original_message,
                            "agent":      agent,
                            "channel_id": self.channel_id,
                            "username":   interaction.user.display_name,
                        },
                        timeout=aiohttp.ClientTimeout(total=180),
                    ) as resp:
                        result = await resp.json()
                response   = result.get("response", "")
                model      = result.get("model", "?")
                iterations = result.get("iterations", 1)
                duration   = result.get("duration", 0)

            embed = make_response_embed(response, agent, model, duration, iterations, None)
            view  = ResponseView(self.original_message, agent, self.channel_id, self.user_id)
            await interaction.followup.send(embed=embed, view=view)
        except Exception as e:
            await interaction.followup.send(embed=make_error_embed(str(e)))


class KiloControlView(discord.ui.View):
    @discord.ui.button(label="✅ סגור", style=discord.ButtonStyle.success)
    async def close(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_message("✓", ephemeral=True, delete_after=1)
        self.stop()
```

שמור ואמת:
```bash
cd /home/ubuntu/ai-system/discord-bot
source ../venv/bin/activate
python -c "from ui_helpers import make_thinking_embed, ResponseView; print('ui_helpers.py OK')"
```

☑️ **Checkpoint**: רואה "ui_helpers.py OK"

---

## שלב 8 — כתיבת discord-bot/project_manager.py

```bash
nano /home/ubuntu/ai-system/discord-bot/project_manager.py
```

הדבק:

```python
# discord-bot/project_manager.py
# Discord Category/Channel management for project workspaces

import json
import os
import discord
import redis.asyncio as aioredis

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ערוצי ברירת מחדל לכל פרויקט חדש
DEFAULT_CHANNELS = [
    ("main",     "main",       "ערוץ ראשי לשיחות כלליות"),
    ("code",     "coder",      "קוד ופיתוח — agent: coder"),
    ("research", "researcher", "מחקר ותיעוד — agent: researcher"),
]


class ProjectManager:
    def __init__(self):
        self.redis = None

    async def init(self, guild: discord.Guild):
        self.redis = aioredis.from_url(REDIS_URL)
        print(f"[PM] Ready for guild: {guild.name}")

    async def create_project(self, guild: discord.Guild, project_name: str) -> dict:
        """
        Creates a Discord Category with 3 default channels.
        Returns dict with category_id and list of channel_ids.
        """
        # Create the category
        category = await guild.create_category(
            name=project_name,
            reason=f"OpenClaw: new project {project_name}",
        )

        channel_ids = []
        for suffix, agent, topic in DEFAULT_CHANNELS:
            # Channel name format: projectname-suffix (lowercase, no spaces)
            ch_name = f"{project_name.lower().replace(' ', '-')}-{suffix}"
            ch = await guild.create_text_channel(
                name=ch_name,
                category=category,
                topic=topic,
            )
            channel_ids.append(ch.id)
            if self.redis:
                await self.redis.set(
                    f"channel_meta:{ch.id}",
                    json.dumps({
                        "project": project_name,
                        "agent":   agent,
                        "topic":   topic,
                    })
                )

        return {
            "category_id": category.id,
            "channel_ids": channel_ids,
            "project":     project_name,
        }

    async def add_channel_to_project(
        self,
        guild:        discord.Guild,
        project_name: str,
        channel_name: str,
        agent:        str = "main",
    ) -> dict:
        """Adds a channel to an existing project category."""
        # Find existing category
        category = discord.utils.get(guild.categories, name=project_name)
        if not category:
            category = await guild.create_category(name=project_name)

        full_name = f"{project_name.lower().replace(' ', '-')}-{channel_name.lower()}"
        ch = await guild.create_text_channel(
            name=full_name,
            category=category,
        )
        if self.redis:
            await self.redis.set(
                f"channel_meta:{ch.id}",
                json.dumps({"project": project_name, "agent": agent})
            )
        return {"channel_id": ch.id}

    async def get_channel_meta(self, channel_id: int) -> dict:
        """Returns channel metadata (project, agent) from Redis."""
        if not self.redis:
            return {}
        try:
            raw = await self.redis.get(f"channel_meta:{channel_id}")
            return json.loads(raw) if raw else {}
        except Exception:
            return {}
```

שמור ואמת:
```bash
python -c "from project_manager import ProjectManager; print('project_manager.py OK')"
```

☑️ **Checkpoint**: רואה "project_manager.py OK"

---

## שלב 9 — כתיבת discord-bot/kilo_bridge.py

```bash
nano /home/ubuntu/ai-system/discord-bot/kilo_bridge.py
```

הדבק:

```python
# discord-bot/kilo_bridge.py
# Bridge between Discord #kilo-code channel and Kilo CLI

import asyncio
import json
import os
import shutil
from typing import Callable, Awaitable, Optional

KILO_BIN  = os.getenv("KILO_BIN", "")
WORK_DIR  = os.getenv("KILO_WORK_DIR", "/home/ubuntu")


class KiloBridge:
    def __init__(self):
        self.available = False
        self.kilo_path: Optional[str] = None

    async def init(self):
        """Checks if kilo CLI is installed on the server."""
        # Try env var first, then PATH
        candidate = KILO_BIN or shutil.which("kilo") or shutil.which("kilocode")
        if candidate and os.path.isfile(candidate):
            self.available = True
            self.kilo_path = candidate
            print(f"[Kilo] ✅ Found at {candidate}")
        else:
            self.available = False
            print("[Kilo] ⚠️  kilo CLI not found. Channel #kilo-code will show error.")

    async def run_task(
        self,
        task:      str,
        callback:  Callable[[str, str], Awaitable[None]],
        work_dir:  str = WORK_DIR,
        timeout:   int = 300,
    ):
        """
        Runs: kilo run --auto "{task}" --format json
        Fires callback(event_type, data) as output arrives.
        event_type: "text" | "done" | "error"
        """
        if not self.available:
            await callback(
                "error",
                "Kilo CLI לא מותקן על השרת.\n"
                "להתקנה: `npm install -g kilocode`\n"
                "לאחר ההתקנה הפעל מחדש: `sudo systemctl restart discord-bot`"
            )
            return

        cmd = [self.kilo_path, "run", "--auto", task, "--format", "json"]
        output_lines = []

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=work_dir,
            )

            async def read_stdout():
                async for raw_line in proc.stdout:
                    line = raw_line.decode(errors="replace").strip()
                    if not line:
                        continue
                    output_lines.append(line)

                    # Try to parse as JSON event from kilo
                    try:
                        ev      = json.loads(line)
                        ev_type = ev.get("type", "")

                        if ev_type == "assistant":
                            content = ev.get("content", "")
                            if isinstance(content, list):
                                for block in content:
                                    if block.get("type") == "text":
                                        await callback("text", block.get("text", ""))
                            elif isinstance(content, str) and content:
                                await callback("text", content)

                        elif ev_type == "tool_use":
                            tool_name = ev.get("name", "?")
                            await callback("text", f"🔧 מפעיל: `{tool_name}`...")

                        elif ev_type == "error":
                            await callback("error", ev.get("message", str(ev)))

                    except json.JSONDecodeError:
                        # Plain text line — send as-is if meaningful
                        if len(line) > 5:
                            await callback("text", line)

            try:
                await asyncio.wait_for(
                    asyncio.gather(read_stdout(), proc.wait()),
                    timeout=timeout,
                )
                summary = "\n".join(output_lines[-40:])
                await callback("done", summary)

            except asyncio.TimeoutError:
                proc.kill()
                await callback("error", f"⏱ Timeout: הפעולה נמשכה יותר מ-{timeout} שניות")

        except Exception as e:
            await callback("error", f"שגיאה בהפעלת Kilo: {e}")
```

שמור ואמת:
```bash
python -c "from kilo_bridge import KiloBridge; print('kilo_bridge.py OK')"
```

☑️ **Checkpoint**: רואה "kilo_bridge.py OK"

---

## שלב 10 — כתיבת discord-bot/bot.py

**גיבוי ישן:**
```bash
cp /home/ubuntu/ai-system/discord-bot/bot.py /home/ubuntu/ai-system/discord-bot/bot.py.v2.bak
```

```bash
nano /home/ubuntu/ai-system/discord-bot/bot.py
```

הדבק:

```python
# discord-bot/bot.py — v3.0

import asyncio
import json
import os
import time
from typing import Optional

import aiohttp
import discord
from discord import app_commands
from discord.ext import commands

from ui_helpers      import (
    make_thinking_embed, make_response_embed, make_tool_log_embed,
    make_error_embed, make_kilo_embed, COLORS,
    ResponseView, AgentSelectView, KiloControlView,
)
from project_manager import ProjectManager
from kilo_bridge     import KiloBridge

# ─── Config ───────────────────────────────────────────────────────
DISCORD_TOKEN   = os.environ["DISCORD_TOKEN"]
GUILD_ID        = int(os.environ["DISCORD_GUILD_ID"])
GATEWAY_URL     = os.getenv("GATEWAY_URL", "http://localhost:4001")

# ערוצים עם טיפול מיוחד (לא נשלחים ל-agentic loop הרגיל)
SPECIAL_CHANNELS = {"ai-admin", "kilo-code"}

# מילות מפתח בשם ערוץ → agent
CHANNEL_AGENTS = {
    "code":     "coder",
    "coding":   "coder",
    "backend":  "coder",
    "frontend": "coder",
    "research": "researcher",
    "knowledge":"researcher",
    "analyze":  "analyzer",
    "analysis": "analyzer",
}

# ─── Setup ────────────────────────────────────────────────────────
intents                  = discord.Intents.default()
intents.message_content  = True
intents.guilds           = True
intents.guild_messages   = True
intents.dm_messages      = True
intents.members          = True

bot  = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree
pm   = ProjectManager()
kb   = KiloBridge()


# ─── Helpers ──────────────────────────────────────────────────────

async def call_gateway(endpoint: str, payload: dict) -> dict:
    """POST to gateway and return JSON response."""
    async with aiohttp.ClientSession() as s:
        async with s.post(
            f"{GATEWAY_URL}{endpoint}",
            json=payload,
            timeout=aiohttp.ClientTimeout(total=180),
        ) as resp:
            if resp.status == 200:
                return await resp.json()
            text = await resp.text()
            raise Exception(f"Gateway {resp.status}: {text[:300]}")


def get_agent_for_channel(channel) -> str:
    """Determines which agent to use based on channel name."""
    name = getattr(channel, "name", "").lower()
    for keyword, agent in CHANNEL_AGENTS.items():
        if keyword in name:
            return agent
    return "main"


def get_project_for_channel(channel) -> Optional[str]:
    """Returns project name from category, or None."""
    if hasattr(channel, "category") and channel.category:
        cat = channel.category.name.lower()
        if cat not in ("tools", "general", "text channels", "voice channels"):
            return channel.category.name
    return None


# ─── Core: agentic message processing ─────────────────────────────

async def process_message(message: discord.Message, override_agent: str = None):
    """
    Full agentic pipeline:
    1. Show animated thinking embed
    2. Call gateway agentic loop
    3. Render response + tool log
    """
    channel = message.channel
    uid     = str(message.author.id)
    cid     = str(channel.id)
    agent   = override_agent or get_agent_for_channel(channel)
    project = get_project_for_channel(channel)

    # 1. Show thinking embed
    status_msg = await channel.send(embed=make_thinking_embed(agent))

    # 2. Animated progress bar while waiting
    stop_evt  = asyncio.Event()
    frame_idx = [0]

    async def animate():
        import ui_helpers
        while not stop_evt.is_set():
            await asyncio.sleep(2.5)
            if stop_evt.is_set():
                break
            frame_idx[0] = (frame_idx[0] + 1) % len(ui_helpers.FRAMES)
            try:
                await status_msg.edit(
                    embed=make_thinking_embed(agent, ui_helpers.FRAMES[frame_idx[0]])
                )
            except Exception:
                break

    anim_task = asyncio.create_task(animate())

    # 3. Call gateway
    t0      = time.time()
    result  = None
    error   = None
    try:
        result = await call_gateway("/chat", {
            "user_id":    uid,
            "message":    message.content,
            "agent":      agent,
            "task_type":  "code" if agent == "coder" else "default",
            "channel_id": cid,
            "username":   message.author.display_name,
            "project":    project,
        })
    except Exception as e:
        error = str(e)
    finally:
        stop_evt.set()
        anim_task.cancel()

    # 4. Render result
    if error:
        await status_msg.edit(embed=make_error_embed(error))
        return

    response   = result.get("response", "")
    model      = result.get("model", "?")
    iterations = result.get("iterations", 1)
    tool_log   = result.get("tool_log", [])
    elapsed    = round(time.time() - t0, 2)

    resp_embed = make_response_embed(response, agent, model, elapsed, iterations, project)
    view       = ResponseView(
        original_message=message.content,
        agent=agent,
        channel_id=cid,
        user_id=uid,
    )
    await status_msg.edit(embed=resp_embed, view=view)

    if tool_log:
        await channel.send(embed=make_tool_log_embed(tool_log))


# ─── on_message ───────────────────────────────────────────────────

@bot.event
async def on_message(message: discord.Message):
    # Ignore bots
    if message.author.bot:
        return

    # Let commands through
    if message.content.startswith("/") or message.content.startswith("!"):
        await bot.process_commands(message)
        return

    channel_name = getattr(message.channel, "name", "dm")

    # DM
    if isinstance(message.channel, discord.DMChannel):
        await process_message(message)
        return

    # Special channels
    if channel_name == "kilo-code":
        await _handle_kilo(message)
        return

    if channel_name == "ai-admin":
        await _handle_admin(message)
        return

    if channel_name == "terminal":
        await _handle_terminal(message)
        return

    # All other channels → full agentic loop
    await process_message(message)


# ─── Special channel handlers ─────────────────────────────────────

async def _handle_kilo(message: discord.Message):
    """Sends message to Kilo CLI and streams output back."""
    task     = message.content.strip()
    if not task:
        return
    channel  = message.channel
    status   = await channel.send(embed=make_kilo_embed("🔄 מפעיל Kilo CLI...", task))
    last_text = [""]

    async def on_event(event_type: str, data: str):
        try:
            if event_type == "text":
                last_text[0] = data
                preview      = data[-600:] if len(data) > 600 else data
                e = make_kilo_embed(f"⚙️ **מעבד...**\n```\n{preview}\n```", task)
                await status.edit(embed=e)
            elif event_type == "done":
                summary = data[-1500:] if len(data) > 1500 else data
                e = make_kilo_embed(f"✅ **הושלם**\n```\n{summary}\n```", task)
                await status.edit(embed=e, view=KiloControlView())
            elif event_type == "error":
                await status.edit(embed=make_error_embed(data))
        except discord.HTTPException:
            pass

    asyncio.create_task(kb.run_task(task, callback=on_event))


async def _handle_terminal(message: discord.Message):
    """Direct bash execution in #terminal channel."""
    cmd = message.content.strip()
    if not cmd:
        return
    wait = await message.channel.send(f"```\n$ {cmd[:100]}\n⏳ מריץ...\n```")
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        out, err = await asyncio.wait_for(proc.communicate(), timeout=30)
        output   = (out.decode(errors="replace") + err.decode(errors="replace")).strip()
        await wait.edit(content=f"```\n$ {cmd[:100]}\n{output[:1800]}\n```")
    except asyncio.TimeoutError:
        proc.kill()
        await wait.edit(content=f"```\n$ {cmd[:100]}\n[TIMEOUT after 30s]\n```")


async def _handle_admin(message: discord.Message):
    """Admin commands + regular agentic chat."""
    text = message.content.strip()
    uid  = str(message.author.id)

    if text.startswith("!reset"):
        async with aiohttp.ClientSession() as s:
            await s.delete(f"{GATEWAY_URL}/memory/{uid}")
        await message.channel.send(f"✅ Context נמחק עבור {message.author.display_name}")
    elif text.startswith("!stats"):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GATEWAY_URL}/memory/{uid}") as resp:
                data = await resp.json()
        await message.channel.send(
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1500]}\n```"
        )
    elif text.startswith("!health"):
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GATEWAY_URL}/health") as resp:
                data = await resp.json()
        await message.channel.send(
            f"```json\n{json.dumps(data, indent=2)}\n```"
        )
    else:
        await process_message(message)


# ─── Slash Commands ────────────────────────────────────────────────

@tree.command(name="main", description="שיחה כללית עם OpenClaw",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה לשאול")
async def cmd_main(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "main")


@tree.command(name="coder", description="קוד — כתיבה, דיבוג, הסבר",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="משימת קוד")
async def cmd_coder(interaction: discord.Interaction, prompt: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "coder", "code")


@tree.command(name="research", description="מחקר עמוק",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה לחקור (אפשר להשאיר ריק לפתיחת טופס)")
async def cmd_research(interaction: discord.Interaction, prompt: str = ""):
    if not prompt:
        await interaction.response.send_modal(ResearchModal())
        return
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "researcher")


@tree.command(name="analyze", description="ניתוח אסטרטגי",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(prompt="מה לנתח (אפשר להשאיר ריק לפתיחת טופס)")
async def cmd_analyze(interaction: discord.Interaction, prompt: str = ""):
    if not prompt:
        await interaction.response.send_modal(AnalyzeModal())
        return
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, prompt, "analyzer", "analysis")


@tree.command(name="orchestrate",
              description="מרובת-סוכנים: auto-select → parallel → critic → synthesis",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task="המשימה (אפשר ריק לטופס)")
async def cmd_orchestrate(interaction: discord.Interaction, task: str = ""):
    if not task:
        await interaction.response.send_modal(OrchModal())
        return
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway("/orchestrate", {
            "user_id":    str(interaction.user.id),
            "task":       task,
            "channel_id": str(interaction.channel_id),
        })
        embed = make_response_embed(
            result["synthesis"], "orchestrator",
            result.get("synthesis_model", "?"),
            result.get("duration", 0), 1,
            get_project_for_channel(interaction.channel),
        )
        embed.add_field(
            name="סוכנים ששימשו",
            value=", ".join(result.get("agents_used", [])),
            inline=True,
        )
        await interaction.followup.send(embed=embed)

        for agent_id, data in result.get("agent_responses", {}).items():
            sub_embed = make_response_embed(
                data["response"], agent_id, "?", 0, 1, None
            )
            await _send_persona(interaction.channel, agent_id, sub_embed)

    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(name="debate", description="דיון: בעד vs נגד",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(topic="נושא הדיון")
async def cmd_debate(interaction: discord.Interaction, topic: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway("/debate", {
            "user_id": str(interaction.user.id),
            "task":    topic,
        })
        embed = discord.Embed(title=f"⚖️ דיון: {topic[:60]}", color=COLORS["critic"])
        embed.add_field(name="✅ בעד",    value=result["pro"]["response"][:500],     inline=False)
        embed.add_field(name="❌ נגד",    value=result["con"]["response"][:500],     inline=False)
        embed.add_field(name="⚖️ פסיקה", value=result["verdict"]["response"][:500], inline=False)
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(name="swarm", description="4 סוכנים מקביל + Critic + synthesis",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task="המשימה")
async def cmd_swarm(interaction: discord.Interaction, task: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await call_gateway("/swarm", {
            "user_id": str(interaction.user.id),
            "task":    task,
        })
        embed = make_response_embed(
            result["synthesis"], "orchestrator", "?",
            result.get("duration", 0), 1, None,
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(name="kilo", description="הרץ משימה ב-Kilo CLI",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(task="המשימה")
async def cmd_kilo(interaction: discord.Interaction, task: str):
    await interaction.response.defer(thinking=True)
    status = await interaction.followup.send(
        embed=make_kilo_embed("🔄 מפעיל Kilo CLI...", task)
    )

    async def on_event(etype: str, data: str):
        try:
            if etype == "done":
                summary = data[-1500:] if len(data) > 1500 else data
                e = make_kilo_embed(f"✅ **הושלם**\n```\n{summary}\n```", task)
                await status.edit(embed=e)
            elif etype == "error":
                await status.edit(embed=make_error_embed(data))
        except Exception:
            pass

    asyncio.create_task(kb.run_task(task, callback=on_event))


@tree.command(name="search", description="חיפוש ברשת",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(query="שאילתת חיפוש")
async def cmd_search(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"חפש ברשת: {query}", "researcher")


@tree.command(name="run", description="הרץ קוד Python",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(code="קוד Python")
async def cmd_run(interaction: discord.Interaction, code: str):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"הרץ:\n```python\n{code}\n```", "coder", "code")


@tree.command(name="recall", description="חפש בזיכרון הארוך-טווח",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(query="מה לחפש")
async def cmd_recall(interaction: discord.Interaction, query: str):
    await interaction.response.defer(thinking=True)
    try:
        result   = await call_gateway("/recall", {
            "user_id": str(interaction.user.id),
            "query":   query,
            "top_k":   5,
        })
        memories = result.get("memories", [])
        if not memories:
            await interaction.followup.send("❌ לא נמצאו זיכרונות רלוונטיים.")
            return
        embed = discord.Embed(title=f"🧠 זיכרונות: {query}", color=COLORS["memory"])
        for m in memories:
            embed.add_field(
                name=f"Score: {m['score']} | {m['agent']}",
                value=m["text"][:300],
                inline=False,
            )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(name="store-memory", description="שמור מידע לזיכרון ארוך-טווח",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(text="מה לשמור")
async def cmd_store(interaction: discord.Interaction, text: str):
    try:
        await call_gateway("/store-memory", {
            "user_id": str(interaction.user.id),
            "text":    text,
            "agent":   "user",
        })
        await interaction.response.send_message(
            f"✅ נשמר בזיכרון: `{text[:100]}`", ephemeral=True
        )
    except Exception as e:
        await interaction.response.send_message(
            embed=make_error_embed(str(e)), ephemeral=True
        )


@tree.command(name="memory", description="סטטיסטיקות שימוש",
              guild=discord.Object(id=GUILD_ID))
async def cmd_memory(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{GATEWAY_URL}/memory/{interaction.user.id}") as resp:
                data = await resp.json()
        await interaction.followup.send(
            f"```json\n{json.dumps(data, indent=2, ensure_ascii=False)[:1500]}\n```",
            ephemeral=True,
        )
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)), ephemeral=True)


@tree.command(name="project-new", description="צור פרויקט חדש (Category + 3 ערוצים)",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(name="שם הפרויקט")
async def cmd_project_new(interaction: discord.Interaction, name: str):
    await interaction.response.defer(thinking=True)
    try:
        result = await pm.create_project(interaction.guild, name)
        embed  = discord.Embed(
            title=f"📁 פרויקט נוצר: {name}",
            description="\n".join([f"<#{cid}>" for cid in result["channel_ids"]]),
            color=COLORS["success"],
        )
        await interaction.followup.send(embed=embed)
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(name="project-add-channel",
              description="הוסף ערוץ לפרויקט קיים",
              guild=discord.Object(id=GUILD_ID))
@app_commands.describe(
    project="שם הפרויקט",
    channel_name="שם הערוץ החדש",
    agent="סוכן: main / coder / researcher / analyzer",
)
async def cmd_add_ch(
    interaction: discord.Interaction,
    project: str,
    channel_name: str,
    agent: str = "main",
):
    await interaction.response.defer(thinking=True)
    try:
        result = await pm.add_channel_to_project(
            interaction.guild, project, channel_name, agent
        )
        await interaction.followup.send(
            f"✅ ערוץ <#{result['channel_id']}> נוסף לפרויקט **{project}** (agent: {agent})"
        )
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


@tree.command(name="help", description="רשימת כל הפקודות",
              guild=discord.Object(id=GUILD_ID))
async def cmd_help(interaction: discord.Interaction):
    embed = discord.Embed(title="🤖 OpenClaw v3 — פקודות", color=COLORS["main"])
    embed.add_field(name="🤖 Agents",       value="/main  /coder  /research  /analyze",           inline=False)
    embed.add_field(name="🧭 Multi-Agent",  value="/orchestrate  /debate  /swarm",                inline=False)
    embed.add_field(name="🔧 Tools",        value="/search  /run  /kilo  /recall  /store-memory  /memory", inline=False)
    embed.add_field(name="📁 Projects",     value="/project-new  /project-add-channel",            inline=False)
    embed.add_field(name="💬 ללא פקודה",   value="כתוב בכל ערוץ — הסוכן יגיב ויפעיל tools אוטומטית", inline=False)
    embed.add_field(name="⚡ Kilo",         value="כתוב בערוץ **#kilo-code** → Kilo CLI",         inline=False)
    embed.add_field(name="💻 Terminal",     value="כתוב בערוץ **#terminal** → bash ישיר",         inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


# ─── Modals ───────────────────────────────────────────────────────

class ResearchModal(discord.ui.Modal, title="🔍 מחקר מקיף"):
    query = discord.ui.TextInput(
        label="מה לחקור?", placeholder="הכנס שאלה או נושא...", max_length=500
    )
    depth = discord.ui.TextInput(
        label="עומק", placeholder="קצר / בינוני / מעמיק",
        default="מעמיק", required=False,
    )
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await _slash_agent(
            interaction,
            f"{self.query.value} (עומק: {self.depth.value})",
            "researcher",
        )


class AnalyzeModal(discord.ui.Modal, title="📊 ניתוח אסטרטגי"):
    query = discord.ui.TextInput(
        label="מה לנתח?", placeholder="נושא לניתוח...", max_length=500
    )
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        await _slash_agent(interaction, self.query.value, "analyzer", "analysis")


class OrchModal(discord.ui.Modal, title="🧭 Orchestrate"):
    task = discord.ui.TextInput(
        label="משימה", placeholder="תאר את המשימה...",
        style=discord.TextStyle.paragraph, max_length=1000,
    )
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(thinking=True)
        try:
            result = await call_gateway("/orchestrate", {
                "user_id":    str(interaction.user.id),
                "task":       self.task.value,
                "channel_id": str(interaction.channel.id),
            })
            embed = make_response_embed(
                result["synthesis"], "orchestrator",
                result.get("synthesis_model", "?"),
                result.get("duration", 0), 1, None,
            )
            await interaction.followup.send(embed=embed)
        except Exception as e:
            await interaction.followup.send(embed=make_error_embed(str(e)))


# ─── Context Menus ─────────────────────────────────────────────────

@tree.context_menu(name="🔍 Analyze Message", guild=discord.Object(id=GUILD_ID))
async def ctx_analyze(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"נתח: {message.content}", "analyzer", "analysis")


@tree.context_menu(name="🌐 Translate", guild=discord.Object(id=GUILD_ID))
async def ctx_translate(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"תרגם לעברית ולאנגלית: {message.content}", "main")


@tree.context_menu(name="📝 Summarize", guild=discord.Object(id=GUILD_ID))
async def ctx_summarize(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"סכם: {message.content}", "main")


@tree.context_menu(name="💡 Explain Code", guild=discord.Object(id=GUILD_ID))
async def ctx_explain(interaction: discord.Interaction, message: discord.Message):
    await interaction.response.defer(thinking=True)
    await _slash_agent(interaction, f"הסבר קוד שורה-שורה: {message.content}", "coder", "code")


# ─── Helpers ──────────────────────────────────────────────────────

async def _slash_agent(
    interaction: discord.Interaction,
    prompt: str,
    agent: str,
    task_type: str = "default",
):
    """Common handler for all slash command agent calls."""
    try:
        result = await call_gateway("/chat", {
            "user_id":    str(interaction.user.id),
            "message":    prompt,
            "agent":      agent,
            "task_type":  task_type,
            "channel_id": str(interaction.channel_id),
            "username":   interaction.user.display_name,
            "project":    get_project_for_channel(interaction.channel),
        })
        embed = make_response_embed(
            result["response"], agent,
            result.get("model", "?"),
            result.get("duration", 0),
            result.get("iterations", 1),
            get_project_for_channel(interaction.channel),
        )
        view = ResponseView(
            original_message=prompt,
            agent=agent,
            channel_id=str(interaction.channel_id),
            user_id=str(interaction.user.id),
        )
        await interaction.followup.send(embed=embed, view=view)
        if result.get("tool_log"):
            await interaction.channel.send(embed=make_tool_log_embed(result["tool_log"]))
    except Exception as e:
        await interaction.followup.send(embed=make_error_embed(str(e)))


AGENT_PERSONA_NAMES = {
    "orchestrator": "🧭 Orchestrator",
    "coder":        "💻 Coder",
    "researcher":   "🔍 Researcher",
    "analyzer":     "📊 Analyzer",
    "critic":       "⚖️ Critic",
    "main":         "🤖 OpenClaw",
}


async def _send_persona(channel: discord.TextChannel, agent: str, embed: discord.Embed):
    """Send a message as a named webhook persona."""
    name = AGENT_PERSONA_NAMES.get(agent, "🤖 OpenClaw")
    try:
        webhooks = await channel.webhooks()
        wh = next((w for w in webhooks if w.name == "OpenClaw"), None)
        if not wh:
            wh = await channel.create_webhook(name="OpenClaw")
        await wh.send(username=name, embed=embed)
    except Exception:
        await channel.send(embed=embed)


# ─── Bot lifecycle ─────────────────────────────────────────────────

@bot.event
async def on_ready():
    synced = await tree.sync(guild=discord.Object(id=GUILD_ID))
    print(f"✅ OpenClaw v3 | {bot.user} | Synced {len(synced)} commands to guild {GUILD_ID}")


@bot.event
async def on_guild_available(guild: discord.Guild):
    if guild.id == GUILD_ID:
        await pm.init(guild)
        await kb.init()
        print(f"[INFO] Guild ready: {guild.name} ({guild.id})")


if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
```

שמור ואמת:
```bash
python -c "
import discord, aiohttp
from ui_helpers      import make_thinking_embed
from project_manager import ProjectManager
from kilo_bridge     import KiloBridge
print('bot.py imports OK')
"
```

☑️ **Checkpoint**: רואה "bot.py imports OK"

---

## שלב 11 — systemd services

### 11.1 kilo-server.service (חדש)

```bash
sudo nano /etc/systemd/system/kilo-server.service
```

הדבק:
```ini
[Unit]
Description=Kilo CLI Server
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu
ExecStart=/usr/local/bin/kilo serve --port 4096 --hostname 127.0.0.1
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### 11.2 ai-gateway.service (עדכון)

```bash
sudo nano /etc/systemd/system/ai-gateway.service
```

הדבק (החלף הכל):
```ini
[Unit]
Description=OpenClaw AI Gateway v3
After=network.target redis.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-system/gateway
ExecStart=/home/ubuntu/ai-system/venv/bin/uvicorn main:app --host 127.0.0.1 --port 4001 --workers 1
EnvironmentFile=/home/ubuntu/ai-system/.env
Restart=always
RestartSec=5
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
```

### 11.3 discord-bot.service (עדכון)

```bash
sudo nano /etc/systemd/system/discord-bot.service
```

הדבק (החלף הכל):
```ini
[Unit]
Description=OpenClaw Discord Bot v3
After=network.target ai-gateway.service

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/ai-system/discord-bot
ExecStart=/home/ubuntu/ai-system/venv/bin/python bot.py
EnvironmentFile=/home/ubuntu/ai-system/.env
Restart=always
RestartSec=5
StartLimitIntervalSec=0

[Install]
WantedBy=multi-user.target
```

### 11.4 Reload systemd

```bash
sudo systemctl daemon-reload
```

☑️ **Checkpoint**: daemon-reload הצליח ללא שגיאות

---

## שלב 12 — עדכון litellm-config.yaml

**גיבוי ישן:**
```bash
cp /home/ubuntu/ai-system/litellm-config.yaml /home/ubuntu/ai-system/litellm-config.yaml.v2.bak
```

```bash
nano /home/ubuntu/ai-system/litellm-config.yaml
```

הדבק (החלף הכל — שים לב: ה-keys נלקחים מ-.env אוטומטית):

```yaml
model_list:

  # ── Groq: llama-3.3-70b-versatile (9 keys = load balancing) ─────
  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_1"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_2"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_3"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_4"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_5"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_6"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_7"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_8"
      rpm: 30

  - model_name: groq/llama-3.3-70b-versatile
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: "os.environ/GROQ_KEY_9"
      rpm: 30

  # ── Groq: llama-3.1-8b-instant (מהיר לתשובות קצרות) ─────────────
  - model_name: groq/llama-3.1-8b-instant
    litellm_params:
      model: groq/llama-3.1-8b-instant
      api_key: "os.environ/GROQ_KEY_1"
      rpm: 60

  - model_name: groq/llama-3.1-8b-instant
    litellm_params:
      model: groq/llama-3.1-8b-instant
      api_key: "os.environ/GROQ_KEY_2"
      rpm: 60

  # ── Cerebras: llama3.1-70b (2000 tok/s) ──────────────────────────
  - model_name: cerebras/llama3.1-70b
    litellm_params:
      model: cerebras/llama3.1-70b
      api_key: "os.environ/CEREBRAS_KEY_1"
      rpm: 30

  - model_name: cerebras/llama3.1-70b
    litellm_params:
      model: cerebras/llama3.1-70b
      api_key: "os.environ/CEREBRAS_KEY_2"
      rpm: 30

  - model_name: cerebras/llama3.1-70b
    litellm_params:
      model: cerebras/llama3.1-70b
      api_key: "os.environ/CEREBRAS_KEY_3"
      rpm: 30

  - model_name: cerebras/llama3.1-70b
    litellm_params:
      model: cerebras/llama3.1-70b
      api_key: "os.environ/CEREBRAS_KEY_4"
      rpm: 30

  # ── Gemini: gemini-2.0-flash ─────────────────────────────────────
  - model_name: gemini/gemini-2.0-flash
    litellm_params:
      model: gemini/gemini-flash-2.0
      api_key: "os.environ/GEMINI_KEY_1"
      rpm: 30

  - model_name: gemini/gemini-2.0-flash
    litellm_params:
      model: gemini/gemini-flash-2.0
      api_key: "os.environ/GEMINI_KEY_2"
      rpm: 30

  - model_name: gemini/gemini-2.0-flash
    litellm_params:
      model: gemini/gemini-flash-2.0
      api_key: "os.environ/GEMINI_KEY_3"
      rpm: 30

  - model_name: gemini/gemini-2.0-flash
    litellm_params:
      model: gemini/gemini-flash-2.0
      api_key: "os.environ/GEMINI_KEY_4"
      rpm: 30

  - model_name: gemini/gemini-2.0-flash
    litellm_params:
      model: gemini/gemini-flash-2.0
      api_key: "os.environ/GEMINI_KEY_5"
      rpm: 30

  # ── Gemini: gemini-2.5-flash (reasoning) ─────────────────────────
  - model_name: gemini/gemini-2.5-flash
    litellm_params:
      model: gemini/gemini-2.5-flash-preview-04-17
      api_key: "os.environ/GEMINI_KEY_1"
      rpm: 10

router_settings:
  routing_strategy: least-busy
  num_retries: 2
  cooldown_time: 60

litellm_settings:
  drop_params: true
  max_tokens: 4096
  set_verbose: false

general_settings:
  master_key: "os.environ/LITELLM_MASTER_KEY"
  port: 4000
```

אמת שה-YAML תקין:
```bash
python3 -c "
import yaml
with open('/home/ubuntu/ai-system/litellm-config.yaml') as f:
    data = yaml.safe_load(f)
print(f'YAML OK — {len(data[\"model_list\"])} models defined')
"
```

☑️ **Checkpoint**: רואה "YAML OK — 21 models defined"

---

## שלב 13 — עדכון .env

```bash
nano /home/ubuntu/ai-system/.env
```

**הוסף** את השורות האלה בסוף (אל תמחק שורות קיימות!):

```bash
# ── שורות חדשות לv3 ───────────────────────────────────────────────
DISCORD_GUILD_ID=REPLACE_WITH_YOUR_GUILD_ID
MY_DISCORD_USER_ID=REPLACE_WITH_YOUR_USER_ID
GATEWAY_URL=http://localhost:4001
MAX_AGENT_ITERATIONS=12
REDIS_URL=redis://localhost:6379
LITELLM_MASTER_KEY=sk-litellm-master-2026
KILO_BIN=/usr/local/bin/kilo
KILO_WORK_DIR=/home/ubuntu
```

**החלף** את המילה `REPLACE_WITH_YOUR_GUILD_ID` בערך האמיתי (מ-שלב 1.6).
**החלף** את המילה `REPLACE_WITH_YOUR_USER_ID` בערך האמיתי (מ-שלב 1.6).

אמת:
```bash
grep "DISCORD_GUILD_ID" /home/ubuntu/ai-system/.env
# צריך לראות שורה עם מספר, לא עם REPLACE
```

☑️ **Checkpoint**: DISCORD_GUILD_ID מכיל מספר אמיתי

---

## שלב 14 — עדכון requirements.txt

```bash
nano /home/ubuntu/ai-system/requirements.txt
```

החלף הכל:

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
```

התקן:
```bash
cd /home/ubuntu/ai-system
source venv/bin/activate
pip install -r requirements.txt
```

זה לוקח 2-5 דקות.

אמת:
```bash
python -c "import discord, fastapi, aiohttp, redis, litellm; print('All packages OK')"
```

☑️ **Checkpoint**: רואה "All packages OK"

---

## שלב 15 — התקנת Kilo CLI

### 15.1 בדוק אם Node.js 22+ מותקן

```bash
node --version
```

אם הגרסה נמוכה מ-v22, עדכן:
```bash
curl -fsSL https://fnm.vercel.app/install | bash
source ~/.bashrc
fnm install 22
fnm use 22
fnm default 22
node --version   # צריך לראות v22.x.x
```

### 15.2 התקן kilo

```bash
npm install -g kilocode
```

### 15.3 אמת

```bash
kilo --version
# אם לא מוצא: which kilo
# עדכן KILO_BIN ב-.env לנתיב המלא
```

אם `kilo` לא נמצא ב-PATH:
```bash
which kilocode
# עדכן ב-.env: KILO_BIN=/path/to/kilocode
```

**אם ההתקנה נכשלת לחלוטין** — לא בעיה! הבוט יפעל רגיל, רק ערוץ `#kilo-code` יציג הודעת שגיאה. ניתן להתקין מאוחר יותר.

☑️ **Checkpoint**: `kilo --version` מחזיר גרסה (או מגדיר KILO_BIN)

---

## שלב 16 — הפעלת כל ה-Services

הפעל **בסדר הזה בדיוק** (כל שלב ממתין לקודם):

```bash
# 1. Redis (בדרך כלל כבר רץ)
sudo systemctl start redis
sleep 2
sudo systemctl status redis | grep "active"
# צריך: active (running)

# 2. LiteLLM
sudo systemctl start litellm
sleep 8
curl -s http://localhost:4000/health | python3 -m json.tool
# צריך: {"status": "healthy", ...}

# 3. Gateway
sudo systemctl start ai-gateway
sleep 5
curl -s http://localhost:4001/health | python3 -m json.tool
# צריך: {"status": "ok", "version": "3.0", ...}

# 4. Discord Bot
sudo systemctl start discord-bot
sleep 3
journalctl -u discord-bot -n 20 --no-pager
# צריך: "✅ OpenClaw v3 | OpenClaw#XXXX | Synced X commands to guild XXXXXXXXXX"

# 5. Kilo Server (אם kilo מותקן)
sudo systemctl start kilo-server
# אם לא מותקן — דלג על שלב זה
```

הפעל אוטומטי בהפעלת שרת:
```bash
sudo systemctl enable redis litellm ai-gateway discord-bot
# אם kilo מותקן:
sudo systemctl enable kilo-server
```

☑️ **Checkpoint**: Discord Bot online בשרת Discord (נקודה ירוקה)

---

## שלב 17 — הגדרות Discord Server

### 17.1 צור Category "TOOLS" ו-4 ערוצים

ב-Discord:
1. לחץ ימני על השרת → **"Create Category"** → שם: `TOOLS`
2. לחץ ימני על ה-Category → **"Create Channel"** → שם: `kilo-code`
3. שוב **"Create Channel"** → שם: `terminal`
4. שוב **"Create Channel"** → שם: `research`
5. שוב **"Create Channel"** → שם: `ai-admin`

**חשוב**: שמות בדיוק כך — אותיות קטנות, ללא רווחים.

### 17.2 תן לבוט הרשאות Webhook

1. שרת Settings → Roles
2. מצא את role שנוצר עבור הבוט (שם הבוט)
3. הפעל: **Manage Webhooks** ✅
4. Save

### 17.3 בדיקה ראשונה

כתוב בכל ערוץ (לא `#kilo-code` ולא `#terminal`):
```
שלום, מה שמך?
```

**ציפייה**: הבוט עונה עם embed כחול עם "🤖 Main" בכותרת.

### 17.4 יצירת פרויקט ראשון

כתוב בכל ערוץ:
```
/project-new name:dealcellolaryk
```

**ציפייה**: נוצרים 3 ערוצים חדשים תחת Category "dealcellolaryk".

---

## שלב 18 — בדיקות מלאות

### בדיקה 1: agentic loop עם tools

כתוב בכל ערוץ (ללא @mention):
```
תראה לי מה יש בתיקייה /home/ubuntu/ai-system ואז תרוץ whoami
```

**ציפייה**:
- Embed "🤖 Main חושב..." עם progress bar
- Embed עם תשובה
- Embed נפרד: "🔧 Tool Execution Log" עם 2 רשומות (list_directory + bash_command)
- Footer embed: "🔄 2 צעדים" (2 iterations)

---

### בדיקה 2: web search

```
מה חדש ב-Python 3.13? חפש ותסכם
```

**ציפייה**: tool log מראה `web_search` + תשובה מסכמת.

---

### בדיקה 3: Kilo CLI

כתוב בערוץ `#kilo-code`:
```
הצג את גרסת Node.js ואת הpackages הגלובליים המותקנים
```

**ציפייה**: Embed "⚡ Kilo CLI" מתעדכן עם תוצאה.

אם kilo לא מותקן: תוצג הודעת שגיאה עם הוראות להתקנה.

---

### בדיקה 4: slash command

```
/orchestrate task:כתוב לי מחלקת Python לניהול חיבורי API עם retry logic ו-rate limiting
```

**ציפייה**: 3 embeds — הסינתזה הראשית + 2 webhook personas (Coder + Researcher).

---

### בדיקה 5: כפתורים

לאחר כל תשובה:
- לחץ **🔄 שאל שוב** — מקבל תשובה חדשה לאותה שאלה
- לחץ **🔀 החלף סוכן** — בוחר מ-dropdown ומקבל תשובה מסוכן אחר
- לחץ **🗑️ מחק** — ההודעה נמחקת

---

## פתרון תקלות מהיר

### הבוט לא עולה
```bash
journalctl -u discord-bot -n 50 --no-pager
```
תקלות נפוצות:
- `KeyError: 'DISCORD_TOKEN'` — חסר ב-.env
- `KeyError: 'DISCORD_GUILD_ID'` — חסר ב-.env
- `ImportError` — חסר קובץ Python. בדוק שכל 8 הקבצים נכתבו

### Gateway לא עולה
```bash
journalctl -u ai-gateway -n 50 --no-pager
# תקלה נפוצה:
cd /home/ubuntu/ai-system/gateway
source ../venv/bin/activate
python main.py   # הרץ ישירות לראות שגיאות
```

### "All models failed"
```bash
# בדוק LiteLLM
sudo systemctl status litellm
journalctl -u litellm -n 30 --no-pager | grep -i error

# בדוק YAML
python3 -c "import yaml; yaml.safe_load(open('litellm-config.yaml').read()); print('YAML OK')"

# בדוק שה-API keys ב-.env קיימים ותקינים
grep "GROQ_KEY_1" /home/ubuntu/ai-system/.env
```

### Bot עולה אבל לא עונה
```bash
# בדוק Message Content Intent
# Discord Developer Portal → Applications → Bot → Privileged Gateway Intents
# ✅ Message Content Intent חייב להיות מופעל!

# בדוק logs
journalctl -u discord-bot -f
# ואז שלח הודעה בDiscord — צריך לראות logs
```

### "Synced 0 commands"
בדוק שה-DISCORD_GUILD_ID ב-.env נכון:
```bash
grep DISCORD_GUILD_ID /home/ubuntu/ai-system/.env
```
לאחר תיקון:
```bash
sudo systemctl restart discord-bot
```

### Kilo לא עובד
```bash
# בדוק נתיב
which kilo
which kilocode

# עדכן ב-.env
echo "KILO_BIN=$(which kilo || which kilocode)" >> /home/ubuntu/ai-system/.env
sudo systemctl restart discord-bot
```

---

## רשימת בדיקה סופית למתכנת

לפני שמדווח שהכל מוכן, ודא:

- [ ] `agents.py` נכתב ואומת
- [ ] `tools.py` נכתב ואומת
- [ ] `memory.py` נכתב ואומת
- [ ] `main.py` נכתב ואומת
- [ ] `ui_helpers.py` נכתב ואומת
- [ ] `project_manager.py` נכתב ואומת
- [ ] `kilo_bridge.py` נכתב ואומת
- [ ] `bot.py` נכתב ואומת
- [ ] כל 3 systemd services עודכנו ו-daemon-reload רץ
- [ ] `litellm-config.yaml` עודכן עם כל 21 models
- [ ] `.env` מכיל DISCORD_GUILD_ID עם מספר אמיתי
- [ ] `.env` מכיל DISCORD_TOKEN עם token אמיתי
- [ ] `pip install -r requirements.txt` הצליח
- [ ] `curl http://localhost:4001/health` מחזיר `"version": "3.0"`
- [ ] Bot online ב-Discord
- [ ] בדיקה 1 (agentic loop) עברה
- [ ] בדיקה 4 (slash command) עברה

---

*OpenClaw Discord AI System v3.0*
*Oracle Cloud ARM64 • Python 3.11 • FastAPI • discord.py 2.5 • LiteLLM • Redis 7 • Kilo CLI*
