# Dashboard Creation Agent — Project Briefing

**Read this file first at the start of every session.**

---

## What this project is and why it exists

This project builds an AI agent that lets a business user describe a dashboard in plain English and receive a working, interactive HTML dashboard within seconds. The user should never need to write SQL, Python, or any code.

The agent's job:
1. Understand what the user wants (using a data dictionary — this is RAG)
2. Ask clarifying questions if the request is vague
3. Produce a structured JSON "spec" describing the dashboard
4. Pass that spec to a renderer that reads the data and builds the HTML

Built by a data and insurance professional learning AI agent development for career transition into AI/ML product or platform roles.

---

## Project folder

`C:\Users\shrad\OneDrive\Documents\claude-practice\dashboard-agent`

---

## Folder structure

```
dashboard-agent/
├── CLAUDE.md                  ← this file
├── .env                       ← API key (never share; excluded by .gitignore)
├── .gitignore
├── data/                      ← synthetic CSV data files
│   ├── policies.csv           ← 1,000 policies
│   ├── quotes.csv             ← 2,703 quotes (37% bind rate)
│   └── claims.csv             ← 566 claims
├── specs/                     ← dashboard spec files
│   ├── spec_format.md         ← canonical spec documentation
│   ├── example_spec_1.json    ← hand-written: quote conversion by state
│   ├── example_spec_2.json    ← hand-written: claims trend by product
│   └── generated_*.json       ← AI-generated specs (timestamped)
├── prompts/                   ← all LLM prompts as .txt files (for Glean reuse)
│   ├── spec_generation_prompt.txt  ← main prompt template (RAG step included)
│   ├── correction_prompt.txt       ← sent on retry if first response is invalid JSON
│   └── clarifier_prompt.txt        ← evaluates whether a request needs clarification
├── output/                    ← generated HTML dashboard files
├── logs/                      ← governance audit logs
│   └── validation_log.txt     ← append-only log of every validation result
├── data_dictionary.md         ← business definitions of every table and column (RAG source)
├── generate_data.py           ← one-time script to create the CSV files (already run)
├── renderer.py                ← reads a spec JSON → writes an HTML dashboard
├── spec_generator.py          ← reads dict + spec format, calls Claude API → JSON spec
├── clarifier.py               ← evaluates request clarity; asks questions if vague (HITL)
├── validator.py               ← governance guardrail: column check + spec checks + logging
├── pipeline.py                ← end-to-end: plain English → clarifier → spec → validator → HTML
├── app.py                     ← Streamlit web UI (Day 4): wraps the full pipeline in a browser app
├── requirements.txt
└── learning-notes.md
```

---

## 7-Day Plan

| Day | Status | Goal |
|-----|--------|------|
| **Day 1** | ✅ Done | Foundation + renderer — synthetic data, data dictionary, spec format, HTML renderer |
| **Day 2** | ✅ Done | LLM spec generation — Claude API wired in; full pipeline working end-to-end |
| **Day 3** | ✅ Done | Clarifying questions + validation — clarifier.py, validator.py, audit log, 5 tests |
| **Day 4** | ✅ Done | Streamlit UI — app.py, six-screen flow, embedded dashboard iframe, sidebar examples |
| **Day 5** | ✅ Done | Testing — 15-request stress test, fixed month_product bug, governance check, confidence indicator, recent requests |
| **Day 6** | ✅ Done | README + demo prep — comments, README.md, RESUME_BULLETS.md, DEMO_SCRIPT.md, GitHub-ready |
| **Day 7** | ⬜ Next | Buffer — push to GitHub, take screenshot, record demo |

---

## What is working right now (as of end of Day 4)

**Two ways to run the agent:**

Option A — Streamlit web app (recommended):
```
python -m streamlit run app.py
```
Opens at http://localhost:8501 — a full browser UI with sidebar example buttons, clarifying question forms, a processing status panel, and the embedded dashboard.

Option B — terminal (original pipeline):
```
python pipeline.py "Show me claims by state this year"
```
Same pipeline, command-line only.

**What each script does:**
- `generate_data.py` — run once; already done. Creates the 3 CSV files.
- `renderer.py` — reads a spec JSON + CSV data → saves an HTML dashboard.
- `spec_generator.py` — reads data dictionary (RAG), calls Claude API, validates JSON structure, saves spec file.
- `clarifier.py` — calls Claude to evaluate request clarity. `evaluate_request()` returns the verdict as a dict (used by app.py). `clarify()` handles terminal I/O (used by pipeline.py).
- `validator.py` — governance guardrail: checks original request for fake column names, checks spec structure, checks spec vocabulary. Logs every result to `logs/validation_log.txt`.
- `pipeline.py` — terminal orchestrator (all four steps).
- `app.py` — Streamlit web UI: six screens (home → evaluating → clarifying → processing → results → error), sidebar with 5 example requests + recent requests history, confidence indicator, embedded dashboard iframe, "What did the agent do?" expander.
- `test_runner.py` — automated stress test: 15 diverse requests, non-interactive, logs results to `logs/test_results.txt`.
- `data/request_history.json` — persistent store of the last 5 successful requests (shown as sidebar buttons).

**Tested and confirmed working (Day 5 stress test: 13/15 pass):**
- All 5 CLEAR requests produce dashboards (5/5)
- All 5 VAGUE requests produce dashboards even without human answers (5/5)
- All-caps, punctuation, and multi-dataset EDGE requests handled correctly
- "Agent salaries" → governance message: "data not available in our system"
- Empty string → blocked before any API call
- Recent Requests sidebar updates after each successful run
- Confidence indicator shows High/Medium/Low on the results screen

**Day 6 starting point:**
The agent is fully functional and stress-tested. Day 6 is documentation and demo prep.

---

## AI Concepts Being Learned

| Concept | What it means in this project |
|---------|-------------------------------|
| **RAG** (Retrieval-Augmented Generation) | The agent reads `data_dictionary.md` before answering, so it knows what columns and tables exist. This prevents hallucination — the LLM cannot make up columns that don't exist. |
| **Prompt Engineering** | Writing instructions to the LLM in `prompts/` as separate files. Each file is a reusable prompt template. |
| **Agentic Workflow** | The system takes multiple steps (understand → clarify → plan → render) rather than answering in one shot. |
| **Structured Output** | The LLM is asked to produce JSON in a defined format, not free-form text. This makes the output machine-readable and renderable. |
| **Human in the Loop** | The clarifying-questions step (Day 3) is intentional: the agent pauses and asks the human before proceeding when it is uncertain. |
| **Deterministic vs Non-deterministic** | The renderer (`renderer.py`) is deterministic — same spec always produces the same chart. The LLM step is non-deterministic — slightly different words may produce slightly different specs. |

---

## Background

- **Domain:** Data governance, insurance (auto and home lines)
- **Goal:** Career pivot into AI/ML product or platform roles
- **Coding level:** Learning — all code decisions are explained in plain business language
- **Target platform:** Prompts will eventually live in Glean (enterprise AI platform). Keep all prompts in `prompts/` as `.txt` or `.md` files, never hardcoded inside Python scripts.

---

## Key design decisions

- **Prompts are external files** — so they can be edited, versioned, and moved to Glean without touching Python
- **JSON spec as the contract** — the spec is the handoff point between the LLM (Day 2+) and the renderer (Day 1). This separation means you can improve either side independently.
- **Standalone HTML output** — each dashboard is a single `.html` file. No server needed, can be emailed.
