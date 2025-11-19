import json
import logging
import requests
import os 
from typing import Dict
from dataclasses import dataclass, field

# Define the data structure for the email task, which will be the input
@dataclass
class EmailTask:
    session_id: str
    recipient: str
    subject_hint: str
    body_hint: str
    task_description: str

# --- Agent Definition ---

class IntentClassifierAgent:
    """
    Analyzes the raw email content (subject and body) and classifies 
    the customer's core intent, urgency, and whether external (web) 
    search is required.
    """
    def __init__(self, model_name: str = "gpt-4o-mini"): 
        # Use the model name passed from the orchestrator
        self.model_name = model_name 
        
        # --- CRITICAL CHANGE: Load API Key from environment variable ---
        # Loads the key from the environment variable OPENAI_API_KEY
        self.api_key = os.getenv("OPENAI_API_KEY", "") 
        
        # --- OpenAI API Endpoint ---
        self.api_url = "https://api.openai.com/v1/chat/completions"
        
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY not found in environment variables. API calls will likely fail.")


    def classify_intent(self, task: EmailTask) -> Dict:
        """
        Uses the OpenAI LLM with structured output to classify the email.
        """
        
        # 1. Define the system prompt (Agent's persona and instructions)
        system_prompt = (
            "You are the Zalando Intent Classifier Agent. Your role is to analyze customer email "
            "content and classify the core purpose. You must output the result in the mandatory JSON schema."
            "Possible intents include: 'Shipping_Delay', 'Refund_Request', 'Incorrect_Item', 'Product_Inquiry', "
            "'Loyalty_Program', 'GDPR_Request', 'Technical_Issue', or 'General_Inquiry'."
            "Urgency is based on keywords like 'URGENT', 'ASAP', or policy-driven timelines (e.g., 7-day delay)."
            "Set 'needs_external_search' to True if the query requires current, public, non-internal data (e.g., 'What is Zalando's stock price today?', 'Is the new collection released?')."
        )
        
        # 2. Define the user query (The specific task)
        user_query = (
            f"Analyze the following customer email. Subject: \"{task.subject_hint}\" Body: \"{task.body_hint}\""
        )
        
        # 3. Define the JSON Schema for structured output (OpenAI style)
        response_schema = {
            "type": "object",
            "properties": {
                "intent_label": {"type": "string", "description": "The primary intent, e.g., Shipping_Delay."},
                "urgency_level": {"type": "string", "description": "High, Normal, or Low."},
                "needs_external_search": {"type": "boolean", "description": "True if the answer requires real-time web search."},
            },
            "required": ["intent_label", "urgency_level", "needs_external_search"]
        }

        # 4. Construct the API payload for OpenAI Chat Completions
        payload = {
            "model": self.model_name,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_query}
            ],
            # Use the response_format parameter for guaranteed JSON output
            "response_format": {"type": "json_object", "schema": response_schema}, 
            "temperature": 0.0, # Low temperature for reliable classification
        }

        # 5. Execute API Call with exponential backoff
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
                
                # Extract and parse the JSON string from the response
                result = response.json()
                
                # OpenAI response structure
                json_text = result['choices'][0]['message']['content']
                return json.loads(json_text)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"OpenAI API Request Failed (Attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    import time
                    time.sleep(2 ** attempt) # Exponential backoff
                    continue
                
                # Fallback
                self.logger.error("All API attempts failed. Returning fallback data.")
                return {
                    "intent_label": "Error_Fallback_API",
                    "urgency_level": "High",
                    "needs_external_search": False,
                }
            except Exception as e:
                self.logger.error(f"Failed to parse LLM response: {e}")
                # Fallback for parsing errors
                return {
                    "intent_label": "Error_Parsing",
                    "urgency_level": "High",
                    "needs_external_search": False,
                }

# --- Example Usage (Testing the Agent) ---
if __name__ == '__main__':
    # Initialize the agent
    classifier = IntentClassifierAgent()
    
    # Create a mock Zalando task (similar to the one we drafted earlier)
    mock_task = EmailTask(
        session_id="MOCK-001",
        recipient="support@zalando.com",
        subject_hint="Where is my order ZL-99876? URGENT!",
        body_hint="My order ZL-99876 has not moved since last Friday. I need these shoes for my trip on Monday. Please help ASAP.",
        task_description="Customer inquiry about shipping delay and urgent need for resolution."
    )

    print("--- Running Intent Classification ---")
    classification_result = classifier.classify_intent(mock_task)
    print(json.dumps(classification_result, indent=2))