import json
import logging
import requests
import os
import time
from typing import Dict, List
from ..models import EmailTask, RetrievedContext

# --- Knowledge Base Mock (Simulates Vector Store Retrieval) ---

# Mock knowledge mapping Intents to relevant file paths
MOCK_KNOWLEDGE_BASE = {
    "Shipping_Delay": [
        "data/knowledge/faq_carrier_escalation.txt",
        "data/knowledge/template_delay_apology.txt",
        "data/knowledge/policy_compensation_limits.txt"
    ],
    "Refund_Request": [
        "data/knowledge/policy_compensation_limits.txt",
        "data/knowledge/transcript_billing_dispute.txt",
        "data/knowledge/template_return_confirmation.txt"
    ],
    "GDPR_Request": [
        "data/knowledge/faq_gdpr_request.txt",
        "data/knowledge/template_dpo_acknowledgement.txt"
    ],
    "Loyalty_Program": [
        "data/knowledge/faq_loyalty_status.txt",
        "data/knowledge/doc_plus_benefits_2024.txt",
        "data/knowledge/transcript_loyalty_inquiry.txt"
    ],
    "Incorrect_Item": [
        "data/knowledge/faq_incorrect_item.txt"
    ],
    "Product_Inquiry": [
        "data/knowledge/doc_care_denim.txt",
        "data/knowledge/doc_sneaker_fit.txt"
    ],
    "General_Inquiry": [
        "data/knowledge/procedure_cancel_window.txt",
        "data/knowledge/doc_gift_card.txt"
    ]
}

def load_document_content(filepath: str) -> str:
    """Loads content from a specific knowledge file, simulating a full document fetch."""
    # Placeholder content based on file titles for simulation:
    content_map = {
        "data/knowledge/faq_carrier_escalation.txt": "**Policy:** Escalate if no update for 7 days (Hermes/DHL). Provide Template 3A.",
        "data/knowledge/template_delay_apology.txt": "**Template 3A:** Apology for delay, includes €15 voucher.",
        "data/knowledge/policy_compensation_limits.txt": "**Policy:** Max €15 for 10+ day delay. Max €25 for major error. Must be voucher, not cash.",
        "data/knowledge/faq_gdpr_request.txt": "**Policy:** Route immediately to DPO team. Reply with Template 5B.",
        "data/knowledge/doc_plus_benefits_2024.txt": "**Plus Benefits:** Free express shipping, early access, 100-day returns.",
        # ... add others as needed for testing ...
    }
    title = os.path.basename(filepath)
    return f"--- DOCUMENT: {title} ---\n{content_map.get(filepath, 'Content not available for mock.')}\n"

# --- NEW: Mock Chroma Vector Store Interface ---

class ChromaVectorStore:
    """
    Mock interface simulating a ChromaDB client for retrieval.
    In a real application, this would handle client initialization and connection.
    """
    def __init__(self, collection_name: str = "zalando_policies"):
        self.collection_name = collection_name
        self.logger = logging.getLogger(self.__class__.__name__)
        # NOTE: In a real environment, you would initialize the Chroma client here.
        self.logger.info(f"Initialized mock Chroma client for collection: {self.collection_name}")

    def similarity_search(self, query: str, k: int = 4, intent_label: str = "General_Inquiry") -> List[Dict]:
        """
        Simulates a RAG search against Chroma.
        In this mock, we use the intent_label to fetch pre-defined documents for testing the workflow.
        In a real application, this method uses the 'query' to search embeddings in the collection.
        """
        # --- MOCKING THE RESULT OF CHROMA SEARCH ---
        relevant_files = MOCK_KNOWLEDGE_BASE.get(intent_label, MOCK_KNOWLEDGE_BASE["General_Inquiry"])
        
        snippets = []
        # Simulate Chroma returning documents with content (page_content) and metadata (source)
        for filepath in relevant_files[:k]:
            snippets.append({
                "source": filepath,
                "page_content": load_document_content(filepath) 
            })
            
        return snippets

def get_vector_store_client() -> ChromaVectorStore:
    """
    Function to simulate fetching the initialized Chroma client instance.
    """
    return ChromaVectorStore()


# --- Agent Definition ---

class RetrieverAgent:
    """
    Retrieves internal knowledge based on the classified intent and synthesizes 
    the context for the Drafter Agent. Uses a Chroma (mock) client for RAG.
    """
    def __init__(self, model_name: str = "gpt-4o-mini"):
        self.model_name = model_name
        
        # --- LLM Setup ---
        self.api_key = os.getenv("OPENAI_API_KEY", "") 
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY not found in environment variables. API calls will likely fail.")

        # --- RAG Setup: Initialize Chroma client ---
        self.vector_store = get_vector_store_client()


    def _determine_escalation(self, intent_label: str, email_body: str) -> bool:
        """Determines if the case requires mandatory internal escalation."""
        
        # Rule 1: GDPR requests must always escalate to DPO
        if intent_label == "GDPR_Request":
            return True
        
        # Rule 2: Shipping Delay escalation (based on faq_carrier_escalation.txt)
        if intent_label == "Shipping_Delay":
            # Check for the 7-day rule mentioned in the task payload
            if "7 days" in email_body or "7 day" in email_body:
                return True
        
        # Rule 3: High Compensation requests (Policy Compensation Limits)
        # Flagging a compensation request to force HIL check later if amount exceeds limit
        if intent_label == "Refund_Request" and "compensation" in email_body.lower():
            return True 
            
        return False

    def _synthesize_context_with_llm(self, raw_context: str, original_query: str) -> str:
        """Uses the LLM to summarize raw documents into a coherent, cited context (via OpenAI)."""
        
        system_prompt = (
            "You are the Zalando Context Synthesizer. Your task is to combine the provided raw policy documents "
            "and FAQs into a single, cohesive, factual text block. Only include facts directly relevant to "
            "answering the customer's original query. Cite the source document title in brackets [] after each fact. "
            "If the compensation policy is retrieved, clearly state the maximum voucher amount that can be offered "
            "without manager approval."
        )
        
        user_query = (
            f"Original Customer Query: {original_query}\n\n"
            f"Raw Documents to Synthesize:\n\n{raw_context}"
        )
        
        # Payload for OpenAI Chat Completions
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            "temperature": 0.1,
        }

        # Execute API Call with exponential backoff
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                # Add Authorization header for OpenAI
                headers = {
                    'Content-Type': 'application/json',
                    'Authorization': f'Bearer {self.api_key}' 
                }
                
                response = requests.post(
                    self.api_url,
                    headers=headers,
                    data=json.dumps(payload),
                    timeout=30
                )
                response.raise_for_status()
                
                # Extract the text content from the OpenAI response structure
                result = response.json()
                
                # Check for content and return
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                else:
                    raise Exception("No content returned from LLM.")

            except requests.exceptions.RequestException as e:
                self.logger.error(f"OpenAI API Request Failed (Attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return "Error: Failed to synthesize context from internal documents."
            except Exception as e:
                self.logger.error(f"Failed to parse LLM response: {e}")
                return "Error: Failed to synthesize context from internal documents."


    def retrieve_context(self, task: EmailTask, intent_result: Dict) -> RetrievedContext:
        """
        Main method to retrieve, synthesize, and package the context using Chroma.
        """
        intent_label = intent_result.get("intent_label", "General_Inquiry")
        
        # 1. Retrieval using Chroma (Mocked call)
        # In a real system, the query would use embeddings of the email body.
        # Here, we pass the intent_label to the mock for predictable testing.
        retrieved_documents = self.vector_store.similarity_search(
            query=task.body_hint, 
            k=4, 
            intent_label=intent_label
        )
        
        # Consolidate raw text from the mock Chroma search results
        raw_retrieved_context = "\n\n".join([doc['page_content'] for doc in retrieved_documents])
            
        # 2. Determine Confidence Score
        # Simplified: High confidence if documents were found, lower otherwise.
        confidence_score = 0.9 if raw_retrieved_context.strip() else 0.4
        
        # 3. Synthesize Context (Call LLM)
        synthesized_context = self._synthesize_context_with_llm(
            raw_retrieved_context, 
            task.subject_hint + " " + task.body_hint
        )
        
        # 4. Determine Escalation Requirement
        escalation = self._determine_escalation(intent_label, task.body_hint)
        
        # 5. Build Final Structured Output
        # Return a RetrievedContext instance for downstream agents
        snippets = [doc['page_content'] for doc in retrieved_documents]
        return RetrievedContext(snippets=snippets, confidence=confidence_score)

# --- Example Usage (Testing the Agent) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # 1. Initialize the agent
    retriever = RetrieverAgent()
    
    # 2. Mock Input from Classifier (based on initial_task_payload.json)
    mock_task = EmailTask(
        session_id="ZAL-EMAIL-10293",
        recipient="support@zalando.com",
        subject_hint="URGENT: Order ZL-99876 has not moved in 7 days (Shipping Delay)",
        body_hint="My order ZL-99876 for the black leather boots was supposed to arrive last week, and the Hermes tracking hasn't updated since last Friday. I need these for my trip on Monday. Please check with the carrier immediately and let me know if it's lost. What compensation can you offer for this failure?",
        task_description="Customer inquiry about shipping delay and urgent need for resolution."
    )
    
    mock_intent_result = {
        "intent_label": "Shipping_Delay",
        "urgency_level": "High",
        "needs_external_search": False,
    }

    print("--- Running Retrieval and Synthesis ---")
    retrieval_result = retriever.retrieve_context(mock_task, mock_intent_result)
    print(json.dumps(retrieval_result, indent=2))