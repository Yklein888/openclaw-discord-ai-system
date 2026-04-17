"""
OpenClaw Agent Workflow System - Phase 22
Smart routing with conversation context and memory.
"""

from typing import Dict, Any, List
import redis
import json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

# ─── Agent Keywords for Smart Routing ────────────────────────────────────────────────
AGENT_KEYWORDS = {
    "coder": [
        "code",
        "python",
        "javascript",
        "function",
        "class",
        "api",
        "debug",
        "fix",
        "build",
        "program",
        "script",
        "run",
        "install",
        "deploy",
    ],
    "researcher": [
        "search",
        "find",
        "what is",
        "how to",
        "who is",
        "info",
        "research",
        "fact",
        "documentation",
        "explain",
    ],
    "analyzer": [
        "analyze",
        "compare",
        "pros",
        "cons",
        "swot",
        "strategy",
        "recommend",
        "decision",
        "best",
        "vs",
        "versus",
    ],
    "critic": [
        "review",
        "check",
        "validate",
        "test",
        "quality",
        "improve",
        "bug",
        "error",
        "issue",
        "problem",
    ],
    "orchestrator": [
        "orchestrate",
        "complex",
        "multiple",
        "plan",
        "manage",
        "project",
        "workflow",
    ],
}


# ─── Conversation State ───────────────────────────────────────────────────────────
def get_user_state(user_id: str) -> Dict[str, Any]:
    key = f"openclaw:state:{user_id}"
    data = r.get(key)
    if data:
        return json.loads(data)
    return {
        "active_task": None,
        "last_agent": None,
        "last_message": None,
        "context": [],  # Last 20 messages
        "continuation_count": 0,
    }


def save_user_state(user_id: str, state: Dict[str, Any]):
    key = f"openclaw:state:{user_id}"
    r.setex(key, 86400, json.dumps(state))  # 24h TTL


def add_to_context(user_id: str, role: str, content: str):
    state = get_user_state(user_id)
    state["context"].append({"role": role, "content": content})
    # Keep last 20 messages
    if len(state["context"]) > 20:
        state["context"] = state["context"][-20:]
    save_user_state(user_id, state)


def clear_context(user_id: str):
    key = f"openclaw:state:{user_id}"
    r.delete(key)


# ─── Smart Routing ──────────────────────────────────────────────────────
def route_message(message: str, user_id: str) -> Dict[str, Any]:
    """Route message to appropriate agent based on keywords and context"""
    state = get_user_state(user_id)
    msg_lower = message.lower()

    # Check if continuation (user is continuing previous task)
    continuation_words = [
        "continue",
        "carry on",
        "go on",
        "and then",
        "also",
        "more",
        "continue",
        "still",
    ]
    is_continuation = any(word in msg_lower for word in continuation_words)

    if is_continuation and state.get("active_task"):
        state["continuation_count"] = state.get("continuation_count", 0) + 1
        save_user_state(user_id, state)
        return {
            "intent": "continuation",
            "agent": state.get("last_agent", "orchestrator"),
            "active_task": state.get("active_task"),
            "context": build_context_string(state),
            "reason": "Continuing previous task",
        }

    # Score each agent by keywords
    agent_scores = {}
    for agent, keywords in AGENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in msg_lower)
        agent_scores[agent] = score

    # Pick best matching agent
    if max(agent_scores.values()) > 0:
        best_agent = max(agent_scores, key=agent_scores.get)
        # Save state for next message
        state["last_agent"] = best_agent
        state["active_task"] = message
        state["continuation_count"] = 0
        save_user_state(user_id, state)
        return {
            "intent": "new_task",
            "agent": best_agent,
            "active_task": message,
            "context": build_context_string(state),
            "reason": f"Matched: {best_agent}",
        }

    # Default to orchestrator
    state["last_agent"] = "orchestrator"
    state["active_task"] = message
    state["continuation_count"] = 0
    save_user_state(user_id, state)
    return {
        "intent": "new_task",
        "agent": "orchestrator",
        "active_task": message,
        "context": build_context_string(state),
        "reason": "Default routing",
    }


def build_context_string(state: Dict[str, Any]) -> str:
    """Build context string from conversation history"""
    context = state.get("context", [])
    if not context:
        return ""

    # Get last 6 messages (3 exchanges)
    recent = context[-6:]
    ctx_str = "\n[ Conversation History ]\n"
    for msg in recent:
        role = "User" if msg["role"] == "user" else "OpenClaw"
        content = (
            msg["content"][:200] + "..."
            if len(msg["content"]) > 200
            else msg["content"]
        )
        ctx_str += f"{role}: {content}\n"
    return ctx_str


# ─── Memory Functions ─────────────────────────────────────────────────────
def save_to_memory(user_id: str, key: str, value: str):
    """Save important info to user's long-term memory"""
    memory_key = f"openclaw:memory:{user_id}:{key}"
    r.set(memory_key, value)


def get_from_memory(user_id: str, key: str) -> str:
    """Get info from user's long-term memory"""
    memory_key = f"openclaw:memory:{user_id}:{key}"
    return r.get(memory_key)


def get_all_memory(user_id: str) -> Dict[str, str]:
    """Get all user's memories"""
    pattern = f"openclaw:memory:{user_id}:*"
    keys = r.keys(pattern)
    memories = {}
    for k in keys:
        key = k.replace(f"openclaw:memory:{user_id}:", "")
        memories[key] = r.get(k)
    return memories
