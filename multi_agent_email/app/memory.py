import json
from pathlib import Path

from app.models import SessionMemory


SESSIONS_DIR = Path("data/sessions")
SESSIONS_DIR.mkdir(parents=True, exist_ok=True)


def _session_path(session_id: str) -> Path:
    return SESSIONS_DIR / f"{session_id}.json"


def load_session(session_id: str) -> SessionMemory:
    path = _session_path(session_id)
    if not path.exists():
        return SessionMemory()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return SessionMemory(**data)
    except Exception:
        return SessionMemory()


def save_session(session_id: str, memory: SessionMemory) -> None:
    path = _session_path(session_id)
    path.write_text(memory.model_dump_json(), encoding="utf-8")


def append_event(session_id: str, event: dict) -> None:
    mem = load_session(session_id)
    mem.history.append(event)
    save_session(session_id, mem)
