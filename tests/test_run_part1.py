"""Offline tests for the measured-run CLI's resume guard (no Ollama contact)."""
from __future__ import annotations

import json

import pytest

from scripts import run_part1


def _fake_git(*args: str) -> str:
    if args == ("rev-parse", "HEAD"):
        return "abc123"
    if args == ("status", "--porcelain", "--", "agent", "env", "evals"):
        return ""  # clean tree
    raise AssertionError(f"unexpected git invocation: {args}")


def test_resume_refuses_when_judge_model_differs(tmp_path, monkeypatch):
    monkeypatch.setattr(run_part1, "_git", _fake_git)

    out = tmp_path / "out"
    out.mkdir()
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "git_commit": "abc123",
                "policy_model": {"name": run_part1.POLICY_MODEL},
                "judge_model": {"name": "gpt-oss:20b-cloud"},
            }
        ),
        encoding="utf-8",
    )
    (out / "runs.jsonl").write_text("", encoding="utf-8")

    def _boom(*_args, **_kwargs):
        raise AssertionError("OllamaLLM must not be constructed once the resume guard refuses")

    monkeypatch.setattr(run_part1, "OllamaLLM", _boom)

    with pytest.raises(SystemExit) as excinfo:
        run_part1.main(["--out", str(out), "--judge-model", "gemma3:4b"])

    message = str(excinfo.value)
    assert "gpt-oss:20b-cloud" in message
    assert str(out) in message
    assert "new --out" in message


def test_resume_refuses_when_policy_model_differs(tmp_path, monkeypatch):
    monkeypatch.setattr(run_part1, "_git", _fake_git)

    out = tmp_path / "out"
    out.mkdir()
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "git_commit": "abc123",
                "policy_model": {"name": "qwen2.5:7b"},
                "judge_model": {"name": run_part1.JUDGE_MODEL},
            }
        ),
        encoding="utf-8",
    )
    (out / "runs.jsonl").write_text("", encoding="utf-8")

    def _boom(*_args, **_kwargs):
        raise AssertionError("OllamaLLM must not be constructed once the resume guard refuses")

    monkeypatch.setattr(run_part1, "OllamaLLM", _boom)

    with pytest.raises(SystemExit) as excinfo:
        run_part1.main(["--out", str(out)])

    message = str(excinfo.value)
    assert "qwen2.5:7b" in message
    assert str(out) in message
    assert "new --out" in message
