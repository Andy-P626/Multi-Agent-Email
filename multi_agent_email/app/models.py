from typing import List, Optional, Dict, Any

from pydantic import BaseModel, EmailStr, Field


# --- Core Task and Intent Models ---

class EmailTask(BaseModel):
    """
    Defines the initial request from the user, triggering the task workflow.
    """
    session_id: str
    recipient: EmailStr
    subject_hint: Optional[str] = None
    body_hint: Optional[str] = None
    task_description: str


# --- Intermediate Agent Models ---

class RetrievedContext(BaseModel):
    """
    Data structure for context returned by the retrieval agent.
    """
    snippets: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class DraftEmail(BaseModel):
    """
    The initial draft produced by the drafting agent.
    """
    subject: str
    body: str
    sources: List[str] = Field(default_factory=list)
    # Optional Langfuse trace identifier for observability
    trace_id: Optional[str] = None


class SafetyReport(BaseModel):
    """
    The outcome of the safety/critique agent, including redactions if necessary.
    """
    approved: bool
    issues: List[str] = Field(default_factory=list)
    redacted_body: str


# --- Final Output Models ---

class FinalEmail(BaseModel):
    """
    The final email structure ready for sending (after human approval/editing).
    """
    recipient: EmailStr
    subject: str
    body: str
    # Optional trace id propagated from the drafting/synthesis step
    trace_id: Optional[str] = None


# --- State and Logging Models ---

class SessionMemory(BaseModel):
    """
    Stores the conversation history for a single session, used by the router/planner.
    """
    # History is a list of generic message objects (user/assistant)
    history: List[Dict[str, Any]] = Field(default_factory=list)


class TaskLogEntry(BaseModel):
    """
    The comprehensive log entry for a single task execution flow.
    This will be used for persistence and Langfuse monitoring.
    """
    session_id: str
    task: EmailTask
    intent: Dict[str, Any] # Intent classification results
    context: RetrievedContext
    external_info: Optional[str] # E.g., results from a web search tool
    draft: DraftEmail
    safety: SafetyReport
    final_email: Optional[FinalEmail] = None
    extra: Dict[str, Any] = Field(default_factory=dict) # For monitoring, debugging, or future expansion