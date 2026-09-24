import pytest

from agent.llm import OllamaLLM, ollama_model_info
from agent.prompts import CLASSIFY_SYSTEM, Classification
from scripts.run_part1 import POLICY_MODEL

pytestmark = pytest.mark.ollama


def _available(model: str) -> bool:
    try:
        ollama_model_info(model)
    except Exception:
        return False
    return True


@pytest.mark.skipif(not _available(POLICY_MODEL), reason=f"Ollama with {POLICY_MODEL} is not available")
def test_policy_model_extracts_order_id(tmp_path):
    llm = OllamaLLM(POLICY_MODEL, cache_path=tmp_path / "cache.sqlite")
    result = llm.structured(CLASSIFY_SYSTEM, "Order ORD-1001 arrived broken, refund please.", Classification, seed=0)
    assert result.order_id == "ORD-1001"
    assert result.intent == "damaged"


@pytest.mark.skipif(not _available(POLICY_MODEL), reason=f"Ollama with {POLICY_MODEL} is not available")
def test_hosted_policy_model_reports_token_usage(tmp_path):
    """Part 2's cost numbers need usage_metadata from Ollama Cloud. If this fails, cost rows
    are all 'unmetered' and the cost table is empty - stop and report, do not zero-fill."""
    llm = OllamaLLM(POLICY_MODEL, cache_path=tmp_path / "cache.sqlite", namespace="smoke")
    llm.text("Reply with one word.", "Say hello.", seed=0)
    usage = llm.usage()
    assert usage["unmetered"] == 0
    assert usage["input_tokens"] > 0 and usage["output_tokens"] > 0
