from typing import List

from app.models import EmailTask, DraftEmail, SafetyReport

BLOCKLIST = ["mot_interdit1", "secret-confidentiel"]


def review_safety(task: EmailTask, draft: DraftEmail) -> SafetyReport:
    _ = task
    body = draft.body
    issues: List[str] = []

    for word in BLOCKLIST:
        if word in body:
            body = body.replace(word, "[REDACTED]")
            issues.append(f"Terme sensible détecté : {word}")

    approved = not issues
    return SafetyReport(approved=approved, issues=issues, redacted_body=body)
