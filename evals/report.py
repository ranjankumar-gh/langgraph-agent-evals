"""Turns a run log into the Part 1 numbers.

- Mutant survival for harness H and mutant M: among runs of M where M's fault fired,
  the fraction H passes.
- Trajectory-Blind Pass rate: among runs that pass the answer-only harness, the
  fraction that fail the three-artifact harness.
- Brittle-fail rate for trajectory layer L: among valid-variant runs whose end state
  and answer both pass, the fraction L rejects.
- A crashed run passes no harness.
- Runs whose grader failed (grading_error) are excluded from every rate and counted separately.
All rates carry Wilson 95% intervals.
"""
from __future__ import annotations

import math
from pathlib import Path

from agent.graph import MUTANTS, VALID_VARIANTS, VARIANTS
from evals.checks.trajectory import MATCH_MODES

HARNESSES = ("answer_only", "three_artifact") + tuple(f"mode:{m}" for m in MATCH_MODES)
TRAJECTORY_LAYERS = ("constraints",) + MATCH_MODES


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
    return {h: rate(sum(passes(r, h) for r in runs), len(runs)) for h in harnesses}


def _tbp(runs: list[dict]) -> dict:
    answer_ok = [r for r in runs if passes(r, "answer_only")]
    return rate(sum(not passes(r, "three_artifact") for r in answer_ok), len(answer_ok))


def summarize(runs: list[dict]) -> dict:
    grading_errors = sum(bool(r.get("grading_error")) for r in runs)
    runs = [r for r in runs if not r.get("grading_error")]
    variants = [v for v in VARIANTS if any(r["variant"] == v for r in runs)]
    summary: dict = {
        "n_runs": len(runs),
        "crashed": sum(bool(r["crashed"]) for r in runs),
        "grading_errors": grading_errors,
        "harness_pass": {},
        "tbp": {},
        "mutant_survival": {},
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
            summary["mutant_survival"][m] = _pass_rates(rs)
    for v in VALID_VARIANTS:
        rs = [r for r in runs if r["variant"] == v and not r["crashed"] and r["end_state_pass"] and r["answer_pass"]]
        if rs:
            summary["brittle_fail"][v] = {
                layer: rate(sum(not _layer_ok(r, layer) for r in rs), len(rs)) for layer in TRAJECTORY_LAYERS
            }
    for sl in sorted({r["slice"] for r in runs}):
        in_slice = [r for r in runs if r["slice"] == sl]
        fired = [r for r in in_slice if r["variant"] in MUTANTS and _fired(r)]
        summary["slices"][sl] = {
            "mutant_survival": _pass_rates(fired, ("answer_only", "three_artifact")),
            "tbp": _tbp(in_slice),
        }
    summary["judge_endorsed_wrong_world"] = rate(
        sum(r["answer_pass"] and not r["end_state_pass"] and not r["crashed"] for r in runs), len(runs)
    )
    return summary


def _fmt(r: dict) -> str:
    if not r["n"]:
        return "-"
    low, high = r["ci95"]
    return f"{r['rate']:.0%} ({r['k']}/{r['n']}; 95% CI {low:.0%}-{high:.0%})"


def render_markdown(summary: dict, metadata: dict) -> str:
    out = ["# Part 1 results", ""]
    out.append(
        f"Commit `{metadata.get('git_commit', '?')}` - langgraph {metadata.get('langgraph', '?')} - "
        f"policy `{metadata.get('policy_model', {}).get('name', '?')}` - judge `{metadata.get('judge_model', {}).get('name', '?')}` - "
        f"k={metadata.get('k', '?')} - {summary['n_runs']} runs, {summary['crashed']} crashed, {summary.get('grading_errors', 0)} grading errors"
    )
    out += ["", "## Mutant survival (lower is better)", "", "| Mutant | " + " | ".join(HARNESSES) + " |",
            "|---" * (len(HARNESSES) + 1) + "|"]
    for m, rates in summary["mutant_survival"].items():
        out.append(f"| {m} | " + " | ".join(_fmt(rates[h]) for h in HARNESSES) + " |")
    out += ["", "## Trajectory-Blind Pass rate", "", "| Variant | TBP rate |", "|---|---|"]
    for v, r in summary["tbp"].items():
        out.append(f"| {v} | {_fmt(r)} |")
    out += ["", "## Brittle-fail rate on valid variants (lower is better)", "",
            "| Variant | " + " | ".join(TRAJECTORY_LAYERS) + " |", "|---" * (len(TRAJECTORY_LAYERS) + 1) + "|"]
    for v, rates in summary["brittle_fail"].items():
        out.append(f"| {v} | " + " | ".join(_fmt(rates[layer]) for layer in TRAJECTORY_LAYERS) + " |")
    out += ["", "## By slice", "", "| Slice | Mutant survival, answer-only | Mutant survival, three-artifact | TBP rate |",
            "|---|---|---|---|"]
    for sl, data in summary["slices"].items():
        ms = data["mutant_survival"]
        out.append(f"| {sl} | {_fmt(ms['answer_only'])} | {_fmt(ms['three_artifact'])} | {_fmt(data['tbp'])} |")
    out += ["", "## Harness pass rate by variant", "", "| Variant | " + " | ".join(HARNESSES) + " |",
            "|---" * (len(HARNESSES) + 1) + "|"]
    for v, rates in summary["harness_pass"].items():
        out.append(f"| {v} | " + " | ".join(_fmt(rates[h]) for h in HARNESSES) + " |")
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
