"""
pipeline.py
End-to-end dashboard agent pipeline — terminal entry point.

This file is the orchestrator. It wires together four independent
modules in sequence, passing the output of each step as input to the next.
The modules themselves don't know about each other — only pipeline.py does.
This design means any module can be improved or swapped out without touching the others.

Flow:
  1. clarifier.py   — Is the request specific enough? If not, ask questions (Human in the Loop).
  2. spec_generator — Read the data dictionary, call Claude API, return a JSON spec (RAG).
  3. validator.py   — Governance check: verify column names and spec structure before rendering.
  4. renderer.py    — Build a standalone HTML dashboard from the validated spec.
  5. Open in browser automatically.

Usage:
    python pipeline.py "Show me quote volume by state for the last 6 months"
    python pipeline.py   ← interactive prompt if no argument given
"""

import sys
import os
from clarifier import clarify
from spec_generator import generate_spec
from validator import validate
from renderer import render


def run_pipeline(user_request: str) -> str:
    """
    Run the full pipeline. Returns the output HTML path, or empty string on failure.
    """
    sep = "=" * 60

    print(f"\n{sep}")
    print(f"  Dashboard Agent")
    print(f"  Request: {user_request}")
    print(f"{sep}\n")

    # ── Step 1: Clarifier ─────────────────────────────────────────────────────
    # Human in the Loop: if the request is too vague (missing a metric, grouping,
    # or time range), the agent pauses and asks clarifying questions before proceeding.
    # This avoids spending API budget on a spec that won't answer the real question.
    print("Checking if your request is clear enough...")
    enriched_request = clarify(user_request)

    # ── Step 2: Spec Generator ────────────────────────────────────────────────
    # RAG step: reads the data dictionary so Claude knows what columns exist,
    # then calls the Claude API to produce a structured JSON "spec" (the plan
    # for what charts to build). This is the non-deterministic AI step.
    print("Generating dashboard spec...")
    spec_path = generate_spec(enriched_request)

    # ── Step 3: Validator ─────────────────────────────────────────────────────
    # Governance guardrail: checks that the AI's plan only references data that
    # actually exists. If this check fails, we stop here — no misleading dashboard
    # is ever rendered. Every result (pass or fail) is logged to logs/.
    print("Validating spec against data dictionary...")
    try:
        validate(spec_path, original_request=user_request)
        print("  Validation passed.")
    except ValueError as e:
        print(e)
        print("  Pipeline stopped. No dashboard was rendered.")
        return ""

    # ── Step 4: Renderer ──────────────────────────────────────────────────────
    # Deterministic step: the same spec always produces the same dashboard.
    # No AI involved here — just pandas for data aggregation and Plotly for charts.
    print("Rendering your dashboard...")
    output_path = render(spec_path)

    abs_path = os.path.abspath(output_path)
    print(f"\n{sep}")
    print(f"  Done!")
    print(f"  Dashboard: {abs_path}")
    print(f"  Opening in browser...")
    print(f"{sep}\n")

    os.startfile(abs_path)
    return output_path


if __name__ == "__main__":
    if len(sys.argv) > 1:
        request = " ".join(sys.argv[1:])
    else:
        print("\nDashboard Agent — describe what you want to see.")
        print("Examples:")
        print('  "Show me quote volume by state for the last 6 months"')
        print('  "What is the bind rate by channel this year?"\n')
        request = input("Your request: ").strip()
        if not request:
            print("No request entered. Exiting.")
            sys.exit(1)

    run_pipeline(request)
