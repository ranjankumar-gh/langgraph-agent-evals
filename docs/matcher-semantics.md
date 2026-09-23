# Trajectory match mode semantics

`match_trajectory(observed, reference, mode)` in `evals/checks/trajectory.py` compares the
sequence of tool call names the agent actually made (`observed`) against a reference
trajectory (`reference`). It supports four modes:

| Mode | Passes when | Counts duplicate calls | Cares about order |
|---|---|---|---|
| `strict` | `observed` equals `reference` exactly, element by element | yes (list equality) | yes |
| `unordered` | `observed` and `reference` contain the same tool calls, with the same per-tool counts, in any order | yes (multiset equality) | no |
| `subset` | every tool call in `observed` fits within `reference`'s per-tool counts — `observed` calls no tool more times than `reference` does, and calls no tool `reference` doesn't call | yes (multiset subset) | no |
| `superset` | every tool call in `reference` fits within `observed`'s per-tool counts — `observed` calls every tool `reference` calls at least as many times | yes (multiset superset) | no |

`subset` and `superset` are multiset (`collections.Counter`) comparisons, not plain set
comparisons. A tool called twice in `observed` but once in `reference` fails `subset` even
though the *set* of tool names observed is a subset of the set of tool names in `reference`.
Concretely: `match_trajectory(["lookup_order", "lookup_order", "issue_refund"], ["lookup_order", "issue_refund"], "subset")`
is `False`, because `lookup_order` appears twice in `observed` and only once in `reference`.

This was not the original implementation. `subset`/`superset` were first written with plain
set comparisons (`set(observed) <= set(reference)` / `set(observed) >= set(reference)`),
which ignores repeat calls entirely. Cross-checking against `agentevals` 0.0.9 surfaced the
divergence (see below), and `match_trajectory` was changed to multiset comparisons to match.
`tests/test_checks.py::test_match_modes` was updated for the one fixture that exposed the
difference (a trajectory that repeats `lookup_order`): `subset` flips from `True` (set-based)
to `False` (multiset-based) for that case.

Verified against agentevals 0.0.9 by `tests/test_agentevals_agreement.py`; tool arguments
are ignored in all four modes (`tool_args_match_mode='ignore'`).
