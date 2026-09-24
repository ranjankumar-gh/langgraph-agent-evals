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


def namespace(arm: str, change: str) -> str:
    """The cache namespace an arm draws from.

    The baseline keeps the un-namespaced cache, so it replays Part 1's draws where they
    exist. Every full rerun and every fork draws fresh. E shares D's namespaces, so on every
    path where E behaves like D it replays D's draws, and any E-versus-D difference comes
    from the routing change alone. fork_naive shares its change's fork namespace, so the
    naive and the paired fork see the same compute_refund decision and differ only in the
    world."""
    if arm == "baseline":
        return ""
    family = "D" if change == "E" else change
    return f"p2-{'fork' if arm.startswith('fork') else 'full'}-{family}"


def namespaces_for(changes: list[str]) -> list[str]:
    return sorted({namespace("baseline", "baseline")} | {namespace(a, c) for c in changes for a in ("full", "fork")})


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
    except Exception as exc:  # a GraphRecursionError under the carried budget is a result, not a harness bug
        crashed = f"{type(exc).__name__}: {exc}"
    rec = grade_run(case, change, trial, conn=tools.conn, tools=tools, nodes=nodes, final=final,
                    fired=fired, crashed=crashed, judge=llms.judge, started=started)
    return _row(arm, change, rec, cost=_cost(llms, before), fork=meta)


def run_group(case: Case, trial: int, changes: list[str], llms: dict[str, ArmLLMs]) -> list[dict]:
    thread_id = f"{case.id}:{trial}"
    saver = InMemorySaver()
    base_llms = llms[namespace("baseline", "baseline")]
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
    rows = [_row("baseline", "baseline", base, cost=_cost(base_llms, before))]

    hist = history(graph, thread_id) if recorded else []  # before any fork adds branches
    left_behind = tools.snapshot()
    for change in changes:
        rows.append(_full(case, change, trial, llms[namespace("full", change)]))
        fork_llms = llms[namespace("fork", change)]
        fork_point = find_fork_point(hist, CHANGED_NODE[change])
        if recorded:
            routing_ok, routing_detail = check_routing(hist, make_routers(change, []), until=fork_point)
        else:
            routing_ok, routing_detail = False, "baseline crashed"
        step = fork_point.metadata["step"] if fork_point else None
        meta = {"fork_point_step": step, "inherited": fork_point is None, "routing_ok": routing_ok,
                "routing_detail": routing_detail,
                "carried_limit": carried_limit(RECURSION_LIMIT, step) if fork_point else None}
        for arm in ("fork", "fork_naive"):
            if fork_point is None:
                inherited = replace(base, variant=change, elapsed_s=0.0)
                rows.append(_row(arm, change, inherited, cost={"policy": dict(_ZERO), "judge": dict(_ZERO)}, fork=dict(meta)))
                continue
            if arm == "fork":
                world = recorded.snapshots[fork_point.config["configurable"]["checkpoint_id"]]
            else:
                world = left_behind
            rows.append(_fork(case, change, trial, arm, fork_point, recorded.nodes[:step], tools.restored(world),
                              saver, fork_llms, dict(meta)))
    return rows
