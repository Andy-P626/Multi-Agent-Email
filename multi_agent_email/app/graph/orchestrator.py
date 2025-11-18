from app.agents.intent import classify_intent
from app.agents.retriever import retrieve_context
from app.agents.external_tool import fetch_external_info
from app.agents.drafter import draft_email
from app.agents.safety import review_safety
from app.memory import append_event
from app.models import (
    EmailTask,
    DraftEmail,
    SafetyReport,
    FinalEmail,
    TaskLogEntry,
    RetrievedContext,
)
from app.services.logging_service import log_task
from app.services.email_sender import send_email


class Orchestrator:
    def __init__(self) -> None:
        pass

    def create_draft(self, task: EmailTask):
        intent = classify_intent(task)
        context, needs_external = retrieve_context(task, intent)

        external_info = None
        routing_decision = {
            "needs_external": needs_external,
            "intent": intent,
            "context_confidence": context.confidence,
        }
        if needs_external:
            external_info = fetch_external_info(task, intent)
            routing_decision["external_called"] = True
        else:
            routing_decision["external_called"] = False

        draft = draft_email(task, context, external_info)
        safety = review_safety(task, draft)

        append_event(
            task.session_id,
            {
                "step": "draft_created",
                "intent": intent,
                "context_confidence": context.confidence,
                "needs_external": needs_external,
            },
        )

        return draft, safety, routing_decision, context, external_info

    def approve_and_send(
        self,
        task: EmailTask,
        draft: DraftEmail,
        safety: SafetyReport,
        routing_decision: dict,
        context: RetrievedContext,
        external_info: str | None,
        send: bool = True,
    ) -> FinalEmail:
        if not safety.approved:
            raise ValueError(f"Draft non approuvé par l'agent Safety : {safety.issues}")

        final_email = FinalEmail(
            recipient=task.recipient,
            subject=draft.subject,
            body=safety.redacted_body,
        )

        if send:
            send_email(final_email)

        entry = TaskLogEntry(
            session_id=task.session_id,
            task=task,
            intent=routing_decision.get("intent", {}),
            context=context,
            external_info=external_info,
            draft=draft,
            safety=safety,
            final_email=final_email,
            extra={"routing_decision": routing_decision},
        )
        log_task(entry)

        append_event(
            task.session_id,
            {
                "step": "email_sent",
                "recipient": str(final_email.recipient),
            },
        )

        return final_email
