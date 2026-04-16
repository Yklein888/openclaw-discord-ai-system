# 📋 OpenClaw v2.0 — Full Command Reference

## 🤖 AI Agent Commands

| Command | Agent | Description |
|---------|-------|-------------|
| `/main <prompt>` | 🤖 Main | General conversation, any topic |
| `/coder <prompt>` | 💻 Coder | Write, debug, explain, refactor code |
| `/research [prompt]` | 🔍 Researcher | Deep research (blank → opens Modal) |
| `/analyze [prompt]` | 📊 Analyzer | Strategic analysis (blank → opens Modal) |

## 🧭 Multi-Agent Commands

### `/orchestrate [task]`
Smart orchestrator — leave blank to open Modal with agent selector.
- Orchestrator **automatically decides** which agents to use
- Runs selected agents **in parallel** (asyncio.gather)
- ⚖️ Critic reviews all results for errors and gaps
- 🧭 Orchestrator synthesizes a final perfect answer
- Each agent's response appears via **Webhook Persona** (their own Discord identity)

### `/debate [topic]`
Two agents argue opposite sides, Critic gives verdict.
- 🔍 Researcher argues **FOR**
- 📊 Analyzer argues **AGAINST**
- ⚖️ Critic gives **objective verdict**

### `/swarm <task>`
All 4 agents run simultaneously:
- 🔍 Researcher + 💻 Coder + 📊 Analyzer run in parallel
- ⚖️ Critic reviews combined results
- 🧭 Orchestrator synthesizes everything
- Results shown via Webhook Personas + prominent synthesis embed

## 🔍 Tool Commands

| Command | Description | Notes |
|---------|-------------|-------|
| `/search <query>` | DuckDuckGo web search | Returns 5 results with links |
| `/run <code>` | Sandboxed Python execution | Blocks: os.system, subprocess, socket, exec, eval |
| `/memory [user_id]` | View user memory stats | Own stats if no user_id given |
| `/recall <query>` | Semantic memory search | Cosine similarity, top 5 matches |
| `/store-memory <text>` | Save to long-term memory | Embedded with Gemini text-embedding-004 |

## 📦 GitHub Commands

| Command | Description |
|---------|-------------|
| `/github <owner/repo>` | Repo info: stars, forks, language, issues (autocomplete) |
| `/github-prs <repo> [state]` | List Pull Requests (open/closed/all) |
| `/github-commits <repo>` | Last 5 commits with messages and authors |

## 📓 Notion Commands

| Command | Description |
|---------|-------------|
| `/notion-add <text> [title]` | Create new page in Notion inbox database |
| `/notion-list` | Last 8 recently edited pages |
| `/notion-search <query>` | Full-text search across entire Notion workspace |

## 🎯 ClawHub Commands

| Command | Description |
|---------|-------------|
| `/clawhub <skill> <prompt>` | Run with specific skill (25 available, with live autocomplete) |
| `/skill-top` | Show top 10 most useful skills |

### Available Skills (25)
`hebrew` `code` `research` `analyze` `translate` `summarize` `explain`
`debug` `refactor` `review` `plan` `brainstorm` `math` `story` `marketing`
`email` `social` `security` `devops` `data` `api` `database` `mobile` `web` `ai`

## ⚙️ Utility Commands

| Command | Description |
|---------|-------------|
| `/schedule <task> [minutes]` | Run a task after a delay, sends DM with result |
| `/help` | Full command list (shown only to you) |

---

## 🖱️ Context Menus (Right-Click on any message)

Right-click any Discord message → **Apps** menu:

| Menu Item | Action |
|-----------|--------|
| 🔍 **Analyze Message** | Deep strategic analysis of the message |
| 🌐 **Translate** | Translate to Hebrew + English |
| 📝 **Summarize** | Short, clear summary |
| 💡 **Explain Code** | Line-by-line code explanation |

---

## 🔘 Interactive UI After Every Response

### ResponseView Buttons:
- **🔄 שאל שוב** — Repeat question with same agent
- **🔀 החלף סוכן** — Switch agent (opens select menu)
- **🗑️ מחק** — Delete the response message

### Agent Select Menu:
After any response, one-click switch to: Main / Coder / Research / Analyze / Orchestrate

### Modals (pop-up forms):
| Command | Modal Fields |
|---------|-------------|
| `/research` (no args) | Query + Depth (קצר/בינוני/מעמיק) |
| `/analyze` (no args) | Topic + Optional context |
| `/orchestrate` (no args) | Task + Optional agents list |
| `/debate` (no args) | Topic |

---

## 📺 Channel Auto-Respond Behavior

The bot responds to **every message** without needing `@mention`:

| Channel | Default Agent | Special Behavior |
|---------|--------------|-----------------|
| `#terminal` | — | Auto-detects code blocks → runs Python sandbox |
| `#knowledge` | 🔍 Research | All messages → researcher agent |
| `#clawhub` | Auto | Detects skill from Hebrew/English keywords |
| `#ai-admin` | 🤖 Main | `!reset`, `!stats` admin commands available |
| Any other channel | 🤖 Main | Responds to all messages, no @mention needed |
| DMs | 🤖 Main | Full persistent conversation |

### 🧠 Per-Channel Context Isolation
Context memory is **separate per channel**:
- Your coding project in `#backend` won't bleed into `#marketing`
- Redis key: `ctx:{user_id}:{channel_id}`
- Long-term semantic memory is **global** (shared across all channels)
- User stats/preferences are **global**
