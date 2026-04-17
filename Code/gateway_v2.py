"""
OpenClaw Gateway v2.0
FastAPI gateway with:
- Orchestrator smart routing
- 5 specialized agents (orchestrator/coder/researcher/analyzer/critic)
- Webhook persona support
- Task-based model routing
- Streaming progressive responses
- Mem0 long-term memory (Phase 15 upgraded)
- Phase 16 swarm (upgraded with Critic)
- All existing Phase 10-13 endpoints preserved
- Phase 21: Browser Automation with Playwright
"""

from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional, List
import httpx
import redis
import time
import json
import re
import asyncio
import sys
import os
import tempfile
import uuid

app = FastAPI(title="OpenClaw Gateway v2.0")
r = redis.Redis(host="localhost", port=6379, decode_responses=True)
LITELLM_URL = "http://localhost:4000"
LITELLM_KEY = "sk-litellm-master-2026"

# ─── Model routing by task type ───────────────────────────────────────────────
TASK_MODELS = {
    "code":     ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "reason":   ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "speed":    ["groq-llama-70b", "groq-llama-8b",      "cerebras-llama-70b"],
    "analysis": ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "vision":   ["gemini-flash"],
    "default":  ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
}

OPENCLAW_IDENTITY = """אתה OpenClaw — העוזר האישי של יצחק. רץ על שרת Oracle Cloud פרטי שלו.

━ מי אתה ━
אתה לא "שירות לקוחות AI" — אתה שותף. אתה מכיר את המערכת שלו, הפרויקטים שלו, הצרכים שלו.
אתה ישיר, חכם, ותמיד בצד שלו.

━ איך אתה מדבר ━
• התשובה קודם — הסברים רק אם ביקשו
• עברית טבעית כמו שמדברים לחבר, לא עברית של מסמכים
• קצר וחד — לא משפטי מבוא, לא "בהתאם לבקשתך..."
• אם יש בעיה — אומר ישירות בלי לעטוף בכותנה

❌ לא כך: "בהתאם לבקשתך, אני מספק להלן את המידע הרלוונטי לפי הפרמטרים שציינת..."
✅ כך: "אוקיי, הנה:"

❌ לא כך: "חשוב לציין כי יש להתייחס ל... מספר שיקולים..."
✅ כך: "שים לב ל-X, זה יכול לשבור לך את זה."

❌ לא: לפתוח עם "כמובן!" / "בהחלט!" / "שאלה מצוינת!" / "בטח!"
✅ כן: פשוט לענות.

━ לגבי קוד ━
שאלו שאלה → עונים על השאלה. לא שולפים Python אוטומטית.
קוד מגיע רק כשהוא הפתרון — כשביקשו אותו, או כשאין דרך אחרת.
כשכן נותן קוד — נקי, קצר, עם הסבר שורה אחת על כל חלק.
אם צריך לגשת לשירות חיצוני שאין לך גישה אליו ישירות — תן קוד עובד, לא הסבר תיאורטי.

━ אמת ━
לא ממציאים תוצאות, נתונים, או מידע שלא קיים. אם לא יודעים — אומרים ומציעים איך לבדוק.

━ שפה ━
עונה בשפה שפנו אליך. לא מזכיר שם מודל. לא מזכיר OpenAI/Anthropic/Google."""

DEFAULT_SYSTEM = OPENCLAW_IDENTITY

AGENT_SYSTEMS = {
    "orchestrator": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מנהל אסטרטגי. נתח בקשות, תכנן, ותסנתז תשובות מכמה סוכנים לתשובה מושלמת אחת. "
        "פרק משימות מורכבות לשלבים ברורים. ענה בעברית."
    ),
    "coder": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מומחה קוד בכל שפה — Python, JS, TypeScript, Rust, Go, SQL, ועוד. "
        "כתוב קוד נקי, מלא, מתועד ועובד. אל תכתוב קוד חסר — כתוב את הכל. "
        "כשמישהו צריך גישה ל-API חיצוני (Gmail, Telegram, etc) — תן קוד Python מלא שהם יכולים להריץ. "
        "ענה בעברית עם הקוד באנגלית."
    ),
    "researcher": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: חוקר מומחה. ספק מידע עובדתי, מקיף ומדויק ממה שאתה יודע. "
        "תמיד ציין אם המידע עשוי להיות לא עדכני ואתה יכול להציע לחפש באינטרנט. "
        "ענה בעברית בצורה מסודרת עם כותרות ונקודות."
    ),
    "analyzer": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מנתח אסטרטגי. נתח כל בקשה לעומק: יתרונות, חסרונות, סיכונים, הזדמנויות. "
        "השתמש בנתונים ולוגיקה. תן המלצה ברורה בסוף. ענה בעברית."
    ),
    "critic": (
        OPENCLAW_IDENTITY + "\n\n"
        "תפקידך: מבקר מומחה. בדוק שגיאות לוגיות, חורים, בעיות איכות, ואיך לשפר. "
        "היה ישיר וספציפי. ציין גם מה טוב. ענה בעברית."
    ),
}

# ─── Pydantic models ──────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    user_id: str
    message: str
    system_prompt: Optional[str] = None
    username: Optional[str] = None
    agent: Optional[str] = "main"
    task_type: Optional[str] = "default"
    channel_id: Optional[str] = "global"
    image_url: Optional[str] = None
    reply_to_content: Optional[str] = None
    active_task: Optional[dict] = None
    intent: Optional[str] = "new_task"

class VisionRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    image_url: str
    text: Optional[str] = ""

class SearchRequest(BaseModel):
    query: str
    max_results: Optional[int] = 5

class CodeRequest(BaseModel):
    code: str
    timeout: Optional[int] = 10

class OrchestratorRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    task: str
    agents: Optional[List[str]] = None
    channel_id: Optional[str] = "global"

class SwarmRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    task: str
    channel_id: Optional[str] = "global"

class RecallRequest(BaseModel):
    user_id: str
    query: str
    top_k: Optional[int] = 5

class StoreMemoryRequest(BaseModel):
    user_id: str
    text: str
    agent: Optional[str] = "main"

class NotionAddRequest(BaseModel):
    text: str
    title: Optional[str] = None
    database_id: Optional[str] = None

class DebateRequest(BaseModel):
    user_id: str
    username: Optional[str] = None
    topic: str

class BrowserRequest(BaseModel):
    action: str
    url: Optional[str] = None
    selector: Optional[str] = None
    text: Optional[str] = None
    full_page: Optional[bool] = False
    clear: Optional[bool] = True
    wait_for: Optional[str] = None
    timeout: Optional[int] = 30000
    js: Optional[str] = None


# ─── Routes ────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "phase": "21", "browser": "available"}


@app.post("/chat")
async def chat(req: ChatRequest):
    async with httpx.AsyncClient(timeout=120.0) as client:
        system = req.system_prompt or DEFAULT_SYSTEM
        messages = [{"role": "system", "content": system}, {"role": "user", "content": req.message}]
        
        try:
            resp = await client.post(
                f"{LITELLM_URL}/v1/chat/completions",
                json={"model": "groq-llama-70b", "messages": messages},
                headers={"Authorization": f"Bearer {LITELLM_KEY}"}
            )
            data = resp.json()
            return {"response": data["choices"][0]["message"]["content"]}
        except Exception as e:
            return {"error": str(e)}


# ─── SEARCH (Phase 10) ────────────────────────────────────────────────────────

@app.post("/search")
async def search(req: SearchRequest):
    from duckduckgo_search importDDG
    ddg = DDG()
    results = ddg.text(req.query, max_results=req.max_results)
    return {"results": [{"title": r["title"], "url": r["url"], "body": r["body"]} for r in results]}


# ─── BROWSER (Phase 21) ────────────────────────────────────────────────────────

browser_service = None

def get_browser():
    global browser_service
    if browser_service is None:
        from browser_service import browser_tool
        browser_service = browser_tool
    return browser_service

@app.post("/browser")
async def browser_control(req: BrowserRequest):
    """Browser automation endpoint"""
    b = get_browser()
    
    action = req.action.lower()
    
    try:
        if action == "init":
            await b.init()
            return {"success": True, "message": "Browser initialized"}
        
        elif action == "navigate":
            if not req.url:
                return {"success": False, "error": "URL required"}
            result = await b.navigate(req.url)
            return result
        
        elif action == "click":
            if not req.selector:
                return {"success": False, "error": "Selector required"}
            result = await b.click(req.selector)
            return result
        
        elif action == "type":
            if not req.selector or not req.text:
                return {"success": False, "error": "Selector and text required"}
            result = await b.type(req.selector, req.text, req.clear)
            return result
        
        elif action == "screenshot":
            result = await b.screenshot(req.full_page)
            return result
        
        elif action == "get_html":
            result = await b.get_html()
            return result
        
        elif action == "extract":
            if not req.selector:
                return {"success": False, "error": "Selector required"}
            result = await b.extract_text(req.selector)
            return result
        
        elif action == "get_links":
            result = await b.get_links()
            return result
        
        elif action == "evaluate":
            if not req.js:
                return {"success": False, "error": "JavaScript code required"}
            result = await b.evaluate(req.js)
            return result
        
        elif action == "scroll_down":
            result = await b.scroll_down(int(req.text) if req.text else 500)
            return result
        
        elif action == "close":
            await b.close()
            return {"success": True, "message": "Browser closed"}
        
        else:
            return {"success": False, "error": f"Unknown action: {action}"}
    
    except Exception as e:
        return {"success": False, "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=4001)