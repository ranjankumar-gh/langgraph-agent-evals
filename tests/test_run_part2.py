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

    def fake_group(case, trial, changes, llms, tag=""):
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
    assert meta["run_tag"] == "p2-abc123"
    assert meta["namespaces"] == [
        "", "p2-fork-D@p2-abc123", "p2-fork-baseline@p2-abc123", "p2-full-D@p2-abc123", "p2-full-baseline@p2-abc123",
    ]


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


def test_run_part2_reruns_only_partial_groups_and_drops_torn_lines(tmp_path, monkeypatch, capsys):
    groups = _setup(monkeypatch)
    out = tmp_path / "p2"
    out.mkdir()
    changes = list(run_part2.ALL_CHANGES)  # ["baseline", "D", "E"]
    per_group = 1 + 3 * len(changes)

    def _group_rows(case_id, trial):
        rows = [{"arm": "baseline", "change": "baseline", "case_id": case_id, "trial": trial}]
        rows += [
            {"arm": arm, "change": ch, "case_id": case_id, "trial": trial}
            for ch in changes for arm in ("full", "fork", "fork_naive")
        ]
        return rows

    complete_group = _group_rows("H01", 0)  # 10 rows, untouched
    partial_group = _group_rows("I01", 0)[:1]  # baseline row only - a crash mid-write

    lines = [json.dumps(r) for r in complete_group] + [json.dumps(r) for r in partial_group]
    lines.append('{"arm": "full", "change": "D", "case_id": "I01", "trial": 0')  # torn last line
    (out / "runs.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "metadata.json").write_text(
        json.dumps({
            "git_commit": "abc123",
            "started_at": "2026-01-01T00:00:00+00:00",
            "policy_model": {"name": run_part2.POLICY_MODEL},
            "judge_model": {"name": run_part2.JUDGE_MODEL},
        }),
        encoding="utf-8",
    )

    args = ["--ids", "H01,I01", "--k", "1", "--out", str(out)]
    assert run_part2.main(args) == 0

    # Only the partial group (I01, trial 0) was re-run; the complete H01 group was left alone.
    assert groups == [("I01", 0)]

    notice = capsys.readouterr().out
    assert "dropped 1 partial group(s) and 1 unparseable line(s) from runs.jsonl; they will be re-run" in notice

    # runs.jsonl now parses cleanly and holds only complete groups.
    lines_out = (out / "runs.jsonl").read_text(encoding="utf-8").splitlines()
    rows = [json.loads(line) for line in lines_out]  # raises if any line is still torn
    assert len(rows) == 2 * per_group
    counts: dict[tuple[str, int], int] = {}
    for row in rows:
        key = (row["case_id"], row["trial"])
        counts[key] = counts.get(key, 0) + 1
    assert counts == {("H01", 0): per_group, ("I01", 0): per_group}

    # F2: the atomic rewrite leaves a .bak of the pre-rewrite runs.jsonl behind.
    assert (out / "runs.jsonl.bak").exists()
    assert not (out / "runs.jsonl.tmp").exists()


def test_run_part2_refuses_a_different_changes_and_leaves_runs_jsonl_untouched(tmp_path, monkeypatch):
    _setup(monkeypatch)
    out = tmp_path / "p2"
    run_part2.main(["--ids", "H01", "--k", "1", "--out", str(out), "--changes", "baseline,D"])
    before = (out / "runs.jsonl").read_bytes()

    _setup(monkeypatch)
    with pytest.raises(SystemExit) as excinfo:
        run_part2.main(["--ids", "H01", "--k", "1", "--out", str(out), "--changes", "baseline,E"])
    assert "['baseline', 'D']" in str(excinfo.value) or "baseline" in str(excinfo.value)

    after = (out / "runs.jsonl").read_bytes()
    assert after == before  # byte-identical: the refusal happened before any write


def test_run_part2_group_error_is_logged_and_the_run_continues(tmp_path, monkeypatch, capsys):
    groups = _setup(monkeypatch)
    real_group = run_part2.run_group

    def flaky_group(case, trial, changes, llms, tag=""):
        if case.id == "H01":
            raise RuntimeError("boom")
        return real_group(case, trial, changes, llms, tag=tag)

    monkeypatch.setattr(run_part2, "run_group", flaky_group)
    out = tmp_path / "p2"
    assert run_part2.main(["--ids", "H01,I01", "--k", "1", "--out", str(out)]) == 0

    err = capsys.readouterr().err
    assert "GROUP-ERROR H01 t0: RuntimeError: boom" in err

    rows = [json.loads(line) for line in (out / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
    case_ids = {r["case_id"] for r in rows}
    assert "H01" not in case_ids  # the failing group wrote nothing
    assert "I01" in case_ids
