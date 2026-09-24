"""Checkpoint-fork evaluation primitives.

Record a run with a world snapshot at every checkpoint, find where a change's fork starts,
check that the fork is a valid measurement, and run the change from there.

The five validity rules (docs/fork-validity.md) and where they live:
1. The fork point precedes the changed node - find_fork_point() takes the earliest
   checkpoint whose next node is the changed node, so it has not run yet.
2. Routing into the changed node is unchanged - check_routing() replays the change's
   routers over the baseline's recorded states.
3. A world snapshot is paired with every stored checkpoint - record_run().
4. Remaining bounds are carried into the fork - carried_limit(), applied by fork_run().
5. Fork from all k baseline trials - evals/runner_part2.py forks every trial.

Every stream uses durability="sync" so a checkpoint is saved before the next step starts.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from langchain_core.messages import HumanMessage
from langgraph.graph import END
from langgraph.types import Command

from agent.tools import Tools, WorldSnapshot

RECURSION_LIMIT = 25


@dataclass
class Recorded:
    values: dict
    nodes: list[str]
    snapshots: dict[str, WorldSnapshot]  # checkpoint_id -> the world right after that step


def _thread(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


def _drive(graph, payload, config: dict, nodes: list[str], on_step: Callable[[], None] | None = None) -> None:
    for chunk in graph.stream(payload, config, stream_mode="updates", durability="sync"):
        nodes.extend(key for key in chunk if key != "__interrupt__")
        if on_step is not None:
            on_step()


def record_run(graph, tools: Tools, *, request: str, customer_id: str, thread_id: str,
               approval: str | None, recursion_limit: int = RECURSION_LIMIT) -> Recorded:
    """Run one request to completion like agent.graph.run_agent, snapshotting the world after
    every step under the checkpoint id that step produced."""
    config = {**_thread(thread_id), "recursion_limit": recursion_limit}
    snapshots: dict[str, WorldSnapshot] = {}
    nodes: list[str] = []

    def snap() -> None:
        checkpoint_id = graph.get_state(config).config["configurable"]["checkpoint_id"]
        snapshots[checkpoint_id] = tools.snapshot()

    _drive(graph, {"messages": [HumanMessage(content=request)], "customer_id": customer_id}, config, nodes, snap)
    state = graph.get_state(config)
    if state.interrupts:
        _drive(graph, Command(resume=approval or "reject"), config, nodes, snap)
        state = graph.get_state(config)
    return Recorded(state.values, nodes, snapshots)


def history(graph, thread_id: str) -> list:
    """The thread's checkpoints, oldest first. Call before forking: forks add branches."""
    return list(reversed(list(graph.get_state_history(_thread(thread_id)))))


def find_fork_point(hist: list, changed_node: str):
    """The earliest checkpoint about to run changed_node, or None if the run never got there."""
    for state in hist:
        if state.next == (changed_node,):
            return state
    return None


def check_routing(hist: list, routers: dict[str, Callable[[dict], str]], until=None) -> tuple[bool, str]:
    """Replay a change's routers over the baseline's recorded steps.

    Covers the steps up to the fork point, or the whole run when there is no fork point. At
    each step the baseline took, the change must route the same way from the same state.
    The node that produced checkpoint i is hist[i-1].next[0]: checkpoint metadata carries
    no writes in langgraph 1.x."""
    for prev, cur in zip(hist, hist[1:]):
        if until is not None and prev.config["configurable"]["checkpoint_id"] == until.config["configurable"]["checkpoint_id"]:
            break
        if len(prev.next) != 1:
            continue
        node = prev.next[0]
        router = routers.get(node)
        if router is None:
            continue
        taken = cur.next[0] if cur.next else END
        wanted = router(cur.values)
        if wanted != taken:
            return False, f"after {node}: baseline went to {taken}, the change routes to {wanted}"
    return True, "ok"


def carried_limit(limit: int, fork_step: int) -> int:
    """The recursion budget that makes a fork stop where the full run would have.

    A fork starts with a fresh budget (verified on langgraph 1.2.12), so subtract the steps
    the baseline spent reaching the fork point: steps 0..fork_step."""
    return limit - (fork_step + 1)


def fork_run(graph, fork_point, *, approval: str | None, recursion_limit: int = RECURSION_LIMIT) -> tuple[dict, list[str]]:
    """Run `graph` (a change compiled on the baseline's checkpointer) from fork_point.

    Only the first invocation carries the budget. A resume after an approval interrupt gets
    a fresh one, exactly as the full-run driver's resume does. The resume targets the
    thread's latest checkpoint, which is this fork's pause."""
    thread_id = fork_point.config["configurable"]["thread_id"]
    nodes: list[str] = []
    first = {**fork_point.config, "recursion_limit": carried_limit(recursion_limit, fork_point.metadata["step"])}
    _drive(graph, None, first, nodes)
    latest = {**_thread(thread_id), "recursion_limit": recursion_limit}
    state = graph.get_state(latest)
    if state.interrupts:
        _drive(graph, Command(resume=approval or "reject"), latest, nodes)
        state = graph.get_state(latest)
    return state.values, nodes
