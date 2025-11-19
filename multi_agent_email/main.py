import os
from typing import Optional

import uvicorn
from fastapi import FastAPI
from langfuse import Langfuse  # toujours optionnel
from openai import OpenAI

# 1. FastAPI app
app = FastAPI(title="LLM Email Assistant API")

# 2. Client Langfuse (optionnel, pas utilisé pour l'instant)
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

# 3. Client OpenAI (vrai LLM)
client = OpenAI(  # la clé est lue dans OPENAI_API_KEY
    api_key=os.getenv("OPENAI_API_KEY"),
)


@app.get("/")
def read_root():
    """Simple health check endpoint."""
    return {"message": "LLM Email Assistant API is running."}


@app.post("/langfuse_trace")
async def start_llm_workflow(
    prompt: str = "Summarize the latest trends in generative AI.",
):
    """
    Workflow principal appelé par Streamlit.

    Il envoie le `prompt` au modèle OpenAI et renvoie un brouillon d'email.
    """

    if not os.getenv("OPENAI_API_KEY"):
        return {
            "status": "error",
            "trace_id": None,
            "message": "OPENAI_API_KEY is not set. Add it to your .env file.",
        }

    # Instructions globales pour le modèle
    instructions = (
        "You are an AI email assistant. "
        "Given the user prompt (which may include an incoming email and constraints), "
        "draft a clear, polite, well-structured reply email body. "
        "Use an appropriate greeting and closing, and respect the language of the prompt."
    )

    try:
        # Appel au vrai LLM (OpenAI Responses API)
        response = client.responses.create(
            model="gpt-4o-mini",  # tu peux changer le modèle si tu veux
            instructions=instructions,
            input=prompt,
        )

        # La lib 2.x expose directement le texte final ici
        email_text = response.output_text

        return {
            "status": "success",
            "trace_id": None,  # on ne fait pas encore de vrai tracking Langfuse
            "message": "Email draft generated successfully.",
            "response": email_text,
        }

    except Exception as e:
        # En cas d'erreur API (clé invalide, quota, etc.)
        return {
            "status": "error",
            "trace_id": None,
            "message": f"LLM call failed: {e}",
        }


# To run the application directly: uvicorn main:app --reload
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
