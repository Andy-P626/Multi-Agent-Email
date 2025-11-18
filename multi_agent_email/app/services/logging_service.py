from pathlib import Path

from app.config import get_settings
from app.models import TaskLogEntry

settings = get_settings()
log_path = Path(settings.log_file)


def log_task(entry: TaskLogEntry) -> None:
    """
    Écrit un log JSONL très simple dans un fichier.
    """
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(entry.model_dump_json() + "\n")
