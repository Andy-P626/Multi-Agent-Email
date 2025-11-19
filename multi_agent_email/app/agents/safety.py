import json
import logging
import os
import time
import requests
from typing import Optional, Dict, Any

class SafetyReviewerAgent:
    """
    An LLM-powered agent that reviews the synthesized context and intent 
    for compliance, high-risk topics (e.g., compensation, legal exposure), 
    and mandatory Human-in-the-Loop (HIL) requirements.
    """
    def __init__(self, llm_model: str = "gpt-4o-mini"):
        self.llm_model = llm_model
        self.logger = logging.getLogger(self.__class__.__name__)

        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.api_url = "https://api.openai.com/v1/chat/completions"
        self.max_retries = 3
        
        if not self.api_key:
            self.logger.warning("OPENAI_API_KEY not found in environment variables. API calls will likely fail.")

    def _get_system_instruction(self) -> str:
        """
        Defines the Safety Reviewer's persona and rules for assessing risk.
        """
        return (
            "You are a Compliance and Safety Review Officer for Zalando. Your task is to analyze the customer's intent, "
            "the retrieved internal context, and any external findings to determine if the resulting email draft "
            "will be high-risk or requires mandatory Human-in-the-Loop (HIL) intervention based on company policy. "
            "You DO NOT draft the email; you only assess the risk of the content that WILL be drafted.\n"
            "Rules for mandatory HIL:\n"
            "1. **Compensation/Refunds:** If the topic involves issuing a specific compensation amount, voucher, or refund (beyond standard policy quotes).\n"
            "2. **Legal/Regulatory:** If the topic involves explicit threats of legal action or potential regulatory non-compliance.\n"
            "3. **Sensitive PII:** If the context contains personally identifiable information (PII) that must be manually redacted.\n"
            "4. **High Escalation:** If the Retriever Agent marked the case as 'escalation_required'."
            "5. **High Confidence:** If the Retriever's confidence score is low (e.g., below 0.7)."
            "Output ONLY a JSON object that strictly matches the required schema."
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
                response.raise_for_status()
                return response.json()
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"OpenAI API Request Failed (Attempt {attempt + 1}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                else:
                    return None
            except Exception as e:
                self.logger.error(f"Fetch failed on attempt {attempt + 1}: {e}")
                return None
        return None
    
    def review_context(self, task_context: str) -> Dict[str, Any]:
        """
        Analyzes the context and intent to determine risk and HIL requirement.
        """
        self.logger.info("Performing LLM-based safety review on gathered context.")

        # 1. Define the Structured Output Schema
        response_schema = {
            "type": "object",
            "properties": {
                "review_status": {"type": "string", "description": "PASS or FAIL depending on risk assessment."},
                "hil_required": {"type": "boolean", "description": "True if Human-in-the-Loop is mandatory, False otherwise."},
                "review_notes": {"type": "string", "description": "A concise note explaining the status and/or reason for HIL requirement."},
            },
            "required": ["review_status", "hil_required", "review_notes"]
        }
        
        # 2. Construct the API Payload
        payload = {
            "model": self.llm_model,
            "messages": [
                {"role": "system", "content": self._get_system_instruction()},
                {"role": "user", "content": f"Analyze the following workflow context and output the safety review JSON:\n\n---\n{task_context}"}
            ],
            "response_format": {"type": "json_object", "schema": response_schema},
            "temperature": 0.0,
        }

        # 3. Make the API Call
        api_result = self._call_openai_api(payload)
        
        if not api_result:
            self.logger.error("LLM call for safety review failed.")
            return {"review_status": "FAIL", "hil_required": True, "review_notes": "System Error: LLM safety review failed."}

        # 4. Process the Response
        try:
            json_text = api_result['choices'][0]['message']['content']
            review_data = json.loads(json_text)
            
            # Ensure required keys exist and return
            if all(k in review_data for k in ["review_status", "hil_required", "review_notes"]):
                return review_data
            else:
                raise ValueError("LLM response did not conform to the expected schema.")
        except (KeyError, IndexError, json.JSONDecodeError, ValueError) as e:
            self.logger.error(f"Failed to parse LLM response for SafetyReviewerAgent: {e}.")
            return {"review_status": "FAIL", "hil_required": True, "review_notes": f"System Error: Failed to parse LLM output: {e}"}