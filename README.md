# Multi-Agent Email & Task Automation Assistant

Generate **executive-style emails** with **context retrieval**, **web/API enrichment**, **safety review**, and **human approval**. The system orchestrates **five agents** with dynamic routing, stores knowledge in a **vector DB**, and logs every action with **Langfuse** for observability.

---

## ✨ Features

- **Five-agent graph:**  
  `Intent → (Retriever ⟂ External Tool) → Drafter → Safety → Human Approval → Send → Log`
- **Dynamic routing** via confidence & guardrails (e.g., “insufficient context → web/API search”)
- **Vector DB (RAG)** over org knowledge (policies, FAQs, past threads)
- **External Tool-Enabled agent** for internet/API lookups when RAG isn’t enough
- **Human-in-the-loop** (mandatory sign-off before sending)
- **Persistent memory** (per session/contact) & **task logging**
- **Observability** with **Langfuse** (traces, spans, prompt/version tracking)

---
## 🧱 Architecture (high level)

```text
CLIENT (UI/CLI/API)
    |
    v
+----------------------------+
| Orchestrator (LangGraph)   |
+-------------+--------------+
              |
              +--> Intent Classifier
              |         |
              |         +-- if context_confidence >= THRESHOLD --> Retriever (Vector DB)
              |         |
              |         +-- else --------------------------------> External Tool (Web/API)
              |
              +--> Drafter (LLM, executive tone)
              |
              +--> Safety Reviewer (policy/PII/tone)
              |
              +--> Human Approval --> Sender --> Logger
                                  |
                                  +-- stores to: Vector DB (Chroma)
                                  +-- writes to: Relational DB (sessions/approvals/audit)
                                  +-- traces in: Langfuse (observability)

Routing logic (simplified):

1. Intent labels task (reply / follow-up / request info / unknown).

2. If context_confidence ≥ τ → Retriever; else → External Tool Agent.(web/API)

3. Drafter composes the executive email with gathered context.

4. Safety enforces policy (PII redaction, tone, blocklist).

5. Human Approval edits/approves → Send → Log.

🗂️ Repository Layout

.
├─ app/
│  ├─ graph/                # nodes, edges, routing policies
│  ├─ agents/
│  │  ├─ intent.py
│  │  ├─ retriever.py
│  │  ├─ external_tool.py   # web/API search tools
│  │  ├─ drafter.py
│  │  └─ safety.py
│  ├─ tools/                # search, calendar, CRM, HTTP, etc.
│  ├─ services/             # email sender, vector store, db
│  ├─ ui/                   # FastAPI review UI (or CLI)
│  └─ config.py
├─ data/                    # seed docs for vector DB
├─ scripts/                 # ingest, bootstrap
├─ tests/
└─ README.md

🧠 Agent Responsibilities
- Intent Classifier
  Detects task type and urgency; emits required context signals (e.g., needs_prior_thread, needs_pricing_policy).

- Retriever Agent (RAG)
  Embeds query; fetches top-k snippets from Vector DB (past emails, policies, product docs).
  Outputs context_confidence.

- External Tool-Enabled Agent
  When context_confidence < τ or needs_external = True, performs web/API search (e.g., company news, product specs, CRM lookup).
  Tools are whitelisted and rate-limited.

- Drafter Agent
  Generates executive-style email: strong subject, concise body, clear CTA; cites sources inline for reviewer.

- Safety Reviewer Agent
  Applies policy guardrails (PII, confidentiality, tone, blocklist). Can redact, revise, or block.

All drafts must pass Human Approval before Sender dispatches via SMTP/Gmail API. Task Logger persists trace & audit.

🔐 Security & Privacy
- No auto-send: human approval is mandatory.

- PII minimization and redaction in logs; store hashes when needed.

- Role-based access for the review UI; signed webhooks for the email provider.

- Configurable domain/phrase blocklists enforced by Safety.

⚙️ Setup
1) Create environment
Code: 
git clone https://github.com/<you>/multi-agent-email-assistant.git
cd multi-agent-email-assistant
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
2) Environment variables (.env)
Code :
# LLM
OPENAI_API_KEY=...

# Vector DB
VECTOR_DB_DIR=./.chroma

# Email (choose one)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASS=...

# Langfuse
LANGFUSE_PUBLIC_KEY=...
LANGFUSE_SECRET_KEY=...
LANGFUSE_HOST=https://cloud.langfuse.com

# External tools (examples)
NEWS_API_KEY=...
CRM_BASE_URL=...
CRM_API_KEY=...

# App
APP_SECRET=change-me
CONFIDENCE_THRESHOLD=0.65

3) Ingest org knowledge
Code
python scripts/ingest.py --path data/knowledge
4) Run
Code
uvicorn app.ui.server:app --reload --port 8000
Open http://localhost:8000 for the review UI.

✅ Example Flow
1. User: “Follow up with ACME on the Q3 pricing revision and include the latest market note.”

2. Intent → client_follow_up; flags needs_prior_thread + needs_market_note.

3. Retriever pulls last thread + pricing policy; confidence = 0.52 (< τ) → route to External Tool Agent.

4. External Tool fetches market note via web/API; returns snippet + link.

5. Drafter produces executive email with CTA and citations.

6. Safety redacts internal codes, OK tone.

7. Human edits one line and approves.

8. Sender dispatches; Logger writes audit + Langfuse trace.

🔎 Observability (Langfuse)
- Each run creates a trace with node spans, prompts, model versions, latencies, and cost.

- Compare different routing thresholds or models side-by-side in the Langfuse dashboard.

🧪 Tests

pytest -q
Unit tests for routing (confidence_threshold), safety rules, and an end-to-end happy path.

🗺️ Roadmap
- Calendar/CRM deep tools (create events, update opportunities)

- Fine-tuned styles per executive/team

- Feedback-to-learn loop (review edits → prompt/model updates)

- Hybrid search (BM25 + embeddings) in Vector DB

- Multi-tenant RBAC & audit exports

🤝 Contributing
Open an issue describing the change; include a short trace/screenshot from Langfuse when relevant. Run tests before submitting a PR.

📝 License
MIT (see LICENSE).

Notes

The stack is provider-agnostic: swap the LLM, Vector DB, or email provider by changing app/config.py and service adapters.

Keep Human-in-the-Loop mandatory for production deployments.
