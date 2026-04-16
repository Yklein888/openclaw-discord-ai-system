# 🧠 OpenClaw Memory System — Complete Guide

OpenClaw has **3 independent memory layers** that work together to give the AI deep, persistent understanding of each user.

---

## Layer 1 — Per-Channel Short-Term Context

**What it is:** The actual conversation history for each channel.

**Redis key:** `ctx:{user_id}:{channel_id}`

**How it works:**
- Every message you send + every bot response is saved
- Rolling window: **20 messages** (oldest auto-removed)
- Max size: 3000 characters (auto-trims if too long)
- Injected into every LLM call as the conversation `messages` array

**Why per-channel:**
```
You in #backend-project:
  "I'm building a REST API with FastAPI"
  "The database schema has Users and Products tables"

You in #marketing-copy:
  "Write a landing page for a SaaS product"

→ Bot NEVER confuses these contexts.
  #backend knows about FastAPI, #marketing knows about SaaS copy.
```

**Clear a channel's context:**
```
DELETE /memory/{user_id}  ← clears ALL channels for this user
```

---

## Layer 2 — Global User Stats

**What it is:** Metadata about the user, shared across all channels.

**Redis key:** `mem:{user_id}`

**Stores:**
```json
{
  "username": "Yitzi",
  "language": "he",
  "request_count": 247,
  "agent_counts": {
    "coder": 120,
    "main": 80,
    "researcher": 47
  },
  "total_duration": 612.4,
  "total_tokens_est": 85000
}
```

**Language detection:**
- Bot auto-detects Hebrew/English/Arabic from each message
- Uses a "3-message streak" system — language only changes after 3 consecutive messages in a new language (prevents accidental switches)

**View your stats:** `/memory` command

---

## Layer 3 — Global Semantic Long-Term Memory (Phase 15)

**What it is:** Important facts about you, stored as AI embeddings, retrieved by meaning (not keywords).

**Redis key:** `longmem:{user_id}:N`

### How It Works

```
Every conversation turn:
  1. Text = "User asked about React, Bot explained hooks"
  2. Gemini text-embedding-004 converts to 768-float vector
  3. Stored in Redis with 30-day TTL

Next time you ask anything:
  1. Your new question is also embedded
  2. System finds top 3 stored memories by cosine similarity
  3. If similarity ≥ 0.40, memory is injected into system prompt:
     "[זיכרונות רלוונטיים:]
      - User is building React app with TypeScript
      - User prefers short concise answers in Hebrew"
  4. AI responds knowing your history
```

### Why This Matters

Without semantic memory:
```
Day 1: "I'm building a SaaS with Supabase and React"
Day 3: "What's the best auth approach?"
→ Bot has NO idea what tech stack you're using.
```

With semantic memory:
```
Day 1: "I'm building a SaaS with Supabase and React"  ← stored as embedding
Day 3: "What's the best auth approach?"
→ System finds "SaaS with Supabase and React" (similarity: 0.72)
→ Injected into prompt
→ Bot says: "For your Supabase+React stack, use Supabase Auth with..."
```

### Settings
| Setting | Value |
|---------|-------|
| Embedding model | Gemini text-embedding-004 (768 dims) |
| Similarity algorithm | Cosine similarity |
| Min threshold | 0.40 (below this = irrelevant, ignored) |
| Max results injected | 3 per request |
| Max stored per user | 200 entries (FIFO rotation) |
| TTL per entry | 30 days |
| Scope | Global (all channels share this) |

### Manage Memory

```
Save manually:   /store-memory <text>
Search:          /recall <query>
Clear all:       DELETE /long-memory/{user_id}
```

**Example `/recall` output:**
```
🟩🟩🟩🟩⬜ 0.84 | main
User is building a React SaaS with Supabase authentication

🟩🟩🟩⬜⬜ 0.71 | coder
User prefers TypeScript with strict mode

🟩🟩⬜⬜⬜ 0.52 | researcher
User is researching competitor SaaS pricing models
```

---

## Memory Flow Diagram

```
User message arrives
        │
        ▼
┌─────────────────────────────────────┐
│  1. Load channel context            │
│     ctx:{uid}:{channel_id}          │
│     → last 20 messages              │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  2. Search long-term memory         │
│     query_embedding = embed(message)│
│     top3 = cosine_search(all_mems)  │
│     if score ≥ 0.40 → inject        │
└──────────────────┬──────────────────┘
                   │
                   ▼
┌─────────────────────────────────────┐
│  3. Build LLM messages array        │
│     [system_prompt + memories]      │
│     + [channel context history]     │
│     + [current message]             │
└──────────────────┬──────────────────┘
                   │
                   ▼
             LLM responds
                   │
                   ▼
┌─────────────────────────────────────┐
│  4. Save back to channel context    │
│  5. Save turn to long-term memory   │
│     (async, doesn't block response) │
│  6. Update user stats               │
└─────────────────────────────────────┘
```
