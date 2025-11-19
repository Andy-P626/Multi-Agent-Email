import os
import sys
import asyncio
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv

# ------------------------------------------------------------------
# 0. Corriger le chemin d'import pour main.py
# ------------------------------------------------------------------
# Ce fichier est dans :  .../multi_agent_email/app/streamlit_app.py
# On ajoute le dossier parent (.../multi_agent_email) à sys.path
CURRENT_FILE = Path(__file__).resolve()
PROJECT_DIR = CURRENT_FILE.parent.parent  # => .../multi_agent_email

if str(PROJECT_DIR) not in sys.path:
    sys.path.insert(0, str(PROJECT_DIR))

# Maintenant, on peut faire: from main import start_llm_workflow
# ------------------------------------------------------------------
# 1. Chargement des variables d'environnement (.env)
# ------------------------------------------------------------------
ENV_PATH = PROJECT_DIR / ".env"
if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()  # fallback: .env dans le cwd

ENV_KEYS = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
]


def ensure_env_vars():
    st.sidebar.header("⚙️ Configuration Langfuse")
    for key in ENV_KEYS:
        current = os.getenv(key)
        if current:
            st.sidebar.text_input(
                key,
                value="********",
                type="password",
                disabled=True,
                help=f"{key} est déjà définie.",
            )
        else:
            value = st.sidebar.text_input(
                key,
                type="password",
                help=f"{key} est manquante. Saisis-la pour cette session.",
            )
            if value:
                os.environ[key] = value

    st.sidebar.caption(
        "Ces valeurs sont injectées dans os.environ avant l'import de main.py "
        "pour que config/settings et Langfuse soient bien initialisés."
    )


# ------------------------------------------------------------------
# 2. Appel de ton workflow existant (start_llm_workflow dans main.py)
# ------------------------------------------------------------------
def run_llm_workflow(prompt: str):
    """
    Appelle la coroutine async start_llm_workflow définie dans main.py.
    """
    from main import start_llm_workflow  # <-- maintenant visible grâce à sys.path

    return asyncio.run(start_llm_workflow(prompt=prompt))


# ------------------------------------------------------------------
# 3. Interface Streamlit
# ------------------------------------------------------------------
def build_email_prompt(to: str, subject: str, incoming: str, instructions: str) -> str:
    """
    Construit un prompt clair pour le workflow LLM à partir des champs email.
    """
    to = to.strip() or "Destinataire non spécifié"
    subject = subject.strip() or "Sans objet"
    incoming = incoming.strip() or "Aucun email collé."
    instructions = instructions.strip() or "Rédige une réponse professionnelle et concise."

    return f"""
You are an AI email assistant. Draft a clear, professional reply email.

Recipient: {to}
Subject: {subject}

Incoming email:
\"\"\"{incoming}\"\"\"

Additional instructions for your reply:
\"\"\"{instructions}\"\"\"

Write only the body of the reply email (no header metadata). 
Use appropriate greeting and closing.
"""

def main():
    st.set_page_config(
        page_title="Email Assistant – Langfuse Demo",
        page_icon="📧",
        layout="wide",
    )

    st.title("📧 Assistant d’email multi-agents (Streamlit)")
    st.caption(
        "Interface Streamlit par-dessus ton workflow LLM (fonction `start_llm_workflow`). "
        "Ici on l’utilise pour rédiger des réponses d’email."
    )

    # Sidebar Langfuse (inchangé)
    ensure_env_vars()

    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("✉️ Email reçu")

        to = st.text_input(
            "Destinataire (To)",
            placeholder="ex: client@entreprise.com",
        )

        subject = st.text_input(
            "Objet",
            placeholder="ex: Proposition de partenariat",
        )

        incoming_email = st.text_area(
            "Contenu de l’email reçu (copier/coller)",
            height=260,
            placeholder="Colle ici l’email auquel tu veux répondre…",
        )

    with col_right:
        st.subheader("🧠 Instructions pour la réponse")

        instructions = st.text_area(
            "Style / contraintes",
            height=260,
            value="Réponse professionnelle, claire et concise, en français.",
        )

        st.markdown("---")
        show_raw = st.checkbox(
            "Afficher aussi la réponse brute (JSON renvoyé par l’API)",
            value=True,
        )

        run_button = st.button("🚀 Générer la réponse d’email")

    st.markdown("---")

    if run_button:
        if not incoming_email.strip():
            st.warning("Merci de coller au moins le contenu de l’email reçu.")
            return

        prompt = build_email_prompt(
            to=to,
            subject=subject,
            incoming=incoming_email,
            instructions=instructions,
        )

        with st.spinner("Le workflow génère la réponse…"):
            try:
                result = run_llm_workflow(prompt)
            except Exception as e:
                st.error(f"❌ Erreur pendant l'exécution : {e}")
                return

        st.success("✅ Workflow terminé")

        # --------- Extraction du corps de la réponse ---------
        email_body = None

        if isinstance(result, dict):
            # notre version actuelle renvoie un champ "response"
            email_body = result.get("response") or result.get("message")
        elif isinstance(result, str):
            email_body = result
        else:
            email_body = str(result)

        # --------- Affichage du brouillon d’email ---------
        st.subheader("✍️ Brouillon de réponse proposé")

        final_subject = subject.strip() or "(Sans objet)"
        final_subject = f"Re: {final_subject}"

        st.markdown(f"**To :** {to or '(non spécifié)'}")
        st.markdown(f"**Subject :** {final_subject}")
        st.markdown("---")

        if email_body:
            st.write(email_body)
        else:
            st.info("Le workflow n’a pas renvoyé de texte de réponse exploitable.")

        # --------- Affichage optionnel de la réponse brute ---------
        if show_raw:
            st.markdown("---")
            st.subheader("📦 Réponse brute (JSON)")
            st.json(result)
