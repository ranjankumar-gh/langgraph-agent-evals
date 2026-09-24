"""Measured Part 2 run: every (case, trial) group, then the summary.

A group is the baseline plus a full rerun, a paired fork and a naive fork for each change.
The run is resumable per group: a group's rows are written together in one write, and a
(case, trial) is complete only once it holds every row of the group (1 + 3 * len(changes)).
A crash mid-write can leave a torn last line or a partial group behind; on resume those are
dropped and re-run rather than trusted. The provenance guard is the same one run_part1
uses.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import sys
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from agent.llm import OllamaLLM
from evals.report_part2 import ALL_CHANGES, render_markdown_part2, summarize_part2
from evals.runner_part2 import ArmLLMs, namespaces_for, run_group
from evals.schema import load_cases
from scripts.provenance import guard
from scripts.run_part1 import JUDGE_MODEL, POLICY_MODEL, _git


def _load_done(runs_path: Path, per_group: int) -> set[tuple[str, int]]:
    """Return the (case_id, trial) groups that are complete (exactly `per_group` rows).

    Reads runs.jsonl line by line: a line that fails to parse is dropped as torn (this can
    only happen on a crash mid-write, and only to the last line). Any group left with fewer
    than `per_group` rows is partial - also dropped, so it is re-run whole rather than
    resumed from a state whose provenance is unknown. If anything was dropped, the file is
    rewritten with only the surviving complete groups before it is reopened for append.
    """
    if not runs_path.exists():
        return set()
    by_group: dict[tuple[str, int], list[str]] = {}
    unparseable = 0
    for line in runs_path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            unparseable += 1
            continue
        by_group.setdefault((row["case_id"], row["trial"]), []).append(line)

    done: set[tuple[str, int]] = set()
    kept_lines: list[str] = []
    partial = 0
    for key, group_lines in by_group.items():
        if len(group_lines) == per_group:
            done.add(key)
            kept_lines.extend(group_lines)
        else:
            partial += 1

    if partial or unparseable:
        # Atomic rewrite: back up the original, write the kept lines to a temp file in the same
        # directory, then rename it onto runs.jsonl. A crash mid-rewrite leaves either the
        # untouched original or a complete temp file behind, never a half-written runs.jsonl -
        # and the .bak is kept so a rewrite that dropped something it shouldn't have is
        # recoverable.
        bak_path = runs_path.with_name(runs_path.name + ".bak")
        shutil.copyfile(runs_path, bak_path)
        tmp_path = runs_path.with_name(runs_path.name + ".tmp")
        tmp_path.write_text("".join(line + "\n" for line in kept_lines), encoding="utf-8")
        os.replace(tmp_path, runs_path)
        print(
            f"dropped {partial} partial group(s) and {unparseable} unparseable line(s) from "
            f"runs.jsonl; they will be re-run",
            flush=True,
        )
    return done


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--changes", default=",".join(ALL_CHANGES))
    parser.add_argument("--cases", default="evals/cases")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", default=None, help="comma-separated case ids, for smoke runs")
    parser.add_argument("--out", default="results/part-2")
    parser.add_argument("--policy-model", default=POLICY_MODEL)
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args(argv)

    changes = args.changes.split(",")
    unknown = [c for c in changes if c not in ALL_CHANGES]
    if unknown:
        sys.exit(f"unknown change(s) {unknown}; expected a subset of {list(ALL_CHANGES)}")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    meta_path = out / "metadata.json"

    if not args.summarize_only:
        commit = _git("rev-parse", "HEAD")
        dirty = bool(_git("status", "--porcelain", "--", "agent", "env", "evals"))
        previous = guard(out, commit=commit, dirty=dirty, allow_dirty=args.allow_dirty,
                         policy_model=args.policy_model, judge_model=args.judge_model, changes=changes)
        cases = load_cases(Path(args.cases))
        if args.ids:
            wanted = set(args.ids.split(","))
            cases = [c for c in cases if c.id in wanted]
        cases = cases[: args.limit]
        # F1: every non-baseline namespace is scoped to this --out at this commit, so a
        # different --out (e.g. a smoke run) or a different commit (a re-run after a fix)
        # never replays this run's draws, and resuming the SAME --out at the SAME commit
        # reuses the same tag and correctly replays its own prior draws.
        tag = f"{out.name}-{commit[:7]}"
        llms = {
            ns: ArmLLMs(OllamaLLM(args.policy_model, num_predict=400, namespace=ns),
                        OllamaLLM(args.judge_model, num_predict=200, namespace=ns))
            for ns in namespaces_for(changes, tag)
        }
        any_llms = next(iter(llms.values()))
        started_at = previous["started_at"] if previous else datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta = {
            "git_commit": commit,
            "dirty": dirty,
            "started_at": started_at,
            "python": platform.python_version(),
            "langgraph": version("langgraph"),
            "langchain_ollama": version("langchain-ollama"),
            "policy_model": {"name": any_llms.policy.name, "digest": any_llms.policy.digest,
                             "temperature": any_llms.policy.temperature, "hosted": any_llms.policy.name.endswith("-cloud")},
            "judge_model": {"name": any_llms.judge.name, "digest": any_llms.judge.digest,
                            "temperature": any_llms.judge.temperature, "hosted": any_llms.judge.name.endswith("-cloud")},
            "k": args.k,
            "changes": changes,
            "namespaces": list(llms),
            "n_cases": len(cases),
            "run_tag": tag,
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        done = _load_done(runs_path, 1 + 3 * len(changes))
        with runs_path.open("a", encoding="utf-8") as fh:
            for trial in range(args.k):
                for case in cases:
                    if (case.id, trial) in done:
                        continue
                    try:
                        rows = run_group(case, trial, changes, llms, tag=tag)
                    except Exception as exc:
                        # M3: a group-level crash (not caught inside run_group itself) must not
                        # abort the whole measured run. No rows are written for this group, so
                        # it is retried whole on resume.
                        print(f"GROUP-ERROR {case.id} t{trial}: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
                        continue
                    fh.write("".join(json.dumps(r) + "\n" for r in rows))  # one write per group
                    fh.flush()
                    crashed = sum(bool(r.get("crashed")) for r in rows)
                    print(f"[t{trial}] {case.id:4} {len(rows)} rows{f', {crashed} crashed' if crashed else ''}", flush=True)
        meta["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta["llm_usage"] = {ns: {"policy": a.policy.usage(), "judge": a.judge.usage()} for ns, a in llms.items()}
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    rows = [json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines()]
    summary = summarize_part2(rows)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    (out / "summary.md").write_text(render_markdown_part2(summary, metadata), encoding="utf-8")
    print(f"{len(rows)} rows summarised to {out / 'summary.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
