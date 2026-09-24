"""Measured Part 2 run: every (case, trial) group, then the summary.

A group is the baseline plus a full rerun, a paired fork and a naive fork for each change.
The run is resumable per group: a group's rows are written together in one write, and a
(case, trial) with a baseline row is complete. The provenance guard is the same one
run_part1 uses.
"""
from __future__ import annotations

import argparse
import json
import platform
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
                         policy_model=args.policy_model, judge_model=args.judge_model)
        cases = load_cases(Path(args.cases))
        if args.ids:
            wanted = set(args.ids.split(","))
            cases = [c for c in cases if c.id in wanted]
        cases = cases[: args.limit]
        llms = {
            ns: ArmLLMs(OllamaLLM(args.policy_model, num_predict=400, namespace=ns),
                        OllamaLLM(args.judge_model, num_predict=200, namespace=ns))
            for ns in namespaces_for(changes)
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
        }
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        done: set[tuple[str, int]] = set()
        if runs_path.exists():
            for line in runs_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                if row["arm"] == "baseline":
                    done.add((row["case_id"], row["trial"]))
        with runs_path.open("a", encoding="utf-8") as fh:
            for trial in range(args.k):
                for case in cases:
                    if (case.id, trial) in done:
                        continue
                    rows = run_group(case, trial, changes, llms)
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
