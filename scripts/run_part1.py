"""Measured Part 1 run: every case x variant x trial, then the summary.

Resumable: re-running appends only missing (case, variant, trial) rows. Refuses to mix
rows from two commits, and refuses to measure uncommitted agent/env/evals code unless
--allow-dirty is passed (smoke runs only).
"""
from __future__ import annotations

import argparse
import json
import platform
import subprocess
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from agent.graph import VARIANTS
from agent.llm import OllamaLLM
from evals.report import render_markdown, summarize, write_transcripts
from evals.runner import run_case
from evals.schema import load_cases

POLICY_MODEL = "qwen3:4b"
JUDGE_MODEL = "gpt-oss:20b-cloud"


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], capture_output=True, text=True, check=True).stdout.strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--k", type=int, default=3)
    parser.add_argument("--variants", default=",".join(VARIANTS))
    parser.add_argument("--cases", default="evals/cases")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--ids", default=None, help="comma-separated case ids, for smoke runs")
    parser.add_argument("--out", default="results/part-1")
    parser.add_argument("--judge-model", default=JUDGE_MODEL)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--summarize-only", action="store_true")
    args = parser.parse_args(argv)

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    runs_path = out / "runs.jsonl"
    meta_path = out / "metadata.json"

    if not args.summarize_only:
        commit = _git("rev-parse", "HEAD")
        dirty = bool(_git("status", "--porcelain", "--", "agent", "env", "evals"))
        if dirty and not args.allow_dirty:
            sys.exit("agent/, env/ or evals/ has uncommitted changes; commit before a measured run")
        if meta_path.exists():
            previous = json.loads(meta_path.read_text())
            if previous["git_commit"] != commit:
                sys.exit(f"{out} holds runs from {previous['git_commit']}; use a new --out or delete it")
            if previous["policy_model"]["name"] != POLICY_MODEL:
                sys.exit(
                    f"{out} holds runs graded by policy model {previous['policy_model']['name']!r}; "
                    f"use a new --out or delete it"
                )
            if previous["judge_model"]["name"] != args.judge_model:
                sys.exit(
                    f"{out} holds runs graded by judge model {previous['judge_model']['name']!r}; "
                    f"use a new --out or delete it"
                )
        variants = args.variants.split(",")
        cases = load_cases(Path(args.cases))
        if args.ids:
            wanted = set(args.ids.split(","))
            cases = [c for c in cases if c.id in wanted]
        cases = cases[: args.limit]
        llm = OllamaLLM(POLICY_MODEL, num_predict=400)
        judge = OllamaLLM(args.judge_model, num_predict=200)
        meta = {
            "git_commit": commit,
            "dirty": dirty,
            "started_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "python": platform.python_version(),
            "langgraph": version("langgraph"),
            "langchain_ollama": version("langchain-ollama"),
            "policy_model": {
                "name": llm.name, "digest": llm.digest, "temperature": llm.temperature,
                "hosted": llm.name.endswith("-cloud"),
            },
            "judge_model": {
                "name": judge.name, "digest": judge.digest, "temperature": judge.temperature,
                "hosted": judge.name.endswith("-cloud"),
            },
            "k": args.k,
            "variants": variants,
            "n_cases": len(cases),
        }
        done: set[tuple[str, str, int]] = set()
        if runs_path.exists():
            for line in runs_path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                done.add((row["case_id"], row["variant"], row["trial"]))
        with runs_path.open("a", encoding="utf-8") as fh:
            for trial in range(args.k):
                for case in cases:
                    for variant in variants:
                        if (case.id, variant, trial) in done:
                            continue
                        rec = run_case(case, variant, trial, llm, judge)
                        fh.write(json.dumps(asdict(rec)) + "\n")
                        fh.flush()
                        print(
                            f"[t{trial}] {case.id:4} {variant:17} answer={rec.answer_pass!s:5} "
                            f"end={rec.end_state_pass!s:5} traj={rec.constraints_pass!s:5} "
                            f"{'CRASH ' + rec.crashed if rec.crashed else ''}"
                            f"{'GRADING-ERROR ' + rec.grading_error if rec.grading_error else ''} {rec.elapsed_s:.1f}s",
                            flush=True,
                        )
        meta["finished_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        meta["llm_calls"] = {"policy": llm.calls, "policy_cache_hits": llm.hits,
                             "judge": judge.calls, "judge_cache_hits": judge.hits}
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    runs = [json.loads(line) for line in runs_path.read_text(encoding="utf-8").splitlines()]
    summary = summarize(runs)
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    metadata = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    (out / "summary.md").write_text(render_markdown(summary, metadata), encoding="utf-8")
    written = write_transcripts(runs, out / "transcripts")
    print(f"{len(runs)} runs summarised; {written} transcripts written to {out / 'transcripts'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
