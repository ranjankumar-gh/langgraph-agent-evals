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


class _OneShotChat:
    """Stands in for ChatOllama on the hosted structured()/text() path: one call to
    invoke() either returns an object whose .content is the scripted string, or raises
    the scripted exception."""

    def __init__(self, outcome) -> None:
        self._outcome = outcome

    def invoke(self, messages):
        if isinstance(self._outcome, BaseException):
            raise self._outcome

        class _Msg:
            def __init__(self, content: str) -> None:
                self.content = content

        return _Msg(self._outcome)


def _hosted_llm(tmp_path, monkeypatch, model="nemotron-3-nano:30b-cloud"):
    monkeypatch.setattr(
        llm_mod,
        "ollama_model_info",
        lambda model, base_url="": {"digest": "d", "capabilities": ["completion", "tools", "thinking"]},
    )
    llm = llm_mod.OllamaLLM(model, cache_path=tmp_path / "cache.sqlite")
    assert llm.hosted is True
    monkeypatch.setattr(llm, "_sleep", lambda seconds: None)
    return llm


def test_hosted_structured_sends_schema_in_system_prompt_and_parses_prose_reply(tmp_path, monkeypatch):
    """Ollama Cloud ignores the json_schema format constraint, so hosted structured()
    must embed the schema in the system prompt (with reasoning on and room for it) and
    parse the JSON object out of a reply that has surrounding prose."""
    llm = _hosted_llm(tmp_path, monkeypatch)
    seen: dict = {}

    def fake_chat(seed, *, reasoning, num_predict):
        seen["reasoning"] = reasoning
        seen["num_predict"] = num_predict

        class _Chat:
            def invoke(self, messages):
                seen["system"] = messages[0][1]
                return _OneShotChat(
                    'Sure thing! {"intent": "damaged", "order_id": "ORD-1001"} Hope that helps.'
                ).invoke(messages)

        return _Chat()

    monkeypatch.setattr(llm, "_chat", fake_chat)

    result = llm.structured("Classify the request.", "user text", Classification, seed=0)

    assert result == Classification(intent="damaged", order_id="ORD-1001")
    assert seen["reasoning"] is True
    assert seen["num_predict"] >= 2048
    assert "Classify the request." in seen["system"]
    assert "JSON schema" in seen["system"]
    assert llm.retries == 0
    assert llm._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 1


def test_hosted_structured_retries_on_bad_json_then_succeeds(tmp_path, monkeypatch):
    llm = _hosted_llm(tmp_path, monkeypatch)
    outcomes = iter(["not json at all", '{"intent": "damaged", "order_id": "ORD-1001"}'])
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _OneShotChat(next(outcomes)))

    result = llm.structured("sys", "user", Classification, seed=0)

    assert result == Classification(intent="damaged", order_id="ORD-1001")
    assert llm.retries == 1
    assert llm.calls == 2
    assert llm._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 1


def test_hosted_structured_exhausts_retries_and_caches_nothing(tmp_path, monkeypatch):
    llm = _hosted_llm(tmp_path, monkeypatch)
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _OneShotChat("still not json"))

    with pytest.raises(llm_mod.StructuredOutputError):
        llm.structured("sys", "user", Classification, seed=0)

    assert llm.retries == 2
    assert llm.calls == 3
    assert llm._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 0


def test_hosted_structured_retries_5xx_response_error_not_4xx(tmp_path, monkeypatch):
    from ollama import ResponseError

    llm = _hosted_llm(tmp_path, monkeypatch)
    outcomes = iter([ResponseError("boom", status_code=500), '{"intent": "damaged", "order_id": "ORD-1001"}'])
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _OneShotChat(next(outcomes)))

    result = llm.structured("sys", "user", Classification, seed=0)

    assert result == Classification(intent="damaged", order_id="ORD-1001")
    assert llm.retries == 1


def test_hosted_structured_does_not_retry_4xx_response_error(tmp_path, monkeypatch):
    from ollama import ResponseError

    llm = _hosted_llm(tmp_path, monkeypatch)
    monkeypatch.setattr(
        llm, "_chat", lambda seed, *, reasoning, num_predict: _OneShotChat(ResponseError("bad", status_code=400))
    )

    with pytest.raises(llm_mod.StructuredOutputError):
        llm.structured("sys", "user", Classification, seed=0)

    assert llm.retries == 0
    assert llm.calls == 1


def test_hosted_text_retries_on_connection_error_then_succeeds(tmp_path, monkeypatch):
    import httpx

    llm = _hosted_llm(tmp_path, monkeypatch, model="gpt-oss:20b-cloud")
    outcomes = iter([httpx.ConnectError("refused"), "a clean reply"])
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _OneShotChat(next(outcomes)))

    result = llm.text("sys", "user", seed=0)

    assert result == "a clean reply"
    assert llm.retries == 1
    assert llm._db.execute("SELECT COUNT(*) FROM cache").fetchone()[0] == 1


def test_hosted_text_does_not_retry_non_retryable_exception(tmp_path, monkeypatch):
    llm = _hosted_llm(tmp_path, monkeypatch, model="gpt-oss:20b-cloud")
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _OneShotChat(ValueError("unexpected")))

    with pytest.raises(ValueError):
        llm.text("sys", "user", seed=0)

    assert llm.retries == 0
    assert llm.calls == 1


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
    """A local model's json_schema/with_structured_output path can still return None (the
    tool wasn't called); structured() must raise a clear StructuredOutputError instead of
    caching/returning None."""
    monkeypatch.setattr(
        llm_mod, "ollama_model_info", lambda model, base_url="": {"digest": "d", "capabilities": ["completion"]}
    )
    llm = llm_mod.OllamaLLM("qwen3:4b", cache_path=tmp_path / "cache.sqlite")
    seen: dict = {}
    monkeypatch.setattr(llm, "_chat", lambda seed, *, reasoning, num_predict: _MethodRecordingChat(seen, None))

    with pytest.raises(llm_mod.StructuredOutputError, match="qwen3:4b"):
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
    prompt_json_key = llm._key(
        "structured", "sys", "user", {}, 0, reasoning=True, num_predict=2048, method="prompt_json"
    )

    assert json_schema_key != prompt_json_key
