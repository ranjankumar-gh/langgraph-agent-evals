"""Upstream state at the fork point, per (case, trial), for the part-2 run.

Offline analysis: reads results/<run>/runs.jsonl, results/<run>/metadata.json and the local
record/replay cache (.cache/llm.sqlite). It calls no model and makes no network request.

The only model call upstream of the fork point is classify_request, which writes `intent` and
`order_id` into state. Every node after it, up to the fork point, is a deterministic tool call
given those two fields. So the state at the fork point is fixed by the classifier's output, and
comparing a full rerun's classification with the baseline's tells you whether the two runs
reached the fork point in the same state.

runs.jsonl does not record the classification, so this script recovers it from the cache: it
rebuilds the classifier call's cache key for each arm's namespace (the same key OllamaLLM builds
at run time) and reads the stored reply. Only arms that run classify_request are covered: the
baseline (un-namespaced, Part 1's draws) and each change's full rerun. Fork arms start after it.

It writes upstream_state.jsonl (one row per forkable pair and change) and prints a summary,
including the Fork Precision Ceiling estimate: the share of the full rerun's squared delta
deviation that sits on pairs whose upstream state differed from the baseline's.

    uv run python -m scripts.upstream_state --runs results/part-2
"""
from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace

from agent.llm import OllamaLLM
from agent.prompts import CLASSIFY_SYSTEM, Classification
from evals.runner_part2 import namespace
from evals.schema import load_cases

POLICY_NUM_PREDICT = 400  # scripts/run_part2.py builds the policy LLM with num_predict=400
CHANGES = ("baseline", "D")  # E shares D's namespaces


def classifier_key(meta: dict, ns: str, request: str, trial: int) -> str:
    """The cache key OllamaLLM._structured_hosted builds for classify_request."""
    policy = meta["policy_model"]
    fake = SimpleNamespace(name=policy["name"], digest=policy["digest"],
                           temperature=policy["temperature"], namespace=ns)
    return OllamaLLM._key(fake, "structured", CLASSIFY_SYSTEM, request,
                          Classification.model_json_schema(), trial, reasoning=True,
                          num_predict=max(POLICY_NUM_PREDICT, 2048), method="prompt_json")


def three_artifact(row: dict) -> int:
    return int(bool(row["end_state_pass"] and row["constraints_pass"] and row["answer_pass"]))


def ceiling_share(deltas: list[tuple[bool, float]]) -> float | None:
    """Share of the sum of squared deviations from the mean that sits on mismatched pairs."""
    mean = sum(d for _, d in deltas) / len(deltas)
    total = sum((d - mean) ** 2 for _, d in deltas)
    if total == 0:
        return None
    return sum((d - mean) ** 2 for mismatch, d in deltas if mismatch) / total


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", default="results/part-2")
    parser.add_argument("--cases", default="evals/cases")
    parser.add_argument("--cache", default=".cache/llm.sqlite")
    args = parser.parse_args()

    out = Path(args.runs)
    meta = json.loads((out / "metadata.json").read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in (out / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    cases = {c.id: c for c in load_cases(Path(args.cases))}
    db = sqlite3.connect(f"file:{args.cache}?mode=ro", uri=True)

    def classified(ns: str, case_id: str, trial: int) -> dict | None:
        key = classifier_key(meta, ns, cases[case_id].request, trial)
        hit = db.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        if hit is None:
            return None
        value = Classification.model_validate_json(hit[0])
        return {"intent": value.intent, "order_id": value.order_id}

    idx = {(r["arm"], r["change"], r["case_id"], r["trial"]): r for r in rows}
    base = {(r["case_id"], r["trial"]): r for r in rows if r["arm"] == "baseline"}
    forkable = sorted(k for k, r in base.items() if "compute_refund" in r["node_sequence"])

    table, lines = [], []
    for change in CHANGES:
        ns = namespace("full", change, meta["run_tag"])
        deltas = {"three_artifact": [], "judge_score": []}
        missing = mismatched = 0
        for case_id, trial in forkable:
            b_state = classified("", case_id, trial)
            f_state = classified(ns, case_id, trial)
            if b_state is None or f_state is None:
                missing += 1
                continue
            mismatch = b_state != f_state
            mismatched += mismatch
            b, f = base[(case_id, trial)], idx[("full", change, case_id, trial)]
            row = {"change": change, "case_id": case_id, "trial": trial, "baseline": b_state,
                   "full": f_state, "mismatch": mismatch,
                   "delta_three_artifact": None, "delta_judge_score": None}
            if not (b.get("crashed") or f.get("crashed")) and b["judge_score"] is not None and f["judge_score"] is not None:
                row["delta_three_artifact"] = three_artifact(f) - three_artifact(b)
                row["delta_judge_score"] = f["judge_score"] - b["judge_score"]
                deltas["three_artifact"].append((mismatch, row["delta_three_artifact"]))
                deltas["judge_score"].append((mismatch, row["delta_judge_score"]))
            table.append(row)
        ids = [f"{r['case_id']}/t{r['trial']}" for r in table if r["change"] == change and r["mismatch"]]
        lines.append(f"{change}: {len(forkable)} forkable pairs, {missing} without a cached classification, "
                     f"{mismatched} with a different upstream state ({', '.join(ids) or 'none'})")
        for score, ds in deltas.items():
            share = ceiling_share(ds)
            shown = "n/a (no variance)" if share is None else f"{share:.4%}"
            lines.append(f"  ceiling estimate, {score}: n={len(ds)}, share on mismatched pairs {shown}")

    (out / "upstream_state.jsonl").write_text("".join(json.dumps(r) + "\n" for r in table), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
