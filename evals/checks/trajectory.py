"""Layer 2: what the agent did. Case-authored constraints plus reference-matching modes."""
from __future__ import annotations

from collections import Counter

from evals.checks import CheckResult
from evals.schema import TrajectoryConstraints

MATCH_MODES = ("strict", "unordered", "subset", "superset")


def check_constraints(calls: list[str], constraints: TrajectoryConstraints) -> CheckResult:
    problems: list[str] = []
    for tool in constraints.required:
        if tool not in calls:
            problems.append(f"missing required {tool}")
    for tool in constraints.forbidden:
        if tool in calls:
            problems.append(f"forbidden {tool} called")
    for before, after in constraints.ordering:
        if after not in calls:
            continue
        if before not in calls:
            problems.append(f"{after} called without {before}")
        elif calls.index(before) > calls.index(after):
            problems.append(f"{after} before {before}")
    for tool, limit in constraints.max_calls.items():
        count = calls.count(tool)
        if count > limit:
            problems.append(f"{tool} called {count} times (max {limit})")
    return CheckResult(not problems, "; ".join(problems) or "ok")


def match_trajectory(observed: list[str], reference: list[str], mode: str) -> bool:
    if mode == "strict":
        return observed == reference
    if mode == "unordered":
        return Counter(observed) == Counter(reference)
    if mode == "subset":
        return set(observed) <= set(reference)
    if mode == "superset":
        return set(observed) >= set(reference)
    raise ValueError(f"unknown mode {mode!r}")
