"""Offline tests for the measured-run CLI's resume guard (no Ollama contact)."""
from __future__ import annotations

import json

import pytest

from evals.runner import RunRecord
from scripts import run_part1


def _fake_git(*args: str) -> str:
    if args == ("rev-parse", "HEAD"):
        return "abc123"
    if args == ("status", "--porcelain", "--", "agent", "env", "evals"):
        return ""  # clean tree
    raise AssertionError(f"unexpected git invocation: {args}")


class _FakeOllamaLLM:
    """Stands in for OllamaLLM: no HTTP, no Ollama contact, just the attributes
    run_part1 reads (name/digest/temperature/calls/hits/retries)."""

    def __init__(self, model, *, num_predict=512, cache_path=None, base_url=None, temperature=0.7):
        self.name = model
        self.digest = "fakedigest"
        self.temperature = temperature
        self.calls = 0
        self.hits = 0
        self.retries = 0


def _fake_run_record(case_id: str, variant: str, trial: int) -> RunRecord:
    return RunRecord(
        case_id=case_id,
        slice="happy",
        risk="low",
        tags=[],
        variant=variant,
        trial=trial,
        seed=trial,
        node_sequence=["classify_request", "respond"],
        tool_calls=[],
        refunds=[],
        final_message="ok",
        mutations_fired=[],
        crashed=None,
        grading_error=None,
        end_state_pass=True,
        end_state_detail="ok",
        constraints_pass=True,
        constraints_detail="ok",
        mode_pass={"strict": True, "unordered": True, "subset": True, "superset": True},
        string_pass=True,
        judge_score=5,
        judge_rationale="fine",
        answer_pass=True,
        elapsed_s=0.01,
    )


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


def test_metadata_written_before_loop_survives_an_interrupted_run(tmp_path, monkeypatch):
    """metadata.json must exist (with provenance) even if the run loop raises partway
    through — the scenario a killed process leaves behind."""
    monkeypatch.setattr(run_part1, "_git", _fake_git)
    monkeypatch.setattr(run_part1, "OllamaLLM", _FakeOllamaLLM)

    calls = {"n": 0}

    def _fake_run_case(case, variant, trial, llm, judge):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("simulated interruption")
        return _fake_run_record(case.id, variant, trial)

    monkeypatch.setattr(run_part1, "run_case", _fake_run_case)

    out = tmp_path / "out"

    with pytest.raises(RuntimeError, match="simulated interruption"):
        run_part1.main(["--out", str(out), "--ids", "H01,F01", "--k", "1"])

    meta_path = out / "metadata.json"
    assert meta_path.exists(), "metadata.json must be written before the loop, not only after it"
    meta = json.loads(meta_path.read_text())
    assert meta["git_commit"] == "abc123"
    assert meta["policy_model"]["name"] == run_part1.POLICY_MODEL
    assert meta["judge_model"]["name"] == run_part1.JUDGE_MODEL
    assert meta["k"] == 1
    assert meta["n_cases"] == 2
    assert "started_at" in meta
    # The loop was interrupted after the first row, so the end-of-loop fields must be absent.
    assert "finished_at" not in meta
    assert "llm_calls" not in meta
    # And the one row that did complete before the interruption was actually written.
    runs = (out / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    assert len(runs) == 1


def test_resume_preserves_started_at_across_an_interrupted_then_resumed_run(tmp_path, monkeypatch):
    monkeypatch.setattr(run_part1, "_git", _fake_git)
    monkeypatch.setattr(run_part1, "OllamaLLM", _FakeOllamaLLM)

    calls = {"n": 0}

    def _fake_run_case_fails_second(case, variant, trial, llm, judge):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("simulated interruption")
        return _fake_run_record(case.id, variant, trial)

    monkeypatch.setattr(run_part1, "run_case", _fake_run_case_fails_second)
    out = tmp_path / "out"
    with pytest.raises(RuntimeError):
        run_part1.main(["--out", str(out), "--ids", "H01,F01", "--k", "1"])
    first_started_at = json.loads((out / "metadata.json").read_text())["started_at"]

    def _fake_run_case_succeeds(case, variant, trial, llm, judge):
        return _fake_run_record(case.id, variant, trial)

    monkeypatch.setattr(run_part1, "run_case", _fake_run_case_succeeds)
    run_part1.main(["--out", str(out), "--ids", "H01,F01", "--k", "1"])

    meta = json.loads((out / "metadata.json").read_text())
    assert meta["started_at"] == first_started_at
    assert "finished_at" in meta


def test_resume_refuses_when_runs_exist_but_metadata_is_missing(tmp_path, monkeypatch):
    monkeypatch.setattr(run_part1, "_git", _fake_git)

    out = tmp_path / "out"
    out.mkdir()
    (out / "runs.jsonl").write_text('{"case_id": "H01", "variant": "baseline", "trial": 0}\n', encoding="utf-8")

    def _boom(*_args, **_kwargs):
        raise AssertionError("OllamaLLM must not be constructed once the resume guard refuses")

    monkeypatch.setattr(run_part1, "OllamaLLM", _boom)

    with pytest.raises(SystemExit) as excinfo:
        run_part1.main(["--out", str(out)])

    message = str(excinfo.value)
    assert "metadata.json" in message
    assert str(out) in message
    assert "new --out" in message


def test_resume_allows_a_fresh_out_with_an_empty_runs_jsonl(tmp_path, monkeypatch):
    """An empty runs.jsonl (e.g. left by a process killed before writing any row) has no
    rows, so the missing-metadata guard must not fire for it."""
    monkeypatch.setattr(run_part1, "_git", _fake_git)
    monkeypatch.setattr(run_part1, "OllamaLLM", _FakeOllamaLLM)
    monkeypatch.setattr(
        run_part1, "run_case", lambda case, variant, trial, llm, judge: _fake_run_record(case.id, variant, trial)
    )

    out = tmp_path / "out"
    out.mkdir()
    (out / "runs.jsonl").write_text("", encoding="utf-8")

    result = run_part1.main(["--out", str(out), "--ids", "H01", "--k", "1"])

    assert result == 0
    assert (out / "metadata.json").exists()


def test_policy_model_flag_overrides_the_default(tmp_path, monkeypatch):
    """--policy-model must actually be used at runtime (constructing OllamaLLM and recorded
    in metadata.json), not just accepted and ignored."""
    monkeypatch.setattr(run_part1, "_git", _fake_git)
    monkeypatch.setattr(run_part1, "OllamaLLM", _FakeOllamaLLM)
    monkeypatch.setattr(
        run_part1, "run_case", lambda case, variant, trial, llm, judge: _fake_run_record(case.id, variant, trial)
    )

    out = tmp_path / "out"

    result = run_part1.main(
        ["--out", str(out), "--policy-model", "qwen3:4b", "--ids", "H01", "--k", "1"]
    )

    assert result == 0
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["policy_model"]["name"] == "qwen3:4b"


def test_resume_guard_compares_against_the_policy_model_flag_not_the_constant(tmp_path, monkeypatch):
    """The resume guard must check args.policy_model, not the hardcoded POLICY_MODEL constant,
    so resuming a run made with an overridden --policy-model doesn't spuriously refuse."""
    monkeypatch.setattr(run_part1, "_git", _fake_git)
    monkeypatch.setattr(run_part1, "OllamaLLM", _FakeOllamaLLM)
    monkeypatch.setattr(
        run_part1, "run_case", lambda case, variant, trial, llm, judge: _fake_run_record(case.id, variant, trial)
    )

    out = tmp_path / "out"
    out.mkdir()
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "git_commit": "abc123",
                "policy_model": {"name": "qwen3:4b"},
                "judge_model": {"name": run_part1.JUDGE_MODEL},
                "started_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    (out / "runs.jsonl").write_text("", encoding="utf-8")

    result = run_part1.main(
        ["--out", str(out), "--policy-model", "qwen3:4b", "--ids", "H01", "--k", "1"]
    )

    assert result == 0


def test_resume_still_refuses_when_policy_model_flag_mismatches_recorded_model(tmp_path, monkeypatch):
    monkeypatch.setattr(run_part1, "_git", _fake_git)

    out = tmp_path / "out"
    out.mkdir()
    (out / "metadata.json").write_text(
        json.dumps(
            {
                "git_commit": "abc123",
                "policy_model": {"name": "qwen3:4b"},
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
        run_part1.main(["--out", str(out), "--policy-model", "gemma3:4b"])

    message = str(excinfo.value)
    assert "qwen3:4b" in message
    assert str(out) in message
    assert "new --out" in message
