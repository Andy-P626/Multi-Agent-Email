from fastapi import FastAPI, Depends

from ..graph.orchestrator import Orchestrator
from ..models import EmailTask, FinalEmail


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
