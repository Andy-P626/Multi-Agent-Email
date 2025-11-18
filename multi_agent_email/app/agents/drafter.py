from typing import Optional, List

from app.models import EmailTask, RetrievedContext, DraftEmail


def draft_email(
    task: EmailTask,
    context: RetrievedContext,
    external_info: Optional[str] = None,
) -> DraftEmail:
    subject = task.subject_hint or "Synthèse & suivi de notre échange"

    body_lines: List[str] = []
    body_lines.append("Bonjour,")
    body_lines.append("")
    body_lines.append("Je reviens vers vous concernant le sujet suivant :")
    body_lines.append(f"- {task.task_description}")
    body_lines.append("")

    if context.snippets:
        body_lines.append("Éléments de contexte interne pris en compte :")
        for snip in context.snippets[:3]:
            one_line = snip.replace("\n", " ")
            body_lines.append(f"- {one_line[:220]}...")
        body_lines.append("")

    if external_info:
        body_lines.append("Informations externes pertinentes :")
        body_lines.append(external_info)
        body_lines.append("")

    if task.body_hint:
        body_lines.append("Précision fournie :")
        body_lines.append(task.body_hint)
        body_lines.append("")

    body_lines.append("N'hésitez pas à me faire part de vos retours ou ajustements.")
    body_lines.append("")
    body_lines.append("Bien à vous,")
    body_lines.append("Votre assistant exécutif automatisé")

    sources: List[str] = []
    if context.snippets:
        sources.append("vector_db")
    if external_info:
        sources.append("external_tool")

    return DraftEmail(subject=subject, body="\n".join(body_lines), sources=sources)
