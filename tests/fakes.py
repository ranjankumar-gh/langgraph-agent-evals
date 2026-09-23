"""Deterministic stand-in for OllamaLLM so unit tests never need a model."""
from __future__ import annotations

from pydantic import BaseModel

from agent.prompts import Classification, RefundDecision


class FakeLLM:
    name = "fake"

    def __init__(self, *, classification=None, decision=None, verdict=None, reply: str = "ok") -> None:
        self.responses: list[BaseModel] = [
            classification or Classification(intent="damaged", order_id="ORD-1001"),
            decision or RefundDecision(refund_type="full", rationale="damaged item"),
        ]
        if verdict is not None:
            self.responses.append(verdict)
        self.reply = reply
        self.prompts: list[tuple[str, str]] = []

    def structured(self, system, user, schema, *, seed):
        self.prompts.append((system, user))
        for response in self.responses:
            if isinstance(response, schema):
                return response
        raise AssertionError(f"FakeLLM has no scripted response for {schema.__name__}")

    def text(self, system, user, *, seed):
        self.prompts.append((system, user))
        return self.reply
