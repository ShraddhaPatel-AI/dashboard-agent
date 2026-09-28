"""
test_runner.py
Automated stress test for the full agent pipeline.

Why this exists: AI agents behave differently from deterministic code.
The same Python logic can produce different outputs depending on how a request
is phrased. Stress testing catches these unexpected behaviors systematically —
running 15 diverse requests through the full pipeline and checking whether
a working dashboard was produced at the end.

Test categories:
  CLEAR — requests that are specific enough to work without clarification.
           These test the happy path.
  VAGUE — requests that are intentionally incomplete (e.g. "Show me claims").
           These test whether the agent handles missing context gracefully.
  EDGE  — unusual inputs: ALL CAPS, punctuation, unavailable data, empty string,
           "show me everything". These test robustness at the boundaries.

The test runner calls evaluate_request() to check clarity, then runs the full
pipeline (generate_spec → validate → render) without any human interaction.
Vague requests proceed with the original request so the test doesn't stall
waiting for terminal input.

Results are appended to logs/test_results.txt with a timestamp so every test
run is permanently recorded. This is part of the governance story.

Usage:
    python test_runner.py
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

# Ensure relative paths resolve to the project folder
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv()

from clarifier import evaluate_request
from spec_generator import generate_spec
from validator import validate
from renderer import render

LOG_DIR  = Path("logs")
LOG_FILE = LOG_DIR / "test_results.txt"

# ── TEST REQUESTS ─────────────────────────────────────────────────────────────
# (category, request)

TEST_REQUESTS = [
    # ── CLEAR: should produce a dashboard with no clarification ───────────────
    ("CLEAR", "Show me quote volume by state for the last 6 months"),
    ("CLEAR", "What is the bind rate by agent channel this year?"),
    ("CLEAR", "Show me monthly claims trend by product this year"),
    ("CLEAR", "Top 10 states by total premium written this year"),
    ("CLEAR", "Compare bound vs lost quotes by channel last quarter"),
    # ── VAGUE: should trigger clarifying questions ─────────────────────────────
    ("VAGUE", "Show me quotes"),
    ("VAGUE", "How are we doing in California?"),
    ("VAGUE", "Claims report"),
    ("VAGUE", "Agent performance"),
    ("VAGUE", "Show me everything"),
    # ── EDGE: must not crash; graceful error or dashboard ─────────────────────
    ("EDGE",  "SHOW ME QUOTE VOLUME BY STATE"),
    ("EDGE",  "show me quote volume by state!!!"),
    ("EDGE",  "Show me agent salaries by state"),
    ("EDGE",  "Show me quotes and claims and policies all together by state by channel "
              "by product for every month this year and last year"),
    ("EDGE",  ""),
]


# ── RESULT DATACLASS ──────────────────────────────────────────────────────────

class TestResult:
    def __init__(self, idx: int, category: str, request: str):
        self.idx                   = idx
        self.category              = category
        self.request               = request
        self.clarification_needed  = None   # True / False / None (not checked)
        self.spec_generated        = False
        self.validation_passed     = False
        self.dashboard_produced    = False
        self.error_message         = ""
        self.elapsed               = 0.0

    def label(self) -> str:
        if not self.request.strip():
            return "BLOCKED"
        if self.dashboard_produced:
            return "PASS"
        return "FAIL"

    def _req_display(self) -> str:
        r = self.request or "(empty)"
        return (r[:65] + "…") if len(r) > 65 else r

    def log_block(self) -> str:
        clar = ("YES" if self.clarification_needed
                else ("NO"  if self.clarification_needed is False
                else  "-"))
        err  = (self.error_message[:120].replace("\n", " ").strip()
                if self.error_message else "—")
        return (
            f"  Test {self.idx:>2} [{self.label():<7}] [{self.category}] "
            f"{self._req_display()}\n"
            f"           Clarify: {clar:<4}  Spec: {'YES' if self.spec_generated else 'NO':<4}  "
            f"Valid: {'YES' if self.validation_passed else 'NO':<4}  "
            f"Dashboard: {'YES' if self.dashboard_produced else 'NO':<4}  "
            f"Time: {self.elapsed:.1f}s\n"
            f"           Error: {err}"
        )


# ── SINGLE-REQUEST RUNNER ─────────────────────────────────────────────────────

def run_one(idx: int, category: str, request: str) -> TestResult:
    r = TestResult(idx, category, request)
    t0 = time.time()

    if not request.strip():
        r.error_message = "Empty input — blocked before any API call"
        r.elapsed = 0.0
        return r

    try:
        # --- Step 1: check whether clarification would be triggered -----------
        print("    checking clarity...", end=" ", flush=True)
        eval_result = evaluate_request(request)
        r.clarification_needed = (eval_result.get("status") == "needs_clarification")
        print("clarify=YES" if r.clarification_needed else "clarify=NO")
        if r.clarification_needed:
            print("    (running pipeline with original request — no human answers in test)")

        # --- Step 2: generate spec --------------------------------------------
        print("    generating spec...", end=" ", flush=True)
        spec_path = generate_spec(request)
        r.spec_generated = True
        print("OK")

        # --- Step 3: validate -------------------------------------------------
        print("    validating...", end=" ", flush=True)
        validate(spec_path, original_request=request)
        r.validation_passed = True
        print("OK")

        # --- Step 4: render ---------------------------------------------------
        print("    rendering...", end=" ", flush=True)
        output_path = render(spec_path)
        if Path(output_path).exists():
            r.dashboard_produced = True
        print("OK")

    except ValueError as e:
        print("FAIL")
        r.error_message = str(e).strip()
    except Exception as e:
        print("FAIL")
        r.error_message = f"{type(e).__name__}: {str(e).strip()}"

    r.elapsed = time.time() - t0
    return r


# ── MAIN ─────────────────────────────────────────────────────────────────────

def run_all() -> list[TestResult]:
    results = []
    total   = len(TEST_REQUESTS)

    for i, (cat, req) in enumerate(TEST_REQUESTS, 1):
        display = (req[:60] + "…") if len(req) > 60 else (req or "(empty)")
        print(f"\n{'─'*60}")
        print(f"Test {i}/{total} [{cat}]: {display}")
        print(f"{'─'*60}")
        result = run_one(i, cat, req)
        results.append(result)
        print(f"  => {result.label()}  ({result.elapsed:.1f}s)")

    return results


def write_log(results: list[TestResult]) -> str:
    ts      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    passes  = sum(1 for r in results if r.dashboard_produced)
    total   = len(results)

    sep  = "=" * 70
    body = [
        sep,
        "DASHBOARD AGENT — STRESS TEST RESULTS",
        f"Run at: {ts}",
        sep,
        "",
        f"SUMMARY: {passes} out of {total} requests produced a working dashboard",
        "",
    ]

    for r in results:
        body.append(r.log_block())
        body.append("")

    body.append("── BY CATEGORY ──────────────────────────────────────────────────────")
    for cat in ("CLEAR", "VAGUE", "EDGE"):
        cat_r   = [r for r in results if r.category == cat]
        cat_p   = sum(1 for r in cat_r if r.dashboard_produced)
        body.append(f"  {cat}: {cat_p}/{len(cat_r)} passed")

    body += ["", sep, ""]
    log_text = "\n".join(body)

    LOG_DIR.mkdir(exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_text + "\n")

    return log_text


if __name__ == "__main__":
    print(f"\nDashboard Agent — Stress Test")
    print(f"Running {len(TEST_REQUESTS)} test requests\n")

    results  = run_all()
    log_text = write_log(results)

    print("\n\n" + "=" * 60)
    print("FINAL RESULTS")
    print("=" * 60)
    print(log_text)
    print(f"Full log: {LOG_FILE.resolve()}")
