import json
import logging
from pathlib import Path
from typing import NoReturn, Dict, Any, Optional

from app.models import SessionMemory # Assuming this is a Pydantic model or dataclass with .model_dump_json()

# Set up logging for error visibility
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')


class SessionManager:
    """
    Manages loading, saving, and updating session memory stored as JSON files
    in a dedicated directory.
    """
    SESSIONS_DIR = Path("data/sessions")

    def __init__(self):
        """Initializes the session directory."""
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        logging.info(f"Session directory ensured at: {self.SESSIONS_DIR.resolve()}")

    def _get_path(self, session_id: str) -> Path:
        """Helper to construct the file path for a given session ID."""
        return self.SESSIONS_DIR / f"{session_id}.json"

    def load_session(self, session_id: str) -> SessionMemory:
        """
        Loads session data from a file. If the file is missing or corrupted, 
        returns a new, empty SessionMemory object.
        """
        path = self._get_path(session_id)
        
        if not path.exists():
            # If the file doesn't exist, return a clean starting memory
            return SessionMemory()
        
        try:
            # Load and parse the JSON content
            data: Dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
            return SessionMemory(**data)
        except json.JSONDecodeError as e:
            # Handle corrupted or invalid JSON files
            logging.error(f"Corrupted session file for ID '{session_id}': {e}. Returning new session.")
            return SessionMemory()
        except Exception as e:
            # Handle other potential errors (e.g., file permissions)
            logging.error(f"Unexpected error loading session '{session_id}': {e}. Returning new session.")
            return SessionMemory()

    def save_session(self, session_id: str, memory: SessionMemory) -> NoReturn:
        """
        Writes the entire SessionMemory object to its corresponding JSON file.
        Uses Pydantic's internal JSON serialization method.
        """
        path = self._get_path(session_id)
        try:
            # memory.model_dump_json() serializes the object to a JSON string
            path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logging.error(f"Failed to save session '{session_id}' to disk: {e}")

    def append_event(self, session_id: str, event: Dict[str, Any]) -> NoReturn:
        """
        Loads the session, appends a new event to its history, and saves it.
        This is an inefficient write pattern but is functional for simple memory.
        """
        # 1. Load the current state
        mem: SessionMemory = self.load_session(session_id)
        
        # 2. Modify the state
        # Note: Assuming 'history' is a list attribute in SessionMemory
        mem.history.append(event)
        
        # 3. Save the new state
        self.save_session(session_id, mem)


# Optional: Create a globally accessible instance if needed throughout the app
# session_manager = SessionManager()

# The original function signature for direct use (now just wraps the class method)
def load_session(session_id: str) -> SessionMemory:
    return SessionManager().load_session(session_id)

def save_session(session_id: str, memory: SessionMemory) -> None:
    SessionManager().save_session(session_id, memory)

def append_event(session_id: str, event: Dict[str, Any]) -> None:
    SessionManager().append_event(session_id, event)