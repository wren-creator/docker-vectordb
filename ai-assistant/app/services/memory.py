import json
import redis
from datetime import datetime
from app.core.config import settings

_client = None

def get_redis() -> redis.Redis:
    global _client
    if _client is None:
        _client = redis.Redis(
            host=settings.redis_host,
            port=settings.redis_port,
            decode_responses=True,
        )
    return _client


def get_session_key(session_id: str) -> str:
    return f"session:{session_id}"


def load_history(session_id: str) -> list[dict]:
    r = get_redis()
    raw = r.get(get_session_key(session_id))
    if not raw:
        return []
    return json.loads(raw)


def save_message(session_id: str, role: str, content: str):
    r = get_redis()
    key = get_session_key(session_id)
    history = load_history(session_id)
    history.append({
        "role": role,
        "content": content,
        "timestamp": datetime.utcnow().isoformat(),
    })
    r.setex(key, settings.conversation_ttl, json.dumps(history))


def clear_session(session_id: str):
    get_redis().delete(get_session_key(session_id))


def format_history_for_prompt(session_id: str, k: int = 4) -> str:
    """Return the last k exchanges as a readable string for the system prompt."""
    history = load_history(session_id)
    recent = history[-(k * 2):]  # k user+assistant pairs
    if not recent:
        return "No prior conversation in this session."
    lines = []
    for msg in recent:
        role = msg["role"].upper()
        lines.append(f"{role}: {msg['content']}")
    return "\n".join(lines)
