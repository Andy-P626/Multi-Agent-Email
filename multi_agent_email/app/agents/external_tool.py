from typing import Optional

import requests

from app.config import get_settings
from app.models import EmailTask


def fetch_external_info(task: EmailTask, intent: dict) -> Optional[str]:
    settings = get_settings()

    # Si pas configuré, on renvoie un texte simulé
    if not settings.news_api_url or not settings.news_api_key:
        return f"[External stub] Synthèse de marché simulée pour : '{task.task_description}'."

    try:
        params = {
            "q": "market pricing" if intent.get("label") == "pricing_request" else task.task_description,
            "pageSize": 3,
            "apiKey": settings.news_api_key,
            "language": "en",
        }
        response = requests.get(settings.news_api_url, params=params, timeout=5)
        response.raise_for_status()
        data = response.json()
        articles = data.get("articles", [])

        if not articles:
            return "[External] Aucun article pertinent trouvé."

        lines = ["[External] Résumé des actualités pertinentes :"]
        for art in articles[:3]:
            title = art.get("title", "")
            source = (art.get("source") or {}).get("name", "")
            lines.append(f"- {title} ({source})")
        return "\n".join(lines)

    except Exception as exc:
        return f"[External error] Impossible d'appeler l'API externe : {exc}"
