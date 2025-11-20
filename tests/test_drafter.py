import json
import pytest

from multi_agent_email.app.agents.drafter import DrafterAgent
from multi_agent_email.app.models import EmailTask, RetrievedContext


class DummyResponse:
    def __init__(self, content, status_code=200):
        self._content = content
        self.status_code = status_code

    def raise_for_status(self):
        if not (200 <= self.status_code < 300):
            raise Exception(f"HTTP {self.status_code}")

    def json(self):
        return self._content


def make_api_result_with_message(content_str: str):
    return {
        "id": "r1",
        "object": "chat.completion",
        "choices": [{"message": {"role": "assistant", "content": content_str}}]
    }


def test_strip_fenced_json(monkeypatch):
    agent = DrafterAgent(llm_model="test-model")
    agent.api_key = "test"

    fenced = "```json\n{\"subject\": \"Hello\",\"body\":\"Body text\"}\n```"
    res = make_api_result_with_message(fenced)

    monkeypatch.setattr('requests.post', lambda *a, **k: DummyResponse(res))

    task = EmailTask(session_id="s1", recipient="user@example.com", subject_hint="h", body_hint="b", task_description="do something")
    context = RetrievedContext(snippets=[], confidence=0.9)
    draft = agent.draft_email(task, context)

    assert draft.subject == "Hello"
    assert "Body text" in draft.body


def test_plain_json(monkeypatch):
    agent = DrafterAgent(llm_model="test-model")
    agent.api_key = "test"

    plain = '{"subject":"Plain","body":"Plain body"}'
    res = make_api_result_with_message(plain)
    monkeypatch.setattr('requests.post', lambda *a, **k: DummyResponse(res))

    task = EmailTask(session_id="s2", recipient="user2@example.com", subject_hint="", body_hint="", task_description="t")
    context = RetrievedContext(snippets=["s1"], confidence=0.8)
    draft = agent.draft_email(task, context)

    assert draft.subject == "Plain"
    assert "Plain body" in draft.body
    assert "vector_db" in draft.sources


def test_malformed_json_returns_error(monkeypatch):
    agent = DrafterAgent(llm_model="test-model")
    agent.api_key = "test"

    bad = "```json\n{not a valid json}\n```"
    res = make_api_result_with_message(bad)
    monkeypatch.setattr('requests.post', lambda *a, **k: DummyResponse(res))

    task = EmailTask(session_id="s3", recipient="user3@example.com", subject_hint="", body_hint="", task_description="t")
    context = RetrievedContext(snippets=[], confidence=0.1)
    draft = agent.draft_email(task, context)

    # When parsing fails the Drafter returns an error DraftEmail starting with [ERROR]
    assert draft.subject.startswith("[ERROR]")
