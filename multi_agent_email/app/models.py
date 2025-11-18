from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class EmailTask(BaseModel):
    session_id: str
    recipient: EmailStr
    subject_hint: Optional[str] = None
    body_hint: Optional[str] = None
    task_description: str


class RetrievedContext(BaseModel):
    snippets: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class DraftEmail(BaseModel):
    subject: str
    body: str
    sources: List[str] = Field(default_factory=list)


class SafetyReport(BaseModel):
    approved: bool
    issues: List[str] = Field(default_factory=list)
    redacted_body: str


class FinalEmail(BaseModel):
    recipient: EmailStr
    subject: str
    body: str


class SessionMemory(BaseModel):
    history: List[dict] = Field(default_factory=list)


class TaskLogEntry(BaseModel):
    session_id: str
    task: EmailTask
    intent: dict
    context: RetrievedContext
    external_info: Optional[str]
    draft: DraftEmail
    safety: SafetyReport
    final_email: Optional[FinalEmail] = None
    extra: dict = Field(default_factory=dict)
