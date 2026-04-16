# OpenClaw Discord AI System v2.0

> מערכת AI פרטית מרובת-סוכנים על Discord, מופעלת על Oracle Cloud ARM64.  
> בנויה עם Python 3.11 · FastAPI · Discord.py 2.5 · LiteLLM · Redis

[![Python](https://img.shields.io/badge/Python-3.11-blue)](https://python.org)
[![Discord.py](https://img.shields.io/badge/discord.py-2.5-5865F2)](https://discordpy.readthedocs.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110-009688)](https://fastapi.tiangolo.com)
[![LiteLLM](https://img.shields.io/badge/LiteLLM-1.x-orange)](https://litellm.ai)
[![Redis](https://img.shields.io/badge/Redis-7-red)](https://redis.io)

---

## תוכן עניינים

1. [מה זה OpenClaw?](#מה-זה-openclaw)
2. [ארכיטקטורה — מבט על](#ארכיטקטורה--מבט-על)
3. [מבנה הקבצים](#מבנה-הקבצים)
4. [זרימת הנתונים — צעד אחר צעד](#זרימת-הנתונים--צעד-אחר-צעד)
5. [מערכת הסוכנים (5 Agents)](#מערכת-הסוכנים-5-agents)
6. [מערכת הזיכרון (3 Layers)](#מערכת-הזיכרון-3-layers)
7. [מערכת הערוצים](#מערכת-הערוצים)
8. [LiteLLM — ניהול מודלים](#litellm--ניהול-מודלים)
9. [כל הפקודות (22)](#כל-הפקודות-22)
10. [ממשקי המשתמש](#ממשקי-המשתמש)
11. [Webhook Personas](#webhook-personas)
12. [Gateway API — כל ה-Endpoints](#gateway-api--כל-ה-endpoints)
13. [התקנה מאפס](#התקנה-מאפס)
14. [משתני סביבה](#משתני-סביבה)
15. [Services (systemd)](#services-systemd)
16. [גיבוי ואחזקה](#גיבוי-ואחזקה)
17. [פתרון תקלות](#פתרון-תקלות)

---

## מה זה OpenClaw?

OpenClaw היא **מערכת AI פרטית** — לא צ'אטבוט גנרי. Discord הוא רק הממשק שדרכו מדברים אל המערכת. הכוח האמיתי נמצא מאחורי הקלעים: 5 סוכנים AI מתמחים, זיכרון סמנטי ארוך-טווח, ניתוח תמונות, הרצת קוד, גישה ל-GitHub ו-Notion, ו-14 מודלי AI עם fallback אוטומטי.

**מה ייחודי בה:**
- כל הודעה בכל ערוץ → תגובת AI (ללא @mention)
- כל ערוץ מבודד — הקשר שיחה נפרד לכל ערוץ
- כל סוכן מדבר עם זהות Discord נפרדת (Webhook Persona)
- אין "אני לא יכול" — המערכת תמיד מוצאת דרך
- 14 מודלים עם fallback אוטומטי — תמיד זמין

---

## ארכיטקטורה — מבט על

```
┌─────────────────────────────────────────────────────────────────┐
│                        DISCORD (ממשק בלבד)                       │
│                                                                   │
│  User writes in any channel  ──────────────────────────────────► │
│  No @mention needed                                               │
│  22 slash commands (/main, /orchestrate, /debate...)              │
│  4 right-click context menus                                      │
│  Modals (popup forms), Select menus, Progress bars               │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP POST (aiohttp)
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   DISCORD BOT  (discord-bot/bot.py)              │
│                   discord.py 2.5 · Python 3.11                   │
│                                                                   │
│  on_message() ──► routes to correct handler                      │
│  Slash commands ──► defers → progress bar → result embed         │
│  Webhook Personas ──► each agent = own Discord identity          │
└─────────────────────────────┬───────────────────────────────────┘
                              │ aiohttp POST/GET  localhost:4001
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                   GATEWAY v2.0  (gateway/main.py)                │
│                   FastAPI · Uvicorn · port 4001                  │
│                                                                   │
│  /chat          single agent + context + long-term memory        │
│  /orchestrate   auto-selects agents → parallel → critic → synth  │
│  /debate        pro vs con → critic verdict                      │
│  /swarm         4 agents parallel → critic → synthesis           │
│  /vision        image analysis (Gemini)                          │
│  /search        DuckDuckGo web search                            │
│  /run-code      sandboxed Python execution                       │
│  /recall        semantic memory search                           │
│  /store-memory  save to long-term memory                         │
│  /github/*      GitHub API                                       │
│  /notion/*      Notion API                                       │
└───────────────┬────────────────────────────┬────────────────────┘
                │ HTTP  localhost:4000         │ redis-py  localhost:6379
                ▼                             ▼
┌───────────────────────┐     ┌──────────────────────────────────┐
│    LITELLM PROXY      │     │              REDIS 7              │
│    port 4000          │     │                                   │
│                       │     │  ctx:{uid}:{channel_id}           │
│  14 AI models         │     │    → per-channel short context    │
│  load balancing       │     │    → rolling 20 messages          │
│  auto-fallback        │     │                                   │
│  multiple API keys    │     │  mem:{uid}                        │
│  cost tracking        │     │    → global user stats/prefs      │
└───────────────────────┘     │                                   │
                               │  longmem:{uid}:N                  │
                               │    → 768-dim embeddings           │
                               │    → semantic long-term memory    │
                               └──────────────────────────────────┘
```

---

## מבנה הקבצים

```
/home/ubuntu/ai-system/            ← שורש הפרויקט
│
├── discord-bot/
│   └── bot.py                     ← הבוט הראשי (≈1200 שורות)
│                                    22 פקודות, 4 context menus,
│                                    webhook personas, modals,
│                                    progress bars, channel handlers
│
├── gateway/
│   └── main.py                    ← ה-API הפנימי (≈800 שורות)
│                                    FastAPI, 5 agents, memory system,
│                                    LiteLLM calls, GitHub/Notion APIs
│
├── litellm-config.yaml            ← הגדרות 14 מודלי AI
│                                    API keys, rate limits, fallback order
│
├── litellm-config.example.yaml    ← תבנית ללא מפתחות (לגיטהאב)
│
├── .env                           ← כל ה-credentials (לא בגיטהאב!)
├── .env.example                   ← תבנית לחדשים
│
├── backup.sh                      ← סקריפט גיבוי יומי (cron 3am)
│
├── docs/
│   ├── ARCHITECTURE.md            ← ארכיטקטורה מפורטת
│   ├── COMMANDS.md                ← כל 22 הפקודות
│   ├── API.md                     ← Gateway API reference
│   ├── MEMORY.md                  ← מערכת הזיכרון
│   └── SETUP.md                   ← מדריך התקנה מלא
│
├── systemd/
│   ├── ai-gateway.service         ← service file לגייטווי
│   ├── discord-bot.service        ← service file לבוט
│   └── litellm.service            ← service file ל-LiteLLM
│
└── venv/                          ← Python virtualenv (לא בגיטהאב)
```

---

## זרימת הנתונים — צעד אחר צעד

### מסלול הודעה רגילה בצ'אט

```
1. המשתמש כותב: "תסביר לי מה זה Docker"
   בערוץ: #backend (ערוץ רגיל, ללא @mention)

2. bot.py / on_message()
   ↓ לא ערוץ מיוחד → מסלול ברירת מחדל
   ↓ קורא _chat_reply(message, "main")

3. bot.py / _chat_reply()
   ↓ שולח embed "חושב..." עם progress bar
   ↓ POST http://localhost:4001/chat
      {
        "user_id":    "123456789",
        "message":    "תסביר לי מה זה Docker",
        "username":   "Yitzi",
        "agent":      "main",
        "channel_id": "987654321"   ← מבטיח context מבודד לערוץ זה
      }

4. gateway/main.py / POST /chat
   ↓ טוען context: GET Redis["ctx:123456789:987654321"]
      → ["מה שאלת לפני", "מה הבוט ענה"]
   ↓ מחפש זיכרון סמנטי: search_long_memory("Docker")
      → ["User is building microservices"] (אם קיים)
   ↓ בונה messages array:
      [system_prompt + memories] + [context] + [שאלה נוכחית]
   ↓ llm_call(messages, "default")
      → מנסה: groq-llama-70b (אם נכשל → cerebras → gemini-flash)

5. LiteLLM (port 4000)
   ↓ מנתב ל-groq-llama-70b
   ↓ מבצע load balancing בין 9 API keys
   ↓ מחזיר תשובה

6. gateway/main.py
   ↓ שומר context חדש ב-Redis (rolling 20 messages)
   ↓ שומר embedding לזיכרון ארוך-טווח (async, לא חוסם)
   ↓ מחזיר: {"response": "...", "model": "groq-llama-70b", "duration": 1.2}

7. bot.py
   ↓ עורך את הודעת ה"חושב..." ← FRONT (התשובה הגלויה)
   ↓ embed עם: התשובה + שם מודל + זמן
   ↓ ResponseView buttons: 🔄 שאל שוב | 🔀 החלף סוכן | 🗑️ מחק
```

### מסלול /orchestrate

```
1. /orchestrate "בנה לי מערכת auth מלאה עם JWT"

2. bot.py → POST /orchestrate
   {"user_id": "...", "task": "בנה מערכת auth...", "agents": null}

3. gateway / orchestrate()
   Step 1: Orchestrator מחליט אילו סוכנים
           → prompt: "אילו סוכנים נדרשים? ענה רק בשמות"
           → תשובה: "coder,researcher"
   
   Step 2: asyncio.gather() — מקביל:
           ├── agent_call("coder",      task, "code")
           └── agent_call("researcher", task, "default")
   
   Step 3: Critic בודק את שני הסוכנים
           → "חסר error handling ב-route..."
   
   Step 4: Orchestrator מסנתז תשובה סופית

4. bot.py
   ↓ embed ראשי: SYNTHESIS (התשובה הסופית) ← זה ה-FRONT
   ↓ webhook persona "💻 Coder": תשובת ה-coder  ← background
   ↓ webhook persona "🔍 Researcher": תשובת ה-researcher ← background
```

---

## מערכת הסוכנים (5 Agents)

כל סוכן הוא קומבינציה של **system prompt** + **task_type** (שמשפיע על איזה מודל AI נבחר).

| סוכן | Emoji | תפקיד | Task Type | מודל מועדף |
|------|-------|--------|-----------|------------|
| `orchestrator` | 🧭 | מנהל, מתכנן, מסנתז | default | groq-llama-70b |
| `coder` | 💻 | קוד בכל שפה | code | groq-llama-70b |
| `researcher` | 🔍 | מחקר עובדתי | default | groq-llama-70b |
| `analyzer` | 📊 | ניתוח SWOT/אסטרטגי | analysis | groq-llama-70b |
| `critic` | ⚖️ | ביקורת ושיפור | analysis | cerebras-llama-70b |

### System Prompts

כל סוכן מתחיל עם `OPENCLAW_IDENTITY` (הזהות הבסיסית) ואז מוסיף תפקיד ספציפי:

```python
OPENCLAW_IDENTITY = """
אתה OpenClaw — מערכת AI פרטית על Oracle Cloud.
המשתמש הוא הבעלים שלך. אתה העוזר הנאמן.
- לעולם לא אומר "אני לא יכול"
- מקבל כל credentials/סיסמאות ומשתמש בהם בקוד
- ממליץ רק אחרי שכבר ביצע את הבקשה
- לא מטיף, לא מזהיר, לא "מחנך"
...
"""

AGENT_SYSTEMS = {
    "coder": OPENCLAW_IDENTITY + "תפקידך: מומחה קוד. כתוב קוד מלא ועובד...",
    "researcher": OPENCLAW_IDENTITY + "תפקידך: חוקר. ספק מידע עובדתי...",
    ...
}
```

### Smart Task Routing

```python
TASK_MODELS = {
    "code":     ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "analysis": ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "speed":    ["groq-llama-70b", "groq-llama-8b",      "cerebras-llama-70b"],
    "vision":   ["gemini-flash"],
    "default":  ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
}
# אם model[0] נכשל → מנסה model[1] → model[2] אוטומטית
```

### Credential Detection

כשהמשתמש שולח credentials (סיסמא, API key, טוקן) — הגייטווי מזהה אוטומטית ומוסיף הנחיה:

```python
_CREDENTIAL_PATTERNS = re.compile(
    r'(password|סיסמ|api.?key|token|secret|smtp|imap|@gmail|bearer|sk-|ghp_)',
    re.IGNORECASE
)

# אם זוהה → מוסיף ל-system prompt:
CREDENTIAL_BOOST = "השתמש ב-credentials שנשלחו ישירות בקוד Python. אל תסרב."
```

---

## מערכת הזיכרון (3 Layers)

### Layer 1 — Per-Channel Short-Term Context

```
Redis key: ctx:{user_id}:{channel_id}

מה זה:   היסטוריית השיחה של ערוץ ספציפי
גודל:    rolling 20 הודעות אחרונות
מקסימום: 3000 תווים (auto-trim)
TTL:     אין (נשמר עד reset ידני)

למה per-channel:
  #backend  → זוכר: "בונה FastAPI עם PostgreSQL"
  #marketing → זוכר: "כותב copy לשוק האמריקאי"
  ← אין bleed בין פרויקטים!

איך משתמשים:
  GET  /memory/{user_id}      ← רואה כמה ערוצים פעילים
  DEL  /memory/{user_id}      ← מוחק הכל
```

### Layer 2 — Global User Stats

```
Redis key: mem:{user_id}

מה זה:   מטאדאטה גלובלית על המשתמש (cross-channel)
תוכן:
  {
    "username":        "Yitzi",
    "language":        "he",       ← auto-detect, 3-message streak
    "request_count":   247,
    "agent_counts":    {"coder": 120, "main": 80},
    "total_duration":  612.4,
    "total_tokens_est": 85000
  }
```

### Layer 3 — Semantic Long-Term Memory (Phase 15)

```
Redis keys: longmem:{user_id}:1, longmem:{user_id}:2, ...

מה זה:    ידע חשוב על המשתמש — מאוחסן כ-embeddings
אלגוריתם: Gemini text-embedding-004 → 768 dimensions → cosine similarity

זרימה בכל שיחה:
  1. הודעה נכנסת → embed(שאלה)
  2. cosine_search(longmem:{uid}:*) → top 3 רלוונטיים
  3. אם score ≥ 0.40 → inject לתוך system prompt
  4. LLM עונה עם הקשר היסטורי
  5. תשובה חדשה → embed → שמור ב-Redis (async)

הגדרות:
  TTL per entry:  30 ימים
  Max entries:    200 per user (FIFO rotation)
  Min threshold:  0.40 cosine similarity
  Auto-inject:    top 3 per request

Shared: גלובלי — עובר בין כל הערוצים
```

**דיאגרמה:**

```
הודעה נכנסת: "איך אני מתחבר ל-PostgreSQL?"
        │
        ├──► embed("איך מתחבר ל-PostgreSQL?") = [0.12, -0.34, 0.78, ...]
        │
        ├──► cosine search in longmem:
        │    score=0.89: "User builds FastAPI app with PostgreSQL"  ← inject!
        │    score=0.71: "User prefers SQLAlchemy ORM"              ← inject!
        │    score=0.34: "User uses dark mode in VS Code"           ← below threshold
        │
        ├──► System prompt = base_prompt + "זיכרונות: [FastAPI+PG, SQLAlchemy]"
        │
        └──► LLM responds: "לפרויקט FastAPI שלך עם SQLAlchemy, הנה ה-connection string..."
```

---

## מערכת הערוצים

הבוט עונה לכל הודעה ללא @mention. הניתוב מבוסס על שם הערוץ:

```python
# on_message() routing logic

if isinstance(channel, DMChannel):
    → agent: main, context: dm:{user_id}

elif channel.name == "terminal":
    → auto-detect code blocks → Python sandbox
    → מחזיר output embed

elif channel.name == "knowledge":
    → agent: researcher
    → context: ctx:{uid}:knowledge_{channel_id}

elif channel.name == "clawhub":
    → auto-detect skill from Hebrew/English keywords
    → routes to: coder / research / analyze / main
    → context: ctx:{uid}:clawhub_{channel_id}

elif channel.name == "ai-admin":
    → !reset → DELETE /memory/{uid}
    → !stats  → GET /memory/{uid} → embed
    → כל שאר → agent: main

else:  # כל ערוץ אחר
    → agent: main
    → context: ctx:{uid}:{channel_id}  ← מבודד לערוץ זה
```

**Context isolation מעשי:**

```
User "Yitzi" (id: 123) כותב ב:

#project-saas (channel: 456):
  ctx:123:456 = ["building SaaS", "using Supabase", "React frontend"]

#learning-rust (channel: 789):
  ctx:123:789 = ["learning Rust", "ownership concept", "borrow checker"]

→ כל ערוץ = context נפרד, פרויקט נפרד, זיכרון נפרד
→ longmem:123:* = global knowledge (מה ש/store-memory נשמר)
```

---

## LiteLLM — ניהול מודלים

LiteLLM פועל כ-proxy בפורט 4000 ומספק:
- **Load balancing** בין keys מרובים לאותו מודל
- **Fallback** אוטומטי אם מודל נכשל
- **Rate limiting** per key
- **Cost tracking**

### מודלים זמינים (14)

| Model Name | Provider | Keys | RPM | שימוש עיקרי |
|------------|----------|------|-----|-------------|
| `groq-llama-70b` | Groq | 9 | 270 | כל דבר — מהיר וחזק |
| `groq-llama-8b` | Groq | 7 | 210 | ultra-fast, תשובות קצרות |
| `cerebras-llama-70b` | Cerebras | 4 | 120 | 2000 tok/s — הכי מהיר |
| `gemini-flash` | Google | 5 | 150 | vision + context ארוך |
| `gemini-2.5-flash` | Google | 1 | 30 | reasoning מתקדם (2026) |
| `deepseek-r1` | OpenRouter | 1 | 20 | chain-of-thought |
| `qwen-1m` | OpenRouter | 1 | 20 | 1M token context |
| `nemotron-120b` | OpenRouter | 1 | 20 | NVIDIA 120B quality |
| `mistral-large` | Mistral | 2 | 60 | European multilingual |
| `openrouter-auto` | OpenRouter | 4 | 120 | auto-routing fallback |
| `gpt-3.5-turbo` | Groq (alias) | 1 | 30 | compatibility alias |

### config structure (`litellm-config.yaml`)

```yaml
model_list:
  - model_name: groq-llama-70b      # שם שהגייטווי קורא
    litellm_params:
      model: groq/llama-3.3-70b-versatile   # שם המודל האמיתי
      api_key: gsk_xxx              # API key (מ-.env בעדיפות)
      rpm: 30                       # rate limit per key

  - model_name: groq-llama-70b      # אותו שם = load balancing!
    litellm_params:
      model: groq/llama-3.3-70b-versatile
      api_key: gsk_yyy              # key שני
      rpm: 30

router_settings:
  routing_strategy: least-busy     # בוחר ה-key הפחות עמוס
  num_retries: 2
  cooldown_time: 60                # אם key נכשל — המתן 60s

litellm_settings:
  drop_params: true                # מסנן params לא-נתמכים
  max_tokens: 4096

general_settings:
  master_key: sk-litellm-master-2026
  port: 4000
```

---

## כל הפקודות (22)

### 🤖 AI Agents
| פקודה | סוכן | תיאור |
|-------|------|--------|
| `/main <prompt>` | 🤖 Main | שיחה כללית, כל נושא |
| `/coder <prompt>` | 💻 Coder | קוד — כתיבה, דיבוג, הסבר |
| `/research [prompt]` | 🔍 Researcher | מחקר עמוק (ריק → Modal) |
| `/analyze [prompt]` | 📊 Analyzer | ניתוח אסטרטגי (ריק → Modal) |

### 🧭 Multi-Agent
| פקודה | תיאור |
|-------|--------|
| `/orchestrate [task]` | Orchestrator בוחר סוכנים → מקביל → Critic → synthesis |
| `/debate [topic]` | Researcher בעד + Analyzer נגד → Critic פוסק |
| `/swarm <task>` | 4 סוכנים מקביל + Critic + synthesis |

### 🔧 Tools
| פקודה | תיאור |
|-------|--------|
| `/search <query>` | DuckDuckGo — 5 תוצאות עם קישורים |
| `/run <code>` | הרצת Python בסביבת sandbox |
| `/memory [uid]` | סטטיסטיקות המשתמש |
| `/recall <query>` | חיפוש סמנטי בזיכרון ארוך-טווח |
| `/store-memory <text>` | שמירה ידנית לזיכרון |

### 📦 GitHub
| פקודה | תיאור |
|-------|--------|
| `/github <owner/repo>` | מידע על repo (stars, forks, language) + autocomplete |
| `/github-prs <repo>` | רשימת Pull Requests |
| `/github-commits <repo>` | 5 קומיטים אחרונים |

### 📓 Notion
| פקודה | תיאור |
|-------|--------|
| `/notion-add <text>` | יצירת דף חדש ב-Notion |
| `/notion-list` | 8 הדפים הנערכים לאחרונה |
| `/notion-search <query>` | חיפוש בכל ה-workspace |

### 🎯 ClawHub
| פקודה | תיאור |
|-------|--------|
| `/clawhub <skill> <prompt>` | 25 כישורים + autocomplete חי |
| `/skill-top` | 10 הכישורים הפופולריים |

### ⚙️ Utility
| פקודה | תיאור |
|-------|--------|
| `/schedule <task> [min]` | ביצוע משימה אחרי דחייה + DM עם תוצאה |
| `/help` | רשימת פקודות (ephemeral) |

### 🖱️ Context Menus (קליק ימני)
| שם | פעולה |
|----|--------|
| 🔍 Analyze Message | ניתוח עמוק של ההודעה |
| 🌐 Translate | תרגום לעברית + אנגלית |
| 📝 Summarize | סיכום קצר |
| 💡 Explain Code | הסבר קוד שורה-שורה |

---

## ממשקי המשתמש

### Progress Bar (animated thinking)

כשהבוט מעבד בקשה, מוצג embed מונפש:

```
🧭 Orchestrator חושב...
🟦🟦🟦⬜⬜
5s — מעבד...
```

הקוד:
```python
PROGRESS_FRAMES = ["⬜⬜⬜⬜⬜","🟦⬜⬜⬜⬜","🟦🟦⬜⬜⬜",
                   "🟦🟦🟦⬜⬜","🟦🟦🟦🟦⬜","🟦🟦🟦🟦🟦"]

async def animate_thinking(msg, agent, stop_event):
    frame = 0
    while not stop_event.is_set():
        await asyncio.sleep(1.2)
        frame += 1
        await msg.edit(embed=thinking_embed(agent, frame))
```

### ResponseView Buttons

אחרי כל תשובה:

```
[🔄 שאל שוב]  [🔀 החלף סוכן]  [🗑️ מחק]
```

### Agent Select Menu

אחרי לחיצה על "החלף סוכן":

```
🔄 שאל שוב עם סוכן אחר...  ▼
  🤖 Main      — סוכן כללי
  💻 Coder     — מומחה קוד
  🔍 Research  — חוקר מידע
  📊 Analyze   — מנתח אסטרטגי
  🧭 Orchestrate — מתאם רב-סוכנים
```

### Modals (popup forms)

`/research` ללא ארגומנטים פותח:

```
┌─────────────────────────────────────┐
│  🔍 מחקר מקיף                        │
│                                      │
│  מה לחקור?                           │
│  ┌──────────────────────────────────┐│
│  │ הכנס שאלה או נושא...            ││
│  └──────────────────────────────────┘│
│                                      │
│  עומק המחקר                          │
│  ┌──────────────────────────────────┐│
│  │ קצר / בינוני / מעמיק            ││
│  └──────────────────────────────────┘│
│                          [Submit]    │
└─────────────────────────────────────┘
```

---

## Webhook Personas

כל סוכן שולח הודעות עם זהות Discord נפרדת:

```python
AGENT_PERSONAS = {
    "orchestrator": ("🧭 Orchestrator", "https://avatar_url"),
    "coder":        ("💻 Coder",        "https://avatar_url"),
    "researcher":   ("🔍 Researcher",   "https://avatar_url"),
    "analyzer":     ("📊 Analyzer",     "https://avatar_url"),
    "critic":       ("⚖️ Critic",       "https://avatar_url"),
}

async def send_via_webhook(channel, agent, content, embed):
    name, avatar = AGENT_PERSONAS[agent]
    webhooks = await channel.webhooks()
    wh = next((w for w in webhooks if w.name == "OpenClaw Personas"), None)
    if not wh:
        wh = await channel.create_webhook(name="OpenClaw Personas")
    await wh.send(username=name, avatar_url=avatar, embed=embed)
```

**תוצאה ב-Discord:**

```
🧭 Orchestrator  [APP]   ← synthesis הסופי (FRONT)
💻 Coder         [APP]   ← תשובת ה-coder  (background detail)
🔍 Researcher    [APP]   ← תשובת ה-researcher (background detail)
```

---

## Gateway API — כל ה-Endpoints

Base URL: `http://localhost:4001`

### `POST /chat`
```json
Request:
{
  "user_id":    "123456789",
  "message":    "שלום",
  "agent":      "main",
  "task_type":  "default",
  "channel_id": "987654321",
  "username":   "Yitzi"
}

Response:
{
  "response": "שלום! אני OpenClaw...",
  "model":    "groq-llama-70b",
  "duration": 1.24
}
```

### `POST /orchestrate`
```json
Request: {"user_id":"...","task":"...","agents":null}

Response:
{
  "plan":             "Orchestrator selected: coder, researcher",
  "agents_used":      ["coder","researcher"],
  "agent_responses":  {"coder": {"response":"...","model":"..."}},
  "critic":           {"response":"...","model":"..."},
  "synthesis":        "תשובה סופית מסוכמת...",
  "synthesis_model":  "groq-llama-70b",
  "duration":         8.4
}
```

### `POST /debate`
```json
Request: {"user_id":"...","topic":"..."}
Response: {"pro":{...}, "con":{...}, "verdict":{...}, "duration":6.2}
```

### `POST /swarm`
```json
Request: {"user_id":"...","task":"..."}
Response: {"agents":{"researcher":{...},"coder":{...},"analyzer":{...},"critic":{...}},
           "synthesis":"...","duration":12.1}
```

### `POST /recall`
```json
Request: {"user_id":"...","query":"PostgreSQL","top_k":5}
Response: {"memories":[{"text":"...","score":0.84,"agent":"coder","timestamp":...}]}
```

### `GET /health`
```json
{"status":"ok","version":"2.0","redis":"ok",
 "agents":["orchestrator","coder","researcher","analyzer","critic"]}
```

→ [תיעוד API מלא](docs/API.md)

---

## התקנה מאפס

### דרישות מינימום
- Ubuntu 22.04 (ARM64 or x86_64)
- 8GB RAM+ (24GB מומלץ)
- Python 3.11+
- Redis 7+

### שלב 1 — שרת
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv redis-server git
sudo systemctl enable --now redis
```

### שלב 2 — קוד
```bash
git clone https://github.com/Yklein888/openclaw-discord-ai-system.git ai-system
cd ai-system
python3 -m venv venv && source venv/bin/activate
pip install discord.py fastapi uvicorn httpx aiohttp redis \
  duckduckgo-search pygithub notion-client litellm
```

### שלב 3 — Credentials
```bash
cp .env.example .env
nano .env
# מלא: DISCORD_TOKEN, GEMINI_KEY_1..5, GITHUB_TOKEN, NOTION_TOKEN
```

### שלב 4 — LiteLLM Config
```bash
cp litellm-config.example.yaml litellm-config.yaml
nano litellm-config.yaml
# החלף YOUR_GROQ_API_KEY_HERE, YOUR_GEMINI_KEY_HERE וכו'
```

### שלב 5 — bot.py עדכון Guild ID
```python
# discord-bot/bot.py שורה 20:
GUILD_ID = YOUR_SERVER_ID  # לחץ ימני על השרת → Copy ID
```

### שלב 6 — systemd Services
```bash
sudo cp systemd/ai-gateway.service /etc/systemd/system/
sudo cp systemd/discord-bot.service /etc/systemd/system/
sudo cp systemd/litellm.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now litellm ai-gateway discord-bot
```

### שלב 7 — אימות
```bash
sudo systemctl status discord-bot ai-gateway litellm redis
curl http://localhost:4001/health
journalctl -u discord-bot -f
# ← צריך לראות: "Logged in as OpenClaw | Synced 22 commands"
```

→ [מדריך התקנה מלא](docs/SETUP.md)

---

## משתני סביבה

קובץ: `/home/ubuntu/ai-system/.env`

```env
# ── Discord ──────────────────────────────────────────
DISCORD_TOKEN=MTQ...                 # Bot Token מ-developer portal

# ── Gemini ───────────────────────────────────────────
# 5 keys = rotation אוטומטית, יותר quota חינמי
GEMINI_KEY_1=AIza...
GEMINI_KEY_2=AIza...
GEMINI_KEY_3=AIza...
GEMINI_KEY_4=AIza...
GEMINI_KEY_5=AIza...

# ── GitHub ───────────────────────────────────────────
GITHUB_TOKEN=ghp_...                 # Personal Access Token (repo scope)

# ── Notion ───────────────────────────────────────────
NOTION_TOKEN=secret_...              # Integration Token
NOTION_INBOX_DB=abc123...            # Database ID לשמירת notes
```

**לקבל API Keys:**
- Discord: https://discord.com/developers/applications
- Gemini: https://aistudio.google.com/apikey (חינם, צור 5)
- Groq: https://console.groq.com (חינם, צור 9 accounts)
- GitHub: https://github.com/settings/tokens
- Notion: https://www.notion.so/my-integrations

---

## Services (systemd)

### `ai-gateway.service`
```ini
[Service]
ExecStart=/venv/bin/uvicorn main:app --host 127.0.0.1 --port 4001
EnvironmentFile=/home/ubuntu/ai-system/.env
Restart=always
RestartSec=5
StartLimitIntervalSec=0       ← מנסה שוב לנצח, ללא הגבלה
```

### `discord-bot.service`
```ini
[Service]
ExecStart=/venv/bin/python bot.py
EnvironmentFile=/home/ubuntu/ai-system/.env
Restart=always
RestartSec=5
```

### `litellm.service`
```ini
[Service]
ExecStart=/venv/bin/litellm --config litellm-config.yaml --port 4000
Restart=always
RestartSec=5
```

**פקודות ניהול:**
```bash
sudo systemctl restart discord-bot ai-gateway litellm
sudo systemctl status  discord-bot ai-gateway litellm
journalctl -u discord-bot -f          # logs חיים
journalctl -u ai-gateway -n 50        # 50 שורות אחרונות
```

---

## גיבוי ואחזקה

### גיבוי אוטומטי — backup.sh

רץ כל לילה ב-3:00 AM (cron):

```bash
# כמה שומר:
Redis dump.rdb     → backups/redis-YYYY-MM-DD.rdb
.env               → backups/env-YYYY-MM-DD.bak
litellm-config.yaml → backups/litellm-YYYY-MM-DD.yaml
service files       → backups/*.service

# שמירה ל-7 ימים אחורה
# log: /var/log/openclaw-backup.log
```

### דיסק (שרת Oracle)

```bash
df -h                                  # בדיקת מצב דיסק
pip3 cache purge                       # פינוי pip cache
sudo apt autoremove && apt clean       # פינוי apt
du -sh /home/ubuntu/ai-system/* | sort -rh | head -10
```

### Redis Memory

```bash
redis-cli info memory | grep used_memory_human
redis-cli --scan --pattern 'ctx:*' | wc -l   # כמה contexts
redis-cli --scan --pattern 'longmem:*' | wc -l # כמה memories
```

---

## פתרון תקלות

### הבוט לא מגיב

```bash
journalctl -u discord-bot -n 50
# צריך לראות: "Logged in as OpenClaw" + "Synced 22 commands"
# אם לא → בדוק DISCORD_TOKEN ב-.env
```

### "כל המודלים נכשלו"

```bash
sudo systemctl status litellm
journalctl -u litellm -n 20 | grep -i 'error\|yaml\|fail'
# בעיה נפוצה: YAML שבור ב-litellm-config.yaml
python3 -c "import yaml; yaml.safe_load(open('litellm-config.yaml').read()); print('OK')"
```

### Gateway לא עונה

```bash
curl http://localhost:4001/health
# אם timeout → sudo systemctl restart ai-gateway
# בדוק: journalctl -u ai-gateway -n 30
```

### Webhook Personas לא עובד

```bash
# הבוט צריך הרשאת "Manage Webhooks"
# Discord → Server Settings → Roles → OpenClaw → Manage Webhooks ✅
```

### דיסק מלא

```bash
df -h
pip3 cache purge
sudo apt autoremove -y && sudo apt clean
find /home/ubuntu/ai-system -name '*.log' -size +10M -delete
find /home/ubuntu/ai-system/backups -mtime +7 -delete
```

---

## מדריכים מפורטים

| מדריך | תיאור |
|-------|--------|
| [ARCHITECTURE.md](docs/ARCHITECTURE.md) | ארכיטקטורה מפורטת עם דיאגרמות |
| [COMMANDS.md](docs/COMMANDS.md) | כל 22 הפקודות עם דוגמאות |
| [API.md](docs/API.md) | Gateway API reference מלא |
| [MEMORY.md](docs/MEMORY.md) | מערכת הזיכרון — 3 layers |
| [SETUP.md](docs/SETUP.md) | מדריך התקנה מלא צעד-אחר-צעד |

---

## Infrastructure

| פרמטר | ערך |
|-------|-----|
| שרת | Oracle Cloud ARM64 Ubuntu 22.04 |
| IP | 129.159.158.110 |
| RAM / CPU | 24GB / 4 vCPU |
| Python | 3.11 + venv |
| Process manager | systemd (Restart=always) |
| Cache | Redis 7 (localhost) |
| AI Proxy | LiteLLM port 4000 |
| Gateway | FastAPI/Uvicorn port 4001 |
| SSH user | ubuntu |

---

*OpenClaw AI System © 2026 — Private deployment on Oracle Cloud*  
*Built with: Discord.py · FastAPI · LiteLLM · Redis · Gemini · Groq · Cerebras*
