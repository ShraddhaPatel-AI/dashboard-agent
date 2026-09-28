"""
clarifier.py
Human-in-the-Loop (HITL) step: evaluates whether a dashboard request is specific
enough to build from before spending any API budget on spec generation.

A good dashboard request needs three things:
  - A metric (what to measure, e.g. quote count, claim amount, bind rate)
  - A grouping (how to slice it, e.g. by state, by product, by month)
  - A time range (e.g. this year, last 6 months)

If any of these are missing, this module asks focused questions instead of guessing.
Max one round of questions — just enough to unblock spec generation, not an interrogation.

Two exported functions:
  evaluate_request() — calls Claude and returns a verdict as a Python dict.
                       No terminal I/O. Used by app.py (Streamlit).
  clarify()          — calls evaluate_request(), then handles terminal prompts/answers.
                       Used by pipeline.py (command line).

This separation of "AI logic" from "I/O handling" means the same intelligence
can be wired to a browser form, a Slack bot, or a terminal without changing
the underlying Claude call.

Usage (standalone):
    python clarifier.py "Show me quotes"

Usage (from pipeline.py):
    from clarifier import clarify
    enriched_request = clarify("Show me quotes")
"""

import os
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
import anthropic

load_dotenv()

MODEL       = "claude-sonnet-4-6"
MAX_TOKENS  = 1024
PROMPTS_DIR = Path("prompts")


def _read_file(path) -> str:
    """Read a file and return its text content."""
    with open(path, encoding="utf-8") as f:
        return f.read()


def _call_claude(prompt: str) -> str:
    """Send a prompt to the Claude API and return the text response."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    client  = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text.strip()


def _extract_json(text: str) -> str:
    """
    Strip markdown code fences if Claude wrapped its JSON response in them.
    The prompt tells Claude to return raw JSON, but it occasionally adds
    triple-backtick fencing anyway. This strips that wrapper so json.loads()
    can parse the content cleanly.
    """
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        inner = "\n".join(lines[1:])
        if inner.rstrip().endswith("```"):
            inner = inner.rstrip()[:-3]
        return inner.strip()
    return text


def evaluate_request(user_request: str) -> dict:
    """
    Ask Claude whether the request is clear enough to build from.
    Returns a dict: {"status": "clear", "enriched_request": "..."}
                 or {"status": "needs_clarification", "questions": [...]}
    Does NOT ask the user anything — that is the caller's responsibility.
    Used by app.py (Streamlit) to get the verdict without terminal I/O.
    """
    template  = _read_file(PROMPTS_DIR / "clarifier_prompt.txt")
    prompt    = template.replace("__USER_REQUEST__", user_request)
    raw       = _call_claude(prompt)
    json_text = _extract_json(raw)
    try:
        return json.loads(json_text)
    except json.JSONDecodeError:
        return {"status": "clear", "enriched_request": user_request}


def clarify(user_request: str) -> str:
    """
    Evaluate the request for completeness.
    Returns either the request as-is (with any enrichment from Claude),
    or a combined request + answers string if the user was asked questions.
    Always returns a non-empty string.
    """
    result = evaluate_request(user_request)
    status = result.get("status", "clear")

    if status == "clear":
        enriched = result.get("enriched_request", user_request)
        print("  Request is specific — proceeding directly.")
        return enriched

    if status == "needs_clarification":
        questions = result.get("questions", [])
        if not questions:
            return user_request

        print("\n  A few quick questions to make your dashboard more useful:\n")
        answers = []
        for i, question in enumerate(questions, 1):
            print(f"  {i}. {question}")
            answer = input("     Your answer: ").strip()
            if answer:
                answers.append(f"{question} -> {answer}")

        if answers:
            enriched = f"{user_request}. Additional context: {'; '.join(answers)}"
        else:
            enriched = user_request

        print("\n  Got it — building your dashboard now.\n")
        return enriched

    return user_request


if __name__ == "__main__":
    request = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else input("Request: ").strip()
    print(f"\nEvaluating: '{request}'")
    enriched = clarify(request)
    print(f"\nEnriched request:\n  {enriched}\n")
