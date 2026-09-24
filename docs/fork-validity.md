# Checkpoint-fork evaluation: validity rules

A checkpoint fork re-runs a change from the baseline's checkpoint just before the changed
node. Upstream nodes are not re-run, so the change and the baseline share their upstream
draw: a paired comparison (common random numbers). It is a valid measurement only when
all five rules hold. This file maps each rule to the code that enforces it in this repo.

| # | Rule | Enforced by |
|---|---|---|
| 1 | The fork point precedes the changed node. | `evals/fork.py:find_fork_point` - the earliest checkpoint whose `next` is the changed node, so the node has not run yet. |
| 2 | Routing into the changed node is unchanged. | `evals/fork.py:check_routing` - replays the change's routers (`agent/graph.py:make_routers`) over every baseline step up to the fork point, or over the whole run when the baseline never reached the node. |
| 3 | A world snapshot is paired with every stored checkpoint. | `evals/fork.py:record_run` + `agent/tools.py:WorldSnapshot` - the database, tool counters and call log after every step, keyed by checkpoint id. A checkpoint restores the thread, not the world. |
| 4 | Remaining bounds are carried into the fork. | `evals/fork.py:carried_limit` - a fork starts with a fresh `recursion_limit` (verified on langgraph 1.2.12), so the fork runs under `limit - (fork_step + 1)`. |
| 5 | Fork from all k baseline trials, not one. | `evals/runner_part2.py:run_group` - one group per (case, trial), every trial forked. |

Rule 1 has a second half `find_fork_point` does not check: nothing upstream of the fork
point may read what the changed node writes, or a fork that skips re-running the upstream
nodes would replay stale reads. That holds by construction for D and E - both edit
`compute_refund`, which no upstream node (`classify_request`, `lookup_order`,
`get_refund_history`, `check_eligibility`) reads - and is not checked by code. A future
change that edits a field an upstream node reads would need its own check; this repo has
none.

## The three ways a fork harness goes wrong, measured in `results/part-2/`

- **No world snapshot (naive fork).** The thread is restored, but the world is the one the
  baseline left behind: its refund row is already there, and so is its tool log. The
  `fork_naive` arm measures what that does to the verdicts.
- **Routing changed (rule 2).** Change E alters the router into `compute_refund`. On cases
  where the baseline never reached `compute_refund` there is no fork point, and a fork
  harness that reuses the baseline verdict there never sees E's regression. `check_routing`
  flags those cases.
- **Fresh budget (rule 4).** Pinned by `tests/test_fork.py::test_a_fork_gets_a_fresh_recursion_budget_unless_it_is_carried`.
  No case in this repo comes near the limit, so it is a unit-tested property, not a measured one.

## Cache namespaces

Each arm draws fresh from the model through its own cache namespace (`evals/runner_part2.py:namespace`).
The Part 1 harness got pairing from the prompt-keyed record/replay cache, which pairs only
when the upstream prompt is byte-identical and the cache is warm. A fork gets its pairing
from the checkpoint, and does not pay for the upstream calls at all.
