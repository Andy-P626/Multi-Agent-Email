import gradio as gr
import requests
import json
from typing import Dict, Any, Tuple

# The FastAPI service must be running on localhost:8000
# Use the /email/draft endpoint exposed by the FastAPI server
FASTAPI_ENDPOINT = "http://localhost:8000/email/draft"


# ------------------------------------------------------------------
# 1. Helper Functions
# ------------------------------------------------------------------

def build_email_prompt(to: str, subject: str, incoming: str, instructions: str) -> str:
    """
    Constructs a clear, comprehensive prompt for the LLM workflow 
    from the email input fields. This function is identical to the one 
    used in the Streamlit app.
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

def generate_email_reply(
    to: str,
    subject: str,
    incoming_email: str,
    instructions: str,
) -> Tuple[str, str, str, str]:
    """
    The core function that the Gradio button calls. 
    It communicates with the external FastAPI server.
    """
    if not incoming_email.strip():
        return "⚠️ Please paste the content of the received email to continue.", "", "", ""

    # Build a proper EmailTask payload expected by the FastAPI server
    from uuid import uuid4

    payload = {
        "session_id": str(uuid4()),
        "recipient": to.strip() or "",
        "subject_hint": subject.strip() or "",
        "body_hint": incoming_email.strip() or "",
        "task_description": instructions.strip() or "Draft a professional reply.",
    }

    try:
        response = requests.post(
            FASTAPI_ENDPOINT,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload),
            timeout=60,
        )

        if response.status_code == 200:
            result = response.json()
            # Expecting FinalEmail: {recipient, subject, body}
            final_subject = result.get("subject", subject.strip() or "(No Subject)")
            email_body = result.get("body", "")
            message = "Success"
            trace_id = result.get("trace_id", "N/A")

            output_body = f"Subject: {final_subject}\n\n{email_body}"
            output_raw = json.dumps(result, indent=2)
            return message, trace_id, output_body, output_raw
        else:
            error_message = f"❌ API Error: Status Code {response.status_code}"
            raw_error = response.text
            return error_message, "N/A", "", raw_error

    except requests.exceptions.ConnectionError:
        error_msg = (
            f"❌ Connection Error: Could not connect to the FastAPI service at {FASTAPI_ENDPOINT}."
        )
        return error_msg, "N/A", "", ""
    except Exception as e:
        return f"An unexpected error occurred: {e}", "N/A", "", ""

# ------------------------------------------------------------------
# 2. Gradio Interface Definition
# ------------------------------------------------------------------

# Define Input Components
input_to = gr.Textbox(label="Recipient (To)", placeholder="e.g., client@company.com")
input_subject = gr.Textbox(label="Subject", placeholder="e.g., Partnership Proposal")
input_incoming = gr.Textbox(label="Content of the Received Email", lines=10, placeholder="Paste the email content you need to reply to here...")
input_instructions = gr.Textbox(label="Style / Constraints", lines=10, value="Professional, clear, and concise reply, written in French.")

# Define Output Components
output_message = gr.Textbox(label="Status Message", interactive=False)
output_trace_id = gr.Textbox(label="Langfuse Trace ID", interactive=False)
output_draft = gr.Textbox(label="Proposed Reply Draft", lines=10, interactive=False, container=False)
output_raw_json = gr.JSON(label="Raw Backend Response (JSON)")


# Define the Gradio Blocks Interface
with gr.Blocks(title="Multi-Agent Email Assistant") as demo:
    gr.HTML(
        """
        <div style='text-align: center; margin-bottom: 20px;'>
            <h1>📧 Multi-Agent Email Assistant (Gradio)</h1>
            <p>Client interface calling the <strong>FastAPI backend</strong> running on <code>localhost:8000/langfuse_trace</code>.</p>
        </div>
        """
    )

    # Setup Instructions
    with gr.Accordion("⚠️ Setup Instructions (MUST READ)", open=False):
        gr.Markdown(
            """
            This application runs as two separate processes:
            
            **1. Run the FastAPI Server (Backend):** In your first terminal window:
            
            ```bash
            uvicorn main:app --host 0.0.0.0 --port 8000
            ```
            
            **2. Run the Gradio Client (Frontend):** In your second terminal window:
            
            ```bash
            python gradio_app.py
            ```
            """
        )

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("## ✉️ Received Email Details")
            input_to.render()
            input_subject.render()
            input_incoming.render()
            
        with gr.Column(scale=1):
            gr.Markdown("## 🧠 Instructions for the Reply")
            input_instructions.render()
            
            # The button triggers the function
            run_button = gr.Button("🚀 Generate Email Reply", variant="primary")
            
            gr.Markdown("---")
            output_message.render()
            output_trace_id.render()

    gr.Markdown("---")
    gr.Markdown("## ✍️ Draft and Output")
    
    # Display the final draft output
    output_draft.render()
    
    # Display the raw JSON response
    with gr.Accordion("📦 Raw Backend Response", open=False):
        output_raw_json.render()


    # Define the actions when the button is clicked
    run_button.click(
        fn=generate_email_reply,
        inputs=[input_to, input_subject, input_incoming, input_instructions],
        outputs=[output_message, output_trace_id, output_draft, output_raw_json]
    )


if __name__ == "__main__":
    # Ensure you install Gradio: pip install gradio requests
    demo.launch(server_name="127.0.0.1", server_port=7860, inbrowser=False)