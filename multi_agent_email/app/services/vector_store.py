from functools import lru_cache
from typing import List

import chromadb

from app.config import get_settings


class VectorStore:
    def __init__(self, persist_dir: str) -> None:
        self.client = chromadb.PersistentClient(path=persist_dir)
        self.collection = self.client.get_or_create_collection(name="knowledge")

    def add_documents(self, texts: List[str], metadatas: List[dict], ids: List[str]) -> None:
        self.collection.add(documents=texts, metadatas=metadatas, ids=ids)

    def similarity_search(self, query: str, k: int = 4) -> List[str]:
        if not query.strip():
            return []
        res = self.collection.query(query_texts=[query], n_results=k)
        if not res.get("documents"):
            return []
        return res["documents"][0]


@lru_cache()
def get_vector_store() -> VectorStore:
    settings = get_settings()
    return VectorStore(settings.vector_db_dir)
