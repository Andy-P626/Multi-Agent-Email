import os
import asyncio

import streamlit as st
from dotenv import load_dotenv

# ------------------------------------------------------------------
# 1. Charger le .env (comme pour ton API FastAPI)
# ------------------------------------------------------------------
load_dotenv()

# Variables nécessaires pour Langfuse (adaptées à ton main.py/config.py)
ENV_KEYS = [
    "LANGFUSE_PUBLIC_KEY",
    "LANGFUSE_SECRET_KEY",
    "LANGFUSE_HOST",
]


def ensure_env_vars():
    """
    Vérifie/complète les variables d'environnement pour Langfuse.
    On ne modifie pas ton code : on se contente de remplir os.environ
    avant d'importer main.py.
    """
    st.sidebar.header("⚙️ Configuration Langfuse")

    for key in ENV_KEYS:
        current = os.getenv(key)

        if current:
            # On montre juste qu'il y en a une sans l'afficher
            st.sidebar.text_input(
                key,
                value="••••••••",
                type="password",
                disabled=True,
                help=f"{key} est déjà définie dans l'environnement / .env.",
            )
        else:
            value = st.sidebar.text_input(
                key,
                type="password",
                help=f"{key} est manquante. Saisis-la pour cette session Streamlit.",
            )
            if value:
                os.environ[key] = value

    st.sidebar.caption(
        "Ces valeurs sont injectées dans os.environ avant l'import de main.py, "
        "pour que config/settings et le client Langfuse soient correctement initialisés."
    )


# ------------------------------------------------------------------
# 2. Fonction qui appelle ton workflow existant (start_llm_workflow)
# ------------------------------------------------------------------
def run_llm_workflow(prompt: str):
    """
    Import tardif de main.start_llm_workflow pour que les variables
    d'environnement aient été définies par ensure_env_vars().
    """
    from multi_agent_email.main import start_llm_workflow  # ✅ nouveau chemin

    return asyncio.run(start_llm_workflow(prompt=prompt))


# ------------------------------------------------------------------
# 3. Interface Streamlit
# ------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="LLM Assistant – Langfuse Demo",
        page_icon="📧",
        layout="centered",
    )

    st.title("📧 LLM Assistant avec Langfuse (Streamlit)")
    st.caption(
        "Interface Streamlit par-dessus ton endpoint FastAPI `/langfuse_trace`, "
        "en appelant directement la fonction `start_llm_workflow`."
    )

    # S'assure que les clés Langfuse sont bien présentes AVANT import de main.py
    ensure_env_vars()

    st.markdown("### 🧾 Prompt à envoyer au workflow")

    prompt = st.text_area(
        "Prompt",
        value="Summarize the latest trends in generative AI.",
        height=150,
        placeholder="Écris ici ce que tu veux envoyer au workflow LLM…",
    )

    if st.button("🚀 Lancer le workflow"):
        if not prompt.strip():
            st.warning("Merci de fournir un prompt.")
            return

        with st.spinner("Exécution du workflow (Langfuse trace en cours)…"):
            try:
                result = run_llm_workflow(prompt.strip())
            except Exception as e:
                st.error(f"❌ Erreur pendant l'exécution : {e}")
                return

        st.success("✅ Workflow terminé")

        st.markdown("### 📦 Réponse brute")
        st.json(result)

        # Si le dict contient un message ou une info utile, on l'affiche joliment
        if isinstance(result, dict):
            if "message" in result:
                st.markdown("### ✍️ Message")
                st.write(result["message"])
            if "trace_id" in result:
                st.markdown("### 🔎 Trace Langfuse")
                st.write(f"Trace ID : `{result['trace_id']}`")


if __name__ == "__main__":
    main()
