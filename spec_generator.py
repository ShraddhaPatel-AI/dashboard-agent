"""
spec_generator.py
The AI brain of the pipeline. Converts a plain-English dashboard request into
a structured JSON "spec" — the machine-readable plan that tells the renderer
exactly what charts to build.

Key design pattern — RAG (Retrieval-Augmented Generation):
  Before calling Claude, this module reads data_dictionary.md and injects its
  full contents into the prompt. This grounds the AI in reality: Claude can only
  reference columns and tables that are documented in the dictionary. Without this
  step, the AI might hallucinate column names that don't exist in the data.

The JSON spec is the "contract" between the AI (this file) and the renderer
(renderer.py). The renderer is deterministic — the same spec always produces
the same dashboard. The spec is the handoff point where the non-deterministic
AI work ends and the deterministic rendering work begins.

Retry logic: if Claude's first response fails validation (wrong format, missing
fields, unrecognized metric names), a correction prompt is sent automatically.
This gives the model a second chance before raising an error.

Usage (standalone):
    python spec_generator.py "Show me quote volume by state for the last 6 months"

Usage (from pipeline.py):
    from spec_generator import generate_spec
    spec_path = generate_spec("Show me quote volume by state")
"""

import os
import json
import sys
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import anthropic

# Load ANTHROPIC_API_KEY from the .env file in this folder
load_dotenv()

# ── CONFIGURATION ─────────────────────────────────────────────────────────────
MODEL      = "claude-sonnet-4-6"
MAX_TOKENS = 4096

PROMPTS_DIR = Path("prompts")
SPECS_DIR   = Path("specs")

# The only valid values our renderer understands.
# If Claude invents something outside these, we reject and retry.
VALID_CHART_TYPES = {"bar", "line", "pie"}
VALID_METRICS = {
    "count_quotes",
    "conversion_rate",
    "sum_premium",
    "count_claims",
    "sum_claim_amount",
    "avg_claim_amount",
}
VALID_GROUPINGS = {"state", "product", "channel", "month_product", "claim_type"}
VALID_SORT_ORDERS = {"asc", "desc", "none"}
VALID_TIME_RANGES = {"all", "last_6_months", "this_year", "last_year", "last_2_years"}


# ── FILE HELPERS ──────────────────────────────────────────────────────────────

def read_file(path: str) -> str:
    with open(path, encoding="utf-8") as f:
        return f.read()


def build_prompt(user_request: str) -> str:
    """
    Build the full prompt by injecting three things into the template:
      1. The data dictionary — so Claude knows what columns exist (RAG step)
      2. The spec format documentation — so Claude knows the required JSON structure
      3. The user's request — the plain-English question to answer

    Uses .replace() instead of Python's .format() because the data dictionary
    contains curly braces in its JSON examples, which would confuse .format().
    """
    template    = read_file(PROMPTS_DIR / "spec_generation_prompt.txt")
    data_dict   = read_file("data_dictionary.md")
    spec_format = read_file(SPECS_DIR / "spec_format.md")

    return (
        template
        .replace("__DATA_DICTIONARY__", data_dict)
        .replace("__SPEC_FORMAT__", spec_format)
        .replace("__USER_REQUEST__", user_request)
    )


def build_correction_prompt(user_request: str, error_message: str) -> str:
    """Fill in the correction prompt template used on a retry."""
    template    = read_file(PROMPTS_DIR / "correction_prompt.txt")
    spec_format = read_file(SPECS_DIR / "spec_format.md")

    return (
        template
        .replace("__ERROR_MESSAGE__", error_message)
        .replace("__SPEC_FORMAT__", spec_format)
        .replace("__USER_REQUEST__", user_request)
    )


# ── API CALL ──────────────────────────────────────────────────────────────────

def call_claude(prompt: str) -> str:
    """Send a prompt to Claude and return the raw text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key or api_key == "paste-your-key-here":
        raise ValueError(
            "ANTHROPIC_API_KEY is not set.\n"
            "Open .env and replace 'paste-your-key-here' with your actual key."
        )

    client = anthropic.Anthropic(api_key=api_key)

    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )

    return message.content[0].text.strip()


# ── JSON EXTRACTION ───────────────────────────────────────────────────────────

def extract_json(text: str) -> str:
    """
    Strip markdown code fences if Claude wrapped the JSON despite being told not to.
    Handles ```json...``` and plain ```...```.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner_lines = lines[1:]           # drop the opening fence line
        inner = "\n".join(inner_lines)
        if inner.rstrip().endswith("```"):
            inner = inner.rstrip()[:-3]   # drop the closing fence
        return inner.strip()
    return text


# ── VALIDATION ────────────────────────────────────────────────────────────────

def validate_spec(spec: dict) -> tuple:
    """
    Check that the spec has all required keys and only uses values the renderer
    understands. Returns (True, "") if valid, or (False, error_message) if not.
    """
    # Top-level keys
    for key in ("title", "description", "filters", "charts", "layout"):
        if key not in spec:
            return False, f"Missing required top-level key: '{key}'"

    # Filters
    for key in ("date_range", "state", "product", "channel"):
        if key not in spec["filters"]:
            return False, f"Missing filter key: '{key}'"

    # Charts array
    if not isinstance(spec["charts"], list) or len(spec["charts"]) == 0:
        return False, "charts must be a non-empty list"

    chart_ids = set()
    for i, chart in enumerate(spec["charts"]):
        for key in ("chart_id", "chart_type", "title", "metric", "grouping", "time_range", "sort_order"):
            if key not in chart:
                return False, f"Chart {i} is missing required key: '{key}'"

        chart_ids.add(chart["chart_id"])

    # Layout array
    if not isinstance(spec["layout"], list) or len(spec["layout"]) == 0:
        return False, "layout must be a non-empty list"

    for i, entry in enumerate(spec["layout"]):
        for key in ("chart_id", "row", "col"):
            if key not in entry:
                return False, f"Layout entry {i} is missing key: '{key}'"
        if entry["chart_id"] not in chart_ids:
            return False, (
                f"Layout entry {i} references chart_id '{entry['chart_id']}' "
                f"which does not exist in the charts array."
            )

    return True, ""


# ── MAIN ENTRY POINT ──────────────────────────────────────────────────────────

def generate_spec(user_request: str) -> str:
    """
    Full flow: plain-English request → Claude API → validated JSON spec file.
    Returns the file path to the saved spec.

    Steps inside this function:
      1. Build the prompt (inject data dictionary + spec format)
      2. Call Claude (first attempt)
      3. Validate the JSON structure
      4. If invalid, send a correction prompt and try once more
      5. Save the valid spec to specs/generated_<timestamp>.json
    """
    # ── Step 1: Build the prompt (RAG) ────────────────────────────────────────
    # The data dictionary is read and injected here so Claude "knows" the schema.
    print(f"  Reading data dictionary and spec format (RAG step)...")
    prompt = build_prompt(user_request)

    # ── Step 2: Call Claude ───────────────────────────────────────────────────
    print(f"  Calling Claude ({MODEL})...")
    raw_response = call_claude(prompt)

    # ── Step 3: Parse and validate the first response ─────────────────────────
    # Claude is asked to return raw JSON. Strip any accidental code fences,
    # then parse and validate the structure against the spec format.
    json_text = extract_json(raw_response)
    spec = None

    try:
        spec = json.loads(json_text)
        is_valid, error = validate_spec(spec)
        if not is_valid:
            raise ValueError(error)
        print(f"  Valid spec received on first attempt.")

    except (json.JSONDecodeError, ValueError) as first_error:
        # ── Step 4: Retry with a correction prompt ────────────────────────────
        # If the first response failed, we tell Claude exactly what went wrong
        # and ask it to fix the spec. This self-correction pattern avoids
        # hard failures on minor formatting mistakes.
        error_msg = str(first_error)
        print(f"  First attempt failed: {error_msg}")
        print(f"  Retrying with correction prompt...")

        correction = build_correction_prompt(user_request, error_msg)
        raw_response = call_claude(correction)
        json_text    = extract_json(raw_response)

        try:
            spec = json.loads(json_text)
            is_valid, error = validate_spec(spec)
            if not is_valid:
                raise ValueError(error)
            print(f"  Valid spec received after correction.")
        except (json.JSONDecodeError, ValueError) as second_error:
            raise RuntimeError(
                f"Could not get a valid spec after 2 attempts.\n"
                f"Second error: {second_error}\n"
                f"Last response:\n{raw_response[:500]}"
            )

    # ── Step 5: Save the spec ─────────────────────────────────────────────────
    # Save with a timestamp so every request is traceable. The spec file is
    # the permanent record of what the AI decided to build.
    SPECS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    spec_path = SPECS_DIR / f"generated_{timestamp}.json"

    with open(spec_path, "w", encoding="utf-8") as f:
        json.dump(spec, f, indent=2)

    print(f"  Spec saved: {spec_path}")
    return str(spec_path)


# ── STANDALONE USE ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print('Usage: python spec_generator.py "Your dashboard request"')
        sys.exit(1)

    request = " ".join(sys.argv[1:])
    print(f"\nRequest: {request}")
    path = generate_spec(request)
    print(f"\nSpec saved to: {path}\n")

    # Print the spec so the user can inspect it
    with open(path) as f:
        print(json.dumps(json.load(f), indent=2))
