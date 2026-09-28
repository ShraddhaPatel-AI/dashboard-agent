"""
validator.py
Governance guardrail — runs between spec_generator.py and renderer.py.

This module answers a critical question in any AI-powered system:
"How do we prevent the AI from producing something that looks correct
but is actually wrong or misleading?"

The answer here is a layered set of checks that run before any dashboard
is ever rendered. If any check fails, the pipeline stops and the user
receives a plain-English explanation — not a Python error and not a
misleading chart.

Four checks, in order:
  Check 0 — Unavailable data: catches requests for data that simply doesn't
             exist in this system (e.g. salaries, headcount, payroll).
             Prevents Claude from silently substituting a proxy metric.
  Check 1 — Request column names: scans the original request for underscore-
             delimited terms (e.g. claim_amount_fake_column) and verifies each
             is a real column name. Without this, hallucinated names get silently
             remapped by Claude instead of surfacing as errors.
  Check 2 — Spec structure: confirms all required JSON keys are present and
             the charts array is non-empty.
  Check 3 — Spec vocabulary: confirms every metric, grouping, and chart_type
             value is from the approved list the renderer can actually execute.

Audit log: every result (pass and fail) is written to logs/validation_log.txt
with a timestamp — a permanent record that can be reviewed for governance purposes.

Usage (standalone):
    python validator.py specs/generated_xxx.json "original user request"

Usage (from pipeline.py):
    from validator import validate
    validate(spec_path, original_request="Show me quote volume by state")
    # Raises ValueError with a plain-English message on failure.
    # Returns the spec dict on success.
"""

import json
import re
import sys
from datetime import datetime
from pathlib import Path


# ── APPROVED VOCABULARY ───────────────────────────────────────────────────────
# These sets define the complete list of values the renderer can handle.
# Any value Claude returns that isn't in one of these sets is rejected here
# before it ever reaches renderer.py, which would crash on an unknown value.

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

# Every real column name from data_dictionary.md.
# Used to catch hallucinated column references in the original user request.
REAL_COLUMNS = {
    "policy_id", "customer_id", "state", "product", "channel",
    "effective_date", "expiry_date", "annual_premium",
    "quote_id", "quote_date", "quoted_premium", "status", "bind_date",
    "claim_id", "claim_date", "claim_type", "claim_amount", "claim_status",
}

# All underscore-containing terms that are legitimately valid in a request
VALID_UNDERSCORE_TERMS = (
    REAL_COLUMNS
    | VALID_METRICS
    | VALID_GROUPINGS
    | {
        "last_6_months", "this_year", "last_year", "last_2_years",
        "bind_rate", "quote_count", "claim_count",
    }
)

# Words that clearly signal data not present in quotes/policies/claims
UNAVAILABLE_DATA_TERMS = {
    "salary", "salaries", "wage", "wages", "payroll",
    "headcount", "employee", "employees", "staff",
    "commission", "commissions", "bonus", "bonuses",
    "expense", "expenses", "budget", "budgets",
    "revenue", "profit", "loss", "losses",
    "inventory", "asset", "assets", "liability", "liabilities",
}

LOG_DIR  = Path("logs")
LOG_FILE = LOG_DIR / "validation_log.txt"


# ── LOGGING ───────────────────────────────────────────────────────────────────

def _log(message: str):
    LOG_DIR.mkdir(exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")


# ── CHECK 0: UNAVAILABLE DATA ─────────────────────────────────────────────────

def _check_unavailable_data(original_request: str) -> tuple:
    """
    Catch requests for data that clearly isn't in the insurance dataset
    (e.g. salaries, headcount, payroll) before calling Claude.
    """
    words = set(re.findall(r'\b[a-z]+\b', original_request.lower()))
    found = words & UNAVAILABLE_DATA_TERMS
    if found:
        term = sorted(found)[0]
        return False, (
            f"I cannot build this dashboard because the data needed "
            f"('{term}') is not available in our system. "
            f"I can help you with dashboards about quotes, policies, and claims."
        )
    return True, ""


# ── CHECK 1: REQUEST COLUMN NAMES ─────────────────────────────────────────────

def _check_request_columns(original_request: str) -> tuple:
    """
    Find underscore-delimited terms in the request and verify each one is a
    real column name, a valid metric key, or a valid grouping key.

    Why this matters: the AI's prompt tells it to only use approved metric keys,
    so 'claim_amount_fake_column' would get silently remapped to 'sum_claim_amount'.
    This check makes the problem visible rather than hiding it.
    """
    terms = re.findall(r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b', original_request.lower())
    for term in terms:
        if term not in VALID_UNDERSCORE_TERMS:
            return False, (
                f"'{term}' is not a recognized column name or metric in the data dictionary.\n"
                f"  Real column names include: {', '.join(sorted(REAL_COLUMNS)[:12])}, ...\n"
                f"  Valid metric keys: {', '.join(sorted(VALID_METRICS))}\n"
                f"  Please check data_dictionary.md for the full list and correct your request."
            )
    return True, ""


# ── CHECK 2: SPEC STRUCTURE ───────────────────────────────────────────────────

def _check_structure(spec: dict) -> tuple:
    for key in ("title", "description", "filters", "charts", "layout"):
        if key not in spec:
            return False, f"Missing required key: '{key}'"

    if not spec.get("title"):
        return False, "Dashboard title is empty"

    if not isinstance(spec["charts"], list) or len(spec["charts"]) == 0:
        return False, "The spec must contain at least one chart"

    chart_ids = set()
    for i, chart in enumerate(spec["charts"]):
        for key in ("chart_id", "chart_type", "title", "metric", "grouping", "time_range", "sort_order"):
            if key not in chart:
                return False, f"Chart {i} is missing required key: '{key}'"
        chart_ids.add(chart["chart_id"])

    if not isinstance(spec.get("layout"), list) or len(spec["layout"]) == 0:
        return False, "The spec must have a layout array"

    for i, entry in enumerate(spec["layout"]):
        if entry.get("chart_id") not in chart_ids:
            return False, (
                f"Layout entry {i} references '{entry.get('chart_id')}' "
                f"which is not in the charts array"
            )

    return True, ""


# ── CHECK 3: SPEC VOCABULARY ──────────────────────────────────────────────────

def _check_vocabulary(spec: dict) -> tuple:
    for i, chart in enumerate(spec["charts"]):
        cid = chart.get("chart_id", f"chart_{i}")

        if chart["chart_type"] not in VALID_CHART_TYPES:
            return False, (
                f"Chart '{cid}' uses unknown chart_type: '{chart['chart_type']}'. "
                f"Valid options: {sorted(VALID_CHART_TYPES)}"
            )
        if chart["metric"] not in VALID_METRICS:
            return False, (
                f"Chart '{cid}' uses unknown metric: '{chart['metric']}'. "
                f"Valid options: {sorted(VALID_METRICS)}"
            )
        if chart["grouping"] not in VALID_GROUPINGS:
            return False, (
                f"Chart '{cid}' uses unknown grouping: '{chart['grouping']}'. "
                f"Valid options: {sorted(VALID_GROUPINGS)}"
            )
    return True, ""


# ── MAIN ENTRY POINT ──────────────────────────────────────────────────────────

def validate(spec_path: str, original_request: str = "") -> dict:
    """
    Run all three validation checks in order.
    Returns the spec dict on success.
    Raises ValueError with a plain-English message on any failure.
    Logs every result (pass or fail) to logs/validation_log.txt.
    """
    # Check 0: unavailable data (salaries, headcount, etc.)
    if original_request:
        ok, error = _check_unavailable_data(original_request)
        if not ok:
            msg = f"FAIL [unavailable_data] | '{original_request[:80]}' | {error}"
            _log(msg)
            raise ValueError(f"\n  {error}\n")

    # Check 1: column names in the original request
    if original_request:
        ok, error = _check_request_columns(original_request)
        if not ok:
            msg = f"FAIL [column_check] | '{original_request[:80]}' | {error.splitlines()[0]}"
            _log(msg)
            raise ValueError(
                f"\n  Validation failed — unrecognized data reference in your request:\n"
                f"  {error}\n"
            )

    # Load the spec file
    with open(spec_path, encoding="utf-8") as f:
        spec = json.load(f)

    # Check 2: structure
    ok, error = _check_structure(spec)
    if not ok:
        msg = f"FAIL [structure] | {spec_path} | {error}"
        _log(msg)
        raise ValueError(f"\n  Validation failed — spec structure problem:\n  {error}\n")

    # Check 3: vocabulary
    ok, error = _check_vocabulary(spec)
    if not ok:
        msg = f"FAIL [vocabulary] | {spec_path} | {error}"
        _log(msg)
        raise ValueError(f"\n  Validation failed — spec uses an unrecognized value:\n  {error}\n")

    # All checks passed
    n = len(spec["charts"])
    _log(f"PASS | {spec_path} | '{original_request[:80]}' | {n} chart(s)")
    return spec


# ── STANDALONE USE ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python validator.py <spec_file.json> [original_request]")
        sys.exit(1)

    spec_path = sys.argv[1]
    original  = " ".join(sys.argv[2:]) if len(sys.argv) > 2 else ""

    try:
        spec = validate(spec_path, original)
        print(f"Validation passed — {len(spec['charts'])} chart(s), title: \"{spec['title']}\"")
    except ValueError as e:
        print(e)
        sys.exit(1)
