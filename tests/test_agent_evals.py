"""
Agent evals: run ADK AgentEvaluator against evals/*.test.json.

Requires: GOOGLE_API_KEY (or equivalent) for the model. Run from repo root:
  pytest tests/test_agent_evals.py -v

To run only unit tests and skip evals (e.g. in CI without API key):
  pytest -v -m "not integration"
"""

from __future__ import annotations

from pathlib import Path

import pytest

# Evals directory next to repo root (same level as tests/)
EVALS_DIR = Path(__file__).resolve().parent.parent / "evals"


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stock_analyst_routing_evals():
    """Run routing + tool trajectory + response_match evals from evals/*.test.json."""
    from google.adk.evaluation.agent_evaluator import AgentEvaluator

    assert EVALS_DIR.is_dir(), f"evals dir not found: {EVALS_DIR}"
    await AgentEvaluator.evaluate(
        agent_module="stock_analyst",
        eval_dataset_file_path_or_dir=str(EVALS_DIR / "stock_analyst_routing.test.json"),
        num_runs=1,
        print_detailed_results=True,
    )
