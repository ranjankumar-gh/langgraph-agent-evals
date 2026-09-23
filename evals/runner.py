"""Runs one (case, variant, trial) and applies every check layer.

Part 1 runner: a fresh in-memory checkpointer and a fresh database per run. Part 2
replaces this with a checkpointer-native runner.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import date

from langgraph.checkpoint.memory import InMemorySaver

from agent.graph import build_graph, run_agent
from agent.llm import LLM
from agent.tools import Tools
from env.db import create_db
from evals.checks.answer import answer_check, string_check
from evals.checks.end_state import check_end_state, observed_refunds
from evals.checks.trajectory import MATCH_MODES, check_constraints, match_trajectory
from evals.schema import Case


@dataclass
class RunRecord:
    case_id: str
    slice: str
    risk: str
    tags: list[str]
    variant: str
    trial: int
    seed: int
    node_sequence: list[str]
    tool_calls: list[dict]
    refunds: list[dict]
    final_message: str
    mutations_fired: list[str]
    crashed: str | None
    grading_error: str | None
    end_state_pass: bool
    end_state_detail: str
    constraints_pass: bool
    constraints_detail: str
    mode_pass: dict[str, bool]
    string_pass: bool
    judge_score: int
    judge_rationale: str
    answer_pass: bool
    elapsed_s: float


def run_case(case: Case, variant: str, trial: int, llm: LLM, judge: LLM) -> RunRecord:
    seed = trial
    conn = create_db(case.env)
    tools = Tools(conn, date.fromisoformat(case.env.today), dict(case.env.faults))
    fired: list[str] = []
    graph = build_graph(variant, llm, tools, seed=seed, fired=fired, checkpointer=InMemorySaver())
    started = time.perf_counter()
    nodes: list[str] = []
    final = ""
    crashed: str | None = None
    try:
        values, nodes = run_agent(
            graph,
            request=case.request,
            customer_id=case.customer_id,
            thread_id=f"{case.id}:{variant}:{trial}",
            approval=case.approval,
        )
        messages = values.get("messages", [])
        final = str(messages[-1].content) if len(messages) > 1 else ""
    except Exception as exc:  # every crash, including GraphRecursionError, is recorded as its own failure class
        crashed = f"{type(exc).__name__}: {exc}"
    calls = [c.name for c in tools.log]
    end = check_end_state(conn, case.end_states)
    constraints = check_constraints(calls, case.constraints)
    grading_error: str | None = None
    string_pass = False
    judge_score = 0
    judge_rationale = ""
    answer_pass = False
    try:
        answer = answer_check(judge, case, final, seed=seed)
        string_pass = answer.string_pass
        judge_score = answer.judge_score
        judge_rationale = answer.judge_rationale
        answer_pass = answer.passed and crashed is None
    except Exception as exc:
        grading_error = f"{type(exc).__name__}: {exc}"
        string_pass = string_check(final, case.answer).passed
        judge_score = 0
        judge_rationale = "grading error"
        answer_pass = False
    return RunRecord(
        case_id=case.id,
        slice=case.slice,
        risk=case.risk,
        tags=list(case.tags),
        variant=variant,
        trial=trial,
        seed=seed,
        node_sequence=nodes,
        tool_calls=[{"name": c.name, "args": c.args, "ok": c.ok, "error": c.error} for c in tools.log],
        refunds=observed_refunds(conn),
        final_message=final,
        mutations_fired=fired,
        crashed=crashed,
        grading_error=grading_error,
        end_state_pass=end.passed and crashed is None,
        end_state_detail=end.detail,
        constraints_pass=constraints.passed and crashed is None,
        constraints_detail=constraints.detail,
        mode_pass={m: match_trajectory(calls, case.reference_trajectory, m) for m in MATCH_MODES},
        string_pass=string_pass,
        judge_score=judge_score,
        judge_rationale=judge_rationale,
        answer_pass=answer_pass,
        elapsed_s=round(time.perf_counter() - started, 3),
    )
