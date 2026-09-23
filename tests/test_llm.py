from agent import llm as llm_mod
from agent.prompts import Classification


class _FakeChat:
    calls = 0

    def with_structured_output(self, schema, method):
        assert method == "json_schema"
        return self

    def invoke(self, messages):
        _FakeChat.calls += 1
        return Classification(intent="damaged", order_id="ORD-1001")


def test_structured_calls_are_cached_per_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "abc", "capabilities": ["completion"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")
    monkeypatch.setattr(llm, "_chat", lambda seed, num_predict=None: _FakeChat())
    _FakeChat.calls = 0

    first = llm.structured("sys", "user", Classification, seed=0)
    second = llm.structured("sys", "user", Classification, seed=0)
    third = llm.structured("sys", "user", Classification, seed=1)

    assert first == second == third
    assert _FakeChat.calls == 2
    assert (llm.calls, llm.hits) == (2, 1)


def test_reasoning_disabled_only_for_thinking_models(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "thinking"]}
    )
    assert llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "a.sqlite")._reasoning is False
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion"]}
    )
    assert llm_mod.OllamaLLM("gemma3:4b", cache_path=tmp_path / "b.sqlite")._reasoning is None
