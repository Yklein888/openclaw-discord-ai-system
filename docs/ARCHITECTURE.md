# 🏗️ OpenClaw v2.0 — System Architecture

## High-Level Data Flow

```
User writes message (any channel, no @mention needed)
                │
                ▼
┌───────────────────────────────────────────────────────┐
│              Discord Bot  (discord-bot/bot.py)         │
│              discord.py 2.5+ • Python 3.11             │
│                                                         │
│  on_message():                                          │
│    #terminal   → Python sandbox exec                    │
│    #knowledge  → Research agent                         │
│    #clawhub    → Skill auto-detect                      │
│    #ai-admin   → Admin commands + main agent            │
│    DMs         → Main agent                             │
│    Any channel → Main agent  ← DEFAULT (no tag needed)  │
│                                                         │
│  22 slash commands + 4 context menus                    │
│  Webhook Personas (per-agent Discord identity)          │
│  Animated progress bars while processing                │
│  Modals, Select Menus, Response Buttons                 │
└──────────────────────┬────────────────────────────────┘
                       │ aiohttp POST/GET
                       ▼
┌───────────────────────────────────────────────────────┐
│              Gateway v2.0  (gateway/main.py)           │
│              FastAPI • Uvicorn • localhost:4001          │
│                                                         │
│  POST /chat              → single-agent conversation    │
│  POST /orchestrate       → smart multi-agent routing    │
│  POST /debate            → pro vs con + verdict         │
│  POST /swarm             → 4 agents parallel            │
│  POST /vision            → image analysis               │
│  POST /search            → DuckDuckGo web search        │
│  POST /run-code          → sandboxed Python             │
│  POST /recall            → semantic memory search       │
│  POST /store-memory      → save embedding to Redis      │
│  GET  /memory/{user_id}  → user stats                   │
│  GET  /agents            → list all agents              │
│  GET  /health            → health check                 │
│  GET  /github/*          → GitHub API via PyGitHub      │
│  GET  /notion/*          → Notion API                   │
└────────┬──────────────────────────────┬───────────────┘
         │ HTTP                          │ redis-py
         ▼                               ▼
┌──────────────────┐       ┌──────────────────────────────┐
│  LiteLLM Proxy   │       │          Redis 7              │
│  Port 4000       │       │          localhost:6379        │
│                  │       │                                │
│  14 AI models    │       │  ctx:{uid}:{channel_id}       │
│  auto-fallback   │       │    ↳ per-channel context      │
│  load balanced   │       │    ↳ 20 message rolling window│
│  cost tracking   │       │                                │
└──────────────────┘       │  mem:{uid}                    │
                            │    ↳ global user stats        │
                            │    ↳ request count, lang pref │
                            │                                │
                            │  longmem:{uid}:N              │
                            │    ↳ 768-dim embeddings       │
                            │    ↳ 30-day TTL, max 200      │
                            │    ↳ global (all channels)    │
                            └──────────────────────────────┘
```

---

## Memory Architecture (3 Layers)

### Layer 1 — Per-Channel Short-Term Context
```
Redis key: ctx:{user_id}:{channel_id}

Purpose:
  Each channel has its own conversation thread.
  No context bleed between projects.

Example:
  ctx:123456789:987654321  → your #backend channel history
  ctx:123456789:111222333  → your #marketing channel history

Settings:
  - Rolling window: 20 messages (oldest auto-trimmed)
  - Max serialized size: 3000 characters
  - Injected into every LLM call as conversation history
```

### Layer 2 — Global User Stats
```
Redis key: mem:{user_id}

Tracks across ALL channels:
  - username
  - preferred language (auto-detected, 3-message streak)
  - request_count
  - agent_counts (which agents used most)
  - total_duration
  - total_tokens_est

Used for:
  - /memory command display
  - Personalization
```

### Layer 3 — Global Semantic Long-Term Memory (Phase 15)
```
Redis key: longmem:{user_id}:N

How it works:
  1. Every conversation turn → embedded with Gemini text-embedding-004
  2. Stored as 768-float vector in Redis
  3. On every new request → cosine similarity search
  4. Top 3 relevant memories (score ≥ 0.40) → injected into system prompt

Shared across ALL channels (global knowledge base):
  "The user is building a React app with TypeScript"
  "The user prefers concise Hebrew answers"
  "The user's GitHub username is Yklein888"

Settings:
  - TTL: 30 days per entry
  - Max entries: 200 per user (FIFO rotation)
  - Min similarity threshold: 0.40
```

---

## Agent System Architecture

```
Task arrives at /orchestrate
        │
        ▼
┌─────────────────────────────────────┐
│         Orchestrator 🧭              │
│                                      │
│  Prompt: "Which agents are needed?"  │
│  Model: groq-llama-70b (speed)       │
│  Output: "coder,researcher"          │
└──────────────┬──────────────────────┘
               │ asyncio.gather() ← PARALLEL
    ┌──────────┴──────────┐
    ▼                     ▼
┌─────────┐         ┌──────────────┐
│ Coder   │         │  Researcher  │
│ 💻      │         │  🔍          │
│ model:  │         │  model:      │
│ groq-   │         │  groq-       │
│ llama   │         │  llama       │
└────┬────┘         └──────┬───────┘
     └──────────┬──────────┘
                │ combined results
                ▼
        ┌──────────────┐
        │   Critic  ⚖️  │
        │              │
        │  "Here are   │
        │   errors..." │
        └──────┬───────┘
               │ critique
               ▼
        ┌──────────────┐
        │ Orchestrator │
        │  (synthesis) │
        │              │
        │  Final       │
        │  answer ✅   │
        └──────────────┘
```

### Agent System Prompts
Each agent has a specialized Hebrew system prompt:
- **orchestrator**: Plans strategy, synthesizes, meta-reasoning
- **coder**: Clean code in any language, documented, explained
- **researcher**: Factual, comprehensive, cites sources
- **analyzer**: SWOT, pros/cons, strategic recommendations
- **critic**: Error detection, logic gaps, quality improvement

---

## Model Routing

```python
TASK_MODELS = {
    "code":     ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "reason":   ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "speed":    ["groq-llama-70b", "groq-llama-8b",      "cerebras-llama-70b"],
    "analysis": ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
    "vision":   ["gemini-flash"],
    "default":  ["groq-llama-70b", "cerebras-llama-70b", "gemini-flash"],
}
```

Fallback chain: try model[0] → if error/timeout → try model[1] → try model[2]
All models go through LiteLLM proxy with load balancing across multiple API keys.

---

## Available Models (14 total via LiteLLM)

| Model Name | Provider | API Keys | Speed | Strength |
|------------|---------|----------|-------|----------|
| groq-llama-70b | Groq | 9 keys | ⚡⚡⚡ | General, code |
| groq-llama-8b | Groq | 7 keys | ⚡⚡⚡⚡ | Ultra-fast |
| cerebras-llama-70b | Cerebras | 4 keys | ⚡⚡⚡⚡ | 2000 tok/s |
| gemini-flash | Google | 5 keys | ⚡⚡ | Vision, long context |
| gemini-2.5-flash | Google | 1 key | ⚡⚡ | Best reasoning (2026) |
| deepseek-r1 | OpenRouter | 1 key | ⚡ | Chain-of-thought |
| qwen-1m | OpenRouter | 1 key | ⚡ | 1M token context |
| nemotron-120b | OpenRouter | 1 key | ⚡ | 120B quality |
| mistral-large | Mistral | 2 keys | ⚡⚡ | European multilingual |
| openrouter-auto | OpenRouter | 4 keys | varies | Auto-routing fallback |
| gpt-3.5-turbo | Groq (alias) | 1 key | ⚡⚡⚡ | Compatibility alias |

---

## Webhook Persona System

```
Bot creates "OpenClaw Personas" webhook once per channel.
For each agent response:
  webhook.send(
    username = "💻 Coder",     ← agent display name
    avatar_url = "...",         ← agent avatar image
    embed = agent_embed(...)    ← colored embed with response
  )

Frontend sees:
  🤖 OpenClaw Bot    ← main bot messages, synthesis
  💻 Coder           ← coder agent responses
  🔍 Researcher      ← researcher agent responses
  📊 Analyzer        ← analyzer agent responses
  ⚖️ Critic           ← critic agent responses
  🧭 Orchestrator    ← orchestrator planning messages
```

---

## Service Architecture

```
systemd manages all 4 services:

redis.service         → always-on cache/memory store
    ↓ depends on
litellm.service       → AI model proxy (port 4000)
    ↓ depends on
ai-gateway.service    → FastAPI gateway (port 4001)
    ↓ depends on
discord-bot.service   → Discord bot (connects to Discord API)

All have: Restart=always, RestartSec=5, StartLimitIntervalSec=0
```
