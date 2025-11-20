import json
import logging
import os
import time
import requests # Import the requests library for API calls
from typing import Optional, List, Dict, Any
from uuid import uuid4
from ..models import EmailTask, RetrievedContext, DraftEmail
from ..config import get_settings

# Try to import langfuse SDK if available. We will fall back to generating
# a UUID trace id if the SDK isn't present or initialization fails.
try:
    from langfuse import Langfuse
    HAS_LANGFUSE = True
except Exception:
    Langfuse = None
    HAS_LANGFUSE = False

class DrafterAgent:
    """
    An LLM-powered agent that synthesizes all available context (internal, 
    external, and human feedback) to produce a professional and accurate email draft.
    """
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model
        self.logger = logging.getLogger(self.__class__.__name__)
        
        # Use the standard OpenAI API environment variable
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.max_retries = 3
        
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY not found in environment variables. API calls will likely fail.")


    def _get_system_instruction(self) -> str:
        """
        Defines the Drafter Agent's persona and rules for generating the email.
        """
        return (
            "You are a world-class Executive Email Drafter for a major international company (Zalando). "
            "Your sole task is to generate the final, professional email response. By default, write in **French**, "
            "unless the customer's query is clearly in another language (e.g., German, English). "
            "Follow these rules strictly:\n"
            "1. **Recipient:** The customer name is NOT known; use a professional salutation like 'Cher client' or 'Chère cliente' (Dear Customer).\n"
            "2. **Tone:** Maintain a polite, professional, and executive tone (e.g., 'Bien à vous', 'Sincères salutations').\n"
            "3. **Content Synthesis:** Combine the customer's original query, the internal context (Vector DB snippets), "
            "the external information, and any Human Feedback into ONE cohesive and complete email body.\n"
            "4. **PII Handling:** Mask or omit all sensitive data (PII) like addresses or full names, using placeholders like [Order ID] or [Customer Name].\n"
            "5. **Subject Line:** Use the suggested subject hint or generate a concise, professional, and relevant subject.\n"
            "6. **Citations:** Do NOT include internal source titles (like [faq_carrier_escalation.txt]) or external URIs in the final email body. This information is for internal use only.\n"
            "7. **Format:** Output ONLY a JSON object that matches the required schema."
        )

    def _call_openai_api(self, payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Handles the API call to OpenAI with exponential backoff."""
        
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {self.api_key}' 
        }

        for attempt in range(self.max_retries):
            try:
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=30
                )
                response.raise_for_status() # Raise exception for 4xx or 5xx status codes
                
                return response.json()
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"OpenAI API Request Failed (Attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt) # Exponential backoff
                    continue
                else:
                    return None
            except Exception as e:
                self.logger.error(f"Fetch failed on attempt {attempt + 1}: {e}")
                return None
        return None

    def draft_email(
        self,
        task: EmailTask,
        context: RetrievedContext,
        external_info: Optional[str] = None,
        human_feedback: Optional[str] = None
    ) -> DraftEmail:
        """
        Synthesizes the final email draft using the LLM based on structured input.
        """
        
        # 1. Compile the User Prompt
        context_parts = []
        context_parts.append(f"CUSTOMER'S CORE TASK/GOAL: {task.task_description}")
        context_parts.append(f"CUSTOMER'S ORIGINAL SUBJECT HINT: {task.subject_hint}")
        context_parts.append(f"CUSTOMER'S ORIGINAL BODY HINT (Context for Tone/Language): {task.body_hint}")
        
        context_parts.append("\n--- INTERNAL CONTEXT (Synthesized Facts from Vector DB) ---")
        # Support RetrievedContext with `snippets` list
        internal_text = "\n\n".join(context.snippets) if hasattr(context, "snippets") else getattr(context, "retrieved_context", "")
        context_parts.append(internal_text)

        context_parts.append("\n--- EXTERNAL CONTEXT (Web Search Summary) ---")
        context_parts.append(external_info or "No external search information was needed or found.")
            
        context_parts.append("\n--- HUMAN FEEDBACK (Must be incorporated) ---")
        context_parts.append(human_feedback or "No human feedback provided.")

        context_parts.append("\n\n---\nINSTRUCTIONS: Generate the final, complete, and professional email draft using ALL the content above. Output ONLY the required JSON object.")
        
        full_user_prompt = "\n".join(context_parts)
        self.logger.info("Drafting prompt compiled. Calling LLM.")
        
        # 2. Define the Structured Output Schema (DraftEmail)
        response_schema = {
            "type": "object",
            "properties": {
                "subject": {"type": "string", "description": "The professional subject line, derived from the task or subject_hint."},
                "body": {"type": "string", "description": "The complete, professional email body in the required language (default: French)."},
            },
            "required": ["subject", "body"]
        }
        
        # 3. Construct the API Payload
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": self._get_system_instruction()},
                {"role": "user", "content": full_user_prompt}
            ],
            # NOTE: the raw REST Chat Completions endpoint does not accept
            # a structured `response_format` with a JSON schema; remove it
            # and parse the assistant's text output as JSON instead.
            "temperature": 0.2,
        }

        # Optionally create a Langfuse trace id (we'll attempt to initialize
        # the SDK only if available; otherwise generate a UUID so we can
        # surface a stable identifier in the response).
        settings = get_settings()
        trace_id = str(uuid4())

        lf_client = None
        lf_trace_ctx = None
        if HAS_LANGFUSE and settings.langfuse_public_key and settings.langfuse_secret_key:
            try:
                lf_client = Langfuse(public_key=settings.langfuse_public_key, secret_key=settings.langfuse_secret_key, host=settings.langfuse_host)
                # Create a Langfuse trace id so all subsequent events are grouped
                try:
                    trace_id = lf_client.create_trace_id()
                    from langfuse import types as _lf_types
                    lf_trace_ctx = _lf_types.TraceContext(trace_id=trace_id)
                except Exception:
                    # Fall back to UUID if SDK call fails
                    pass
            except Exception:
                lf_client = None

        # Optionally record the request event in Langfuse (if available)
        if lf_client and lf_trace_ctx:
            try:
                lf_client.create_event(trace_context=lf_trace_ctx, name="draft.request", input=payload)
            except Exception:
                pass

        # 4. Make the API Call
        api_result = self._call_openai_api(payload)
        
        if not api_result:
            self.logger.error("LLM call for drafting failed after all retries.")
            return DraftEmail(
                subject="[ERROR] Échec de la génération du brouillon",
                body="Une erreur critique s'est produite lors de la génération du brouillon par le LLM. Veuillez réessayer plus tard.",
                sources=["system_error"]
            )
        
        # 5. Process the Response
        try:
            # Extract the assistant content and attempt to clean fenced code blocks
            raw_content = api_result['choices'][0]['message']['content']
            # Remove common Markdown code fences (```json ... ```)
            import re
            m = re.search(r"```(?:json)?\n?(.*)```$", raw_content, flags=re.DOTALL)
            if m:
                json_text = m.group(1).strip()
            else:
                # Fallback: strip any triple backticks if present
                json_text = raw_content.replace('```', '').strip()

            draft_data = json.loads(json_text)
            
            # Determine sources used for the system log
            sources = []
            # `RetrievedContext` exposes `snippets` and `confidence`.
            if hasattr(context, "snippets") and getattr(context, "snippets"):
                sources.append("vector_db")
            if external_info and not external_info.startswith("[External error]"):
                sources.append("external_tool")
            if human_feedback:
                sources.append("human_feedback")
            
            # Record the assistant response in Langfuse if possible
            if lf_client and lf_trace_ctx:
                try:
                    lf_client.create_event(trace_context=lf_trace_ctx, name="draft.response", input=payload, output=api_result)
                except Exception:
                    pass

            return DraftEmail(
                subject=draft_data.get("subject", "Brouillon d'e-mail"),
                body=draft_data.get("body", "Le contenu du corps du brouillon est manquant."),
                sources=sources,
                trace_id=trace_id,
            )
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            self.logger.error(f"Failed to parse LLM response for DrafterAgent: {e}. Raw response: {api_result}")
            return DraftEmail(
                subject="[ERROR] Échec de l'analyse de la réponse du LLM",
                body=f"Le LLM a retourné une réponse non analysable. Détails de l'erreur: {e}",
                sources=["system_error"]
            )