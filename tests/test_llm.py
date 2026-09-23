import pytest

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


class _RecordingChat:
    """Stands in for ChatOllama on the text() path: returns a canned .content."""

    def __init__(self, text_value: str = "a clean reply") -> None:
        self._text_value = text_value

    def invoke(self, messages):
        class _Msg:
            def __init__(self, content: str) -> None:
                self.content = content

        return _Msg(self._text_value)


def test_structured_calls_are_cached_per_seed(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "abc", "capabilities": ["completion"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _FakeChat())
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
    assert llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "a.sqlite")._thinking_capable is True
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion"]}
    )
    assert llm_mod.OllamaLLM("gemma3:4b", cache_path=tmp_path / "b.sqlite")._thinking_capable is False


def test_text_lets_thinking_models_reason_with_room_for_it(tmp_path, monkeypatch):
    """text() on a thinking-capable model must ask ChatOllama for reasoning=True (so the clean
    reply lands in .content, not the chain-of-thought) and a num_predict big enough for both the
    reasoning and the reply."""
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "thinking"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", num_predict=512, cache_path=tmp_path / "cache.sqlite")
    seen = {}

    def fake_chat(seed, *, reasoning, num_predict):
        seen["reasoning"] = reasoning
        seen["num_predict"] = num_predict
        return _RecordingChat("a clean reply mentioning 149.00")

    monkeypatch.setattr(llm, "_chat", fake_chat)

    result = llm.text("sys", "user", seed=0)

    assert result == "a clean reply mentioning 149.00"
    assert seen["reasoning"] is True
    assert seen["num_predict"] >= 2048


def test_structured_still_suppresses_reasoning_on_thinking_models(tmp_path, monkeypatch):
    """structured() must keep reasoning=False on a thinking model, and must not inflate
    num_predict — only text() gets the larger budget."""
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "thinking"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", num_predict=512, cache_path=tmp_path / "cache.sqlite")
    seen = {}

    def fake_chat(seed, *, reasoning, num_predict):
        seen["reasoning"] = reasoning
        seen["num_predict"] = num_predict
        return _FakeChat()

    monkeypatch.setattr(llm, "_chat", fake_chat)

    llm.structured("sys", "user", Classification, seed=0)

    assert seen["reasoning"] is False
    assert seen["num_predict"] == 512


def test_non_thinking_model_gets_no_reasoning_flag_on_either_path(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion"]}
    )
    llm = llm_mod.OllamaLLM("gemma3:4b", num_predict=512, cache_path=tmp_path / "cache.sqlite")
    seen = {}

    def fake_chat(seed, *, reasoning, num_predict):
        seen.setdefault("calls", []).append((reasoning, num_predict))
        return _RecordingChat("hi")

    monkeypatch.setattr(llm, "_chat", fake_chat)
    llm.text("sys", "user", seed=0)

    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: (
        seen.setdefault("calls", []).append((reasoning, num_predict)) or _FakeChat()
    ))
    llm.structured("sys", "user", Classification, seed=0)

    assert seen["calls"] == [(None, 512), (None, 512)]


def test_cache_key_differs_between_old_and_new_reasoning_flags(tmp_path, monkeypatch):
    """A cache entry recorded under the old reasoning=False/num_predict=512 behaviour for
    text() must never be replayed now that text() uses reasoning=True/num_predict>=2048."""
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "thinking"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")

    old_key = llm._key("text", "sys", "user", None, 0, reasoning=False, num_predict=512)
    new_key = llm._key("text", "sys", "user", None, 0, reasoning=True, num_predict=2048)

    assert old_key != new_key


def test_cache_key_does_not_collide_text_and_structured(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "thinking"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")

    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _FakeChat())
    llm.structured("same", "prompt", Classification, seed=0)

    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _RecordingChat("clean reply"))
    llm.text("same", "prompt", seed=0)

    rows = llm._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    assert rows == 2


class _MethodRecordingChat:
    """Stands in for ChatOllama on the structured() path: records which
    with_structured_output(method=...) it was built with."""

    def __init__(self, seen: dict, result):
        self._seen = seen
        self._result = result

    def with_structured_output(self, schema, method):
        self._seen["method"] = method
        return self

    def invoke(self, messages):
        return self._result


def test_structured_uses_function_calling_for_hosted_cloud_models(tmp_path, monkeypatch):
    """A '-cloud' model name marks it hosted; hosted models ignore the json_schema format
    constraint on Ollama Cloud, so structured() must ask for function_calling instead."""
    monkeypatch.setattr(
        llm_mod,
        "ollama_model_info",
        lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "tools", "thinking"]},
    )
    llm = llm_mod.OllamaLLM("nemotron-3-nano:30b-cloud", cache_path=tmp_path / "cache.sqlite")
    assert llm.hosted is True
    seen: dict = {}
    result = Classification(intent="damaged", order_id="ORD-1001")
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _MethodRecordingChat(seen, result))

    out = llm.structured("sys", "user", Classification, seed=0)

    assert seen["method"] == "function_calling"
    assert out == result


def test_structured_uses_json_schema_for_local_models(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")
    assert llm.hosted is False
    seen: dict = {}
    result = Classification(intent="damaged", order_id="ORD-1001")
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _MethodRecordingChat(seen, result))

    out = llm.structured("sys", "user", Classification, seed=0)

    assert seen["method"] == "json_schema"
    assert out == result


def test_structured_none_result_raises_and_is_not_cached(tmp_path, monkeypatch):
    """When the model never calls the tool (seen from nemotron acting as judge), structured()
    must raise a clear StructuredOutputError instead of caching/returning None."""
    monkeypatch.setattr(
        llm_mod,
        "ollama_model_info",
        lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "tools"]},
    )
    llm = llm_mod.OllamaLLM("nemotron-3-nano:30b-cloud", cache_path=tmp_path / "cache.sqlite")
    seen: dict = {}
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _MethodRecordingChat(seen, None))

    with pytest.raises(llm_mod.StructuredOutputError, match="nemotron-3-nano:30b-cloud"):
        llm.structured("sys", "user", Classification, seed=0)

    rows = llm._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0]
    assert rows == 0


def test_cache_key_differs_by_structured_output_method(tmp_path, monkeypatch):
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")

    json_schema_key = llm._key(
        "structured", "sys", "user", {}, 0, reasoning=False, num_predict=400, method="json_schema"
    )
    function_calling_key = llm._key(
        "structured", "sys", "user", {}, 0, reasoning=False, num_predict=400, method="function_calling"
    )

    assert json_schema_key != function_calling_key
