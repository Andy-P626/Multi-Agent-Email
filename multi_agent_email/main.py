import streamlit as st
import requests
import json

# The FastAPI service must be running on localhost:8000
FASTAPI_ENDPOINT = "http://localhost:8000/langfuse_trace"


# ------------------------------------------------------------------
# 1. Build Prompt Function (Unchanged Logic)
# ------------------------------------------------------------------
def build_email_prompt(to: str, subject: str, incoming: str, instructions: str) -> str:
    """
    Constructs a clear, comprehensive prompt for the LLM workflow 
    from the email input fields.
    """
    to = to.strip() or "Unspecified Recipient"
    subject = subject.strip() or "No Subject"
    incoming = incoming.strip() or "No incoming email content provided."
    instructions = instructions.strip() or "Draft a professional and concise reply."

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

# ------------------------------------------------------------------
# 2. Streamlit Interface (Updated Core Logic)
# ------------------------------------------------------------------
def main():
    st.set_page_config(
        page_title="Email Assistant – Langfuse Demo",
        page_icon="📧",
        layout="wide",
    )

    st.title("📧 Multi-Agent Email Assistant (Streamlit)")
    st.caption(
        "Client interface calling the **FastAPI backend** running on `localhost:8000/langfuse_trace`."
    )

    # --- Instructions moved to sidebar ---
    st.sidebar.header("⚠️ Required Setup")
    st.sidebar.markdown(
        """
        You **MUST** run the backend API separately for this app to work.
        
        **1. Run the FastAPI Server:**
        
        ```bash
        python main.py
        ```
        
        **2. Run the Streamlit Client:**
        
        ```bash
        streamlit run app/streamlit_app.py
        ```
        The server handles Langfuse initialization and the LLM call.
        """
    )


    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.subheader("✉️ Received Email Details")
        to = st.text_input("Recipient (To)", placeholder="e.g., client@company.com", key="to_input")
        subject = st.text_input("Subject", placeholder="e.g., Partnership Proposal", key="subject_input")
        incoming_email = st.text_area(
            "Content of the Received Email (Copy/Paste)",
            height=260,
            placeholder="Paste the email content you need to reply to here...",
            key="incoming_email_input"
        )

    with col_right:
        st.subheader("🧠 Instructions for the Reply")
        instructions = st.text_area(
            "Style / Constraints",
            height=260,
            value="Professional, clear, and concise reply, written in French.",
            key="instructions_input"
        )
        st.markdown("---")
        show_raw = st.checkbox(
            "Show Raw JSON Response (from the backend)",
            value=True,
        )
        run_button = st.button("🚀 Generate Email Reply", use_container_width=True, type="primary")

    st.markdown("---")

    if run_button:
        if not incoming_email.strip():
            st.warning("Please paste the content of the received email to continue.")
            return

        # 1. Build the LLM prompt
        prompt = build_email_prompt(to=to, subject=subject, incoming=incoming_email, instructions=instructions)

        # 2. Run the workflow by calling the HTTP API
        with st.spinner(f"Calling FastAPI at {FASTAPI_ENDPOINT}..."):
            try:
                # Prepare the data payload for the API
                data = json.dumps({"prompt": prompt})

                # Send the POST request to the FastAPI endpoint
                response = requests.post(
                    FASTAPI_ENDPOINT,
                    headers={"Content-Type": "application/json"},
                    data=data,
                    timeout=60 # Increased timeout for long LLM calls
                )

                if response.status_code == 200:
                    result = response.json()
                    st.success("✅ Workflow completed and API responded successfully!")
                else:
                    st.error(f"❌ API Error: Status Code {response.status_code}")
                    st.json(response.json())
                    return

            except requests.exceptions.ConnectionError:
                st.error(
                    "❌ Connection Error: Could not connect to the FastAPI service at `http://localhost:8000`. "
                    "**Action Required:** Please ensure you ran `python main.py` in a separate terminal."
                )
                return
            except Exception as e:
                st.error(f"An unexpected error occurred: {e}")
                return

        # --------- Extract and Display the Response Body ---------
        email_body = result.get("response") # Use .get() for safety

        st.subheader("✍️ Proposed Reply Draft")

        final_subject = subject.strip() or "(No Subject)"
        final_subject = f"Re: {final_subject}"

        st.markdown(f"**To :** {to or '(unspecified)'}")
        st.markdown(f"**Subject :** {final_subject}")
        st.markdown("---")

        if email_body:
            st.code(email_body, language="markdown")
        else:
            st.info("The API did not return a response body.")

        # --------- Optional Display of Raw JSON ---------
        if show_raw:
            st.markdown("---")
            st.subheader("📦 Raw Backend Response (JSON)")
            st.json(result)

if __name__ == "__main__":
    main()