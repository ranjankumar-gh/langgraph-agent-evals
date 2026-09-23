"""LLM access for the agent and the judge: local Ollama only, behind a record/replay cache.

The cache key covers model digest, sampling options, prompts, schema and seed, so a
re-run of an unchanged case replays instead of calling the model. Seeds are the trial
index, which makes every variant see the same draw for the same (case, trial).
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import urllib.request
from pathlib import Path
from typing import Protocol, TypeVar

from pydantic import BaseModel

M = TypeVar("M", bound=BaseModel)


class StructuredOutputError(RuntimeError):
    """Raised when structured() gets no parsed result back from the model (seen when a
    hosted model never calls the structured-output tool)."""


class LLM(Protocol):
    name: str

    def structured(self, system: str, user: str, schema: type[M], *, seed: int) -> M: ...

    def text(self, system: str, user: str, *, seed: int) -> str: ...


def _get_json(url: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def ollama_model_info(model: str, base_url: str = "http://localhost:11434") -> dict:
    """Digest and capabilities of an installed Ollama model."""
    tags = _get_json(f"{base_url}/api/tags")
    match = [m for m in tags["models"] if m["name"] == model]
    if not match:
        raise RuntimeError(f"Ollama model {model!r} is not installed; run: ollama pull {model}")
    show = _get_json(f"{base_url}/api/show", {"model": model})
    return {"digest": match[0]["digest"], "capabilities": show.get("capabilities", [])}


class OllamaLLM:
    def __init__(
        self,
        model: str,
        *,
        temperature: float = 0.7,
        num_predict: int = 512,
        cache_path: Path = Path(".cache/llm.sqlite"),
        base_url: str = "http://localhost:11434",
    ) -> None:
        info = ollama_model_info(model, base_url)
        self.name = model
        # Ollama Cloud models (name ends "-cloud") ignore the json_schema format constraint on
        # structured output, so structured() picks its with_structured_output method off this.
        self.hosted = model.endswith("-cloud")
        self.digest = info["digest"]
        # qwen3 thinks by default. On text() we let it think (reasoning=True) so the clean reply
        # lands in .content and the chain-of-thought goes to additional_kwargs instead of being
        # returned; on structured() we still suppress it (reasoning=False) because the json_schema
        # format already constrains the output and that path is smoke-tested. Models without the
        # capability get no flag at all (reasoning=None) on either path.
        self._thinking_capable = "thinking" in info["capabilities"]
        self.temperature = temperature
        self.num_predict = num_predict
        self.base_url = base_url
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(cache_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.calls = 0
        self.hits = 0

    def _key(
        self,
        kind: str,
        system: str,
        user: str,
        extra: object,
        seed: int,
        *,
        reasoning: bool | None,
        num_predict: int,
        method: str | None = None,
    ) -> str:
        # reasoning, num_predict and method are the EFFECTIVE values for this call (which differ
        # between text() and structured(), and from the constructor default for thinking models'
        # text() calls, and between hosted and local models' structured() calls) so that a cache
        # entry recorded under old behaviour is never replayed.
        blob = json.dumps(
            [
                self.name,
                self.digest,
                self.temperature,
                num_predict,
                reasoning,
                method,
                kind,
                system,
                user,
                extra,
                seed,
            ],
            sort_keys=True,
        )
        return hashlib.sha256(blob.encode()).hexdigest()

    def _lookup(self, key: str) -> str | None:
        row = self._db.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        if row is None:
            return None
        self.hits += 1
        return row[0]

    def _store(self, key: str, value: str) -> None:
        self._db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (key, value))
        self._db.commit()

    def _chat(self, seed: int, *, reasoning: bool | None, num_predict: int):
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=self.name,
            base_url=self.base_url,
            temperature=self.temperature,
            seed=seed,
            num_predict=num_predict,
            reasoning=reasoning,
        )

    def structured(self, system: str, user: str, schema: type[M], *, seed: int) -> M:
        reasoning = False if self._thinking_capable else None
        num_predict = self.num_predict
        # Ollama Cloud ignores the json_schema format constraint (a raw call with a schema
        # still returns bare text), so hosted models get structured output via tool calling
        # instead; local models keep json_schema, which is what's smoke-tested there.
        method = "function_calling" if self.hosted else "json_schema"
        key = self._key(
            "structured",
            system,
            user,
            schema.model_json_schema(),
            seed,
            reasoning=reasoning,
            num_predict=num_predict,
            method=method,
        )
        cached = self._lookup(key)
        if cached is not None:
            return schema.model_validate_json(cached)
        self.calls += 1
        result = (
            self._chat(seed, reasoning=reasoning, num_predict=num_predict)
            .with_structured_output(schema, method=method)
            .invoke([("system", system), ("human", user)])
        )
        if result is None:
            raise StructuredOutputError(f"{self.name} returned no structured output")
        self._store(key, result.model_dump_json())
        return result

    def text(self, system: str, user: str, *, seed: int) -> str:
        reasoning = True if self._thinking_capable else None
        # Thinking models need room for the reasoning trace AND the reply that follows it.
        num_predict = max(self.num_predict, 2048) if self._thinking_capable else self.num_predict
        key = self._key("text", system, user, None, seed, reasoning=reasoning, num_predict=num_predict)
        cached = self._lookup(key)
        if cached is not None:
            return json.loads(cached)
        self.calls += 1
        content = str(
            self._chat(seed, reasoning=reasoning, num_predict=num_predict)
            .invoke([("system", system), ("human", user)])
            .content
        )
        self._store(key, json.dumps(content))
        return content
