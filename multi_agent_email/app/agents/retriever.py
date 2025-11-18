from typing import Tuple

from app.config import get_settings
from app.models import EmailTask, RetrievedContext
from app.services.vector_store import get_vector_store


def retrieve_context(task: EmailTask, intent: dict) -> Tuple[RetrievedContext, bool]:
    settings = get_settings()
    vs = get_vector_store()

    snippets = vs.similarity_search(query=task.task_description, k=4)
    confidence = 0.2
    if snippets:
        confidence = 0.85

    needs_external = bool(intent.get("needs_external") and confidence < settings.confidence_threshold)

    ctx = RetrievedContext(snippets=snippets, confidence=confidence)
    return ctx, needs_external
