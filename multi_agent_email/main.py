import os
from time import sleep
from typing import Optional

import uvicorn
from fastapi import FastAPI
from langfuse import Langfuse

# Compat avec anciennes/nouvelles versions du SDK Langfuse
try:
    from langfuse.model import CreateSpan  # type: ignore
except ImportError:
    CreateSpan = None

# 1. Initialize FastAPI App
app = FastAPI(title="LLM Assistant API with Langfuse Monitoring")

# 2. Initialize Langfuse Client (directement depuis les variables d'env)
langfuse: Optional[Langfuse] = None
try:
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    host = os.getenv("LANGFUSE_HOST")

    if public_key and secret_key:
        langfuse = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
        print("Langfuse client initialized successfully.")
    else:
        print("Warning: Langfuse keys are not set. Monitoring will be disabled.")
except Exception as e:
    print(f"Failed to initialize Langfuse: {e}")
    langfuse = None


@app.get("/")
def read_root():
    """Simple health check endpoint."""
    return {"message": "LLM Assistant API is running."}


@app.post("/langfuse_trace")
async def start_llm_workflow(
    prompt: str = "Summarize the latest trends in generative AI.",
):
    """
    Simulates a full agent workflow.
    - Si Langfuse est disponible et expose .trace, on envoie les spans.
    - Sinon, on exécute le workflow sans monitoring.
    """

    # Si pas de client Langfuse OU pas de méthode .trace -> pas de monitoring
    if not langfuse or not hasattr(langfuse, "trace"):
        # --- Workflow "simple", sans Langfuse ---
        sleep(0.1)
        retrieved_context = (
            "The latest trends involve large multimodal models and "
            "local deployment optimization."
        )
        sleep(0.5)
        final_response = (
            f"Based on context: {retrieved_context}. Here is a concise summary."
        )

        return {
            "status": "success",
            "trace_id": None,
            "message": "Workflow completed (Langfuse monitoring disabled or unsupported SDK).",
            "response": final_response,
        }

    # --- Ici : version avec Langfuse, si .trace existe vraiment ---
    trace = langfuse.trace(
        name="Agent_Workflow_Execution",
        user_id="user-42",  # Example unique ID for the user
        input=prompt,
    )

    # --- Step 1: Simulate RAG/Database Retrieval (Span 1) ---
    if CreateSpan is not None:
        retrieval_span = trace.span(
            CreateSpan(
                name="ChromaDB_Retrieval",
                input={"query": prompt},
                metadata={"collection": "docs_index"},
            )
        )
    else:
        retrieval_span = trace.span(
            name="ChromaDB_Retrieval",
            input={"query": prompt},
            metadata={"collection": "docs_index"},
        )

    sleep(0.1)  # Simulate network/database time
    retrieved_context = (
        "The latest trends involve large multimodal models and "
        "local deployment optimization."
    )
    retrieval_span.end(output={"context": retrieved_context})

    # --- Step 2: Simulate LLM Call (Span 2) ---
    if CreateSpan is not None:
        llm_span = trace.span(
            CreateSpan(
                name="OpenAI_Call_Summary",
                input={
                    "model": "gpt-4o-mini",
                    "prompt": prompt,
                    "context": retrieved_context,
                },
                metadata={"temperature": 0.7},
            )
        )
    else:
        llm_span = trace.span(
            name="OpenAI_Call_Summary",
            input={
                "model": "gpt-4o-mini",
                "prompt": prompt,
                "context": retrieved_context,
            },
            metadata={"temperature": 0.7},
        )

    sleep(0.5)  # Simulate LLM response time
    final_response = (
        f"Based on context: {retrieved_context}. Here is a concise summary."
    )
    llm_span.end(output={"response": final_response, "token_usage": 150})

    trace.update(status="Success")

    return {
        "status": "success",
        "trace_id": trace.id,
        "message": f"Workflow completed. View trace {trace.id} in Langfuse.",
        "response": final_response,
    }
