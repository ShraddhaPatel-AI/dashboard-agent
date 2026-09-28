# Resume Content — AI Dashboard Creation Agent

---

## FORMAT A: PROJECT TITLE AND ONE-LINE SUMMARY

**AI Dashboard Creation Agent** | Python, Streamlit, Anthropic Claude API

Built an AI agent that converts plain-English business requests into interactive data dashboards using RAG, agentic workflows, and a governance validation layer — no SQL or coding required from the end user.

---

## FORMAT B: THREE DETAIL BULLETS

- **Designed a multi-step agentic pipeline** using the Anthropic Claude API (`claude-sonnet-4-6`) with RAG (Retrieval-Augmented Generation): the agent reads a live data dictionary before every API call to ground responses in real schema — eliminating hallucinated column names and reducing invalid specs to near zero across 15-request stress testing.

- **Built a full-stack AI application** in Python and Streamlit with a six-screen interactive UI, Human-in-the-Loop clarification forms, live pipeline status updates, a keyword-based confidence indicator, and persistent request history — wiring together four independent modules (clarifier, spec generator, validator, renderer) so each can be improved without affecting the others.

- **Implemented a governance guardrail layer** (`validator.py`) with four automated checks that run before any dashboard is rendered: blocking requests for unavailable data, catching hallucinated column references, verifying structured output format, and validating AI-generated vocabulary — with an append-only audit log that records every pipeline result for review.

---

## FORMAT C: SKILLS TO ADD TO YOUR RESUME

**AI and Machine Learning**
- Retrieval-Augmented Generation (RAG)
- Prompt Engineering
- Agentic Workflow Design
- Human-in-the-Loop (HITL) Systems
- Structured Output / JSON Schema Enforcement
- AI Self-Evaluation and Confidence Scoring
- LLM Governance and Guardrail Design
- Anthropic Claude API

**Tools and Technologies**
- Python
- Streamlit
- Pandas
- Plotly
- python-dotenv
- Anthropic SDK (`anthropic`)

**Concepts and Methodologies**
- Multi-step AI Pipeline Architecture
- Separation of Concerns (AI logic vs. I/O vs. rendering)
- Deterministic vs. Non-deterministic System Design
- Automated Stress Testing for AI Agents
- Governance Audit Logging
- Graceful Error Handling and User-Facing Messaging
