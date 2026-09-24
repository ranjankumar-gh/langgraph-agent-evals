"""Part 2: one (case, trial) group.

A group is a recorded baseline followed by three arms for each change. It is the unit of
work because forks need the baseline's checkpoints and world snapshots, which live in
memory for the group's lifetime.

Arms (see docs/fork-validity.md):
- baseline:   the reference run, recorded with a world snapshot at every checkpoint.
- full:       the change run end to end on a fresh world and a fresh checkpointer.
- fork:       the change run from the baseline checkpoint before the changed node, on a
              private copy of the world as it was at that checkpoint (paired fork).
- fork_naive: the same fork on a copy of the world as the baseline run left it. The thread
              is restored and the world is not, which is what a fork harness without
              environment snapshots does.

When the baseline never reached the changed node there is no fork point. Both fork arms
then inherit the baseline's verdicts, as a fork harness that skips unaffected cases
would, and the row records whether the routing check says that shortcut was valid.
"""
from __future__ import annotations

import time
from dataclasses import asdict, dataclass, replace
from datetime import date

from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import CHANGED_NODE, build_graph, make_routers
from agent.llm import LLM, usage_delta
from agent.tools import Tools
from env.db import create_db
from evals.fork import RECURSION_LIMIT, carried_limit, check_routing, find_fork_point, fork_run, history, record_run
from evals.runner import RunRecord, final_message, grade_run, run_case
from evals.schema import Case

ARMS = ("baseline", "full", "fork", "fork_naive")
_ZERO = {"calls": 0, "hits": 0, "input_tokens": 0, "output_tokens": 0, "unmetered": 0, "seconds": 0.0}


@dataclass
class ArmLLMs:
    policy: LLM
    judge: LLM


def namespace(arm: str, change: str, tag: str = "") -> str:
    """The cache namespace an arm draws from, scoped to one measured run.

    The baseline keeps the un-namespaced cache, so it replays Part 1's draws where they
    exist - this is deliberate: the no-op control measures drift, and is unaffected by
    `tag`. Every full rerun and every fork draws fresh. E shares D's namespaces, so on every
    path where E behaves like D it replays D's draws, and any E-versus-D difference comes
    from the routing change alone. fork_naive shares its change's fork namespace, so it
    starts from the same cached draws fork would - it does not thereby guarantee the same
    compute_refund decision, since a hosted model's sampling can still diverge them (see
    evals/report_part2.py: wrong_verdicts pairs only rows whose decision actually agreed).

    `tag` (typically f"{out.name}-{commit[:7]}", set once per measured run by
    scripts/run_part2.py) is appended as "@{tag}" when non-empty, so a smoke run's draws
    (under a smoke --out) are never replayed by the measured run, and any void-and-rerun of
    the measured run at a fresh --out or commit draws fresh instead of replaying a stale
    namespace's cache entries. Resuming the same --out at the same commit reuses the same
    tag, so it correctly replays its own prior draws."""
    if arm == "baseline":
        return ""
    family = "D" if change == "E" else change
    base = f"p2-{'fork' if arm.startswith('fork') else 'full'}-{family}"
    return f"{base}@{tag}" if tag else base


def namespaces_for(changes: list[str], tag: str = "") -> list[str]:
    return sorted(
        {namespace("baseline", "baseline", tag)} | {namespace(a, c, tag) for c in changes for a in ("full", "fork")}
    )


def _usage(llms: ArmLLMs) -> tuple[dict, dict]:
    return llms.policy.usage(), llms.judge.usage()


def _cost(llms: ArmLLMs, before: tuple[dict, dict]) -> dict:
    return {"policy": usage_delta(before[0], llms.policy.usage()), "judge": usage_delta(before[1], llms.judge.usage())}


def _row(arm: str, change: str, rec: RunRecord, *, cost: dict, fork: dict | None = None) -> dict:
    return {"arm": arm, "change": change, **asdict(rec), "cost": cost, "fork": fork}


def _fresh_tools(case: Case) -> Tools:
    return Tools(create_db(case.env), date.fromisoformat(case.env.today), dict(case.env.faults),
                 reprice_on_reread=case.env.reprice_on_reread)


def _full(case: Case, change: str, trial: int, llms: ArmLLMs) -> dict:
    before = _usage(llms)
    rec = run_case(case, change, trial, llms.policy, llms.judge)
    return _row("full", change, rec, cost=_cost(llms, before))


def _fork(case: Case, change: str, trial: int, arm: str, fork_point, prefix: list[str], tools: Tools,
          saver, llms: ArmLLMs, meta: dict) -> dict:
    fired: list[str] = []
    graph = build_graph(change, llms.policy, tools, seed=trial, fired=fired, checkpointer=saver)
    before = _usage(llms)
    started = time.perf_counter()
    nodes, final, crashed = list(prefix), "", None
    try:
        values, forked = fork_run(graph, fork_point, approval=case.approval)
        nodes += forked
        final = final_message(values)
        # F3: the compute_refund decision this arm actually made. Absent (None) if the fork
        # crashed before producing values - wrong_verdicts() then excludes the pair, since a
        # verdict difference without a matching decision could come from the decision, not the
        # world.
        meta["decision"] = {"refund_type": values.get("refund_type"), "refund_amount": values.get("refund_amount")}
    except Exception as exc:  # a GraphRecursionError under the carried budget is a result, not a harness bug
        crashed = f"{type(exc).__name__}: {exc}"
    rec = grade_run(case, change, trial, conn=tools.conn, tools=tools, nodes=nodes, final=final,
                    fired=fired, crashed=crashed, judge=llms.judge, started=started)
    return _row(arm, change, rec, cost=_cost(llms, before), fork=meta)


def run_group(case: Case, trial: int, changes: list[str], llms: dict[str, ArmLLMs], tag: str = "") -> list[dict]:
    thread_id = f"{case.id}:{trial}"
    saver = InMemorySaver()
    base_llms = llms[namespace("baseline", "baseline", tag)]
    tools = _fresh_tools(case)
    fired: list[str] = []
    graph = build_graph("baseline", base_llms.policy, tools, seed=trial, fired=fired, checkpointer=saver)
    before = _usage(base_llms)
    started = time.perf_counter()
    recorded, crashed = None, None
    try:
        recorded = record_run(graph, tools, request=case.request, customer_id=case.customer_id,
                              thread_id=thread_id, approval=case.approval)
    except Exception as exc:
        crashed = f"{type(exc).__name__}: {exc}"
    base = grade_run(case, "baseline", trial, conn=tools.conn, tools=tools,
                     nodes=recorded.nodes if recorded else [], final=final_message(recorded.values) if recorded else "",
                     fired=fired, crashed=crashed, judge=base_llms.judge, started=started)
    base_row = _row("baseline", "baseline", base, cost=_cost(base_llms, before))
    base_row["exec_order"] = 0  # F5: baseline always executes first
    rows = [base_row]

    hist = history(graph, thread_id) if recorded else []  # before any fork adds branches
    left_behind = tools.snapshot()
    # F5: alternate which arm runs first so a prefix cache serving the byte-identical compute
    # prompt doesn't systematically favour one arm's tokens/latency. fork_naive must still run
    # right after fork (it replays fork's compute draw), so the only two valid orders are
    # full-first and fork-first.
    flip = (trial + sum(map(ord, case.id))) % 2
    arm_order = ("full", "fork", "fork_naive") if flip == 0 else ("fork", "fork_naive", "full")
    exec_order = 1
    for change in changes:
        full_llms = llms[namespace("full", change, tag)]
        fork_llms = llms[namespace("fork", change, tag)]
        fork_point = find_fork_point(hist, CHANGED_NODE[change])
        if recorded:
            routing_ok, routing_detail = check_routing(hist, make_routers(change, []), until=fork_point)
        else:
            routing_ok, routing_detail = False, "baseline crashed"
        step = fork_point.metadata["step"] if fork_point else None
        meta = {"fork_point_step": step, "inherited": fork_point is None, "routing_ok": routing_ok,
                "routing_detail": routing_detail,
                "carried_limit": carried_limit(RECURSION_LIMIT, step) if fork_point else None,
                "decision": None, "baseline_crashed": crashed is not None}
        produced: dict[str, dict] = {}
        for arm in arm_order:
            if arm == "full":
                produced["full"] = _full(case, change, trial, full_llms)
            elif fork_point is None:
                inherited = replace(base, variant=change, elapsed_s=0.0)
                produced[arm] = _row(arm, change, inherited, cost={"policy": dict(_ZERO), "judge": dict(_ZERO)},
                                     fork=dict(meta))
            else:
                world = (recorded.snapshots[fork_point.config["configurable"]["checkpoint_id"]]
                         if arm == "fork" else left_behind)
                produced[arm] = _fork(case, change, trial, arm, fork_point, recorded.nodes[:step],
                                      tools.restored(world), saver, fork_llms, dict(meta))
            produced[arm]["exec_order"] = exec_order
            exec_order += 1
        rows += [produced["full"], produced["fork"], produced["fork_naive"]]  # emitted order is fixed
    return rows
