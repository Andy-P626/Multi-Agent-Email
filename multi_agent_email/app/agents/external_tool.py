import json
import logging
import requests
import os
import time
from typing import Dict, Optional, Any
from dataclasses import dataclass

# --- Dependency Models (Copied from Intent Agent for self-contained use) ---
@dataclass
class EmailTask:
    session_id: str
    recipient: str
    subject_hint: str
    body_hint: str
    task_description: str

# --- Agent Definition ---

class ExternalToolAgent:
    """
    Fetches real-time, external information (e.g., market news, public stock data) 
    using the Tavily Search API.
    """
    def __init__(self):
        # --- API Setup: Switching from NEWS_API to TAVILY_API ---
        # Loads the Tavily API URL, defaulting to the standard endpoint
        self.tavily_api_url = os.getenv("TAVILY_API_URL", "https://api.tavily.com/search")
        # Loads the key from the environment variable TAVILY_API_KEY
        self.tavily_api_key = os.getenv("TAVILY_API_KEY", "") 
        self.logger = logging.getLogger(self.__class__.__name__)
        
        if not self.tavily_api_key:
            self.logger.warning("TAVILY_API_KEY not found in environment variables. External search will be stubbed.")

    def fetch_external_info(self, task: EmailTask, intent_result: Dict) -> str:
        """
        Retrieves search results (snippets) and summarizes them into a single string 
        for the Drafter Agent.
        
        Args:
            task: The EmailTask object containing the customer query.
            intent_result: The classification result from the IntentClassifierAgent.

        Returns:
            A string containing the summarized external context or an error message.
        """
        
        # 1. Check for stub condition
        if not self.tavily_api_key:
            # Using French fallback text for consistency with your original code
            return f"[External stub] Synthèse de marché simulée pour : '{task.task_description}'."

        # 2. Determine the query string
        intent_label = intent_result.get("intent_label", "")
        if intent_label == "Pricing_Request" or intent_label == "Product_Inquiry":
            # Focus search on public information relevant to pricing/product
            query_text = f"Zalando news and market information for {task.subject_hint}"
        else:
            # Use the overall task description for general news context
            query_text = f"Zalando public information about {task.task_description}"
            
        # 3. Prepare request payload for Tavily
        payload = {
            "api_key": self.tavily_api_key,
            "query": query_text,
            "search_depth": "basic", # Basic depth is usually faster and sufficient for context
            "max_results": 3,
            "include_answer": False,
            "include_raw_content": False
        }
        
        # 4. Execute API Call with exponential backoff
        max_retries = 3
        
        for attempt in range(max_retries):
            try:
                response = requests.post(
                    self.tavily_api_url, 
                    json=payload, 
                    timeout=10
                )
                response.raise_for_status()
                data = response.json()
                
                # Tavily returns 'results' which is a list of documents
                results = data.get("results", [])

                if not results:
                    return "[External] Aucun article pertinent trouvé."

                # 5. Summarize the results
                lines = ["[External] Résumé des actualités pertinentes :"]
                for res in results:
                    # Tavily results have 'title', 'url', and 'content' (snippet)
                    title = res.get("title", "No Title")
                    content = res.get("content", "No Snippet")
                    # Use the snippet as the primary information
                    lines.append(f"- {title}: {content}")
                
                return "\n".join(lines)

            except requests.exceptions.RequestException as e:
                self.logger.error(f"Tavily API Request Failed (Attempt {attempt + 1}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt) # Exponential backoff
                    continue
                
                return f"[External error] Impossible d'appeler l'API externe (Tavily): {e}"
            
            except Exception as e:
                self.logger.error(f"Failed to process external API response: {e}")
                return f"[External error] Erreur de traitement de la réponse (Tavily) : {e}"

# --- Example Usage (Testing the Agent) ---
if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    
    # NOTE: To run this test successfully, you must set the TAVILY_API_KEY environment variable.
    # export TAVILY_API_KEY="YOUR_API_KEY_HERE"
    
    agent = ExternalToolAgent()
    
    mock_task = EmailTask(
        session_id="EXT-001",
        recipient="support@zalando.com",
        subject_hint="Inquiry about new collection release date",
        body_hint="When is the latest Nike collection expected to be available for purchase? I heard some news about a delay.",
        task_description="Customer asking about public release date of a new product collection."
    )
    
    mock_intent_result = {
        "intent_label": "Product_Inquiry",
        "urgency_level": "Normal",
        "needs_external_search": True, # Simulate classifier deciding external search is needed
    }

    print("--- Running External Tool Retrieval (Tavily) ---")
    external_context = agent.fetch_external_info(mock_task, mock_intent_result)
    print(external_context)
