# 🤖 OpenClaw Discord AI System v2.0

> **Production-grade multi-agent AI system** built on Oracle Cloud, powered by Discord.py 2.5+ with Webhook Personas, Modals, Context Menus, Autocomplete, animated progress bars, and a 5-agent Orchestrator architecture.

---

## 🏗️ Architecture Overview

```
Discord Users
    │
    ▼
Discord Bot (bot.py) ──── Discord API
    │  22 slash commands
    │  4 context menus (right-click)
    │  Webhook Personas (per-agent identity)
    │  Modals, Select menus, Progress bars
    │
    ▼
Gateway v2.0 (gateway/main.py)   ← FastAPI on port 4001
    │
    ├── /chat            → LiteLLM → model routing
    ├── /orchestrate     → Orchestrator + N agents parallel + Critic + Synthesis
    ├── /debate          → PRO agent vs CON agent → Critic verdict
    ├── /swarm           → 3 agents parallel + Critic + Synthesis
    ├── /vision          → Gemini Flash vision
    ├── /search          → DuckDuckGo
    ├── /run-code        → Sandboxed Python exec
    ├── /recall          → Semantic memory search (cosine similarity)
    ├── /store-memory    → Manual long-term memory
    ├── /github/*        → GitHub API (PyGitHub)
    └── /notion/*        → Notion API
    │
    ▼
LiteLLM Proxy (port 4000)   ← unified OpenAI-compatible API
    │
    ├── groq-llama-70b       (9 API keys, round-robin)
    ├── groq-llama-8b        (7 keys — ultra-fast)
    ├── cerebras-llama-70b   (4 keys — 2000 tok/s)
    ├── gemini-flash         (5 keys — vision + long ctx)
    ├── gemini-2.5-flash     (new — best reasoning)
    ├── deepseek-r1          (new — chain-of-thought)
    ├── qwen-1m              (new — 1M token context)
    ├── nemotron-120b        (new — 120B quality)
    ├── mistral-large        (2 keys)
    └── openrouter-auto      (4 keys — fallback)
    │
    ▼
Redis (localhost:6379)
    ├── ctx:{user_id}        → conversation context (20 turns)
    ├── mem:{user_id}        → user stats & preferences
    └── longmem:{user_id}:N  → semantic memory entries (embeddings)
```

---

## 🖥️ Infrastructure

| Component | Details |
|-----------|---------|
| **Server** | Oracle Cloud ARM64 Ubuntu 22.04 |
| **IP** | `129.159.158.110` |
| **RAM/CPU** | 24GB / 4 vCPU |
| **SSH User** | `ubuntu` |
| **Services** | `discord-bot.service`, `ai-gateway.service`, `litellm.service` |
| **Process Manager** | systemd with `Restart=always` |
| **Reverse Proxy** | ngrok (public tunnel) |
| **Cache/Memory** | Redis 7 |
| **Python** | 3.11 + venv at `/home/ubuntu/ai-system/venv` |

---

## 🤖 Agent System

### 5 Specialized Agents

| Agent | Emoji | Role | Task Type |
|-------|-------|------|-----------|
| **Orchestrator** | 🧭 | Plans strategy, synthesizes final answer | default |
| **Coder** | 💻 | Writes, debugs, explains code | code |
| **Researcher** | 🔍 | Deep factual research, cites sources | default |
| **Analyzer** | 📊 | SWOT, pros/cons, strategic analysis | analysis |
| **Critic** | ⚖️ | Reviews errors, logic gaps, quality | analysis |

### Smart Task Routing

```python
TASK_MODELS = {
    "code":     ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "reason":   ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "speed":    ["groq-llama-70b", "groq-llama-8b", "cerebras-llama-70b"],
    "analysis": ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "vision":   ["gemini-flash"],
    "default":  ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
}
```
Each task type tries models in order — automatic fallback if one fails.

---

## 📋 Discord Commands (22 total)

### 🤖 AI Agents
| Command | Description |
|---------|-------------|
| `/main <prompt>` | Chat with main AI agent |
| `/coder <prompt>` | Code specialist — write, debug, explain |
| `/research [prompt]` | Deep research (empty = Modal with depth selector) |
| `/analyze [prompt]` | Strategic analysis (empty = Modal with context field) |

### 🧭 Multi-Agent
| Command | Description |
|---------|-------------|
| `/orchestrate [task]` | Smart orchestrator — auto-selects agents, runs parallel, Critic reviews, synthesizes |
| `/debate [topic]` | PRO vs CON debate with Critic verdict |
| `/swarm <task>` | All 4 agents in parallel + Critic + synthesis |

### 🔍 Tools
| Command | Description |
|---------|-------------|
| `/search <query>` | DuckDuckGo web search |
| `/run <code>` | Execute Python in sandbox |
| `/memory [user_id]` | View user memory/stats |
| `/recall <query>` | Semantic memory search (cosine similarity) |
| `/store-memory <text>` | Manually save long-term memory |

### 📦 GitHub
| Command | Description |
|---------|-------------|
| `/github <owner/repo>` | Repository info (with autocomplete) |
| `/github-prs <repo>` | List Pull Requests |
| `/github-commits <repo>` | Last 5 commits |

### 📓 Notion
| Command | Description |
|---------|-------------|
| `/notion-add <text>` | Create Notion page |
| `/notion-list` | Recent pages |
| `/notion-search <query>` | Search Notion |

### 🎯 ClawHub
| Command | Description |
|---------|-------------|
| `/clawhub <skill> <prompt>` | 25 skills with live autocomplete |
| `/skill-top` | Top skills list |

### 📋 Misc
| Command | Description |
|---------|-------------|
| `/schedule <task> [minutes]` | Delayed task execution + DM result |
| `/help` | Full command reference (ephemeral) |

---

## 🖱️ Context Menus (Right-click on any message)

| Menu Item | Action |
|-----------|--------|
| 🔍 **Analyze Message** | Deep strategic analysis |
| 🌐 **Translate** | Translate to Hebrew + English |
| 📝 **Summarize** | Short summary |
| 💡 **Explain Code** | Line-by-line code explanation |

---

## 💡 Webhook Personas

Each agent sends messages under its own Discord identity via a single `OpenClaw Personas` webhook:

| Agent | Display Name | Notes |
|-------|-------------|-------|
| orchestrator | 🧭 Orchestrator | Custom avatar |
| coder | 💻 Coder | Custom avatar |
| researcher | 🔍 Researcher | Custom avatar |
| analyzer | 📊 Analyzer | Custom avatar |
| critic | ⚖️ Critic | Custom avatar |

---

## 📺 Channel Handlers

| Channel | Behavior |
|---------|----------|
| `#terminal` | Auto-detect code blocks → sandboxed Python exec → output embed |
| `#ai-admin` | `!reset`, `!stats` admin commands + main AI fallback |
| `#knowledge` | All messages → research agent |
| `#clawhub` | Auto-detect skill from Hebrew/English keywords → best agent |
| DMs | Full conversation with main agent (persistent context) |
| @mention / reply | Triggers main agent + ResponseView buttons |

---

## 🧠 Memory System

### Phase 15: Semantic Long-Term Memory
- Embeddings via **Gemini text-embedding-004** (768 dimensions)
- Stored in Redis with 30-day TTL (max 200 entries/user)
- **Cosine similarity** search at retrieval time
- Min score threshold: 0.40
- Auto-injected into system prompt on every chat call

```
POST /store-memory  { user_id, text, agent }
POST /recall        { user_id, query, top_k }
DELETE /long-memory/{user_id}
```

### Short-Term Context
- Rolling window of 20 messages per user
- Max 3000 chars serialized (auto-trims oldest)

---

## 🌐 Gateway API Reference

### `POST /orchestrate`
```json
{
  "user_id": "123",
  "username": "Yitzi",
  "task": "Build me a full React app with auth",
  "agents": null
}
```
Response:
```json
{
  "plan": "Orchestrator selected: coder, researcher",
  "agents_used": ["coder", "researcher"],
  "agent_responses": {
    "coder": { "response": "...", "model": "groq-llama-70b" },
    "researcher": { "response": "...", "model": "cerebras-llama-70b" }
  },
  "critic": { "response": "...", "model": "groq-llama-70b" },
  "synthesis": "Final combined answer...",
  "synthesis_model": "groq-llama-70b",
  "duration": 8.4
}
```

### `POST /debate`
```json
{ "user_id": "123", "username": "Yitzi", "topic": "Will AI replace developers?" }
```
Response: `pro`, `con`, `verdict`, `duration`

### `POST /swarm`
```json
{ "user_id": "123", "username": "Yitzi", "task": "..." }
```
Response: `agents` (researcher/coder/analyzer/critic), `synthesis`, `duration`

### `POST /chat`
```json
{
  "user_id": "123",
  "message": "Hello",
  "agent": "coder",
  "task_type": "code",
  "username": "Yitzi"
}
```

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
Returns all agents with emoji and system prompt preview.

---

## 📁 Project Structure

```
/home/ubuntu/ai-system/
├── discord-bot/
│   └── bot.py                  ← Discord bot v2.0 (22 commands)
├── gateway/
│   └── main.py                 ← FastAPI gateway v2.0
├── litellm-config.yaml         ← LiteLLM model config (14+ models)
├── .env                        ← All credentials (never commit!)
├── backup.sh                   ← Daily backup cron script
├── backups/                    ← Redis dumps + config backups
└── venv/                       ← Python virtualenv

/etc/systemd/system/
├── discord-bot.service
├── ai-gateway.service
└── litellm.service
```

---

## 🔧 Setup Guide (Fresh Deploy)

### 1. Install Dependencies
```bash
sudo apt update && sudo apt install -y python3 python3-pip python3-venv redis-server
cd /home/ubuntu && mkdir ai-system && cd ai-system
python3 -m venv venv && source venv/bin/activate
pip install discord.py fastapi uvicorn httpx redis aiohttp \
  duckduckgo-search pygithub notion-client litellm \
  crawl4ai qdrant-client mem0ai
```

### 2. Configure `.env`
```env
DISCORD_TOKEN=your_bot_token
GEMINI_KEY_1=AIza...
GEMINI_KEY_2=AIza...
GEMINI_KEY_3=AIza...
GEMINI_KEY_4=AIza...
GEMINI_KEY_5=AIza...
GITHUB_TOKEN=ghp_...
NOTION_TOKEN=secret_...
NOTION_INBOX_DB=your_database_id
```

### 3. systemd Services
See `discord-bot.service`, `ai-gateway.service`, `litellm.service` in repo.
All use `EnvironmentFile=/home/ubuntu/ai-system/.env` and `Restart=always`.

### 4. Start
```bash
sudo systemctl daemon-reload
sudo systemctl enable --now redis litellm ai-gateway discord-bot
```

### 5. Verify
```bash
sudo systemctl status discord-bot ai-gateway litellm
curl http://localhost:4001/health
journalctl -u discord-bot -f
```

---

## 🔑 Required API Keys

| Service | Purpose | Free? |
|---------|---------|-------|
| Discord Bot Token | Bot auth | ✅ Free |
| Groq API (9 keys) | LLaMA 70B fast inference | ✅ 6k req/day |
| Cerebras API (4 keys) | 2000 tok/s LLaMA | ✅ Free tier |
| Gemini API (5 keys) | Vision + embeddings | ✅ Free tier |
| OpenRouter (4 keys) | DeepSeek R1, Nemotron, fallback | 💰 Pay per token |
| Mistral API (2 keys) | Mistral Large | ✅ Free tier |
| GitHub PAT | Repo operations | ✅ Free |
| Notion Integration | Notes management | ✅ Free |

---

## 💾 Backup System

Cron at 3:00 AM UTC daily:
```bash
/home/ubuntu/ai-system/backup.sh
```
Backs up: Redis dump, `.env`, `litellm-config.yaml`, service files.
Retention: 7 days. Logs to `/var/log/openclaw-backup.log`.

---

## 🔐 Security

- Redis `127.0.0.1:6379` only — never exposed externally
- LiteLLM protected by master key
- Gateway `127.0.0.1:4001` — internal only (ngrok for public)
- Code sandbox blocks: `os.system`, `subprocess`, `socket`, `exec`, `eval`
- SSH key auth only

---

## 🚀 v1 → v2 Improvements

| Feature | v1 | v2 |
|---------|----|----|
| Commands | 20 | 22 |
| Agents | 3 | 5 (+Orchestrator +Critic) |
| Model routing | Fixed | Task-based auto-routing |
| UI | Embeds only | Modals + Select menus + Progress bars |
| Agent identity | Single bot | Webhook Personas |
| Context menus | None | 4 right-click actions |
| Autocomplete | None | /github, /clawhub |
| Backup | None | Daily cron |
| Models | 10 | 14 (+DeepSeek R1, Qwen 1M, Gemini 2.5, Nemotron) |

---

## 🛠️ Quick Reference

```bash
# SSH
ssh -i oracle-key.pem ubuntu@129.159.158.110

# Service status
sudo systemctl status discord-bot ai-gateway litellm

# Live logs
journalctl -u discord-bot -f

# Restart all
sudo systemctl restart discord-bot ai-gateway litellm

# Test gateway
curl http://localhost:4001/health

# Manual backup
/home/ubuntu/ai-system/backup.sh
```

---

*OpenClaw AI System © 2026 — Built with Discord.py + FastAPI + LiteLLM + Redis*
