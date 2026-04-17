"""
OpenClaw Agent Workflow - Phase 22
Smart routing with conversation context.
"""
import redis
import json

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

AGENT_KEYWORDS = {
    "coder": ["code", "python", "javascript", "function", "api", "debug", "fix", "build"],
    "researcher": ["search", "find", "what is", "how to", "info", "research", "fact"],
    "analyzer": ["analyze", "compare", "pros", "cons", "swot", "strategy", "recommend"],
    "critic": ["review", "check", "validate", "test", "quality", "improve", "bug", "error"],
    "orchestrator": ["orchestrate", "complex", "multiple", "plan", "manage", "project"]
}

def get_user_state(user_id: str):
    key = f"openclaw:state:{user_id}"
    data = r.get(key)
    if data:
        return json.loads(data)
    return {"active_task": None, "last_agent": None, "context": [], "continuation_count": 0}

def save_user_state(user_id: str, state: dict):
    key = f"openclaw:state:{user_id}"
    r.setex(key, 86400, json.dumps(state))

def add_to_context(user_id: str, role: str, content: str):
    state = get_user_state(user_id)
    state["context"].append({"role": role, "content": content})
    if len(state["context"]) > 20:
        state["context"] = state["context"][-20:]
    save_user_state(user_id, state)

def route_message(message: str, user_id: str):
    state = get_user_state(user_id)
    msg_lower = message.lower()
    
    # Check for continuation
    continuation_words = ["continue", "carry on", "go on", "and then", "also"]
    is_continuation = any(word in msg_lower for word in continuation_words)
    
    if is_continuation and state.get("active_task"):
        state["continuation_count"] = state.get("continuation_count", 0) + 1
        save_user_state(user_id, state)
        return {
            "intent": "continuation",
            "agent": state.get("last_agent", "orchestrator"),
            "active_task": state.get("active_task"),
            "context": build_context_string(state),
            "reason": "Continuing"
        }
    
    # Score agents
    agent_scores = {}
    for agent, keywords in AGENT_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in msg_lower)
        agent_scores[agent] = score
    
    if max(agent_scores.values()) > 0:
        best_agent = max(agent_scores, key=agent_scores.get)
        state["last_agent"] = best_agent
        state["active_task"] = message
        state["continuation_count"] = 0
        save_user_state(user_id, state)
        return {
            "intent": "new_task",
            "agent": best_agent,
            "active_task": message,
            "context": build_context_string(state),
            "reason": f"Matched: {best_agent}"
        }
    
    state["last_agent"] = "orchestrator"
    state["active_task"] = message
    state["continuation_count"] = 0
    save_user_state(user_id, state)
    return {
        "intent": "new_task",
        "agent": "orchestrator",
        "active_task": message,
        "context": build_context_string(state),
        "reason": "Default"
    }

def build_context_string(state: dict):
    context = state.get("context", [])
    if not context:
        return ""
    recent = context[-6:]
    ctx_str = "\n[History]\n"
    for msg in recent:
        role = "User" if msg["role"] == "user" else "OpenClaw"
        content = msg["content"][:200] + "..." if len(msg["content"]) > 200 else msg["content"]
        ctx_str += f"{role}: {content}\n"
    return ctx_str
