from app.models import EmailTask


def classify_intent(task: EmailTask) -> dict:
    text = task.task_description.lower()

    intent = "general"
    if "follow up" in text or "relance" in text:
        intent = "follow_up"
    elif "merci" in text or "thank you" in text:
        intent = "thank_you"
    elif any(w in text for w in ["prix", "tarif", "pricing", "quote"]):
        intent = "pricing_request"

    urgency = "normal"
    if any(w in text for w in ["urgent", "asap", "dès que possible"]):
        urgency = "high"

    needs_external = any(w in text for w in ["marché", "market", "news"])

    return {
        "label": intent,
        "urgency": urgency,
        "needs_external": needs_external,
    }
