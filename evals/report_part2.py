"""Turns a Part 2 run log into the fork-evaluation numbers.

- Cost: wall-clock, LLM calls and tokens for full reruns vs paired forks, over the
  (case, trial) pairs the change can be forked on. A row counts only when every LLM call in
  it went to the model and reported token usage (metered). Other rows are counted as
  excluded, never summed as zero.
- Paired delta: the change's score minus the baseline's for the same (case, trial), as a
  full rerun and as a paired fork, over the forkable pairs, with a case-clustered bootstrap
  interval. The interval's width is the variance comparison.
- Wrong verdicts: the naive fork vs the paired fork on the same (case, trial), per layer.
  Pairs are compared only when both forks made the same compute_refund decision. End state
  differs only through the world. Constraints differ through the carried tool log, which is
  part of the world snapshot. Answer can also differ by sampling, because the refund id in
  the reply facts differs. A pair whose decisions disagree, or where either row crashed, is
  excluded rather than counted either way.
- Routing change: the regressions a full rerun sees vs those the fork arm sees (inherited
  verdicts included), and which pairs the routing check flags as not forkable. A pair whose
  baseline crashed is excluded from the routing-flagged count: the fork's "baseline crashed"
  routing detail is not a routing failure.

Rows with a grading error are left out of every comparison they would enter.
"""
from __future__ import annotations

import random
import statistics

from agent.graph import CHANGES
from evals.report import BOOTSTRAP_RESAMPLES, BOOTSTRAP_SEED, _percentile, passes

ALL_CHANGES = ("baseline",) + CHANGES
SCORES = ("three_artifact", "judge_score")
LAYERS = ("end_state", "constraints", "answer", "three_artifact")


def _index(rows: list[dict]) -> dict:
    return {(r["arm"], r["change"], r["case_id"], r["trial"]): r for r in rows}


def _score(row: dict, score: str) -> float:
    return float(passes(row, "three_artifact")) if score == "three_artifact" else float(row["judge_score"])


def _verdict(row: dict, layer: str) -> bool:
    if row["crashed"]:
        return False
    if layer == "end_state":
        return row["end_state_pass"]
    if layer == "constraints":
        return row["constraints_pass"]
    if layer == "answer":
        return row["answer_pass"]
    return passes(row, "three_artifact")


def forkable_pairs(rows: list[dict], change: str) -> list[tuple[str, int]]:
    return sorted({(r["case_id"], r["trial"]) for r in rows
                   if r["arm"] == "fork" and r["change"] == change and not r["fork"]["inherited"]})


def metered(row: dict) -> bool:
    return all(row["cost"][who]["hits"] == 0 and row["cost"][who]["unmetered"] == 0 for who in ("policy", "judge"))


def cost_table(rows: list[dict], change: str) -> dict:
    idx = _index(rows)
    pairs = forkable_pairs(rows, change)
    out = {}
    for arm in ("full", "fork"):
        present = [idx[(arm, change, c, t)] for c, t in pairs if (arm, change, c, t) in idx]
        good = [r for r in present if metered(r)]
        walls = [r["elapsed_s"] for r in good]
        out[arm] = {
            "n": len(good),
            "excluded": len(present) - len(good),
            "wall_s_total": round(sum(walls), 1),
            "wall_s_median": round(statistics.median(walls), 2) if walls else None,
            "policy_calls": sum(r["cost"]["policy"]["calls"] for r in good),
            "judge_calls": sum(r["cost"]["judge"]["calls"] for r in good),
            "input_tokens": sum(r["cost"][w]["input_tokens"] for r in good for w in ("policy", "judge")),
            "output_tokens": sum(r["cost"][w]["output_tokens"] for r in good for w in ("policy", "judge")),
        }
    return out


def case_bootstrap_mean(units: list[tuple[str, float]]) -> tuple[float, float]:
    """Case-clustered percentile bootstrap 95% interval for the mean of per-run values."""
    if not units:
        return (0.0, 0.0)
    per_case: dict[str, list[float]] = {}
    for case_id, value in units:
        per_case.setdefault(case_id, []).append(value)
    clusters = [per_case[c] for c in sorted(per_case)]
    rng = random.Random(BOOTSTRAP_SEED)
    means = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        values = [v for cluster in rng.choices(clusters, k=len(clusters)) for v in cluster]
        means.append(sum(values) / len(values))
    means.sort()
    return (_percentile(means, 0.025), _percentile(means, 0.975))


def paired_delta(rows: list[dict], change: str, arm: str, score: str) -> dict:
    idx = _index(rows)
    units = []
    for c, t in forkable_pairs(rows, change):
        base, other = idx.get(("baseline", "baseline", c, t)), idx.get((arm, change, c, t))
        if base is None or other is None or base.get("grading_error") or other.get("grading_error"):
            continue
        units.append((c, _score(other, score) - _score(base, score)))
    if not units:
        return {"n": 0, "mean": None, "sd": None, "ci95_case": [0.0, 0.0], "width": 0.0}
    values = [v for _, v in units]
    low, high = case_bootstrap_mean(units)
    return {
        "n": len(values),
        "mean": round(sum(values) / len(values), 4),
        "sd": round(statistics.stdev(values), 4) if len(values) > 1 else 0.0,
        "ci95_case": [round(low, 4), round(high, 4)],
        "width": round(high - low, 4),
    }


def wrong_verdicts(rows: list[dict], change: str) -> dict:
    idx = _index(rows)
    out = {
        layer: {"n": 0, "agree": 0, "naive_fail_paired_pass": 0, "naive_pass_paired_fail": 0, "excluded": 0}
        for layer in LAYERS
    }
    for c, t in forkable_pairs(rows, change):
        paired, naive = idx.get(("fork", change, c, t)), idx.get(("fork_naive", change, c, t))
        if paired is None or naive is None or paired.get("grading_error") or naive.get("grading_error"):
            continue
        # F3: only compare a pair when neither row crashed and both made the same
        # compute_refund decision - otherwise a verdict difference could come from the
        # decision itself rather than from the world, and the pair is not isolating what it
        # claims to.
        same_decision = (
            not paired["crashed"] and not naive["crashed"]
            and paired["fork"].get("decision") is not None
            and paired["fork"].get("decision") == naive["fork"].get("decision")
        )
        for layer in LAYERS:
            counts = out[layer]
            if not same_decision:
                counts["excluded"] += 1
                continue
            vp, vn = _verdict(paired, layer), _verdict(naive, layer)
            counts["n"] += 1
            if vp == vn:
                counts["agree"] += 1
            elif vp:
                counts["naive_fail_paired_pass"] += 1
            else:
                counts["naive_pass_paired_fail"] += 1
    return out


def routing_change(rows: list[dict], change: str) -> dict:
    idx = _index(rows)
    full_reg, fork_reg, flagged, hidden, hidden_fast_path = [], [], [], [], []
    for c, t in sorted({(r["case_id"], r["trial"]) for r in rows if r["arm"] == "baseline"}):
        base, full, fork = (idx.get(("baseline", "baseline", c, t)), idx.get(("full", change, c, t)),
                            idx.get(("fork", change, c, t)))
        if not (base and full and fork) or any(r.get("grading_error") for r in (base, full, fork)):
            continue
        label = f"{c}/t{t}"
        base_ok = passes(base, "three_artifact")
        full_ok, fork_ok = passes(full, "three_artifact"), passes(fork, "three_artifact")
        if base_ok and not full_ok:
            full_reg.append(label)
            if fork_ok:
                hidden.append(label)
                if "E:damaged_fast_path" in full["mutations_fired"]:
                    hidden_fast_path.append(label)
        if base_ok and not fork_ok:
            fork_reg.append(label)
        # F4: a baseline crash is not a routing failure - exclude it, otherwise every
        # baseline-crashed pair (routing_ok forced False by run_group) is miscounted as the
        # routing check catching something.
        if not fork["fork"]["routing_ok"] and not fork["fork"]["baseline_crashed"]:
            flagged.append(label)
    return {
        "full_regressions": full_reg,
        "fork_regressions": fork_reg,
        "routing_flagged": flagged,
        "hidden_by_fork": hidden,
        "hidden_by_fast_path": hidden_fast_path,
        "hidden_and_flagged": sorted(set(hidden) & set(flagged)),
    }


def variance_ratio(rows: list[dict], change: str, score: str) -> dict:
    """Case-clustered bootstrap of var(fork diff) / var(full diff) over the forkable pairs
    where both arms have a diff against the baseline (same (case, trial), same score).

    Each resample redraws the case list once and applies it to both arms (M5), so the ratio
    compares fork and full variance under the same clustering noise. A resample whose
    full-arm variance is 0 is skipped (undefined ratio); the number skipped is reported."""
    idx = _index(rows)
    fork_by_case: dict[str, list[float]] = {}
    full_by_case: dict[str, list[float]] = {}
    for c, t in forkable_pairs(rows, change):
        base, fork, full = (idx.get(("baseline", "baseline", c, t)), idx.get(("fork", change, c, t)),
                            idx.get(("full", change, c, t)))
        if base is None or fork is None or full is None:
            continue
        if base.get("grading_error") or fork.get("grading_error") or full.get("grading_error"):
            continue
        fork_by_case.setdefault(c, []).append(_score(fork, score) - _score(base, score))
        full_by_case.setdefault(c, []).append(_score(full, score) - _score(base, score))
    cases = sorted(set(fork_by_case) & set(full_by_case))
    fork_all = [v for c in cases for v in fork_by_case[c]]
    full_all = [v for c in cases for v in full_by_case[c]]
    if len(fork_all) < 2 or len(full_all) < 2:
        return {"n": len(fork_all), "point": None, "ci95_case": [None, None], "skipped_resamples": 0}
    full_var = statistics.variance(full_all)
    point = round(statistics.variance(fork_all) / full_var, 4) if full_var else None
    rng = random.Random(BOOTSTRAP_SEED)
    ratios = []
    skipped = 0
    for _ in range(BOOTSTRAP_RESAMPLES):
        draw = rng.choices(cases, k=len(cases))
        f_vals = [v for c in draw for v in fork_by_case[c]]
        u_vals = [v for c in draw for v in full_by_case[c]]
        if len(f_vals) < 2 or len(u_vals) < 2:
            skipped += 1
            continue
        full_v = statistics.variance(u_vals)
        if full_v == 0:
            skipped += 1
            continue
        ratios.append(statistics.variance(f_vals) / full_v)
    ratios.sort()
    ci = [round(_percentile(ratios, 0.025), 4), round(_percentile(ratios, 0.975), 4)] if ratios else [None, None]
    return {"n": len(fork_all), "point": point, "ci95_case": ci, "skipped_resamples": skipped}


def full_control_identical_reply_rate(rows: list[dict]) -> dict:
    """M6: over all (case, trial) pairs, the fraction where change="baseline"'s full row (a
    fresh end-to-end run of the unchanged agent) produced the exact same final_message as the
    baseline row. Should be low - Ollama Cloud ignores seeds, so the full arm draws fresh."""
    idx = _index(rows)
    n = k = 0
    for c, t in sorted({(r["case_id"], r["trial"]) for r in rows if r["arm"] == "baseline"}):
        base, full = idx.get(("baseline", "baseline", c, t)), idx.get(("full", "baseline", c, t))
        if base is None or full is None:
            continue
        n += 1
        if base["final_message"] == full["final_message"]:
            k += 1
    return {"k": k, "n": n, "rate": (k / n if n else None)}


def summarize_part2(rows: list[dict]) -> dict:
    changes = [c for c in ALL_CHANGES if any(r["change"] == c and r["arm"] != "baseline" for r in rows)]
    summary: dict = {
        "n_rows": len(rows),
        "crashed": sum(bool(r["crashed"]) for r in rows),
        "grading_errors": sum(bool(r.get("grading_error")) for r in rows),
        "changes": changes,
        "per_change": {},
        "full_control_identical_reply_rate": full_control_identical_reply_rate(rows),
    }
    for change in changes:
        forks = [r for r in rows if r["arm"] == "fork" and r["change"] == change]
        summary["per_change"][change] = {
            "forkable_pairs": len(forkable_pairs(rows, change)),
            "inherited_pairs": sum(r["fork"]["inherited"] for r in forks),
            "routing_flagged": sum(not r["fork"]["routing_ok"] and not r["fork"]["baseline_crashed"] for r in forks),
            "baseline_crashed_pairs": sum(r["fork"]["baseline_crashed"] for r in forks),
            "cost": cost_table(rows, change),
            "delta": {arm: {s: paired_delta(rows, change, arm, s) for s in SCORES} for arm in ("full", "fork")},
            "variance_ratio": {s: variance_ratio(rows, change, s) for s in SCORES},
            "wrong_verdicts": wrong_verdicts(rows, change),
            "routing": routing_change(rows, change),
        }
    return summary


def _ids(labels: list[str]) -> str:
    return f"{len(labels)}" + (f" ({', '.join(labels)})" if labels else "")


def render_markdown_part2(summary: dict, metadata: dict) -> str:
    out = ["# Part 2 results", ""]
    out.append(
        f"Commit `{metadata.get('git_commit', '?')}` - langgraph {metadata.get('langgraph', '?')} - "
        f"policy `{metadata.get('policy_model', {}).get('name', '?')}` - judge `{metadata.get('judge_model', {}).get('name', '?')}` - "
        f"k={metadata.get('k', '?')} - {summary['n_rows']} rows, {summary['crashed']} crashed, "
        f"{summary['grading_errors']} grading errors"
    )
    out += ["", "`baseline` as a change is the no-op control: the unchanged agent forked into itself.", ""]
    out += ["| Change | Forkable pairs | Inherited pairs (no fork point) | Routing check flagged | Baseline crashed |",
            "|---|---|---|---|---|"]
    for ch, d in summary["per_change"].items():
        out.append(f"| {ch} | {d['forkable_pairs']} | {d['inherited_pairs']} | {d['routing_flagged']} | "
                   f"{d['baseline_crashed_pairs']} |")

    out += ["", "## Cost: full rerun vs paired fork", "",
            "Over the change's forkable pairs; only metered rows (no cache hit, token usage reported). "
            "\"Policy calls\" and \"judge calls\" count attempts, retries included.", "",
            "| Change | Arm | Metered runs (excluded) | Wall-clock total s | Median s/run | Policy calls | Judge calls | Input tokens | Output tokens |",
            "|---|---|---|---|---|---|---|---|---|"]
    for ch, d in summary["per_change"].items():
        for arm in ("full", "fork"):
            c = d["cost"][arm]
            out.append(f"| {ch} | {arm} | {c['n']} ({c['excluded']}) | {c['wall_s_total']} | {c['wall_s_median']} | "
                       f"{c['policy_calls']} | {c['judge_calls']} | {c['input_tokens']} | {c['output_tokens']} |")

    out += ["", "## Paired delta vs baseline", "",
            "Change score minus baseline score for the same (case, trial), over the forkable pairs. "
            "`three_artifact` is 0/1; `judge_score` is 1-5. By-case bootstrap 95% CI.", "",
            "| Change | Score | Arm | n | Mean | SD | By-case 95% CI | CI width |", "|---|---|---|---|---|---|---|---|"]
    for ch, d in summary["per_change"].items():
        for score in SCORES:
            for arm in ("full", "fork"):
                r = d["delta"][arm][score]
                low, high = r["ci95_case"]
                out.append(f"| {ch} | {score} | {arm} | {r['n']} | {r['mean']} | {r['sd']} | {low} to {high} | {r['width']} |")

    out += ["", "E shares D's cache namespaces, so on forkable pairs E's full and fork rows replay D's draws: its "
            "cost rows are excluded and its deltas equal D's by construction. E is the routing demonstration only.", ""]

    out += ["", "## Variance ratio: fork vs full (var(fork diff) / var(full diff))", "",
            "Case-clustered bootstrap; a value near 1 means the fork isn't adding measurement noise relative to "
            "a full rerun. Resamples where the full-arm variance is 0 are skipped.", ""]
    for ch, d in summary["per_change"].items():
        for score in SCORES:
            r = d["variance_ratio"][score]
            low, high = r["ci95_case"]
            out.append(f"- {ch} / {score}: point {r['point']}, 95% CI {low} to {high} "
                       f"(n={r['n']}, {r['skipped_resamples']} resamples skipped)")

    out += ["", "## Naive fork vs paired fork", "",
            "Pairs are compared only when both forks made the same compute_refund decision. End state differs "
            "only through the world. Constraints differ through the carried tool log, which is part of the "
            "world snapshot. Answer can also differ by sampling, because the refund id in the reply facts "
            "differs.", "",
            "| Change | Layer | n | Agree | Naive fail, paired pass | Naive pass, paired fail | Excluded (different decision) |",
            "|---|---|---|---|---|---|---|"]
    for ch, d in summary["per_change"].items():
        for layer, c in d["wrong_verdicts"].items():
            out.append(f"| {ch} | {layer} | {c['n']} | {c['agree']} | {c['naive_fail_paired_pass']} | "
                       f"{c['naive_pass_paired_fail']} | {c['excluded']} |")

    out += ["", "## Routing change", "",
            "Three-artifact regressions (baseline passes, the arm fails) seen by a full rerun vs by the fork arm, "
            "whose inherited rows reuse the baseline's verdict. A pair whose baseline crashed is excluded from "
            "the routing-flagged count.", ""]
    for ch, d in summary["per_change"].items():
        r = d["routing"]
        out += [f"### {ch}", "",
                f"- Full-rerun regressions: {_ids(r['full_regressions'])}",
                f"- Fork-arm regressions: {_ids(r['fork_regressions'])}",
                f"- Hidden by the fork (full fails, fork passes): {_ids(r['hidden_by_fork'])}",
                f"- Hidden by the fast path (E:damaged_fast_path): {_ids(r['hidden_by_fast_path'])}",
                f"- Routing check flagged as not forkable: {_ids(r['routing_flagged'])}",
                f"- Hidden and flagged: {_ids(r['hidden_and_flagged'])}", ""]

    fcr = summary.get("full_control_identical_reply_rate", {"k": 0, "n": 0, "rate": None})
    rate_str = f"{fcr['rate']:.0%}" if fcr.get("rate") is not None else "-"
    out += ["", f"Full-arm reply identical to the baseline reply, on change=baseline (the no-op control): "
                f"{fcr['k']}/{fcr['n']} ({rate_str}). This should be low: Ollama Cloud ignores seeds, and the "
                f"full arm draws fresh.", ""]
    return "\n".join(out)
