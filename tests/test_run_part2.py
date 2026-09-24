"""Offline tests for the Part 2 CLI (no Ollama contact)."""
from __future__ import annotations

import json

import pytest

from scripts import run_part2


class _FakeOllamaLLM:
    def __init__(self, model, *, num_predict=512, cache_path=None, base_url=None, temperature=0.7, namespace=""):
        self.name = model
        self.digest = "fakedigest"
        self.temperature = temperature
        self.namespace = namespace

    def usage(self):
        return {"calls": 0, "hits": 0, "input_tokens": 0, "output_tokens": 0, "unmetered": 0, "seconds": 0.0}


def _setup(monkeypatch, commit="abc123"):
    def fake_git(*args):
        if args == ("rev-parse", "HEAD"):
            return commit
        if args == ("status", "--porcelain", "--", "agent", "env", "evals"):
            return ""
        raise AssertionError(args)

    groups = []

    def fake_group(case, trial, changes, llms):
        groups.append((case.id, trial))
        return [{"arm": "baseline", "change": "baseline", "case_id": case.id, "trial": trial}] + [
            {"arm": arm, "change": ch, "case_id": case.id, "trial": trial} for ch in changes for arm in ("full", "fork", "fork_naive")
        ]

    monkeypatch.setattr(run_part2, "_git", fake_git)
    monkeypatch.setattr(run_part2, "OllamaLLM", _FakeOllamaLLM)
    monkeypatch.setattr(run_part2, "run_group", fake_group)
    monkeypatch.setattr(run_part2, "summarize_part2", lambda rows: {"n_rows": len(rows)})
    monkeypatch.setattr(run_part2, "render_markdown_part2", lambda summary, meta: "# Part 2 results\n")
    return groups


def test_run_part2_resumes_whole_groups(tmp_path, monkeypatch):
    groups = _setup(monkeypatch)
    out = tmp_path / "p2"
    args = ["--ids", "H01,I01", "--k", "2", "--out", str(out)]
    assert run_part2.main(args) == 0
    assert sorted(groups) == [("H01", 0), ("H01", 1), ("I01", 0), ("I01", 1)]
    rows = [json.loads(line) for line in (out / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 4 * (1 + 3 * 3)

    groups.clear()
    assert run_part2.main(args) == 0
    assert groups == []  # every group already complete

    meta = json.loads((out / "metadata.json").read_text())
    assert meta["changes"] == ["baseline", "D", "E"]
    assert meta["namespaces"] == ["", "p2-fork-D", "p2-fork-baseline", "p2-full-D", "p2-full-baseline"]


def test_run_part2_refuses_a_different_commit(tmp_path, monkeypatch):
    _setup(monkeypatch, commit="abc123")
    out = tmp_path / "p2"
    run_part2.main(["--ids", "H01", "--k", "1", "--out", str(out)])
    _setup(monkeypatch, commit="def456")
    with pytest.raises(SystemExit) as excinfo:
        run_part2.main(["--ids", "H01", "--k", "1", "--out", str(out)])
    assert "abc123" in str(excinfo.value)


def test_run_part2_rejects_an_unknown_change(tmp_path, monkeypatch):
    _setup(monkeypatch)
    with pytest.raises(SystemExit) as excinfo:
        run_part2.main(["--changes", "baseline,Z", "--out", str(tmp_path / "p2")])
    assert "Z" in str(excinfo.value)
