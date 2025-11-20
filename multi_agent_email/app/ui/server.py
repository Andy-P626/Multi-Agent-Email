
from fastapi import FastAPI, Depends
from ..graph.orchestrator import Orchestrator
from ..models import EmailTask, FinalEmail
from ..config import get_settings


app = FastAPI(title="Multi-Agent Email & Task Automation Assistant")


def get_orchestrator() -> Orchestrator:
    return Orchestrator()


@app.post("/email/draft", response_model=FinalEmail)
def create_email_draft(
    task: EmailTask,
    orchestrator: Orchestrator = Depends(get_orchestrator),
) -> FinalEmail:
    draft, safety, routing_decision, context, external_info = orchestrator.create_draft(task)
    final_email = orchestrator.approve_and_send(
        task=task,
        draft=draft,
        safety=safety,
        routing_decision=routing_decision,
        context=context,
        external_info=external_info,
        send=False,  # on n'envoie pas l'email pour de vrai
    )
    return final_email



@app.get("/langfuse/trace/{trace_id}")
def resolve_langfuse_trace(trace_id: str):
    """Return a Langfuse trace URL for a given trace_id if the SDK and keys are present.

    This endpoint is intentionally lightweight: it will attempt to initialize the
    Langfuse client using environment keys and return the resolved URL, or
    `{{"trace_url": None}}` if unavailable.
    """
    settings = get_settings()
    try:
        # Import here so the server can run even when langfuse isn't installed.
        from langfuse import Langfuse

        if not (settings.langfuse_public_key and settings.langfuse_secret_key):
            return {"trace_url": None}

        lf = Langfuse(public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key, host=settings.langfuse_host)
        url = lf.get_trace_url(trace_id=trace_id)
        return {"trace_url": url}
    except Exception:
        return {"trace_url": None}
