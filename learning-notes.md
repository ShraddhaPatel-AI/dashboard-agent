# Learning Notes — Day 1 & Day 2

*Plain-English explanations of what was built and why.*

---

## What each file does and why it exists

| File | What it does | Why it exists |
|------|-------------|---------------|
| `CLAUDE.md` | Project briefing — context, plan, concepts | Every AI session reads this first so it knows the project without you explaining it again. Think of it as the "onboarding doc" for the AI. |
| `generate_data.py` | Builds the three CSV data files from scratch | We needed realistic insurance data to practice with. Real data has privacy constraints; synthetic data lets you learn freely. Run it once; never need to run it again unless you want fresh data. |
| `data/policies.csv` | 1,000 insurance policies | The "policies in force" table — the core of any insurance data model. |
| `data/quotes.csv` | 2,703 quotes (37% bound, rest lost/open) | The sales funnel table — lets the agent answer questions about conversion rates and pipeline. |
| `data/claims.csv` | 566 claims | The loss experience table — lets the agent answer questions about claims trends and severity. |
| `data_dictionary.md` | Business definitions of every table and column | This is the "RAG document" — the agent reads it before answering so it knows what data exists and what it means. Without this, the AI would guess or make up column names. |
| `specs/spec_format.md` | Defines the JSON blueprint format | The contract between the AI (which creates the spec) and the renderer (which builds the dashboard). Both sides need to speak the same language. |
| `specs/example_spec_1.json` | Hand-written spec: "Quote conversion by state" | A test case and an example for the AI to learn from on Day 2. |
| `specs/example_spec_2.json` | Hand-written spec: "Claims trend by product" | A second test case covering different chart types and metrics. |
| `renderer.py` | Reads a spec JSON → produces an HTML dashboard | The deterministic engine. Takes the AI's plan and executes it into a real, viewable file. |
| `output/example_spec_1.html` | Interactive dashboard: quote conversion | A working 4-chart HTML file, opens in any browser, no internet required. |
| `output/example_spec_2.html` | Interactive dashboard: claims trend | A working 3-chart HTML file. |
| `prompts/` | (Empty today — Day 2+) | Will hold all prompts as .txt/.md files so they can be reused in Glean without touching Python. |
| `requirements.txt` | Lists Python dependencies | Lets anyone recreate your environment with one command: `python -m pip install -r requirements.txt`. |

---

## What RAG means in this project

**RAG = Retrieval-Augmented Generation.**

In plain English: before the AI answers a question, it first *reads a document* to ground itself in facts.

In this project:
- The "retrieval" step is the agent reading `data_dictionary.md`.
- The "generation" step is the AI producing a JSON spec based on what it learned.

**Why does this matter?**  
Without RAG, if a user asks "show me claims by peril type," the AI might invent a column called `peril_type` that doesn't exist in the data. By reading the dictionary first, it knows the actual column is called `claim_type` — and it also knows the valid values (collision, fire, etc.).

**The business analogy:** It's like giving a new analyst a glossary before they write a report. Without the glossary, they'll guess. With it, they'll use the right terms.

---

## What deterministic vs non-deterministic means here

**Deterministic:** Same input always produces the same output. No randomness.  
**Non-deterministic:** Same input may produce slightly different output each time. Involves probability or LLM generation.

| Part of the system | Type | Why |
|---|---|---|
| `renderer.py` | **Deterministic** | Given the same spec JSON and data files, it always produces the exact same HTML. Pure math and logic. |
| LLM spec generation (Day 2) | **Non-deterministic** | Two users typing "show me claims by state" might get slightly different JSON specs — different column choices, different chart types. The AI is probabilistic. |
| `generate_data.py` | **Deterministic** | We set a random seed (`np.random.seed(42)`) so the same script always produces the same CSV data. |

**Why does this distinction matter?**  
- When something goes wrong in a non-deterministic step, you test it with many inputs and look at the distribution of outputs.  
- When something goes wrong in a deterministic step, you debug it like a spreadsheet formula — it's always reproducible.  
- Good AI systems push as much logic as possible into the deterministic layer (the renderer) and keep the non-deterministic layer (the LLM) focused on understanding intent.

---

## What I should be able to explain to my manager or in an interview

**"What did you build?"**  
A proof-of-concept pipeline where a business user describes a dashboard in plain English, and the system produces an interactive HTML dashboard automatically. Today I built the data foundation and the rendering engine. The AI-reasoning layer comes on Day 2.

**"What's the architecture?"**  
Three layers:  
1. **Data layer** — three linked CSV files (policies, quotes, claims) with a formal data dictionary.  
2. **Planning layer** — a JSON spec that bridges the user's intent and the technical rendering. The spec is like a blueprint: human-readable, auditable, and machine-executable.  
3. **Rendering layer** — a Python script that reads the spec and produces a standalone HTML dashboard using Plotly.

**"What AI concepts does this use?"**  
- **RAG:** The agent reads the data dictionary before answering, which prevents hallucination and keeps the output grounded in real data.  
- **Structured output:** The LLM produces JSON, not free text, so the output can be executed by code reliably.  
- **Separation of concerns:** Prompts are in separate `.txt` files (not buried in code) so they can be moved to an enterprise AI platform (Glean) without rewriting the system.

**"What's the business value?"**  
A business analyst or underwriting manager today spends 30–60 minutes requesting a dashboard from IT, waiting, and then iterating. This system could reduce that to under 60 seconds by letting them describe what they want in natural language. The same concept applies to any organization with structured data and non-technical stakeholders.

---

## Day 1 summary (5 lines)

1. Created a synthetic insurance dataset — 4,269 rows across policies, quotes, and claims — with realistic distributions matching the US insurance market.
2. Wrote a formal data dictionary documenting every column in business language, which the AI will read in later days to stay grounded in real data.
3. Defined a JSON spec format as the contract between the AI planning layer and the code rendering layer.
4. Built a renderer that converts any valid spec JSON into a professional, interactive HTML dashboard — no code needed after today.
5. Confirmed the system works end-to-end by rendering two dashboards: one on quote conversion by state/channel, one on monthly claims trends by product.

---

# Day 2 Notes — The Agent Brain

---

## What each new file does and why it exists

| File | What it does | Why it exists |
|------|-------------|---------------|
| `.env` | Stores your Anthropic API key | Keeps the key out of the code. If the key were inside a Python file, anyone who saw the file could use your account and run up a bill. |
| `.gitignore` | Tells git (and similar tools) to skip the `.env` file | Prevents the key from being accidentally uploaded to GitHub or shared in a zip file. |
| `prompts/spec_generation_prompt.txt` | The instructions sent to Claude to turn a plain-English request into a JSON spec | Keeping this in a text file — not inside Python — means you can edit the instructions without touching code, and you can copy the whole file into Glean when ready. |
| `prompts/correction_prompt.txt` | The instructions sent to Claude on a retry, if the first response was not valid JSON | A safety net. It tells Claude exactly what went wrong and asks it to try again with tighter constraints. |
| `spec_generator.py` | The "brain" — orchestrates the RAG step, the API call, validation, retry, and file save | This is the first time an LLM is actually involved. Everything before today was pure Python logic. |
| `pipeline.py` | The single command that runs the whole chain end-to-end | Without this, you would have to run spec_generator, then renderer, then open the file manually. This glues them together. |

---

## What RAG means — using today's work as the concrete example

**RAG = Retrieval-Augmented Generation.**  
You retrieve a document first, then you generate from it.

**Before today**, if you asked the AI "show me claims by state", it might invent a column called `region` or `territory` that doesn't exist in the data. That is called hallucination.

**Today's RAG step in plain English:**

1. Before calling Claude, `spec_generator.py` reads the full `data_dictionary.md` file (this is the "retrieval" step — fetching relevant context)
2. That content is pasted directly into the prompt — Claude reads it as part of the instructions
3. The prompt says: "Only use columns that appear in this dictionary"
4. Now Claude knows that the column is `state`, not `region` or `territory`

**The business analogy:** It is like handing a new consultant the company's data glossary before they write a report. Without the glossary, they might use the wrong terminology. With it, they use the exact terms the rest of the business recognizes.

**Why it is called RAG and not just "prompt engineering":** In production systems, the dictionary would be stored in a database and only the relevant pieces would be fetched per query (so a claims question only retrieves claims columns, not policy columns). Today we pass the whole dictionary because it is small. As the data model grows, you would want a true retrieval step — searching for the most relevant table definitions and including only those.

---

## What the .env file is and why it matters

An **API key** is like a password that gives you the right to use a paid service (in this case, Anthropic's AI). If someone else got your key, they could send requests that get billed to your account.

The `.env` file is a simple text file that stores secrets like this key. It sits on your laptop but never gets shared. The Python library `python-dotenv` reads it at runtime and makes the key available to the script as if you had typed it in the terminal — but without you ever typing it in the terminal.

The `.gitignore` file is a list of files that should never be copied or uploaded anywhere. Adding `.env` to it means: even if you later connect this folder to GitHub, OneDrive sync, or a zip tool, the `.env` file stays behind.

**Rule of thumb:** Secrets go in `.env`. Code goes in `.py`. They never mix.

---

## What structured output means and why we validate the JSON

**Structured output** means asking the AI to respond in a specific machine-readable format — in this case, a JSON object with exact keys — instead of free-form text.

Without structure, Claude might respond: *"I'd suggest a bar chart showing quote volume by state over the last 6 months, with California and Texas likely at the top..."* That is useful to a human, but Python cannot turn it into a chart.

With structured output, Claude responds with a JSON object that Python can directly read, validate, and pass to the renderer.

**Why we validate the JSON:**  
Claude is non-deterministic — it can occasionally produce:
- JSON wrapped in markdown code fences (```json ... ```) even when told not to
- A metric name with a slight variation (e.g., `"quote_count"` instead of `"count_quotes"`)
- A chart_id in the layout that doesn't match any chart

The `validate_spec()` function in `spec_generator.py` catches all of these before they crash the renderer. If it finds a problem, it sends a "correction prompt" to Claude explaining exactly what was wrong and asks for another attempt. Today, all three test requests passed on the first attempt with no correction needed.

---

## What the pipeline does — plain English, step by step

When you run `python pipeline.py "Show me quote volume by state"`:

1. **`pipeline.py` receives your words** and passes them to `spec_generator.py`

2. **`spec_generator.py` does the RAG step** — it opens `data_dictionary.md` and `specs/spec_format.md` and pastes their contents into the prompt template from `prompts/spec_generation_prompt.txt`

3. **The filled-in prompt is sent to Claude via the Anthropic API** — Claude reads the dictionary, the format rules, and your request, then responds with a JSON spec

4. **The JSON is validated** — if it has all the required keys and only uses valid metric/chart_type/grouping values, it is accepted; if not, a correction prompt is sent and Claude tries again

5. **The spec is saved** as a timestamped file in `specs/` — e.g., `specs/generated_20260928_093538.json` — so you have a record of what was generated

6. **`renderer.py` reads the spec** — it loads the CSV data, filters by time range, groups by the specified grouping, calculates the metric, and builds Plotly charts

7. **A standalone HTML file is saved** in `output/` — the file is named after the spec (same timestamp)

8. **The file opens in your browser automatically**

The whole chain from your words to a browser tab takes about 5–10 seconds.

---

## What I can say in an interview about what was built today

**"What does the agent do on Day 2?"**  
The agent takes a plain-English dashboard request, reads the company's data dictionary to understand what data is available (that's the RAG step), calls the Claude API to convert the request into a structured JSON spec, validates that the spec is well-formed, and then passes it to the rendering engine from Day 1. The whole chain from request to open browser tab takes under 10 seconds.

**"What is RAG and why does it matter here?"**  
RAG stands for Retrieval-Augmented Generation. Instead of asking the AI to answer from its training data alone (where it might invent column names), you first retrieve a relevant document — in this case the data dictionary — and inject it into the prompt. The AI can only reference what is in that document. This is the primary technique for preventing hallucination in enterprise AI applications where accuracy of data references matters.

**"What is structured output and why validate it?"**  
Structured output is when you instruct the AI to respond in a specific format — JSON, XML, a schema — rather than free text. It is what makes the AI's response machine-executable rather than just human-readable. Validation is necessary because AI models are non-deterministic: the same prompt can produce slightly different outputs. A validation layer catches format errors before they propagate through the system, and a correction prompt gives the AI a second chance to self-correct.

**"What design decision separates this from a simple chatbot?"**  
The separation of the prompt (in a .txt file) from the code (in .py files). This means the instructions can be edited by a business analyst, versioned separately from the code, and moved to an enterprise AI platform like Glean without any Python changes. It also means the rendering step is fully deterministic — once you have a valid spec, the output is always the same.

---

## Day 2 summary (5 lines)


1. Wired in the Anthropic API so the agent can now take any plain-English request and automatically generate a valid JSON dashboard spec using Claude.
2. Built the RAG step: the data dictionary is read and injected into every prompt, so Claude only references columns and tables that actually exist.
3. Added structured output validation — the spec is checked for required keys, valid metric names, and layout consistency before being passed to the renderer.
4. Connected spec generation to the renderer in a single `pipeline.py` command that produces an open browser tab in one step.
5. Confirmed the end-to-end pipeline on three real requests: quote volume by state, bind rate by channel, and monthly claims trend — all three passed on the first Claude call with no correction needed.

---

# Day 3 Notes — Human in the Loop and Data Governance

---

## What each new file does and why it exists

| File | What it does | Why it exists |
|------|-------------|---------------|
| `clarifier.py` | Calls Claude to evaluate whether a request has enough detail. If vague, prints questions for the user, collects typed answers, and returns an enriched request. | Without this, vague requests like "show me quotes" would get sent straight to spec generation. The result would be a dashboard that may not answer the actual business question. The clarifier ensures the agent understands intent before spending API budget. |
| `prompts/clarifier_prompt.txt` | Instructions for Claude telling it what makes a request "clear enough" — needs a metric, a grouping, and a time range. Lists all available options so Claude asks focused questions. | Same reason prompts live in `.txt` files generally: the logic can be tuned without changing Python code, and can be moved to Glean. |
| `validator.py` | Runs three governance checks after the spec is generated: (1) scan the original request for fake column names, (2) check the spec has all required keys, (3) check all metric/grouping/chart_type values are from the approved list. Logs every result to `logs/validation_log.txt`. | This is the data governance guardrail. Without it, a user could ask for "claim_amount_fake_column" and the AI would silently remap it to a real metric — hiding the error. The validator makes this problem visible and stops the pipeline before a misleading dashboard is rendered. |
| `logs/validation_log.txt` | Append-only log of every validation result with timestamp, spec file, and original request. | An audit trail. In a production system, governance teams want to know: who asked for what, did it pass, and if it failed, why. This file provides exactly that — it grows over time as the agent is used. |

---

## What Human in the Loop (HITL) means

**Human in the Loop** means pausing an automated process to ask a human for input before continuing.

In this project, the clarifier creates a HITL moment:

1. User types a vague request ("Show me quotes")
2. The agent evaluates it — finds it's missing a metric, grouping, or time range
3. **The pipeline pauses** and prints questions to the terminal
4. The user types answers
5. The pipeline resumes with a more specific request

**Why this matters:** Without HITL, an AI system either guesses (and may be wrong) or fails silently. With HITL, the agent asks instead of assumes — which produces better outputs and builds user trust in the system.

**The design choice: max one round of questions.** We deliberately limited the clarifier to a single round of questions. More rounds feel like an interrogation. The goal is just enough clarification to unblock the generation step, not a full requirements gathering session.

**HITL vs. fully automated:** Some requests are specific enough to skip HITL entirely ("What is bind rate by channel this year?" went straight through in testing). The clarifier evaluates each request individually, adding friction only where it is genuinely needed.

---

## What the validator does — and why it runs on the original request

The validator runs on **both** the spec (the AI's output) and the **original user request** (what the user typed).

**Why check the original request?** Here is the problem it solves:

A user types: "Show me claim_amount_fake_column by state"

Without governance:
1. Claude sees a term that looks like a column name
2. Claude's prompt says to only use approved metrics, so it maps the fake term to `sum_claim_amount`
3. The dashboard renders — but it answers a different question than what the user asked
4. The user has no idea the substitution happened

With the validator:
1. The validator scans the original request for any underscore-delimited terms
2. It checks each one against the list of real column names, metric keys, and grouping keys
3. `claim_amount_fake_column` is not in that list → pipeline stops with a plain error
4. User is told: "this is not a recognized column name" and shown the valid options

**The business value of this check:** In insurance, inaccurate data references can lead to wrong business decisions. A dashboard silently reporting on a remapped metric is worse than a dashboard that fails to render — because at least a failure is visible. The validator makes the data contract explicit: if you reference a column name, it must be real.

---

## What the validation log tells you

The file `logs/validation_log.txt` grows every time the pipeline runs. Here is what today's tests produced:

```
[2026-09-28 09:58:44] PASS | specs\generated_... | 'Show me monthly quote volume by state' | 1 chart(s)
[2026-09-28 09:59:04] PASS | specs\generated_... | 'What is bind rate by channel this year?' | 1 chart(s)
[2026-09-28 09:59:59] FAIL [column_check] | 'Show me claim_amount_fake_column by state' | 'claim_amount_fake_column' is not a recognized column...
[2026-09-28 10:00:24] PASS | specs\generated_... | 'Show me claims by state this year' | 1 chart(s)
```

Each line has: timestamp, pass/fail, which check failed (column_check, structure, or vocabulary), the spec file, and the first 80 characters of the request. This format makes it easy to grep for failures, count usage, and build a compliance report.

---

## Deterministic vs non-deterministic — applied to today's pipeline

Day 1 introduced this concept. Today's pipeline makes the distinction concrete:

| Step | File | Deterministic? | Why |
|---|---|---|---|
| Clarifier evaluation | `clarifier.py` → Claude API | **Non-deterministic** | Claude decides whether a request is clear; the same request could occasionally get a different verdict |
| User question + answer | Terminal input | **Deterministic** | Whatever the user types is what it is |
| Spec generation | `spec_generator.py` → Claude API | **Non-deterministic** | Claude's JSON output can vary slightly across runs |
| Spec validation | `validator.py` | **Deterministic** | Regex + set lookup — same input always gives the same result |
| Rendering | `renderer.py` | **Deterministic** | Pure pandas + Plotly — same spec always produces the same HTML |
| Logging | `validator.py` | **Deterministic** | Always appends a timestamped line |

The pattern: **non-deterministic steps understand; deterministic steps execute.** The AI interprets intent and generates plans. Python enforces rules and produces outputs. This division of responsibility is the foundation of reliable AI systems.

---

## Prompts in separate files — why it matters more now

Today's pipeline has three prompts:

| Prompt file | Used by | Purpose |
|---|---|---|
| `spec_generation_prompt.txt` | `spec_generator.py` | Turn a plain-English request into a JSON spec |
| `correction_prompt.txt` | `spec_generator.py` | Retry if the first JSON was invalid |
| `clarifier_prompt.txt` | `clarifier.py` | Evaluate whether a request needs clarification |

Each file uses `__PLACEHOLDER__` markers. Python reads the file, substitutes the markers with real values, and sends the filled-in text to Claude. Claude never sees Python code — only text.

**Why does this separation matter?**
- A business analyst who understands insurance can improve the clarifier prompt by editing a `.txt` file — no Python knowledge required
- When this agent moves to Glean, each `.txt` file maps directly to a Glean skill prompt
- The prompts can be versioned separately from the code — you can try different versions of the clarifier instructions without touching the Python logic

---

## What I can say in an interview about Day 3

**"What is Human in the Loop and why did you add it?"**
Human in the Loop means pausing an automated workflow to collect human input before continuing. I added a clarification step that evaluates each request for completeness before calling the AI to generate a spec. If a request is missing a metric, grouping, or time range, the agent asks the user 2-3 focused questions, collects answers, and combines them with the original request. This produces better dashboards and avoids wasting API budget on requests that are too vague to answer well.

**"What is a data governance guardrail?"**
A governance guardrail is a rule that enforces the data contract — the agreement about what data references are valid. In this system, the validator scans the user's original request for any underscore-delimited terms (which look like column names) and checks them against the real list of column names, metrics, and groupings. If a term doesn't match, the pipeline stops with a plain-English error. This prevents the AI from silently remapping a fake column reference to a real metric, which would produce a dashboard that appears to answer one question but actually answers a different one.

**"Why does the validator check the original request instead of just the spec?"**
Because the AI is instructed to use only approved metric names, it will always produce a valid spec — it silently translates unknown terms to the closest match. The spec alone never reveals the translation. By checking the original request, we catch the discrepancy between what the user asked for and what was actually computed. The spec check handles structural and vocabulary errors; the request check handles governance violations.

**"What is an audit log and why does this system have one?"**
An audit log is an append-only record of what happened and when. The validation log records every request that ran through the pipeline — including the timestamp, spec file, original request text, and whether it passed or failed. In an enterprise setting, governance teams need this kind of record to answer: who used the system, what did they ask for, did the request meet data standards, and if it failed, why. The log also helps with debugging — if a user reports that a dashboard was wrong, you can find the original spec and request and trace back to what was generated.

---

## Day 3 summary (5 lines)

1. Added a clarifier step that uses Claude to evaluate each request and ask 2-3 focused questions if the request is too vague — the agent now has a human-in-the-loop before committing API budget to spec generation.
2. Built a validator with three governance checks: fake column detection in the original request, spec structure validation, and spec vocabulary validation — all three run before the renderer is called.
3. Moved vocabulary checks out of `spec_generator.py` and into `validator.py`, giving each module a single clear responsibility: the spec generator produces JSON, the validator enforces rules.
4. Added an append-only validation log at `logs/validation_log.txt` that records every pipeline run with timestamp and pass/fail details — the beginning of an audit trail.
5. Confirmed all 5 test cases: vague requests triggered questions, specific requests passed through directly, the fake column was caught by the validator, and the final clean request produced a rendered dashboard in the browser.

---

# Day 4 Notes — Streamlit Web Interface

---

## What changed today and why

Until today, the entire agent ran in a terminal window. A business user had to open PowerShell, type a Python command, and read status messages in a console. Day 4 wraps the exact same pipeline in a proper web application so the user never touches a terminal.

The pipeline code (`spec_generator.py`, `validator.py`, `renderer.py`) did not change at all. Only two things changed:

1. `clarifier.py` got a new exported function, `evaluate_request()`, that returns the clarifier's verdict as a Python dict without calling `input()`. The Streamlit app calls this instead of `clarify()`, because Streamlit handles questions as form elements on the page — not as terminal prompts.
2. `app.py` was written from scratch as a Streamlit application that wraps the whole pipeline.

This is an important pattern: the business logic and the user interface are separate. You can swap the UI (terminal → web → Slack bot → API endpoint) without touching the agent logic at all.

---

## What Streamlit is

**Streamlit** is a Python library that turns a regular Python script into a web application. You write Python, run one command, and get a browser app.

The core idea: every time the user interacts with the page (clicks a button, types in a box), Streamlit re-runs the entire script from top to bottom. It then compares the new output to the old output and updates only what changed.

**What this means for our agent:**
- We store where the user is in the flow using `st.session_state` (a dictionary that persists between reruns)
- We use an `if / elif` block to route to the right screen based on the current state
- Each screen renders its own widgets and sets the next state when the user acts

**The key mental model:** Streamlit is not a traditional web framework with separate routes and controllers. It is a Python script that reruns on every click. Session state is the only memory that survives between reruns.

---

## What the five screens do

| Screen | Trigger | What it shows |
|---|---|---|
| `home` | App starts (or "Build Another" is clicked) | Title, text area for the request, Build button |
| `evaluating` | User clicks Build | Spinner while Claude evaluates the request |
| `clarifying` | Claude says request is vague | The clarifying questions as a form, one input per question |
| `processing` | User submits answers (or request was already clear) | Step-by-step status panel: spec → validate → render |
| `results` | Pipeline succeeds | Embedded dashboard iframe + "What did the agent do?" expander |
| `error` | Validator raises ValueError | Friendly plain-English error message, not a Python traceback |

The code has one `if / elif` block that checks `st.session_state["screen"]` and renders the appropriate screen. Each screen ends by setting the next screen value and calling `st.rerun()` to transition.

---

## Why `evaluate_request()` is separate from `clarify()`

The original `clarify()` function had terminal I/O built in: it called `input()` to collect answers. That works in a terminal but breaks in Streamlit, because Streamlit's Python process does not have a terminal attached.

The fix: pull the Claude call into its own function, `evaluate_request()`, that returns a plain Python dict (`{"status": "clear", ...}` or `{"status": "needs_clarification", "questions": [...]}`). The Streamlit app calls that function to get Claude's verdict, then renders the questions as form elements itself. The `clarify()` function still exists unchanged for terminal use via `pipeline.py`.

This is called **separation of concerns**: the function that calls Claude is separate from the function that handles I/O. The same intelligence can be wired to different input/output mechanisms.

---

## What the `os.chdir()` line does and why it is necessary

At the top of `app.py`:

```python
os.chdir(os.path.dirname(os.path.abspath(__file__)))
```

**The problem:** When you run `python -m streamlit run app.py`, Streamlit starts from a scratch workspace directory — not from the project folder. Every `open("prompts/clarifier_prompt.txt")` call in the other modules looks for that file relative to the scratch workspace and fails.

**The fix:** `os.path.abspath(__file__)` gives the full path to `app.py` itself. `os.path.dirname(...)` strips the filename, leaving just the folder. `os.chdir(...)` changes the working directory to that folder. After this one line, all relative paths in all modules resolve correctly.

**The lesson:** Any Python app that uses relative file paths must control its working directory. In a server environment, the launch location is not guaranteed to be the project folder.

---

## What an iframe is and why we use it

An **iframe** (inline frame) is an HTML element that embeds another web page inside the current page. In `app.py`:

```python
components.html(html_content, height=720, scrolling=True)
```

This reads the rendered HTML dashboard file (the 4.7 MB self-contained Plotly file) and embeds it directly in the Streamlit page. The user sees the interactive dashboard — with hover effects, tooltips, and chart interactions — without ever leaving the Streamlit app or opening a new tab.

The iframe is self-contained: because the HTML file includes the Plotly JavaScript library, it works perfectly inside an iframe with no external dependencies.

---

## What I can say in an interview about Day 4

**"How does the Streamlit app relate to the existing pipeline code?"**
The Streamlit app is a new interface layer on top of the existing pipeline. The four pipeline modules — `clarifier.py`, `spec_generator.py`, `validator.py`, `renderer.py` — were imported unchanged and called the same way. The only modification was adding `evaluate_request()` to `clarifier.py` to expose the Claude call without terminal I/O. This separation means you could add a Slack bot interface or a REST API using the same pipeline modules with no changes to the business logic.

**"How does Streamlit handle the multi-step flow?"**
Streamlit reruns the entire script on every user interaction. State is preserved in `st.session_state`, a dictionary that persists between reruns. The app uses a `screen` key in session state to track where the user is in the flow — home, evaluating, clarifying, processing, results, or error — and an `if / elif` block to render the appropriate screen. Each screen sets the next screen value and calls `st.rerun()` to transition.

**"How is the dashboard displayed in the app?"**
The rendered HTML dashboard file is read and embedded using `st.components.v1.html()`, which creates an iframe inside the Streamlit page. The HTML file is self-contained — it includes the Plotly charting library — so it works correctly inside an iframe with no external dependencies. The user gets a fully interactive Plotly chart without leaving the page.

**"What happens when validation fails?"**
The `validator.py` raises a `ValueError` with a technical error message. The Streamlit app catches this in a `try/except` block, stores the message in session state, and transitions to the error screen. The error screen inspects the message text and displays a plain-English explanation with actionable suggestions — not the raw Python error. The user sees something like "I could not build this dashboard because the data reference in your request is not in the data dictionary" with examples of valid terms to use instead.

---

## Day 4 summary (5 lines)

1. Built a Streamlit web app (`app.py`) that wraps the full Day 1–3 pipeline behind a clean browser interface — no terminal required for the business user.
2. Added `evaluate_request()` to `clarifier.py` to separate the Claude API call from terminal I/O, allowing the Streamlit app to display clarifying questions as an on-screen form instead of terminal prompts.
3. Implemented a six-screen flow (home → evaluating → clarifying → processing → results → error) using `st.session_state` to track position and `st.rerun()` to transition between screens.
4. Embedded the rendered HTML dashboard as an iframe directly in the Streamlit page using `st.components.v1.html()`, keeping the user on one page throughout.
5. Confirmed all 4 test scenarios: vague request shows clarification form, sidebar examples auto-fill the text box, a clear request produces an embedded dashboard with a "What did the agent do?" panel, and a fake column request shows a friendly error screen.

---

# Day 5 Notes — Stress Testing and Hardening

---

## What each new or changed file does

| File | What changed | Why |
|------|-------------|-----|
| `test_runner.py` | New file | Automated stress test — runs all 15 requests non-interactively without a browser or human, logs every result to `logs/test_results.txt`. Lets you catch bugs in minutes instead of hours of manual testing. |
| `renderer.py` | Fixed `month_product` grouping for all 5 metrics | The `month_product` grouping creates a two-column result (month + product). The renderer only handled this for `count_claims`. All other metrics tried `df.groupby('month_product')` — but that column doesn't exist in any DataFrame — causing a `KeyError` crash. |
| `renderer.py` | Fixed bar charts with `month_product` grouping | Bar charts with `month_product` now use `x='month'`, `color='product'`, `barmode='group'` — a grouped bar chart that correctly shows both dimensions. |
| `validator.py` | Added `_check_unavailable_data()` as Check 0 | New check that runs before the column-name check. Scans the original request for words like "salary", "headcount", "payroll" that are clearly outside the insurance dataset. Raises a friendly error instead of letting Claude silently remap the request to a proxy metric. |
| `app.py` | Added Recent Requests sidebar section | Loads `data/request_history.json` on every render. Shows the last 5 successful requests as clickable buttons at the top of the sidebar, exactly like the example buttons. Saves to history on every successful pipeline run. |
| `app.py` | Added confidence indicator on results screen | Computes a 1/2/3 score based on keyword overlap between the original request and the spec's metrics and groupings. Displays as ●●○ or ●●● with green/yellow/red color and a plain-English note. |
| `data/request_history.json` | New file | Persistent store for recent requests. Simple JSON array, max 5 entries, deduplicated. Lives in `data/` alongside the CSV files. |

---

## What stress testing means in AI agent development

**Stress testing** means running many different inputs through your system in a systematic way — not just the happy path you designed for.

For an AI agent, stress testing matters more than for deterministic software because:
- The same code behaves differently with different inputs
- The LLM may make reasonable assumptions for some inputs and wild ones for others
- Some combinations of words trigger unexpected code paths in the renderer

The 15-request test suite in `test_runner.py` was designed to cover three categories:
- **CLEAR** — requests that should work without clarification (test the happy path)
- **VAGUE** — requests that should trigger clarifying questions (test the HITL step)
- **EDGE** — inputs the system should handle gracefully: all caps, punctuation, unavailable data, overwhelming complexity, empty string

---

## What the test results taught us

**Before fixes:** 9/15 passed. All 5 failures shared the same root cause — `KeyError: 'month_product'`.

**After fixes:** 13/15 passed. The 2 remaining non-passes are intentional:
- Test 13 (agent salaries): **FAIL with a friendly governance message** — this is the correct behavior. The validator now catches it before Claude even generates a spec.
- Test 15 (empty string): **BLOCKED** — caught before any API call. Also correct.

**The pattern:** All 5 original failures traced to one bug in one function. This is common in software — a single assumption ("`month_product` grouping only matters for `count_claims`") propagates into multiple failures. Once you identify the root cause, the fix is clean and fixes all failures at once.

---

## What "graceful failure" means

A **graceful failure** is when a system encounters a problem and responds with a useful, readable message instead of crashing with a raw error.

In this project:
- **Crash (before):** `KeyError: 'month_product'` — Python traceback printed, pipeline stops, user sees nothing useful
- **Graceful failure (after):** "I cannot build this dashboard because the data needed ('salaries') is not available in our system. I can help you with dashboards about quotes, policies, and claims."

The difference matters in a business context. A data or insurance professional using this tool does not know what a `KeyError` means. A friendly message tells them what to do next.

**Design principle:** The user-facing error message should answer two questions: (1) What went wrong? (2) What can I do instead?

---

## What the confidence indicator measures

The confidence indicator (●●● High, ●●○ Medium, ●○○ Low) is a self-evaluation — the agent rating how well its own output matches the original request.

**How it works:** The function `compute_confidence()` maps known request keywords (like "claims", "state", "monthly") to expected spec values (like `count_claims`, `state` grouping, `month_product` grouping). It counts how many mapped keywords appear in both the request and the spec. If 75%+ match: High. If 40–74% match: Medium. Below 40%: Low.

**Why it matters:** AI agents sometimes produce technically valid output that does not match what the user actually wanted. The confidence indicator makes this mismatch visible — a Medium or Low score tells the user to look carefully before trusting the dashboard.

**Limitation:** The indicator is keyword-based and imperfect. A request like "How are we doing in California?" has no mapped keywords, so it defaults to Medium even if Claude produced a perfectly relevant dashboard. Self-evaluation in AI agents is hard and this is a good-enough approximation.

---

## What I can say in an interview about Day 5

**"How do you test an AI agent?"**
You cannot use unit tests the same way you test deterministic code, because the LLM's output varies. Instead, you build a non-interactive test runner that sends diverse inputs through the full pipeline and checks whether the end-to-end result (dashboard produced: yes/no) is correct. You categorize inputs by type — clear, vague, and edge cases — and you look for patterns in the failures. In our testing, all 5 original failures shared one root cause: a missing `month_product` branch in the renderer. One fix resolved all five.

**"How do you handle requests for data the system doesn't have?"**
We added a "Check 0" to the validator that runs before spec generation. It scans the request for terms that are clearly outside the available dataset — words like "salary", "headcount", "payroll". If found, it raises a `ValueError` with a specific plain-English message: "I cannot build this dashboard because the data needed is not available in our system." This stops the pipeline before spending API credits on a spec that cannot be rendered correctly.

**"What is a confidence indicator in an AI agent context?"**
It is a self-evaluation score that rates how well the agent's output matches the user's original intent. It compares keywords from the request to the metric and grouping values in the generated spec. A High score means strong alignment; a Low score means the agent made significant assumptions and the user should review the output carefully. It is transparency, not accuracy — the agent is honest about its own uncertainty.

---

## Three resume bullets for Day 5

1. **Built a 15-request automated stress test suite** that catches rendering bugs, governance gaps, and edge-case failures without any manual testing — reduced the time to find a root-cause bug from hours to minutes.
2. **Hardened the governance layer** by adding an "unavailable data" check that intercepts requests for data outside the system (salaries, headcount) before any API call is made, returning a plain-English refusal instead of a misleading proxy dashboard.
3. **Added a confidence indicator and recent request history** to the Streamlit UI, giving business users transparency into how well the agent understood their request and one-click access to their most recent dashboards.

---

## Day 5 summary (5 lines)

1. Built `test_runner.py` to stress test all 15 requests non-interactively; initial run showed 9/15 passing, with all 5 failures caused by a single `KeyError: 'month_product'` bug in `renderer.py`.
2. Fixed `renderer.py` by adding `month_product` branch handling to all five metric types (`count_quotes`, `conversion_rate`, `sum_premium`, `sum_claim_amount`, `avg_claim_amount`) and to bar chart rendering.
3. Added a "Check 0" to `validator.py` that catches requests for unavailable data (salaries, headcount, payroll) before spec generation, returning a specific governance message.
4. Added a Recent Requests sidebar section to `app.py` backed by `data/request_history.json`, and a keyword-based confidence indicator (High/Medium/Low) on the results screen.
5. Confirmed 13/15 pass after fixes (5/5 CLEAR, 5/5 VAGUE, 3/5 EDGE); the 2 non-passes are intentional: test 13 fails with a friendly governance message, test 15 is blocked before any API call.

---

# Day 6 Notes — Packaging for GitHub

---

## The complete project story in 10 bullet points

1. **Day 1:** Created three synthetic insurance CSV datasets (1,000 policies, 2,703 quotes, 566 claims), wrote a data dictionary defining every table and column, designed a JSON spec format as the contract between AI and renderer, and built the deterministic HTML renderer that turns any valid spec into an interactive Plotly dashboard.

2. **Day 2:** Wired in the Anthropic Claude API using RAG — the data dictionary is read and injected into every prompt so Claude can only reference columns that actually exist. Built the spec generator with automatic retry logic: if the first response is invalid, a correction prompt is sent once before raising an error.

3. **Day 3:** Added the Human-in-the-Loop clarifier that evaluates whether a request is specific enough before spending API budget. Added the validator with three checks (column names, spec structure, spec vocabulary) and an append-only audit log. Ran 5 manual tests to confirm the pipeline.

4. **Day 4:** Built the Streamlit web UI with six screens (home, evaluating, clarifying, processing, results, error). Separated `evaluate_request()` from `clarify()` in clarifier.py so the same AI call works in both a browser form and a terminal prompt. Fixed the working directory issue using `os.chdir()` so file paths resolve correctly regardless of launch location.

5. **Day 5:** Built an automated stress test runner for 15 diverse requests. Initial results: 9/15 pass. Root cause: `month_product` grouping was only handled for one metric — fixed by adding the same branch to all five metrics and to bar chart rendering. Added "Check 0" to the validator to catch requests for unavailable data (salaries, headcount). Final results: 13/15 pass; the 2 non-passes are correct governance behavior.

6. **Day 5 (continued):** Added the Recent Requests sidebar (last 5 successful requests stored in JSON, shown as one-click buttons) and a confidence indicator (keyword-overlap score of High/Medium/Low) to the Streamlit UI.

7. **Day 6:** Cleaned the project folder (deleted 40 generated test specs and 33 generated HTML files). Added plain-English comments to all 7 Python files explaining each section's purpose for a non-technical reader.

8. **Day 6 (continued):** Wrote `README.md` — the GitHub landing page — with a full concept table, pipeline overview, tech stack, project structure, setup instructions, and a personal reflection. Wrote `RESUME_BULLETS.md` with a project summary, three detail bullets, and a categorized skills list.

9. **Day 6 (continued):** Wrote `DEMO_SCRIPT.md` — a 2-minute word-for-word recording script showing the clarification flow, the dashboard render, the confidence indicator, and the governance explanation. Created `screenshots/` folder with instructions for adding the demo screenshot.

10. **Day 6 (continued):** Updated `.gitignore` to exclude generated specs, HTML output files, log files, and runtime state. Updated `requirements.txt` with comments explaining each dependency. The project is ready to push to GitHub.

---

## Every AI concept learned — in my own words

**RAG (Retrieval-Augmented Generation)**
Before the AI answers, you give it the information it needs to answer well. In this project, that means reading the data dictionary and injecting it into the prompt. The AI cannot make up column names because it already knows what the real ones are. RAG is the difference between an AI that guesses and an AI that looks things up.

**Prompt Engineering**
Writing instructions to an AI is a skill. You have to be specific about the format you want, give examples, define what valid looks like, and anticipate what the AI might get wrong. In this project, every prompt lives in a separate `.txt` file so the instructions can be improved without touching the Python code.

**Agentic Workflow**
An agent doesn't answer in one step — it works through a sequence of steps. In this project: evaluate the request → clarify if needed → generate a plan → validate the plan → render the result. Each step has one job. This makes the system predictable, testable, and easy to improve one piece at a time.

**Human in the Loop (HITL)**
An intentional pause in an automated system where a human can review, answer a question, or redirect before the system continues. The clarifier creates a HITL moment: if the request is too vague, the agent stops and asks instead of guessing. The human's answer shapes what gets built.

**Structured Output**
Instead of asking the AI for a free-form answer, you ask it to return a specific data structure — in this case, a JSON object with defined fields. Structured output is what makes the AI's response machine-readable, testable, and directly usable by another piece of code.

**Self-Evaluation**
An AI system rating its own output. The confidence indicator in this project compares keywords from the user's request to the metric and grouping values the AI chose. It's not a perfect measure — it's an approximation — but it gives the user a signal about how literally their request was interpreted.

**Deterministic vs. Non-deterministic Design**
Deterministic means the same input always produces the same output. Non-deterministic means the output can vary. In this project, the AI step is non-deterministic (slightly different wording may produce a different spec). The renderer is deterministic (the same spec always produces the same dashboard). Keeping these two kinds of logic separate makes the system easier to reason about and test.

**Governance Guardrail**
A layer of checks that runs before a system produces output — not to slow things down, but to prevent the system from producing something wrong or misleading. The validator in this project is a governance guardrail: it checks four things and stops the pipeline if any of them fail. It also logs every result for later review.

---

## Three things I would say if a hiring manager asked "tell me about a project you're proud of"

**1. "The spec was the anchor."**
Before I wrote a single line of AI code, I designed the JSON spec format — the contract between the AI and the renderer. Every field was deliberate. Once the format existed, I could write the prompt to generate it, the validator to check it, and the renderer to execute it. The spec gave me something concrete to build toward instead of chasing an open-ended AI output. That discipline — defining the interface before writing the implementation — is something I carried over from years of data work, where you always define the schema before loading the data.

**2. "The validator is the most important file in the project."**
It's not the biggest or the most technically impressive file, but it's the one that makes the system trustworthy. Without it, a user could ask for something that doesn't exist in the data, Claude would silently remap it to the nearest proxy metric, and they'd get a dashboard that looks correct but answers a different question. The validator makes that impossible. It was the first thing I thought about because it's the first thing I ask about any data system: what's stopping bad data from becoming a bad decision?

**3. "Two test results were supposed to fail — and that was the point."**
When I ran the 15-request stress test, 13/15 produced working dashboards. The 2 that didn't — the empty string and the salary request — failed exactly the way I designed them to fail: with a specific, plain-English message and no wasted API call. A system that fails gracefully and informatively is more useful than one that works 100% of the time in ideal conditions. Building to handle the edge cases is what separates a demo from something you could actually deploy.

---

## What I want to build next

**Live metadata catalog via MCP.** The data dictionary in this project is a static markdown file. In a real enterprise, the schema changes constantly — tables are added, columns are renamed, definitions are updated. The next version of this agent would connect to a live metadata catalog (like Alation, Atlan, or Collibra) via MCP (Model Context Protocol) and query it at runtime. Instead of a frozen snapshot of what the data looks like, the agent would always know exactly what's available right now — making it deployable across any dataset, not just the insurance data it was built with.

---

## What this week taught me about AI agent design

Building an AI agent from scratch in six days taught me something I didn't expect: the interesting problems are almost never the AI calls themselves. The Claude API calls are maybe 15 lines of code. The interesting work is everything around them — what you inject into the prompt before you call, how you validate what comes back, how you handle the failure cases, how you present the result to a user who doesn't know what a JSON spec is. The AI is the brain, but the system is the thing that makes the brain useful. A week ago I thought "building an AI agent" meant figuring out how to call an LLM. Now I think it means figuring out everything else.

---

## Day 6 summary (5 lines)

1. Cleaned the project folder: deleted all generated specs and HTML output files, leaving a professional structure ready for GitHub.
2. Added plain-English comments to all 7 Python files explaining each section's purpose in terms a non-technical reader can follow.
3. Wrote `README.md` with the full project overview, AI concept table, pipeline description, tech stack, project structure, and setup instructions.
4. Created `RESUME_BULLETS.md` with three formats of resume-ready content and `DEMO_SCRIPT.md` with a word-for-word 2-minute recording script.
5. Updated `.gitignore` and `requirements.txt`; created `screenshots/` folder with instructions — project is packaged and ready to push to GitHub.
