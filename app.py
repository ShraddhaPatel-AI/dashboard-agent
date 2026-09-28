"""
app.py
Streamlit web interface for the Dashboard Creation Agent.

This file is the user-facing layer. It wraps the same four pipeline modules
(clarifier, spec_generator, validator, renderer) behind a clean browser UI.
The pipeline modules are imported unchanged — this file only handles what the
user sees and how they interact with the agent.

Key Streamlit concept: every time the user clicks something, Streamlit reruns
this entire script from top to bottom. The "screen" variable in st.session_state
remembers where the user is in the flow, so the right screen is rendered each time.

Six screens, in order:
    home        → user types request and clicks Build
    evaluating  → brief spinner while clarifier calls Claude to check the request
    clarifying  → if vague, show questions as a form for the user to answer
    processing  → run the full pipeline with live step-by-step status messages
    results     → embed the rendered dashboard + confidence indicator + agent details
    error       → friendly plain-English error message (never a raw Python traceback)

Design note — working directory:
    os.chdir() at the top ensures all relative file paths (prompts/, data/, specs/)
    resolve correctly regardless of where Streamlit was launched from. This must
    happen before any other import that might read a file.

Run with:
    python -m streamlit run app.py
"""

import json
import os
from pathlib import Path

# Ensure all relative paths resolve to the project folder,
# regardless of where `streamlit run` was launched from.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import streamlit as st
import streamlit.components.v1 as components
from dotenv import load_dotenv

from clarifier import evaluate_request
from spec_generator import generate_spec
from validator import validate
from renderer import render

load_dotenv()

# ── PAGE CONFIG ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Dashboard Creation Agent",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── SESSION STATE DEFAULTS ────────────────────────────────────────────────────
# st.session_state is Streamlit's cross-rerun memory. Without it, every click
# would start fresh with no memory of what the user has done so far.
# _DEFAULTS defines the starting value for every key used across all screens.

_DEFAULTS = {
    "screen":                   "home",
    "original_request":         "",
    "enriched_request":         "",
    "clarification_questions":  [],
    "spec_path":                "",
    "output_path":              "",
    "spec_data":                None,
    "validation_passed":        False,
    "error_message":            "",
}

for _k, _v in _DEFAULTS.items():
    if _k not in st.session_state:
        st.session_state[_k] = _v

# ── HELPER ────────────────────────────────────────────────────────────────────

# ── RECENT REQUESTS HISTORY ───────────────────────────────────────────────────
# Stores the last 5 successful requests in a JSON file so they appear as
# sidebar buttons even after the app restarts. The file is gitignored because
# it is runtime state, not source code.

HISTORY_FILE = Path("data/request_history.json")
HISTORY_MAX  = 5


def load_history() -> list:
    try:
        if HISTORY_FILE.exists():
            return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def save_to_history(request: str):
    history = load_history()
    history = [r for r in history if r != request]  # deduplicate
    history.insert(0, request)
    history = history[:HISTORY_MAX]
    HISTORY_FILE.write_text(json.dumps(history, indent=2), encoding="utf-8")


# ── CONFIDENCE SCORING ────────────────────────────────────────────────────────
# Maps plain-English words from the user's request to the spec values Claude
# should have chosen. A High score means strong alignment between what was asked
# and what was built; a Low score means the agent made significant assumptions.
# This gives the user transparency into how literally their request was interpreted.

_KEYWORD_MAP = {
    "state": {"state"},
    "channel": {"channel"},
    "product": {"product"},
    "claim": {"count_claims", "sum_claim_amount", "avg_claim_amount"},
    "claims": {"count_claims", "sum_claim_amount", "avg_claim_amount"},
    "quote": {"count_quotes", "conversion_rate"},
    "quotes": {"count_quotes", "conversion_rate"},
    "premium": {"sum_premium"},
    "bind": {"conversion_rate"},
    "conversion": {"conversion_rate"},
    "monthly": {"month_product"},
    "month": {"month_product"},
    "trend": {"month_product"},
}


def compute_confidence(original_request: str, spec: dict) -> int:
    """
    Return 1 (low), 2 (medium), or 3 (high) based on how well the spec
    matches the keywords in the original request.
    """
    if not spec:
        return 1

    words = set(original_request.lower().split())
    spec_terms = set()
    for chart in spec.get("charts", []):
        spec_terms.add(chart.get("metric", ""))
        spec_terms.add(chart.get("grouping", ""))

    matched = 0
    total   = 0
    for word in words:
        if word in _KEYWORD_MAP:
            total += 1
            if spec_terms & _KEYWORD_MAP[word]:
                matched += 1

    if total == 0:
        return 2  # no mappable keywords — medium confidence
    ratio = matched / total
    if ratio >= 0.75:
        return 3
    if ratio >= 0.4:
        return 2
    return 1


def reset_to_home():
    """Clear all pipeline state and return to the home screen."""
    for k in _DEFAULTS:
        st.session_state[k] = _DEFAULTS[k]
    # Also clear the text area widget so it shows empty
    if "request_input" in st.session_state:
        del st.session_state["request_input"]


# ── SIDEBAR ───────────────────────────────────────────────────────────────────

with st.sidebar:
    # ── Recent Requests ───────────────────────────────────────────────────────
    history = load_history()
    if history:
        st.markdown("## Recent Requests")
        for req in history:
            label = (req[:50] + "…") if len(req) > 50 else req
            if st.button(label, use_container_width=True, key=f"hist_{req}"):
                reset_to_home()
                st.session_state["request_input"] = req
                st.rerun()
        st.divider()

    st.markdown("## Example Requests")
    st.markdown("Click any example to fill the request box automatically.")

    EXAMPLES = [
        "Quote volume by state last 6 months",
        "Bind rate by agent channel this year",
        "Monthly claims trend by product",
        "Top states by premium written",
        "Quote to bind conversion this quarter",
    ]

    for example in EXAMPLES:
        if st.button(example, use_container_width=True, key=f"ex_{example}"):
            reset_to_home()
            st.session_state["request_input"] = example  # set AFTER reset clears it
            st.rerun()

    st.divider()

    st.markdown("## About This Agent")
    st.markdown(
        """
        - **Reads a data dictionary first** so it only references columns that actually exist in the data — no hallucination
        - **Asks clarifying questions** when a request is too vague, before spending API budget on generation
        - **Validates every request** against the data dictionary before rendering, so misleading dashboards are blocked
        """
    )


# ── SCREEN ROUTER ─────────────────────────────────────────────────────────────

screen = st.session_state["screen"]


# ══════════════════════════════════════════════════════════════════════════════
# HOME
# ══════════════════════════════════════════════════════════════════════════════

if screen == "home":
    st.title("📊 Dashboard Creation Agent")
    st.markdown(
        "Describe the dashboard you need in plain English and I will build it for you."
    )
    st.divider()

    user_request = st.text_area(
        "What dashboard do you need?",
        height=100,
        placeholder='e.g. "Show me quote volume by state for the last 6 months"',
        key="request_input",
    )

    if st.button("🔨  Build My Dashboard", type="primary", use_container_width=True):
        if not user_request.strip():
            st.warning("Please describe the dashboard you want.")
        else:
            st.session_state["original_request"] = user_request.strip()
            st.session_state["screen"] = "evaluating"
            st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# EVALUATING  (brief: calls Claude to check clarity, then branches)
# ══════════════════════════════════════════════════════════════════════════════

elif screen == "evaluating":
    st.title("📊 Dashboard Creation Agent")
    st.markdown(f"**Your request:** {st.session_state['original_request']}")

    with st.spinner("Checking your request..."):
        result = evaluate_request(st.session_state["original_request"])

    if result.get("status") == "needs_clarification":
        st.session_state["clarification_questions"] = result.get("questions", [])
        st.session_state["screen"] = "clarifying"
    else:
        st.session_state["enriched_request"] = result.get(
            "enriched_request", st.session_state["original_request"]
        )
        st.session_state["screen"] = "processing"

    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# CLARIFYING  (show questions as a form; user types answers and submits)
# ══════════════════════════════════════════════════════════════════════════════

elif screen == "clarifying":
    st.title("📊 Dashboard Creation Agent")
    st.info("Let me ask you a couple of questions first so I can build exactly what you need.")
    st.markdown(f"**Your request:** *{st.session_state['original_request']}*")
    st.divider()

    questions = st.session_state["clarification_questions"]

    with st.form("clarification_form"):
        answers = []
        for i, question in enumerate(questions):
            answer = st.text_input(f"{i + 1}. {question}", key=f"q_{i}")
            answers.append((question, answer))

        submitted = st.form_submit_button("Submit Answers →", type="primary", use_container_width=True)

    if submitted:
        filled = [(q, a) for q, a in answers if a.strip()]
        if filled:
            context = "; ".join(f"{q} → {a}" for q, a in filled)
            enriched = f"{st.session_state['original_request']}. Additional context: {context}"
        else:
            enriched = st.session_state["original_request"]

        st.session_state["enriched_request"] = enriched
        st.session_state["screen"] = "processing"
        st.rerun()

    if st.button("← Start over"):
        reset_to_home()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PROCESSING  (runs the full pipeline with live status updates)
# ══════════════════════════════════════════════════════════════════════════════

elif screen == "processing":
    st.title("📊 Dashboard Creation Agent")
    request = st.session_state["enriched_request"] or st.session_state["original_request"]
    st.markdown(f"**Building:** *{st.session_state['original_request']}*")

    with st.status("Building your dashboard...", expanded=True) as status:
        try:
            st.write("⚙️  Generating dashboard spec...")
            spec_path = generate_spec(request)
            st.session_state["spec_path"] = spec_path

            st.write("🔍  Validating against data dictionary...")
            validate(spec_path, original_request=st.session_state["original_request"])
            st.session_state["validation_passed"] = True

            st.write("🎨  Rendering your dashboard...")
            output_path = render(spec_path)
            st.session_state["output_path"] = output_path

            with open(spec_path, encoding="utf-8") as f:
                st.session_state["spec_data"] = json.load(f)

            status.update(label="Dashboard ready!", state="complete")
            save_to_history(st.session_state["original_request"])
            st.session_state["screen"] = "results"

        except ValueError as e:
            st.session_state["error_message"] = str(e)
            status.update(label="Could not build dashboard", state="error")
            st.session_state["screen"] = "error"

        except Exception as e:
            st.session_state["error_message"] = str(e)
            status.update(label="Something went wrong", state="error")
            st.session_state["screen"] = "error"

    # Rerun AFTER the status block exits — transitions to results or error
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# RESULTS  (embedded dashboard + agent details expander)
# ══════════════════════════════════════════════════════════════════════════════

elif screen == "results":
    st.title("📊 Dashboard Creation Agent")
    st.success("Your dashboard is ready!")

    # ── Confidence indicator ───────────────────────────────────────────────────
    conf = compute_confidence(
        st.session_state["original_request"],
        st.session_state.get("spec_data") or {},
    )
    conf_labels = {3: "High", 2: "Medium", 1: "Low"}
    conf_colors = {3: "green", 2: "orange", 1: "red"}
    conf_notes  = {
        3: "The dashboard closely matches your request.",
        2: "The dashboard is a reasonable interpretation of your request.",
        1: "The agent made significant assumptions — review the charts carefully.",
    }
    st.markdown(
        f"**Confidence:** "
        f"<span style='color:{conf_colors[conf]};font-weight:700'>"
        f"{'●' * conf}{'○' * (3 - conf)}  {conf_labels[conf]}</span>"
        f"&nbsp; — {conf_notes[conf]}",
        unsafe_allow_html=True,
    )

    # ── Embed the HTML dashboard as an iframe ─────────────────────────────────
    output_path = st.session_state["output_path"]
    with open(output_path, encoding="utf-8") as f:
        html_content = f.read()

    components.html(html_content, height=720, scrolling=True)

    # ── "What did the agent do?" expander ─────────────────────────────────────
    with st.expander("🔍  What did the agent do?"):
        col_left, col_right = st.columns(2)

        with col_left:
            st.markdown("**Request received:**")
            st.markdown(f"> {st.session_state['original_request']}")

            enriched = st.session_state.get("enriched_request", "")
            if enriched and enriched != st.session_state["original_request"]:
                st.markdown("**Request used (after clarification):**")
                st.markdown(f"> {enriched}")

            st.markdown("**Validation:**")
            if st.session_state["validation_passed"]:
                st.success("All three checks passed: column names, spec structure, spec vocabulary.")

        with col_right:
            spec = st.session_state["spec_data"]
            if spec:
                st.markdown("**Charts generated:**")
                for chart in spec.get("charts", []):
                    st.markdown(
                        f"- **{chart['title']}** — "
                        f"{chart['chart_type']} chart, "
                        f"metric: `{chart['metric']}`, "
                        f"grouped by: `{chart['grouping']}`, "
                        f"period: `{chart['time_range']}`"
                    )

                st.markdown("**Full JSON spec:**")
                st.json(spec)

    st.divider()
    if st.button("🔄  Build Another Dashboard", type="primary", use_container_width=True):
        reset_to_home()
        st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# ERROR  (friendly message, not raw Python traceback)
# ══════════════════════════════════════════════════════════════════════════════

elif screen == "error":
    st.title("📊 Dashboard Creation Agent")

    error = st.session_state.get("error_message", "")

    # Map technical errors to friendly plain-English explanations
    if "not available in our system" in error:
        st.error(error.strip())
        st.markdown(
            "**What I can help with:**\n"
            "- Quote volume, bind rate, conversion rate by state / channel / product\n"
            "- Policy count and premium written\n"
            "- Claim counts and amounts by type, state, or product\n"
            "\nExample: *'Show me quote volume by state for the last 6 months'*"
        )
    elif "not a recognized column name" in error or "column_check" in error or "unrecognized data reference" in error:
        st.error(
            "I could not build this dashboard because the data reference in your request "
            "is not in the data dictionary."
        )
        st.markdown("**What to try:**")
        st.markdown(
            "- Use column names from the data dictionary: `state`, `product`, `channel`, "
            "`claim_type`, `annual_premium`\n"
            "- Valid metrics include: count_quotes, conversion_rate, sum_premium, "
            "count_claims, sum_claim_amount, avg_claim_amount\n"
            "- Example: *'Show me quote volume by state for the last 6 months'*"
        )
    elif "structure" in error or "vocabulary" in error or "Missing required" in error:
        st.error(
            "I could not build this dashboard because the generated plan was not valid. "
            "Try rephrasing your request more specifically."
        )
    else:
        st.error(
            "I could not build this dashboard. "
            "Try asking about quotes, policies, or claims — for example: "
            "'Show me claims by state this year'."
        )

    with st.expander("Technical details"):
        st.code(error)

    col1, col2 = st.columns(2)
    with col1:
        if st.button("← Try Again", type="primary", use_container_width=True):
            st.session_state["screen"] = "home"
            st.session_state["error_message"] = ""
            st.rerun()
    with col2:
        if st.button("🏠  Start Over", use_container_width=True):
            reset_to_home()
            st.rerun()
