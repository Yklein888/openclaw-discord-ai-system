# 🌐 OpenClaw Gateway v2.0 — Full API Reference

Base URL: `http://localhost:4001`

All POST endpoints accept `Content-Type: application/json`.

---

## Core Chat

### `POST /chat`
Single-agent conversation with persistent per-channel context.

**Request:**
```json
{
  "user_id": "123456789",
  "message": "How do I implement a binary search tree?",
  "username": "Yitzi",
  "agent": "coder",
  "task_type": "code",
  "channel_id": "987654321",
  "system_prompt": null
}
```

**Fields:**
| Field | Required | Default | Description |
|-------|----------|---------|-------------|
| user_id | ✅ | — | Discord user ID |
| message | ✅ | — | User's message |
| username | ❌ | null | Display name |
| agent | ❌ | "main" | Agent: main/coder/researcher/analyzer/orchestrator |
| task_type | ❌ | "default" | Routing: default/code/analysis/speed/vision |
| channel_id | ❌ | "global" | Channel ID for per-channel context isolation |
| system_prompt | ❌ | null | Override system prompt |

**Response:**
```json
{
  "response": "A binary search tree is...",
  "model": "groq-llama-70b",
  "duration": 1.24
}
```

---

## Multi-Agent

### `POST /orchestrate`
Smart multi-agent orchestration with automatic agent selection.

**Request:**
```json
{
  "user_id": "123456789",
  "username": "Yitzi",
  "task": "Build a complete REST API with FastAPI and PostgreSQL",
  "agents": null
}
```

Set `agents` to `["coder", "researcher"]` to override auto-selection.

**Response:**
```json
{
  "plan": "Orchestrator selected: coder, researcher",
  "agents_used": ["coder", "researcher"],
  "agent_responses": {
    "coder": {
      "response": "Here's the complete FastAPI code...",
      "model": "groq-llama-70b"
    },
    "researcher": {
      "response": "FastAPI with PostgreSQL best practices...",
      "model": "cerebras-llama-70b"
    }
  },
  "critic": {
    "response": "The code is missing error handling for...",
    "model": "groq-llama-70b"
  },
  "synthesis": "Complete integrated answer combining all agent responses...",
  "synthesis_model": "groq-llama-70b",
  "duration": 8.4
}
```

---

### `POST /debate`
Two agents argue opposite sides, Critic gives verdict.

**Request:**
```json
{
  "user_id": "123456789",
  "username": "Yitzi",
  "topic": "Should all code be written with TypeScript?"
}
```

**Response:**
```json
{
  "pro": {
    "response": "TypeScript provides: 1) Type safety...",
    "model": "groq-llama-70b"
  },
  "con": {
    "response": "TypeScript has downsides: 1) Build overhead...",
    "model": "cerebras-llama-70b"
  },
  "verdict": {
    "response": "Analyzing both sides objectively: TypeScript is beneficial when...",
    "model": "groq-llama-70b"
  },
  "duration": 6.2
}
```

---

### `POST /swarm`
All 4 agents (Researcher + Coder + Analyzer + Critic) run in parallel.

**Request:**
```json
{
  "user_id": "123456789",
  "username": "Yitzi",
  "task": "How should I architect a SaaS subscription system?"
}
```

**Response:**
```json
{
  "agents": {
    "researcher": { "response": "...", "model": "groq-llama-70b" },
    "coder":      { "response": "...", "model": "groq-llama-70b" },
    "analyzer":   { "response": "...", "model": "cerebras-llama-70b" },
    "critic":     { "response": "...", "model": "groq-llama-70b" }
  },
  "synthesis": "Complete combined answer...",
  "model": "groq-llama-70b",
  "duration": 12.1
}
```

---

## Vision

### `POST /vision`
Analyze images using Gemini Flash.

**Request:**
```json
{
  "user_id": "123456789",
  "username": "Yitzi",
  "image_url": "https://example.com/screenshot.png",
  "text": "What error does this screenshot show?"
}
```

**Response:**
```json
{
  "response": "The screenshot shows a TypeError: Cannot read property...",
  "model": "gemini-flash-vision",
  "duration": 2.1
}
```

---

## Search & Code

### `POST /search`
DuckDuckGo web search.

**Request:** `{ "query": "latest Python 3.13 features", "max_results": 5 }`

**Response:**
```json
{
  "results": [
    {
      "title": "Python 3.13 Release Notes",
      "url": "https://docs.python.org/3.13/whatsnew/",
      "body": "Python 3.13 includes..."
    }
  ],
  "count": 5,
  "duration": 0.8
}
```

---

### `POST /run-code`
Execute Python code in a sandboxed subprocess.

**Request:** `{ "code": "print(sum(range(100)))", "timeout": 10 }`

**Response:**
```json
{ "success": true, "output": "4950", "exit_code": 0, "duration": 0.3 }
```

**Blocked patterns:** `os.system`, `subprocess`, `shutil.rmtree`, `socket`, `ftplib`, `smtplib`, `__import__`, `importlib`, `exec(`, `eval(`

---

## Memory System

### `POST /store-memory`
Save text to long-term semantic memory with embedding.

**Request:** `{ "user_id": "123", "text": "I prefer TypeScript over JavaScript", "agent": "main" }`

**Response:** `{ "status": "stored" }`

---

### `POST /recall`
Search semantic memory with cosine similarity.

**Request:** `{ "user_id": "123", "query": "programming preferences", "top_k": 5 }`

**Response:**
```json
{
  "memories": [
    {
      "text": "I prefer TypeScript over JavaScript",
      "score": 0.847,
      "agent": "main",
      "timestamp": 1744800000
    }
  ],
  "count": 1
}
```

---

### `GET /memory/{user_id}`
Get user statistics and memory info.

**Response:**
```json
{
  "user_id": "123",
  "username": "Yitzi",
  "language": "he",
  "request_count": 142,
  "favorite_agent": "coder",
  "agent_counts": { "coder": 80, "main": 40, "researcher": 22 },
  "avg_duration": 2.3,
  "total_duration": 326.6,
  "total_tokens_est": 45200,
  "context_messages": 3
}
```

---

### `DELETE /memory/{user_id}`
Reset all context and stats for a user.

### `DELETE /memory`
Reset ALL users' memory and context.

### `DELETE /long-memory/{user_id}`
Clear only semantic (long-term) memory for a user.

---

## GitHub

### `GET /github/repo/{owner}/{repo_name}`
```
GET /github/repo/facebook/react
```
Returns: name, description, stars, forks, issues, language, branch, url, private

### `GET /github/prs/{owner}/{repo_name}?state=open`
Returns list of Pull Requests.

### `GET /github/commits/{owner}/{repo_name}`
Returns last 5 commits with sha, message, author, date.

---

## Notion

### `POST /notion/add`
```json
{ "text": "Meeting notes...", "title": "Team Meeting 2026-04-16" }
```
Returns: `{ "status": "created", "page_id": "...", "url": "..." }`

### `GET /notion/list`
Returns 8 most recently edited pages.

### `GET /notion/search?q=query`
Full-text search across workspace.

---

## Health & Meta

### `GET /health`
```json
{
  "status": "ok",
  "version": "2.0",
  "redis": "ok",
  "agents": ["orchestrator", "coder", "researcher", "analyzer", "critic"],
  "task_models": ["code", "reason", "speed", "analysis", "vision", "default"]
}
```

### `GET /agents`
```json
{
  "agents": [
    { "name": "orchestrator", "emoji": "🧭", "system_preview": "אתה מנהל AI חכם..." },
    { "name": "coder",        "emoji": "💻", "system_preview": "אתה מומחה קוד..." },
    { "name": "researcher",   "emoji": "🔍", "system_preview": "אתה חוקר מומחה..." },
    { "name": "analyzer",     "emoji": "📊", "system_preview": "אתה מנתח אסטרטגי..." },
    { "name": "critic",       "emoji": "⚖️", "system_preview": "אתה מבקר מומחה..." }
  ]
}
```

### `GET /stats/{user_id}`
Alias for `GET /memory/{user_id}`.
