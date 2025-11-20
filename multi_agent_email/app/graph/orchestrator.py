import os
from typing import TypedDict, Annotated, List

# Optional imports for LangGraph/Langfuse — guard so module can be imported
HAS_LANGGRAPH = True
try:
    from langgraph.graph import StateGraph, END, START
    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.prebuilt import ToolNode
    from langgraph.graph.message import add_messages
except Exception:
    # LangGraph not installed in the environment; provide lightweight fallbacks
    HAS_LANGGRAPH = False
    StateGraph = None
    END = None
    START = None
    SqliteSaver = None
    ToolNode = None
    def add_messages(x):
        return x

HAS_LANGFUSE = True
try:
    from langfuse import Langfuse
    from langfuse.callback import CallbackHandler
except Exception:
    HAS_LANGFUSE = False
    Langfuse = None
    CallbackHandler = None

# Import the agent classes defined in the 'agents' directory
# NOTE: Ensure your agents/__init__.py file is correct for these imports to work.
from ..agents import (
    IntentClassifierAgent,
    RetrieverAgent,
    DrafterAgent,
    SafetyReviewerAgent,
    ExternalToolAgent
)

# --- 1. CONFIGURATION AND INITIALIZATION ---

# Initialize Langfuse for observability
# The callback handler will automatically track traces and spans for all LLM calls.
# NOTE: Replace 'YOUR_PUBLIC_KEY' and 'YOUR_SECRET_KEY' with your actual keys.
# LgFuse = Langfuse(
#     public_key="YOUR_PUBLIC_KEY",
#     secret_key="YOUR_SECRET_KEY",
#     host="https://cloud.langfuse.com"
# )
# LgFuse_callback = CallbackHandler(langfuse=LgFuse)

# Initialize SqliteSaver for persistence
# Memory = SqliteSaver.from_conn_string(":memory:") # Use ":memory:" for simple in-memory storage
# OR use a file for persistent state:
# Memory = SqliteSaver.from_conn_string("sqlite:///agent_state.sqlite")

# Placeholder for real initialization (assuming environment variables are set)
LgFuse_callback = None
if SqliteSaver is not None:
    Memory = SqliteSaver.from_conn_string(":memory:")
else:
    Memory = None


# --- 2. STATE DEFINITION ---

# Define the state object that will be passed between nodes.
# Annotated is used for list operations, which LangGraph supports natively.
class GraphState(TypedDict):
    """Represents the state of our graph."""
    user_query: str                    # The initial input from the user.
    intent: str                        # Classification result from IntentClassifierAgent.
    context_data: str                  # Retrieved context from VectorDB or External Tool.
    draft: str                         # The generated email draft.
    safety_check_passed: bool          # Result of the SafetyReviewerAgent.
    draft_version: int                 # Counter for redrafting attempts.
    agent_history: Annotated[List[str], add_messages] # Tracks the execution path.
    citations: List[str]               # Sources for the retrieved context.


# --- 3. ORCHESTRATOR CLASS ---

class EmailAutomationOrchestrator:
    def __init__(self):
        # Initialize all required agents
        self.intent_classifier = IntentClassifierAgent()
        self.retriever = RetrieverAgent()
        self.drafter = DrafterAgent()
        self.safety_reviewer = SafetyReviewerAgent()
        self.external_tool = ExternalToolAgent() # Assumes this agent wraps a search tool

        # Build the LangGraph
        self.app = self._build_graph()

    # --- Node Functions ---

    def _classify_intent(self, state: GraphState) -> GraphState:
        """Node 1: Classify the user's request (e.g., Email, Research, Simple Task)."""
        print("---AGENT: CLASSIFYING INTENT---")
        # In a real implementation, this agent would call an LLM to categorize the query.
        result = self.intent_classifier.run(state["user_query"])
        
        # For simplicity, we assume the result is a dict with the necessary fields
        # E.g., {'intent': 'draft_email_with_retrieval', 'requires_search': True}
        state["intent"] = result.get("intent", "default_draft")
        state["agent_history"].append(f"Intent Classified: {state['intent']}")
        return state

    def _retrieve_context(self, state: GraphState) -> GraphState:
        """Node 2: Retrieve context from the VectorDB (Organizational Knowledge)."""
        print("---AGENT: RETRIEVING CONTEXT---")
        # Use the query to search the vector store
        context, citations = self.retriever.run(state["user_query"])

        if context:
            state["context_data"] = context
            state["citations"] = citations
            state["agent_history"].append("Context Retrieval: SUCCESS")
        else:
            state["context_data"] = "No relevant organizational context found."
            state["citations"] = []
            state["agent_history"].append("Context Retrieval: FAILURE")

        return state

    def _external_search(self, state: GraphState) -> GraphState:
        """Node 3: Use the external tool (Web Search) for current, external data."""
        print("---AGENT: PERFORMING EXTERNAL SEARCH---")
        
        # Only search if context is not already found and the intent suggests a need for external data
        if "No relevant organizational context found" in state["context_data"] or state["intent"] in ["research_task", "external_email_draft"]:
            search_query = state["user_query"] # Could be refined by an internal planning step
            search_result = self.external_tool.run(search_query)
            
            # Append external search results to the context
            state["context_data"] += "\n\n--- External Search Results ---\n" + search_result
            state["agent_history"].append("External Search Performed.")
        else:
            state["agent_history"].append("External Search Skipped (Sufficient context found).")
            
        return state

    def _generate_draft(self, state: GraphState) -> GraphState:
        """Node 4: Draft the email based on the query, context, and intent."""
        print("---AGENT: GENERATING DRAFT---")
        
        # Concatenate all necessary inputs for the DrafterAgent
        prompt = (
            f"User Query: {state['user_query']}\n"
            f"Intent: {state['intent']}\n"
            f"Context: {state['context_data']}"
        )
        
        # Track draft version for iterative revision
        state["draft_version"] = state.get("draft_version", 0) + 1
        
        new_draft = self.drafter.run(prompt)
        state["draft"] = new_draft
        state["agent_history"].append(f"Draft Version {state['draft_version']} Generated.")
        
        return state

    def _review_safety(self, state: GraphState) -> GraphState:
        """Node 5: Review the generated draft for safety and compliance."""
        print("---AGENT: REVIEWING SAFETY---")
        
        # The safety reviewer checks for sensitive information, bias, toxicity, etc.
        is_safe = self.safety_reviewer.run(state["draft"]) # Returns True/False
        
        state["safety_check_passed"] = is_safe
        state["agent_history"].append(f"Safety Check Passed: {is_safe}")
        
        return state

    def _send_and_log(self, state: GraphState) -> GraphState:
        """Node 6 (Final Step): Simulate sending the email and logging the task."""
        print("---SYSTEM: SIMULATING SEND & LOGGING TASK---")
        
        # In a real app, this would trigger an API call to send the email and save the task log.
        log_entry = (
            f"Email successfully processed and simulated for sending.\n"
            f"Final Draft:\n{state['draft']}\n"
            f"Sources: {', '.join(state['citations'])}"
        )
        state["agent_history"].append(log_entry)
        
        return state
    
    # --- Conditional Edges (Routers) ---

    def _route_intent(self, state: GraphState) -> str:
        """Router 1: Determines the next step after intent classification."""
        intent = state["intent"]
        
        if "research" in intent or "external" in intent:
            # If the intent is explicitly research or requires external search
            return "external_search"
        elif "retrieval" in intent:
            # If the intent requires internal organizational knowledge
            return "retrieve_context"
        else:
            # For simple drafts, or tasks that can proceed without research
            return "generate_draft"

    def _route_retrieval(self, state: GraphState) -> str:
        """Router 2: Determines flow after internal retrieval."""
        context = state["context_data"]
        
        if "No relevant organizational context found" in context and state["intent"] in ["draft_email_with_retrieval"]:
            # If retrieval failed but organizational context was necessary, try external search
            print("Router: Retrieval failed, routing to external search.")
            return "external_search"
        else:
            # If context was found, or if external search is not relevant for this task
            print("Router: Sufficient context found/not required, routing to draft generation.")
            return "generate_draft"

    def _route_safety(self, state: GraphState) -> str:
        """Router 3: Determines if the draft needs revision or is ready for approval."""
        if state["safety_check_passed"]:
            print("Router: Safety check passed. Routing to Human Approval.")
            return "human_approval"
        else:
            # Loop back to draft generation for an automatic revision by the DrafterAgent
            print("Router: Safety check failed. Looping back for revision.")
            # We would typically prompt the drafter with instructions on *why* it failed.
            state["context_data"] += "\n\n--- REVISION NOTE: Safety check failed. Please revise the draft to remove sensitive/unsafe content. ---"
            return "generate_draft"

    # The human_approval node is a special step managed externally (when running the graph)
    # The output from the human approval step (edit/approve) will determine the final route.
    def _route_human_approval(self, state: GraphState) -> str:
        """Router 4: Determines final action after human review."""
        # For simplicity, we assume an 'approved' flag is set in the state by the Human step.
        # In a real application, the user would explicitly send a message to advance the graph.
        if state.get("human_approved", False):
            print("Router: Human approved. Routing to Send & Log.")
            return "send_and_log"
        else:
            # If the user rejected and added more instructions, loop back to retrieval/draft
            # For this example, we assume rejection means restarting the research phase.
            print("Router: Human rejected/requested more research. Routing to Retrieval.")
            return "retrieve_context"

    # --- Graph Construction ---

    def _build_graph(self):
        """Build the LangGraph structure."""
        workflow = StateGraph(GraphState)

        # 1. Define Nodes (Agent Steps)
        workflow.add_node("classify_intent", self._classify_intent)
        workflow.add_node("retrieve_context", self._retrieve_context)
        workflow.add_node("external_search", self._external_search)
        workflow.add_node("generate_draft", self._generate_draft)
        workflow.add_node("review_safety", self._review_safety)
        workflow.add_node("send_and_log", self._send_and_log)

        # 2. Add a special node for Human-in-the-Loop approval/editing
        # This will be where the execution PAUSES and awaits user input.
        workflow.add_node("human_approval", lambda state: state) # Identity function, state doesn't change until user acts.

        # 3. Set the Entry Point
        workflow.set_entry_point("classify_intent")

        # 4. Define Edges (Flow)

        # Agent -> Router 1 (Intent)
        workflow.add_edge(START, "classify_intent")
        workflow.add_conditional_edges("classify_intent", self._route_intent, {
            "retrieve_context": "retrieve_context",
            "external_search": "external_search",
            "generate_draft": "generate_draft",
        })

        # Router 2 (Retrieval)
        workflow.add_conditional_edges("retrieve_context", self._route_retrieval, {
            "external_search": "external_search",
            "generate_draft": "generate_draft",
        })
        
        # External Search -> Draft
        workflow.add_edge("external_search", "generate_draft")

        # Draft -> Safety Review
        workflow.add_edge("generate_draft", "review_safety")

        # Router 3 (Safety Check)
        workflow.add_conditional_edges("review_safety", self._route_safety, {
            "human_approval": "human_approval",
            "generate_draft": "generate_draft", # Loop for redrafting
        })

        # Router 4 (Human Approval)
        # In a real app, the human input would trigger this route based on a button click
        # For a basic graph, we just define the conditional paths
        workflow.add_conditional_edges("human_approval", self._route_human_approval, {
            "send_and_log": "send_and_log",
            "retrieve_context": "retrieve_context", # e.g., if human requests more research
        })

        # Final Node
        workflow.add_edge("send_and_log", END)

        # Compile and return the runnable graph
        return workflow.compile(checkpointer=Memory)

# --- EXAMPLE USAGE (HOW TO RUN THE ORCHESTRATOR) ---
# The orchestrator is designed to run in a loop where the system executes
# steps until it hits a human_approval node or END.

def run_orchestrator(query: str, thread_id: str):
    """Initializes and runs the orchestrator."""
    orchestrator = EmailAutomationOrchestrator()
    
    # Initial state
    initial_state = GraphState(
        user_query=query,
        intent="",
        context_data="",
        draft="",
        safety_check_passed=False,
        draft_version=0,
        agent_history=[f"User Input: {query}"],
        citations=[],
        # Set human_approved to True here to force it past the human_approval node
        # when running in a non-interactive simulation.
        human_approved=True 
    )

    # Stream the output for the given thread_id (for persistence/session tracking)
    # Config includes the thread_id for persistence and the callback for Langfuse
    config = {"configurable": {"thread_id": thread_id}}
    
    # NOTE: Add langfuse callback handler to config if initialized:
    # config = {"configurable": {"thread_id": thread_id}, "callbacks": [LgFuse_callback]}

    print(f"\n--- Starting Orchestrator for Thread ID: {thread_id} ---")
    
    # Stream the execution steps
    for s in orchestrator.stream(initial_state, config=config):
        print(s)
        
    # Get the final state for the last step
    final_state = orchestrator.get_state(config)
    print("\n--- FINAL STATE SUMMARY ---")
    print(f"Final Draft:\n{final_state.values['draft']}")
    print(f"Citations: {final_state.values['citations']}")
    print(f"Workflow Path:\n" + "\n".join(final_state.values['agent_history']))


class Orchestrator:
    """Compatibility adapter exposing a small imperative API expected by the FastAPI server.

    Methods implemented:
    - create_draft(task) -> (draft, safety_report, routing_decision, context, external_info)
    - approve_and_send(..., send=False) -> FinalEmail
    """
    def __init__(self):
        # Do not call the heavy EmailAutomationOrchestrator initializer (it requires langgraph).
        # Instead, instantiate only the agent classes we need for the simple adapter.
        self._intent = IntentClassifierAgent()
        self._retriever = RetrieverAgent()
        self._drafter = DrafterAgent()
        self._safety = SafetyReviewerAgent()
        self._external = ExternalToolAgent()

    def create_draft(self, task):
        # Accept either pydantic model or dict-like
        try:
            intent_res = self._intent.classify_intent(task)
        except Exception:
            intent_res = {"intent_label": "General_Inquiry", "needs_external_search": False}

        context = self._retriever.retrieve_context(task, intent_res)

        external_info = None
        if intent_res.get("needs_external_search"):
            external_info = self._external.fetch_external_info(task, intent_res)

        draft = self._drafter.draft_email(task, context, external_info=external_info)

        safety_result = self._safety.review_context("\n\n".join(context.snippets) if hasattr(context, "snippets") else "")

        # Convert safety result to SafetyReport-like simple object
        from ..models import SafetyReport, FinalEmail

        approved = False
        notes = []
        redacted = draft.body if hasattr(draft, "body") else ""
        if isinstance(safety_result, dict):
            approved = safety_result.get("review_status", "FAIL") == "PASS"
            notes = [safety_result.get("review_notes", "")] if safety_result.get("review_notes") else []

        safety_report = SafetyReport(approved=approved, issues=notes, redacted_body=redacted)

        routing = "send" if approved else "human_approval"

        return draft, safety_report, routing, context, external_info

    def approve_and_send(self, task, draft, safety, routing_decision, context, external_info, send: bool = False):
        from ..models import FinalEmail

        # Propagate trace_id (if any) from the draft to the final response so
        # the frontend can show a Langfuse trace link.
        trace_id = getattr(draft, "trace_id", None)
        final = FinalEmail(recipient=task.recipient, subject=draft.subject, body=draft.body, trace_id=trace_id)
        # If send=True, integrate with email sender; here we only simulate
        return final

if __name__ == "__main__":
    # Simulate a user query
    user_request = "Draft an executive summary email to the team about the Q3 financial results and mention the key finding that our market share grew by 5% in the last quarter."
    
    # Use a unique thread ID for session persistence
    session_id = "session-12345" 
    
    # Run the simulation
    # NOTE: This will fail unless you have the actual agent classes implemented
    # and the LangGraph/LangChain libraries installed.
    # run_orchestrator(user_request, session_id)
    print("\nOrchestrator defined. You need to uncomment the run_orchestrator call")
    print("and implement the actual agent logic in the 'agents' package to run this.")