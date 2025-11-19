# pip install chromadb sentence-transformers pydantic
# session_manager.py
import json
import logging
from pathlib import Path
from typing import NoReturn, Dict, Any, Optional, List

# ---- Ton modèle existant (importe le tien si déjà défini)
# from app.models import SessionMemory
from pydantic import BaseModel, Field

class SessionMemory(BaseModel):
    history: List[Dict[str, Any]] = Field(default_factory=list)

# ---- Logs
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# ---- Chroma & embeddings
import chromadb
from chromadb import ClientAPI
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer


class SessionManager:
    """
    JSON + Vector store:
      - État de session en JSON (compatibilité avec ton code).
      - Indexation/recherche sémantique des événements avec ChromaDB.
    """
    SESSIONS_DIR = Path("data/sessions")
    CHROMA_DIR = Path("data/chroma")
    COLLECTION_NAME = "session_events"
    EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

    def __init__(self):
        # Dossiers
        self.SESSIONS_DIR.mkdir(parents=True, exist_ok=True)
        self.CHROMA_DIR.mkdir(parents=True, exist_ok=True)

        # Chroma client (persistant)
        self.chroma: ClientAPI = chromadb.PersistentClient(
            path=str(self.CHROMA_DIR),
            settings=Settings(anonymized_telemetry=False)
        )

        # Collection (documents = texte des events ; metadatas = session_id, index)
        self.collection = self.chroma.get_or_create_collection(
            name=self.COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"}  # distance métrique
        )

        # Modèle d’embedding (petit, rapide)
        self.encoder = SentenceTransformer(self.EMBEDDING_MODEL)

        logging.info(f"Session dir: {self.SESSIONS_DIR.resolve()}")
        logging.info(f"Chroma dir:   {self.CHROMA_DIR.resolve()}")
        logging.info(f"Collection:   {self.COLLECTION_NAME}")

    # ---------- Fichiers JSON (inchangé)
    def _get_path(self, session_id: str) -> Path:
        return self.SESSIONS_DIR / f"{session_id}.json"

    def load_session(self, session_id: str) -> SessionMemory:
        path = self._get_path(session_id)
        if not path.exists():
            return SessionMemory()
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SessionMemory(**data)
        except json.JSONDecodeError as e:
            logging.error(f"Corrupted session file '{session_id}': {e}. New session returned.")
            return SessionMemory()
        except Exception as e:
            logging.error(f"Unexpected error loading session '{session_id}': {e}. New session returned.")
            return SessionMemory()

    def save_session(self, session_id: str, memory: SessionMemory) -> NoReturn:
        path = self._get_path(session_id)
        try:
            path.write_text(memory.model_dump_json(indent=2), encoding="utf-8")
        except Exception as e:
            logging.error(f"Failed to save session '{session_id}' to disk: {e}")

    # ---------- Indexation Chroma
    def _event_to_doc(self, event: Dict[str, Any]) -> str:
        """
        Transforme un événement en texte indexable.
        Adapte ici selon ta structure (role, content, tool, etc.)
        """
        try:
            return json.dumps(event, ensure_ascii=False)
        except Exception:
            return str(event)

    def _index_event(self, session_id: str, event_idx: int, event: Dict[str, Any]) -> None:
        """
        Crée/MAJ un document vectoriel pour l'événement donné.
        """
        doc_text = self._event_to_doc(event)
        emb = self.encoder.encode([doc_text], normalize_embeddings=True).tolist()

        doc_id = f"{session_id}:{event_idx}"  # ID unique par session + index
        metadata = {
            "session_id": session_id,
            "event_idx": event_idx
        }

        # upsert (idempotent) — remplace si déjà présent
        self.collection.upsert(
            ids=[doc_id],
            documents=[doc_text],
            metadatas=[metadata],
            embeddings=emb
        )

    def append_event(self, session_id: str, event: Dict[str, Any]) -> NoReturn:
        """
        Ajoute un événement dans l'historique JSON et l'indexe dans Chroma.
        """
        mem = self.load_session(session_id)
        mem.history.append(event)
        self.save_session(session_id, mem)

        # Indexation vecteur
        event_idx = len(mem.history) - 1
        try:
            self._index_event(session_id, event_idx, event)
        except Exception as e:
            logging.error(f"Chroma upsert failed for {session_id}:{event_idx} – {e}")

    # ---------- Recherche sémantique
    def search_events(
        self,
        session_id: Optional[str],
        query_text: str,
        top_k: int = 5
    ) -> List[Dict[str, Any]]:
        """
        Recherche sémantique d'événements (dans une session donnée ou globalement).
        Retourne la liste des hits: {id, score, metadata, document}.
        """
        q_emb = self.encoder.encode([query_text], normalize_embeddings=True).tolist()

        where = {"session_id": session_id} if session_id else None
        res = self.collection.query(
            query_embeddings=q_emb,
            n_results=top_k,
            where=where
        )
        # Normalise sortie Chroma -> liste de dicts
        hits = []
        for i in range(len(res.get("ids", [[]])[0])):
            hits.append({
                "id": res["ids"][0][i],
                "score": res["distances"][0][i] if "distances" in res else None,
                "metadata": res["metadatas"][0][i],
                "document": res["documents"][0][i],
            })
        return hits

    # ---------- Utilitaires
    def reindex_session(self, session_id: str) -> None:
        """
        Reconstruit l'index Chroma pour une session (utile si tu as déjà de l'historique).
        """
        mem = self.load_session(session_id)
        for i, ev in enumerate(mem.history):
            self._index_event(session_id, i, ev)

    def delete_session_index(self, session_id: str) -> None:
        """
        Supprime tous les documents de Chroma pour une session.
        """
        # Récupère les ids avec where et supprime
        res = self.collection.get(where={"session_id": session_id})
        ids = res.get("ids", [])
        if ids:
            self.collection.delete(ids=ids)


# ----- Fonctions wrapper (compatibles avec ton interface initiale)
def load_session(session_id: str) -> SessionMemory:
    return SessionManager().load_session(session_id)

def save_session(session_id: str, memory: SessionMemory) -> None:
    SessionManager().save_session(session_id, memory)

def append_event(session_id: str, event: Dict[str, Any]) -> None:
    SessionManager().append_event(session_id, event)

def search_events(session_id: Optional[str], query_text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    return SessionManager().search_events(session_id, query_text, top_k)
