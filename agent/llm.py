"""LLM access for the agent and the judge, behind a record/replay cache.

Models are either installed locally or served from Ollama Cloud through the local Ollama
daemon at base_url (no API key) - a model name ending "-cloud" marks it hosted, recorded
as self.hosted.

Ollama Cloud ignores the json_schema `format` constraint on structured output (a raw call
with a schema still returns bare text), and the tool-calling alternative
(with_structured_output(method="function_calling")) leaves the model failing to call the
tool in 15-25% of gpt-oss judge calls and worse for other models, regardless of thinking
mode. So hosted models get structured output a third way: the JSON schema is appended to
the system prompt, the call is made with reasoning on (so the clean reply lands in
.content and the chain-of-thought doesn't) and num_predict raised to leave room for both,
and the reply is parsed by scanning it for every brace-balanced top-level "{...}"
substring (tracking depth, and not counting braces inside JSON string literals), trying
them last-first, and returning the first one that validates against the schema - a reply
that echoes the schema before giving its answer ("the schema is {...} and my answer is
{...}") has two such candidates, and a single first-to-last-brace span across both would
be invalid JSON. Local models are unaffected - they keep the json_schema method with
reasoning off, exactly as before.

Ollama Cloud also returns transient `ResponseError` 5xx (Internal Server Error) fairly
often. So hosted calls (both structured() and text()) get a bounded retry: up to 3
attempts total, with a short backoff between attempts (self._sleep, patchable in tests so
they don't actually sleep). A retry is taken on a 5xx ResponseError, a connection error
(httpx.ConnectError / httpx.ReadTimeout / ConnectionError), and, for structured(), a
failure to extract or validate the JSON reply (StructuredOutputError or a pydantic
ValidationError) - any other exception is not retried. Only a successful call is cached;
retries are counted on the public self.retries so callers can record them. After the last
attempt, the last error is raised - for structured(), always as a StructuredOutputError
that chains the underlying cause.

The cache key covers model digest, sampling options, prompts, schema, seed and the method
used (json_schema for local vs the hosted prompt-embedded-schema approach), so a change in
behaviour - old vs new reasoning/num_predict, or the retired function_calling method -
never replays a stale cache entry. Seeds are the trial index and are passed to the model,
but Ollama Cloud does not honour the seed, so for hosted models the seed alone does not
make variants see the same draw. What pairs variants is this cache: the seed is part of
the key, so any two variants whose prompt to a node is identical (same case, trial and
facts) replay the same cached classification, refund decision, reply and judge verdict.
Variants that hand a node different facts get a different key and a fresh draw.

A namespace (default empty) is appended to the cache key only when set, so a namespaced
instance draws fresh from the model even for a prompt another instance has cached, and an
un-namespaced instance keeps exactly the keys it had before namespaces existed. Part 2 gives
each eval arm its own namespace so a full rerun and a fork are independent draws.

Every live call is metered: wall seconds, and input/output tokens from the reply's
usage_metadata. A reply with no usage (the local json_schema structured path returns only the
parsed object) is counted as unmetered rather than as zero tokens. Cache hits add nothing.
usage() snapshots the counters; usage_delta() diffs two snapshots.
"""
from __future__ import annotations

import hashlib
import json
import sqlite3
import time
import urllib.request
from pathlib import Path
from typing import Protocol, TypeVar

import httpx
from ollama import ResponseError
from pydantic import BaseModel, ValidationError

M = TypeVar("M", bound=BaseModel)

# Backoff between hosted-call retry attempts: RETRY_DELAYS[0] before attempt 2,
# RETRY_DELAYS[1] before attempt 3.
RETRY_DELAYS = (2, 5)


class StructuredOutputError(RuntimeError):
    """Raised when structured() gets no parsed result back from the model (seen when a
    hosted model's reply has no JSON object that validates against the schema, or - on
    the local json_schema path - the parsed result comes back empty)."""


def _retryable(exc: BaseException) -> bool:
    """Whether a hosted-call failure is worth a bounded retry."""
    if isinstance(exc, (StructuredOutputError, ValidationError)):
        return True
    if isinstance(exc, ResponseError):
        return (exc.status_code or 0) >= 500
    if isinstance(exc, (httpx.ConnectError, httpx.ReadTimeout, ConnectionError)):
        return True
    return False


def _balanced_json_objects(content: str) -> list[str]:
    """Every brace-balanced top-level "{...}" substring in content, in the order they
    appear. Braces inside a JSON string literal (respecting \\" escapes) don't count
    toward depth, so a string value that itself contains "{" or "}" doesn't unbalance the
    object around it, and a nested object inside an answer stays part of its parent
    instead of closing it early."""
    candidates: list[str] = []
    depth = 0
    start: int | None = None
    in_string = False
    escaped = False
    for i, ch in enumerate(content):
        if in_string:
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            continue
        if ch == '"':
            in_string = True
        elif ch == "{":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "}" and depth > 0:
            depth -= 1
            if depth == 0 and start is not None:
                candidates.append(content[start : i + 1])
                start = None
    return candidates


def _parse_structured_reply(content: str, schema: type[M], model_name: str) -> M:
    """Try every brace-balanced object in content against schema, last-appearing first
    (a reply that echoes the schema before its answer puts the real answer last), and
    return the first that validates. Raises StructuredOutputError (retryable) if none
    do."""
    for candidate in reversed(_balanced_json_objects(content)):
        try:
            return schema.model_validate_json(candidate)
        except ValidationError:
            continue
    raise StructuredOutputError(f"{model_name} reply had no JSON object matching the schema: {content!r}")


class LLM(Protocol):
    name: str

    def structured(self, system: str, user: str, schema: type[M], *, seed: int) -> M: ...

    def text(self, system: str, user: str, *, seed: int) -> str: ...

    def usage(self) -> dict: ...


def usage_delta(before: dict, after: dict) -> dict:
    """Counter differences between two usage() snapshots of the same LLM."""
    return {k: round(after[k] - before[k], 3) if k == "seconds" else after[k] - before[k] for k in after}


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
        namespace: str = "",
    ) -> None:
        info = ollama_model_info(model, base_url)
        self.name = model
        # Ollama Cloud models (name ends "-cloud") ignore the json_schema format constraint on
        # structured output, so structured() picks its approach off this (see module docstring).
        self.hosted = model.endswith("-cloud")
        self.digest = info["digest"]
        # qwen3 thinks by default. On text() we let it think (reasoning=True) so the clean reply
        # lands in .content and the chain-of-thought goes to additional_kwargs instead of being
        # returned; on local structured() we still suppress it (reasoning=False) because the
        # json_schema format already constrains the output and that path is smoke-tested. Hosted
        # structured() always reasons (see module docstring). Models without the capability get
        # no flag at all (reasoning=None) on either local path.
        self._thinking_capable = "thinking" in info["capabilities"]
        self.temperature = temperature
        self.num_predict = num_predict
        self.base_url = base_url
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(cache_path, check_same_thread=False)
        self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
        self.calls = 0
        self.hits = 0
        # Count of retry attempts taken across every hosted call this instance has made
        # (0 on a run with no retries). scripts/run_part1.py records this in metadata.
        self.retries = 0
        # A patchable hook so tests can skip the real backoff.
        self._sleep = time.sleep
        self.namespace = namespace
        self.input_tokens = 0
        self.output_tokens = 0
        # Live calls whose reply carried no usage_metadata: tokens unknown, not zero.
        self.unmetered = 0
        self.seconds = 0.0

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
        parts = [
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
        ]
        # Appended only when set, so an un-namespaced key is byte-identical to the part-1 key.
        if self.namespace:
            parts.append(self.namespace)
        blob = json.dumps(parts, sort_keys=True)
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

    def _meter(self, message, started: float) -> None:
        self.seconds += time.perf_counter() - started
        usage = getattr(message, "usage_metadata", None)
        if usage:
            self.input_tokens += usage.get("input_tokens", 0)
            self.output_tokens += usage.get("output_tokens", 0)
        else:
            self.unmetered += 1

    def usage(self) -> dict:
        return {
            "calls": self.calls,
            "hits": self.hits,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "unmetered": self.unmetered,
            "seconds": round(self.seconds, 3),
        }

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
        if self.hosted:
            return self._structured_hosted(system, user, schema, seed)
        reasoning = False if self._thinking_capable else None
        num_predict = self.num_predict
        method = "json_schema"
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
        started = time.perf_counter()
        result = (
            self._chat(seed, reasoning=reasoning, num_predict=num_predict)
            .with_structured_output(schema, method=method)
            .invoke([("system", system), ("human", user)])
        )
        self._meter(None, started)
        if result is None:
            raise StructuredOutputError(f"{self.name} returned no structured output")
        self._store(key, result.model_dump_json())
        return result

    def _structured_hosted(self, system: str, user: str, schema: type[M], seed: int) -> M:
        reasoning = True
        num_predict = max(self.num_predict, 2048)
        method = "prompt_json"
        schema_system = (
            f"{system}\n\nRespond with only a JSON object that validates against this JSON "
            f"schema, and nothing else:\n{json.dumps(schema.model_json_schema())}"
        )
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

        # The loop below always exits from inside itself - by returning on success, or by
        # raising once attempt 2 (the last) fails - so there is no fall-through case after it.
        for attempt in range(3):
            if attempt > 0:
                self.retries += 1
                self._sleep(RETRY_DELAYS[attempt - 1])
            self.calls += 1
            try:
                started = time.perf_counter()
                message = self._chat(seed, reasoning=reasoning, num_predict=num_predict).invoke(
                    [("system", schema_system), ("human", user)]
                )
                self._meter(message, started)
                content = str(message.content)
                result = _parse_structured_reply(content, schema, self.name)
            except Exception as exc:
                if attempt < 2 and _retryable(exc):
                    continue
                if isinstance(exc, StructuredOutputError):
                    raise
                raise StructuredOutputError(f"{self.name} structured() failed: {exc}") from exc
            else:
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
        if self.hosted:
            content = self._text_hosted(system, user, seed, reasoning=reasoning, num_predict=num_predict)
        else:
            self.calls += 1
            started = time.perf_counter()
            message = self._chat(seed, reasoning=reasoning, num_predict=num_predict).invoke(
                [("system", system), ("human", user)]
            )
            self._meter(message, started)
            content = str(message.content)
        self._store(key, json.dumps(content))
        return content

    def _text_hosted(self, system: str, user: str, seed: int, *, reasoning: bool | None, num_predict: int) -> str:
        # Same shape as _structured_hosted's loop: always exits from inside itself, by
        # returning on success or re-raising once attempt 2 (the last) fails.
        for attempt in range(3):
            if attempt > 0:
                self.retries += 1
                self._sleep(RETRY_DELAYS[attempt - 1])
            self.calls += 1
            try:
                started = time.perf_counter()
                message = self._chat(seed, reasoning=reasoning, num_predict=num_predict).invoke(
                    [("system", system), ("human", user)]
                )
                self._meter(message, started)
                return str(message.content)
            except Exception as exc:
                if attempt < 2 and _retryable(exc):
                    continue
                raise
