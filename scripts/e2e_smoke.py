"""End-to-end smoke test against the real LLM provider (spec §27 acceptance criteria).

Runs the full loop: upload material -> extract concepts and relationships -> build the
graph -> choose a target -> detect gaps -> generate a targeted question -> grade the
answer -> update mastery -> recommend the next step.

Usage:
    ./.runtime/python312/python.exe scripts/e2e_smoke.py [answer]

Set DATA_DIR to run against a scratch database instead of the default data/ directory.
"""

from __future__ import annotations

import os
import sys
import tempfile

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app

SOURCE = """# Brownian Motion

Brownian motion is a continuous-time stochastic process that models the random
movement of particles suspended in a fluid. It has independent increments, and
its sample paths are continuous but nowhere differentiable. Brownian motion is
the foundation of stochastic calculus.

# Ito's Lemma

Ito's Lemma is the stochastic counterpart of the chain rule from ordinary
calculus. For a function of a Brownian motion, the second-order term does not
vanish, because the quadratic variation of Brownian motion grows linearly in
time. Ito's Lemma therefore includes a second derivative correction term.

# Black-Scholes Model

The Black-Scholes model prices European options by assuming the underlying asset
follows geometric Brownian motion. The model derives a partial differential
equation whose solution gives the option price as a function of volatility,
the risk-free rate, and time to maturity. Understanding the Black-Scholes model
requires familiarity with geometric Brownian motion and Ito's Lemma.
"""


def main() -> None:
    answer_text = sys.argv[1] if len(sys.argv) > 1 else None

    # Windows consoles default to GBK; force UTF-8 so symbols like ✓/✗ print.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    if os.environ.get("DATA_DIR", "").strip():
        print(f"Using existing DATA_DIR={os.environ['DATA_DIR']} (unset it to use a scratch DB)")
    else:
        os.environ.pop("DATA_DIR", None)
        os.environ["DATA_DIR"] = tempfile.mkdtemp(prefix="e2e-smoke-")

    settings = Settings.from_environment()
    if not settings.llm_enabled:
        print("No LLM provider configured in .env — this smoke test needs one.")
        raise SystemExit(1)
    print(f"Using LLM {settings.llm_model} at {settings.llm_base_url}, data in {settings.data_dir}")

    client = TestClient(create_app(settings))

    upload = client.post(
        "/documents/upload", files={"file": ("quant.md", SOURCE.encode(), "text/markdown")}
    )
    print(f"[1] upload -> {upload.status_code}: {upload.json()}")

    learn = client.post("/agent/chat", json={"message": "help me learn Black-Scholes"})
    payload = learn.json()
    print(f"\n[2] chat 'help me learn Black-Scholes' -> {learn.status_code}\n")
    print(payload["reply"])
    print("\n    actions:", [action["tool"] for action in payload["actions"]])
    pending = payload["pending"]
    if pending is None:
        print("No pending question; stopping.")
        return
    print("    pending:", pending["concept_name"], "|", pending["question"][:80], "...")

    user_answer = answer_text
    if user_answer is None and pending["question"].startswith("True or False"):
        user_answer = "true"  # deterministic evaluator path; correct for this material
    if user_answer is None:
        user_answer = input("\nYour answer: ")
    answer = client.post("/agent/chat", json={"message": user_answer})
    print(f"\n[3] chat answer -> {answer.status_code}\n")
    print(answer.json()["reply"])
    print("    actions:", [action["tool"] for action in answer.json()["actions"]])

    recommend = client.post("/agent/chat", json={"message": "what should I study next?"})
    print(f"\n[4] chat 'what should I study next?' -> {recommend.status_code}\n")
    print(recommend.json()["reply"])

    graph = client.get("/graph").json()
    print(
        f"\n[5] graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges; "
        f"edges = {[(e['source'], e['target'], e['type']) for e in graph['edges'][:6]]}"
    )


if __name__ == "__main__":
    main()
