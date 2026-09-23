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
