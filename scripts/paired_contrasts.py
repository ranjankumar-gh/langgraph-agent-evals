"""Paired contrasts for the part-2 run that summary.md does not report.

Offline analysis of results/<run>/runs.jsonl: it calls no model and makes no network request.
It uses the same case-clustered bootstrap (seed, resample count, percentile method) as
evals/report_part2.py, so every interval is comparable with summary.md.

Reported:
- the fork-vs-full variance ratio over the 96 forked pairs (as in summary.md) and over all 165
  (case, trial) groups, where the 69 inherited pairs carry the baseline verdict (delta 0)
- D's paired deltas and ratios with the H03/t1 pair excluded: an Ollama Cloud 429 timeout that
  crashed in both D arms and was graded as a fail with judge score 1
- D minus the no-op fork and the no-op fork minus the no-op full rerun, pair by pair
- how the no-op and D fork judge-score lower bounds move across bootstrap seeds 0-19
- verdict flips against the baseline, the baseline judge-score distribution, path equality up
  to the fork point and identical replies, on the no-op control

    uv run python -m scripts.paired_contrasts --runs results/part-2
"""
from __future__ import annotations

import argparse
import json
import random
import statistics
from collections import Counter
from pathlib import Path

from evals.report import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, _percentile
from evals.report_part2 import _index, _score, forkable_pairs

CRASH_PAIR = ("H03", 1)
SCORES = ("three_artifact", "judge_score")


def _clusters(units: list[tuple[str, float]]) -> list[list[float]]:
    per_case: dict[str, list[float]] = {}
    for case_id, value in units:
        per_case.setdefault(case_id, []).append(value)
    return [per_case[c] for c in sorted(per_case)]


def mean_ci(units: list[tuple[str, float]], seed: int = BOOTSTRAP_SEED) -> tuple[float, float, float]:
    clusters = _clusters(units)
    rng = random.Random(seed)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        values = [v for cluster in rng.choices(clusters, k=len(clusters)) for v in cluster]
        means.append(sum(values) / len(values))
    means.sort()
    return (sum(v for _, v in units) / len(units), _percentile(means, 0.025), _percentile(means, 0.975))


def variance_ratio(fork: dict, full: dict) -> tuple[float, float, float, int]:
    """var(fork diff) / var(full diff), resampling cases once for both arms (as report_part2)."""
    keys = sorted(fork)
    cases = sorted({c for c, _ in keys})
    by_case = {c: [k for k in keys if k[0] == c] for c in cases}
    point = statistics.variance([fork[k] for k in keys]) / statistics.variance([full[k] for k in keys])
    rng = random.Random(BOOTSTRAP_SEED)
    ratios, skipped = [], 0
    for _ in range(BOOTSTRAP_RESAMPLES):
        draw = [k for c in rng.choices(cases, k=len(cases)) for k in by_case[c]]
        full_v = statistics.variance([full[k] for k in draw])
        if full_v == 0:
            skipped += 1
            continue
        ratios.append(statistics.variance([fork[k] for k in draw]) / full_v)
    ratios.sort()
    return point, _percentile(ratios, 0.025), _percentile(ratios, 0.975), skipped


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--runs", default="results/part-2")
    args = parser.parse_args()
    out = Path(args.runs)
    rows = [json.loads(line) for line in (out / "runs.jsonl").read_text(encoding="utf-8").splitlines() if line]
    idx = _index(rows)
    groups = sorted((r["case_id"], r["trial"]) for r in rows if r["arm"] == "baseline")

    def diff(arm: str, change: str, key: tuple[str, int], score: str) -> float:
        return _score(idx[(arm, change, *key)], score) - _score(idx[("baseline", "baseline", *key)], score)

    def fmt(t) -> str:
        return f"{t[0]:+.4f} ({t[1]:.4f} to {t[2]:.4f})"

    lines = ["# Paired contrasts (part-2 run)", "",
             "Generated offline by `uv run python -m scripts.paired_contrasts --runs results/part-2` "
             "(no model calls). Case-clustered bootstrap, seed "
             f"{BOOTSTRAP_SEED}, {BOOTSTRAP_RESAMPLES} resamples, as in summary.md.", ""]

    lines += ["## Variance ratio, var(fork diff) / var(full diff)", "",
              "Over all 165 groups, the 69 inherited pairs have a fork-arm delta of exactly 0.", "",
              "| Change | Score | 96 forked pairs | All 165 groups |", "|---|---|---|---|"]
    for change in ("baseline", "D"):
        forked = forkable_pairs(rows, change)
        for score in SCORES:
            cells = []
            for keys in (forked, groups):
                r = variance_ratio({k: diff("fork", change, k, score) for k in keys},
                                   {k: diff("full", change, k, score) for k in keys})
                cells.append(f"{r[0]:.4f} ({r[1]:.4f} to {r[2]:.4f}), {r[3]} skipped")
            lines.append(f"| {change} | {score} | {cells[0]} | {cells[1]} |")

    forked = forkable_pairs(rows, "D")
    no_crash = [k for k in forked if k != CRASH_PAIR]
    lines += ["", f"## D with {CRASH_PAIR[0]}/t{CRASH_PAIR[1]} excluded (429 timeout in both D arms)", "",
              "| Score | Full delta | Fork delta | Variance ratio |", "|---|---|---|---|"]
    for score in SCORES:
        full = mean_ci([(c, diff("full", "D", (c, t), score)) for c, t in no_crash])
        fork = mean_ci([(c, diff("fork", "D", (c, t), score)) for c, t in no_crash])
        r = variance_ratio({k: diff("fork", "D", k, score) for k in no_crash},
                           {k: diff("full", "D", k, score) for k in no_crash})
        lines.append(f"| {score} | {fmt(full)} | {fmt(fork)} | {r[0]:.4f} ({r[1]:.4f} to {r[2]:.4f}) |")
    kept = len(no_crash)
    lines.append("")
    lines.append(f"{kept} pairs kept of {len(forked)}.")

    noop = forkable_pairs(rows, "baseline")
    lines += ["", "## Pair-by-pair contrasts on the judge score", ""]
    for label, keys in (("all forked pairs", noop), ("H03/t1 excluded", [k for k in noop if k != CRASH_PAIR])):
        d_minus = mean_ci([(c, diff("fork", "D", (c, t), "judge_score") - diff("fork", "baseline", (c, t), "judge_score"))
                           for c, t in keys])
        lines.append(f"- D fork minus no-op fork, {label}: {fmt(d_minus)}")
    gap = mean_ci([(c, diff("fork", "baseline", (c, t), "judge_score") - diff("full", "baseline", (c, t), "judge_score"))
                   for c, t in noop])
    lines.append(f"- no-op fork minus no-op full: {fmt(gap)}")

    lines += ["", "## Judge-score lower bound across bootstrap seeds 0-19", ""]
    for label, change, keys in (("no-op fork", "baseline", noop), ("D fork", "D", forked),
                                ("D fork, H03/t1 excluded", "D", no_crash)):
        lows = [mean_ci([(c, diff("fork", change, (c, t), "judge_score")) for c, t in keys], seed=s)[1]
                for s in range(20)]
        lines.append(f"- {label}: lower bound <= 0 on {sum(1 for x in lows if x <= 0)} of 20 seeds "
                     f"(range {min(lows):.4f} to {max(lows):.4f})")

    lines += ["", "## No-op control, forked pairs", ""]
    base_scores = Counter(idx[("baseline", "baseline", *k)]["judge_score"] for k in noop)
    lines.append(f"- baseline judge scores: {dict(sorted(base_scores.items()))}")
    for arm in ("full", "fork"):
        flips = Counter()
        for k in noop:
            b, a = idx[("baseline", "baseline", *k)], idx[(arm, "baseline", *k)]
            d = _score(a, "three_artifact") - _score(b, "three_artifact")
            flips["three_artifact up" if d > 0 else "three_artifact down" if d < 0 else "same"] += 1
            flips["answer flipped"] += a["answer_pass"] != b["answer_pass"]
            flips["end_state flipped"] += a["end_state_pass"] != b["end_state_pass"]
            flips["judge score changed"] += a["judge_score"] != b["judge_score"]
            flips["reply identical"] += a["final_message"] == b["final_message"]
            prefix = b["node_sequence"][:b["node_sequence"].index("compute_refund")]
            flips["path to fork point matched"] += a["node_sequence"][:len(prefix)] == prefix
        lines.append(f"- {arm}: " + ", ".join(f"{k} {v}" for k, v in sorted(flips.items()) if k != "same"))

    (out / "paired_contrasts.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
