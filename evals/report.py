"""Turns a run log into the Part 1 numbers.

- Mutant survival for harness H and mutant M (primary, conditioned on the baseline):
  among (case, trial) pairs where M's fault fired in M's run AND the baseline run for the
  same (case, trial) passes H, the fraction where M's run passes H. A pair whose baseline
  run fails H is excluded (H cannot tell the fault apart from a failure the unmutated
  agent also has), as is a pair with no baseline row; both exclusions are counted on the
  rate ("excluded_baseline_failed", "excluded_no_baseline").
- Unconditional mutant survival (secondary, "mutant_survival_unconditional"): among runs
  of M where M's fault fired, the fraction H passes, with no reference to the baseline.
- Trajectory-Blind Pass rate: among runs that pass the answer-only harness, the
  fraction that fail the three-artifact harness.
- Brittle-fail rate for trajectory layer L: among valid-variant runs whose end state
  and answer both pass, the fraction L rejects. Reported overall and per slice.
- A crashed run passes no harness.
- Runs whose grader failed (grading_error) are excluded from every rate and counted separately.

Every rate carries two 95% intervals:
- "ci95": Wilson score interval treating each run as independent ("per-run").
- "ci95_case": case-clustered percentile bootstrap ("by case"): the case ids that
  contribute at least one run to the rate's denominator are resampled with replacement
  (random.Random(0), 2000 resamples), the rate is recomputed from all runs of the
  resampled cases, and the 2.5th/97.5th percentiles are taken. Outcomes cluster by case
  (a case's trials and variants share prompts and often replay the same cached draws),
  so the per-run interval understates uncertainty; the by-case interval is the one to cite.
"""
from __future__ import annotations

import math
import random
from pathlib import Path

from agent.graph import MUTANTS, VALID_VARIANTS, VARIANTS
from evals.checks.trajectory import MATCH_MODES

HARNESSES = ("answer_only", "three_artifact") + tuple(f"mode:{m}" for m in MATCH_MODES)
TRAJECTORY_LAYERS = ("constraints",) + MATCH_MODES
BOOTSTRAP_RESAMPLES = 2000
BOOTSTRAP_SEED = 0


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def rate(k: int, n: int) -> dict:
    return {"k": k, "n": n, "rate": (k / n if n else None), "ci95": list(wilson(k, n))}


def _percentile(sorted_values: list[float], q: float) -> float:
    """Linear-interpolated percentile (numpy's default method) of an already sorted list."""
    pos = (len(sorted_values) - 1) * q
    lo, hi = math.floor(pos), math.ceil(pos)
    return sorted_values[lo] + (sorted_values[hi] - sorted_values[lo]) * (pos - lo)


def case_bootstrap(units: list[tuple[str, bool]]) -> tuple[float, float]:
    """Case-clustered percentile bootstrap 95% interval for the fraction of units that succeed.

    units holds one (case_id, success) pair per run in the rate's denominator."""
    if not units:
        return (0.0, 0.0)
    per_case: dict[str, list[int]] = {}
    for case_id, ok in units:
        kn = per_case.setdefault(case_id, [0, 0])
        kn[0] += bool(ok)
        kn[1] += 1
    clusters = [per_case[c] for c in sorted(per_case)]
    rng = random.Random(BOOTSTRAP_SEED)
    rates = []
    for _ in range(BOOTSTRAP_RESAMPLES):
        draw = rng.choices(clusters, k=len(clusters))
        rates.append(sum(c[0] for c in draw) / sum(c[1] for c in draw))
    rates.sort()
    return (_percentile(rates, 0.025), _percentile(rates, 0.975))


def case_rate(units: list[tuple[str, bool]]) -> dict:
    """rate() over (case_id, success) units, plus the case-clustered bootstrap interval."""
    out = rate(sum(bool(ok) for _, ok in units), len(units))
    out["ci95_case"] = list(case_bootstrap(units))
    return out


def passes(run: dict, harness: str) -> bool:
    if run["crashed"]:
        return False
    if harness == "answer_only":
        return run["answer_pass"]
    if harness == "three_artifact":
        return run["answer_pass"] and run["end_state_pass"] and run["constraints_pass"]
    mode = harness.removeprefix("mode:")
    return run["answer_pass"] and run["end_state_pass"] and run["mode_pass"][mode]


def _layer_ok(run: dict, layer: str) -> bool:
    return run["constraints_pass"] if layer == "constraints" else run["mode_pass"][layer]


def _fired(run: dict) -> bool:
    return any(f.startswith(f"{run['variant']}:") for f in run["mutations_fired"])


def _pass_rates(runs: list[dict], harnesses=HARNESSES) -> dict:
    return {h: case_rate([(r["case_id"], passes(r, h)) for r in runs]) for h in harnesses}


def _conditional_survival(fired: list[dict], baseline: dict, harnesses=HARNESSES) -> dict:
    """Survival of fired mutant runs over the (case, trial) pairs whose baseline run passes H."""
    out = {}
    for h in harnesses:
        units = []
        no_baseline = baseline_failed = 0
        for r in fired:
            b = baseline.get((r["case_id"], r["trial"]))
            if b is None:
                no_baseline += 1
            elif not passes(b, h):
                baseline_failed += 1
            else:
                units.append((r["case_id"], passes(r, h)))
        out[h] = case_rate(units)
        out[h]["excluded_no_baseline"] = no_baseline
        out[h]["excluded_baseline_failed"] = baseline_failed
    return out


def _tbp(runs: list[dict]) -> dict:
    answer_ok = [r for r in runs if passes(r, "answer_only")]
    return case_rate([(r["case_id"], not passes(r, "three_artifact")) for r in answer_ok])


def _brittle(runs: list[dict]) -> dict:
    """Brittle-fail rate per trajectory layer for each valid variant present in runs."""
    out = {}
    for v in VALID_VARIANTS:
        rs = [r for r in runs if r["variant"] == v and not r["crashed"] and r["end_state_pass"] and r["answer_pass"]]
        if rs:
            out[v] = {
                layer: case_rate([(r["case_id"], not _layer_ok(r, layer)) for r in rs]) for layer in TRAJECTORY_LAYERS
            }
    return out


def summarize(runs: list[dict]) -> dict:
    grading_errors = sum(bool(r.get("grading_error")) for r in runs)
    runs = [r for r in runs if not r.get("grading_error")]
    variants = [v for v in VARIANTS if any(r["variant"] == v for r in runs)]
    baseline = {(r["case_id"], r["trial"]): r for r in runs if r["variant"] == "baseline"}
    summary: dict = {
        "n_runs": len(runs),
        "crashed": sum(bool(r["crashed"]) for r in runs),
        "grading_errors": grading_errors,
        "harness_pass": {},
        "tbp": {},
        "mutant_survival": {},
        "mutant_survival_unconditional": {},
        "brittle_fail": {},
        "slices": {},
    }
    for v in variants:
        rs = [r for r in runs if r["variant"] == v]
        summary["harness_pass"][v] = _pass_rates(rs)
        summary["tbp"][v] = _tbp(rs)
    summary["tbp"]["all"] = _tbp(runs)
    for m in MUTANTS:
        rs = [r for r in runs if r["variant"] == m and _fired(r)]
        if rs:
            summary["mutant_survival"][m] = _conditional_survival(rs, baseline)
            summary["mutant_survival_unconditional"][m] = _pass_rates(rs)
    summary["brittle_fail"] = _brittle(runs)
    two = ("answer_only", "three_artifact")
    for sl in sorted({r["slice"] for r in runs}):
        in_slice = [r for r in runs if r["slice"] == sl]
        fired = [r for r in in_slice if r["variant"] in MUTANTS and _fired(r)]
        summary["slices"][sl] = {
            "mutant_survival": _conditional_survival(fired, baseline, two),
            "mutant_survival_unconditional": _pass_rates(fired, two),
            "tbp": _tbp(in_slice),
            "brittle_fail": _brittle(in_slice),
        }
    summary["judge_endorsed_wrong_world"] = case_rate(
        [(r["case_id"], bool(r["answer_pass"] and not r["end_state_pass"] and not r["crashed"])) for r in runs]
    )
    return summary


def _fmt(r: dict) -> str:
    if not r["n"]:
        return "-"
    low, high = r["ci95"]
    text = f"{r['rate']:.0%} ({r['k']}/{r['n']}; per-run {low:.0%}-{high:.0%}"
    if "ci95_case" in r:
        clow, chigh = r["ci95_case"]
        text += f"; by case {clow:.0%}-{chigh:.0%}"
    return text + ")"


def _table(header: str, rows: dict, columns) -> list[str]:
    out = [f"| {header} | " + " | ".join(columns) + " |", "|---" * (len(columns) + 1) + "|"]
    for name, rates in rows.items():
        out.append(f"| {name} | " + " | ".join(_fmt(rates[c]) for c in columns) + " |")
    return out


def render_markdown(summary: dict, metadata: dict) -> str:
    out = ["# Part 1 results", ""]
    out.append(
        f"Commit `{metadata.get('git_commit', '?')}` - langgraph {metadata.get('langgraph', '?')} - "
        f"policy `{metadata.get('policy_model', {}).get('name', '?')}` - judge `{metadata.get('judge_model', {}).get('name', '?')}` - "
        f"k={metadata.get('k', '?')} - {summary['n_runs']} runs, {summary['crashed']} crashed, {summary.get('grading_errors', 0)} grading errors"
    )
    out += ["", "Every cell: rate (k/n; per-run Wilson 95% CI; by-case bootstrap 95% CI). Outcomes cluster "
            "by case, so the per-run interval understates uncertainty; the by-case interval is the one to cite."]
    out += ["", "## Mutant survival, conditioned on baseline passing (primary; lower is better)", "",
            "Among (case, trial) pairs where the mutant's fault fired and the baseline run for the same "
            "(case, trial) passes the harness, the fraction where the mutant's run also passes.", ""]
    out += _table("Mutant", summary["mutant_survival"], HARNESSES)
    out += ["", "Fired pairs excluded from the table above (baseline run fails the harness / no baseline row):", "",
            "| Mutant | " + " | ".join(HARNESSES) + " |", "|---" * (len(HARNESSES) + 1) + "|"]
    for m, rates in summary["mutant_survival"].items():
        out.append(f"| {m} | " + " | ".join(
            f"{rates[h]['excluded_baseline_failed']} / {rates[h]['excluded_no_baseline']}" for h in HARNESSES) + " |")
    out += ["", "## Mutant survival, unconditional (secondary; lower is better)", "",
            "Among fired runs of the mutant, the fraction that pass the harness, ignoring the baseline.", ""]
    out += _table("Mutant", summary["mutant_survival_unconditional"], HARNESSES)
    out += ["", "## Trajectory-Blind Pass rate", "", "| Variant | TBP rate |", "|---|---|"]
    for v, r in summary["tbp"].items():
        out.append(f"| {v} | {_fmt(r)} |")
    out += ["", "## Brittle-fail rate on valid variants (lower is better)", ""]
    out += _table("Variant", summary["brittle_fail"], TRAJECTORY_LAYERS)
    out += ["", "## By slice", "",
            "Mutant survival pools every fired run of A, B and C in the slice.", "",
            "| Slice | Mutant survival, answer-only (conditioned on baseline) | Mutant survival, three-artifact "
            "(conditioned on baseline) | Mutant survival, answer-only (unconditional) | Mutant survival, "
            "three-artifact (unconditional) | TBP rate |",
            "|---|---|---|---|---|---|"]
    for sl, data in summary["slices"].items():
        ms, mu = data["mutant_survival"], data["mutant_survival_unconditional"]
        out.append(f"| {sl} | {_fmt(ms['answer_only'])} | {_fmt(ms['three_artifact'])} | "
                   f"{_fmt(mu['answer_only'])} | {_fmt(mu['three_artifact'])} | {_fmt(data['tbp'])} |")
    out += ["", "## Brittle-fail rate by slice (valid variants; lower is better)", "",
            "| Slice | Variant | " + " | ".join(TRAJECTORY_LAYERS) + " |", "|---" * (len(TRAJECTORY_LAYERS) + 2) + "|"]
    for sl, data in summary["slices"].items():
        for v, rates in data["brittle_fail"].items():
            out.append(f"| {sl} | {v} | " + " | ".join(_fmt(rates[layer]) for layer in TRAJECTORY_LAYERS) + " |")
    out += ["", "## Harness pass rate by variant", ""]
    out += _table("Variant", summary["harness_pass"], HARNESSES)
    out += ["", f"Judge endorsed a reply the database contradicts: {_fmt(summary['judge_endorsed_wrong_world'])}", ""]
    return "\n".join(out)


def _transcript(run: dict, kind: str) -> str:
    calls = "\n".join(
        f"{i}. `{c['name']}` {c['args']}" + ("" if c["ok"] else f" - FAILED ({c['error']})")
        for i, c in enumerate(run["tool_calls"], 1)
    ) or "(no tool calls)"
    return "\n".join([
        f"# {kind}: {run['case_id']} / {run['variant']} / trial {run['trial']}",
        "",
        f"Mutations fired: {run['mutations_fired'] or 'none'}",
        "",
        "## Tool calls", "", calls,
        "", "## Refund rows after the run", "", str(run["refunds"] or "none"),
        "", "## Final message", "", run["final_message"] or "(none)",
        "", "## Verdicts", "",
        f"- answer: {run['answer_pass']} (judge {run['judge_score']}/5: {run['judge_rationale']})",
        f"- end state: {run['end_state_pass']} ({run['end_state_detail']})",
        f"- trajectory constraints: {run['constraints_pass']} ({run['constraints_detail']})",
        "",
    ])


def write_transcripts(runs: list[dict], directory: Path, per_kind: int = 5) -> int:
    directory.mkdir(parents=True, exist_ok=True)
    fooled = [r for r in runs if not r["crashed"] and r["answer_pass"] and not r["end_state_pass"]]
    fooled.sort(key=lambda r: (r["variant"] not in MUTANTS, r["case_id"], r["variant"], r["trial"]))
    blind = [
        r for r in runs
        if r["variant"] in MUTANTS and not r["crashed"]
        and r["answer_pass"] and r["end_state_pass"] and not r["constraints_pass"]
    ]
    blind.sort(key=lambda r: (r["case_id"], r["variant"], r["trial"]))
    written = 0
    for kind, selection in (("judge-fooled", fooled[:per_kind]), ("trajectory-blind", blind[:per_kind])):
        for r in selection:
            path = directory / f"{kind}-{r['case_id']}-{r['variant']}-t{r['trial']}.md"
            path.write_text(_transcript(r, kind), encoding="utf-8")
            written += 1
    return written
