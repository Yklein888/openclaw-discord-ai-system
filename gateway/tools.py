# gateway/tools.py
# All tool implementations for the agentic loop

import asyncio
import os
import tempfile

import aiohttp

from core_memory import get_all_blocks, append_to_block, replace_entire_block
from working_memory import wm_set, wm_get, wm_list_all

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
                    "command": {"type": "string", "description": "פקודת bash להרצה"},
                    "timeout": {
                        "type": "integer",
                        "description": "timeout בשניות (ברירת מחדל: 30)",
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
                    "code": {"type": "string", "description": "קוד Python להרצה"},
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
                    "query": {"type": "string", "description": "שאילתת חיפוש"},
                    "max_results": {
                        "type": "integer",
                        "description": "מספר תוצאות (ברירת מחדל: 5)",
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
                    "path": {"type": "string", "description": "נתיב מלא לקובץ"},
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
                    "path": {"type": "string", "description": "נתיב מלא לקובץ"},
                    "content": {"type": "string", "description": "תוכן לכתיבה"},
                    "mode": {
                        "type": "string",
                        "description": "w לכתיבה מחדש, a להוספה. ברירת מחדל: w",
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
                    "url": {"type": "string"},
                    "method": {
                        "type": "string",
                        "description": "GET או POST. ברירת מחדל: GET",
                    },
                    "body": {
                        "type": "object",
                        "description": "JSON body ל-POST requests",
                    },
                    "headers": {"type": "object", "description": "HTTP headers נוספים"},
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
                        "description": "למשל: /repos/owner/repo/commits",
                    },
                    "method": {
                        "type": "string",
                        "description": "GET, POST, PATCH, DELETE. ברירת מחדל: GET",
                    },
                    "body": {"type": "object", "description": "JSON body לשליחה"},
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
                    "title": {"type": "string", "description": "כותרת הדף"},
                    "content": {"type": "string", "description": "תוכן הדף"},
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
                    "path": {"type": "string", "description": "נתיב לתיקייה"},
                    "depth": {
                        "type": "integer",
                        "description": "עומק רקורסיה. ברירת מחדל: 1",
                    },
                },
                "required": ["path"],
            },
        },
    },
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
                    "key": {
                        "type": "string",
                        "description": "שם המפתח (למשל: api_url)",
                    },
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
                    "label": {
                        "type": "string",
                        "description": "persona / user / current_project / important_facts",
                    },
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
                    "label": {"type": "string"},
                    "new_content": {"type": "string"},
                },
                "required": ["label", "new_content"],
            },
        },
    },
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
                    "steps": {"type": "array", "items": {"type": "string"}},
                    "example": {"type": "string", "description": "דוגמה מלאה"},
                },
                "required": ["trigger", "steps", "example"],
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
            return await _write_file(
                args["path"], args["content"], args.get("mode", "w")
            )
        elif name == "fetch_url":
            return await _fetch_url(
                args["url"],
                args.get("method", "GET"),
                args.get("body"),
                args.get("headers", {}),
            )
        elif name == "github_api":
            return await _github_api(
                args["endpoint"], args.get("method", "GET"), args.get("body")
            )
        elif name == "notion_add":
            return await _notion_add(args["title"], args["content"])
        elif name == "list_directory":
            return await _list_dir(args["path"], args.get("depth", 1))
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
            return await replace_entire_block(
                user_id, args["label"], args["new_content"]
            )
        elif name == "save_learned_pattern":
            from procedural_memory import save_pattern

            await save_pattern(
                user_id,
                args["trigger"],
                args["steps"],
                args["example"],
            )
            return f"✅ דפוס נשמר: {args['trigger']}"
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
    with tempfile.NamedTemporaryFile(
        suffix=".py", delete=False, mode="w", encoding="utf-8"
    ) as f:
        f.write(code)
        fname = f.name
    try:
        proc = await asyncio.create_subprocess_exec(
            "python3",
            fname,
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
            body = r.get("body", "")
            href = r.get("href", "")
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
                "timeout": aiohttp.ClientTimeout(total=20),
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
        "properties": {"Name": {"title": [{"text": {"content": title}}]}},
        "children": [
            {
                "object": "block",
                "type": "paragraph",
                "paragraph": {"rich_text": [{"text": {"content": content[:2000]}}]},
            }
        ],
    }
    headers = {
        "Authorization": f"Bearer {NOTION_TOKEN}",
        "Notion-Version": "2022-06-28",
        "Content-Type": "application/json",
    }
    return await _fetch_url(url, "POST", body, headers)


async def _list_dir(path: str, depth: int = 1) -> str:
    return await _bash(f"find {path} -maxdepth {depth} | sort | head -100")
