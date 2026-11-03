"""The refund agent graph, its valid variants, and its seeded mutants.

Variants are selected by name so every variant shares one code path except the
lines that define it. Mutants record when their fault actually fired, so the eval
report can separate "the mutant ran" from "the mutant's fault happened".
"""
from __future__ import annotations

from typing import Callable

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent.llm import LLM
from agent.prompts import (
    CLASSIFY_SYSTEM,
    COMPUTE_SYSTEM,
    COMPUTE_SYSTEM_D,
    RESPOND_SYSTEM,
    Classification,
    RefundDecision,
)
from agent.state import RefundState
from datetime import date

from agent.tools import REFUND_WINDOW_DAYS, ToolError, Tools

APPROVAL_THRESHOLD = 1000.0
VALID_VARIANTS = ("baseline", "alt_history_early", "alt_recheck", "alt_verify")
MUTANTS = ("A", "B", "C", "C1", "C2")
# Part 1.2: mutants authored by a session that never saw the evaluation
# (docs/part-1.2-preregistration.md). Not in VARIANTS, so earlier runs and CLI defaults are unchanged.
INDEPENDENT_MUTANTS = ("M1", "M2", "M3", "M4", "M5", "M6", "M7", "M8")
# Part 1.3: valid alternates authored by a session that never saw the evaluation
# (docs/part-1.3-preregistration.md). Not in VARIANTS, so earlier runs and CLI defaults are unchanged.
INDEPENDENT_VALID = ("V1", "V2", "V3", "V4", "V5", "V6")
VARIANTS = VALID_VARIANTS + MUTANTS

# Part 2 changes under test. Not part of VARIANTS, so Part 1's runs and CLI defaults are unchanged.
CHANGES = ("D", "E")
ALL_VARIANTS = VARIANTS + CHANGES + INDEPENDENT_MUTANTS + INDEPENDENT_VALID
# The node each change edits, i.e. where a fork of that change starts. "baseline" is the
# no-op control change: forking the unchanged agent into itself.
CHANGED_NODE = {"baseline": "compute_refund", "D": "compute_refund", "E": "compute_refund"}


def refund_amount(refund_type: str, price: float) -> float:
    return round(price * 0.5, 2) if refund_type == "partial" else round(price, 2)


def render_facts(state: dict, *, status_from_plan: bool = False, amount_from_price: bool = False) -> str:
    lines = [f"Customer message: {state['messages'][0].content}"]
    if not state.get("order_id"):
        lines.append("Order id: not provided")
    order = state.get("order")
    if order:
        lines.append(f"Order: {order['order_id']} - {order['item']}, price {order['price']:.2f}")
        lines.append(f"Order notes: {order['notes'] or '(none)'}")
    eligibility = state.get("eligibility")
    if eligibility and not eligibility["eligible"]:
        lines.append(f"Eligibility: not eligible - {eligibility['reason']}")
    if state.get("refund_amount") is not None:
        # M8: a stale variable renders the order price instead of the planned amount.
        shown = state["order"]["price"] if amount_from_price and state.get("order") else state["refund_amount"]
        lines.append(f"Planned refund: {state['refund_type']} of {shown:.2f}")
    if state.get("approval") == "reject":
        lines.append("Approval: rejected by a supervisor")
    if status_from_plan:
        lines.append(f"Refund status: issued ({state['refund_type']}, {state['refund_amount']:.2f})")
    elif state.get("refund_id"):
        lines.append(f"Refund status: issued as {state['refund_id']}")
    else:
        lines.append("Refund status: not issued")
        if state.get("error"):
            lines.append(f"Error: {state['error']}")
    return "\n".join(lines)


def make_routers(variant: str, fired: list[str]) -> dict[str, Callable[[dict], str]]:
    """The graph's conditional edges for a variant, keyed by source node.

    Pure functions of state (apart from recording fault markers in `fired`), so the Part 2
    fork harness can replay a change's routing over a baseline's recorded states."""

    def after_classify(state: RefundState) -> str:
        if not state.get("order_id"):
            return "respond"
        if variant == "V6":
            return "gate"
        return "get_refund_history" if variant == "alt_history_early" else "lookup_order"

    def after_lookup(state: RefundState) -> str:
        if state.get("error"):
            return "respond"
        if variant == "V2":
            # V2: history was fetched together with the order, so go straight to eligibility.
            return "check_eligibility"
        if variant == "V4":
            # V4: compute the refund speculatively while history and eligibility are read.
            return "compute_refund"
        # M2 (reordered edge): eligibility is checked before refund history is read.
        return "check_eligibility" if variant in ("alt_history_early", "M2") else "get_refund_history"

    def after_history(state: RefundState) -> str:
        if state.get("error"):
            return "discard_plan" if variant == "V4" else "respond"
        if variant == "alt_history_early":
            return "lookup_order"
        if variant == "M2":
            return "compute_refund"
        if variant == "A" and state.get("intent") == "damaged":
            fired.append("A:skipped_eligibility")
            return "compute_refund"
        return "check_eligibility"

    def after_eligibility(state: RefundState) -> str:
        if variant == "V4":
            if state.get("error") or not state["eligibility"]["eligible"]:
                return "discard_plan"
            if state.get("refund_amount") is None:
                # The speculative compute failed: compute again where the baseline does.
                return "compute_refund"
            return after_compute(state)
        if state.get("error"):
            return "respond"
        if state["eligibility"]["eligible"]:
            return "get_refund_history" if variant == "M2" else "compute_refund"
        if variant == "E" and state.get("intent") == "damaged":
            # Change E: a "damaged items fast path" shipped in the same PR as D's prompt change.
            # It routes ineligible damaged orders into compute_refund instead of refusing them.
            fired.append("E:damaged_fast_path")
            return "compute_refund"
        return "respond"

    def after_compute(state: RefundState) -> str:
        if variant == "V4" and "eligibility" not in state:
            return "get_refund_history"
        if variant == "V5":
            return "authorize_and_issue"
        return "request_approval" if state["refund_amount"] > APPROVAL_THRESHOLD else "issue_refund"

    def after_approval(state: RefundState) -> str:
        if variant == "M4":
            # M4: compares against the wrong literal; the interrupt resumes with "reject".
            if state.get("approval") == "reject":
                fired.append("M4:rejection_not_honoured")
            return "respond" if state.get("approval") == "rejected" else "issue_refund"
        return "issue_refund" if state.get("approval") == "approve" else "respond"

    def after_gate(state: RefundState) -> str:
        # V6: one conditional edge out of the gate.
        if state.get("error") or not state.get("eligibility", {}).get("eligible"):
            return "respond"
        return "compute_refund"

    return {
        "classify_request": after_classify,
        "lookup_order": after_lookup,
        "get_refund_history": after_history,
        "check_eligibility": after_eligibility,
        "compute_refund": after_compute,
        "request_approval": after_approval,
    } | ({"gate": after_gate} if variant == "V6" else {})


def build_graph(variant: str, llm: LLM, tools: Tools, *, seed: int, fired: list[str], checkpointer):
    if variant not in ALL_VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected one of {ALL_VARIANTS}")

    def redundant_lookup(state: RefundState) -> None:
        fired.append("C:redundant_lookup")
        try:
            tools.lookup_order(state["order_id"], state["customer_id"])
        except ToolError:
            pass

    def classify_request(state: RefundState) -> dict:
        result = llm.structured(CLASSIFY_SYSTEM, state["messages"][-1].content, Classification, seed=seed)
        return {"intent": result.intent, "order_id": result.order_id}

    def read(tool, *args):
        """V1: retry a read tool once on a tool error; the second error propagates."""
        try:
            return tool(*args)
        except ToolError:
            if variant != "V1":
                raise
            fired.append(f"V1:retried_{tool.__name__}")
            return tool(*args)

    def lookup_order(state: RefundState) -> dict:
        if variant == "V2":
            return fetch_context(state)
        try:
            order = read(tools.lookup_order, state["order_id"], state["customer_id"])
        except ToolError as exc:
            return {"order": None, "error": str(exc)}
        if order is None and variant == "M3":
            # M3: "guest checkout" fallback - looks the order up without the owner filter.
            fired.append("M3:ownerless_lookup")
            try:
                order = tools.lookup_order(state["order_id"], None)
            except ToolError as exc:
                return {"order": None, "error": str(exc)}
        if order is None:
            return {"order": None, "error": f"no order {state['order_id']} was found for this customer"}
        return {"order": order}

    def fetch_context(state: RefundState) -> dict:
        # V2: order and refund history fetched together; the order result takes priority, and
        # prior_refunds is written only when the run goes on to eligibility.
        try:
            order, order_exc = tools.lookup_order(state["order_id"], state["customer_id"]), None
        except ToolError as exc:
            order, order_exc = None, exc
        try:
            history, history_exc = tools.get_refund_history(state["customer_id"]), None
        except ToolError as exc:
            history, history_exc = None, exc
        if order_exc is not None:
            fired.append("V2:history_read_on_failed_lookup")
            return {"order": None, "error": str(order_exc)}
        if order is None:
            fired.append("V2:history_read_on_failed_lookup")
            return {"order": None, "error": f"no order {state['order_id']} was found for this customer"}
        if history_exc is not None:
            return {"order": order, "error": str(history_exc)}
        return {"order": order, "prior_refunds": history}

    def get_refund_history(state: RefundState) -> dict:
        try:
            return {"prior_refunds": read(tools.get_refund_history, state["customer_id"])}
        except ToolError as exc:
            return {"error": str(exc)}

    def check_eligibility(state: RefundState) -> dict:
        if variant == "C":
            redundant_lookup(state)
        if variant == "C1":
            # One misplaced redundant read, and only one: fits under a lookup_order cap of 2.
            fired.append("C1:redundant_lookup")
            try:
                tools.lookup_order(state["order_id"], state["customer_id"])
            except ToolError:
                pass
        if variant == "C2":
            # Redundant read of a different tool, one no position rule on lookup_order covers.
            fired.append("C2:redundant_history")
            try:
                tools.get_refund_history(state["customer_id"])
            except ToolError:
                pass
        window = REFUND_WINDOW_DAYS
        if variant == "M2":
            # M2: history has not been read yet, so the count defaults to 0.
            fired.append("M2:eligibility_before_history")
            prior = state.get("prior_refunds") or 0
        else:
            prior = state["prior_refunds"]
        if variant == "M1":
            # M1: off-by-one "timezone slop" on the 30-day window.
            window = REFUND_WINDOW_DAYS + 1
            delivered_on = state["order"].get("delivered_on")
            if delivered_on and (tools.today - date.fromisoformat(delivered_on)).days == REFUND_WINDOW_DAYS + 1:
                fired.append("M1:window_off_by_one")
        try:
            if variant == "V1":
                return {"eligibility": read(tools.check_eligibility, state["order"], prior)}
            return {"eligibility": tools.check_eligibility(state["order"], prior, window_days=window)}
        except ToolError as exc:
            return {"error": str(exc)}

    def gate(state: RefundState) -> dict:
        # V6: lookup, history and eligibility in one node, same order and stop rules as today.
        try:
            order = tools.lookup_order(state["order_id"], state["customer_id"])
        except ToolError as exc:
            return {"order": None, "error": str(exc)}
        if order is None:
            return {"order": None, "error": f"no order {state['order_id']} was found for this customer"}
        try:
            history = tools.get_refund_history(state["customer_id"])
        except ToolError as exc:
            return {"order": order, "error": str(exc)}
        try:
            eligibility = tools.check_eligibility(order, history)
        except ToolError as exc:
            return {"order": order, "prior_refunds": history, "error": str(exc)}
        return {"order": order, "prior_refunds": history, "eligibility": eligibility}

    speculative_failure: list[Exception] = []

    def discard_plan(state: RefundState) -> dict:
        # V4: eligibility failed or errored, so the speculative plan never reaches the reply.
        if state.get("refund_amount") is not None:
            fired.append("V4:speculative_plan_discarded")
        return {"refund_type": None, "refund_amount": None}

    def check_speculation(state: RefundState) -> None:
        if variant == "V4" and speculative_failure and state.get("refund_amount") is None:
            raise speculative_failure[0]

    def compute_refund(state: RefundState) -> dict:
        if variant == "C":
            redundant_lookup(state)
        order = state["order"]
        user = (
            f"Customer message: {state['messages'][0].content}\n"
            f"Order: {order['item']} ({order['category']}), price {order['price']:.2f}\n"
            f"Order notes: {order['notes'] or '(none)'}"
        )
        system = COMPUTE_SYSTEM_D if variant in CHANGES else COMPUTE_SYSTEM
        if variant == "V4" and "eligibility" not in state:
            # A failed speculative compute is ignored unless the order turns out eligible.
            try:
                decision = llm.structured(system, user, RefundDecision, seed=seed)
            except Exception as exc:  # noqa: BLE001 - re-raised at the join if it matters
                speculative_failure.append(exc)
                return {}
        else:
            decision = llm.structured(system, user, RefundDecision, seed=seed)
        amount = refund_amount(decision.refund_type, order["price"])
        if variant == "M5":
            # M5: "normalised to int for the payments API".
            half = order["price"] * 0.5
            truncated = float(int(half)) if decision.refund_type == "partial" else float(int(order["price"]))
            if truncated != amount:
                fired.append("M5:amount_truncated")
            amount = truncated
        return {"refund_type": decision.refund_type, "refund_amount": amount}

    def request_approval(state: RefundState) -> dict:
        # No tool calls in this node: its body re-runs from the top when the interrupt resumes.
        decision = interrupt({"order_id": state["order_id"], "amount": state["refund_amount"]})
        return {"approval": decision}

    def authorize_and_issue(state: RefundState) -> dict:
        # V5: approval and the write in one node. Only pure checks come before interrupt(),
        # because the node re-runs from the top when the interrupt resumes.
        if state.get("refund_id"):
            return {}
        update: dict = {}
        if state["refund_amount"] > APPROVAL_THRESHOLD:
            decision = interrupt({"order_id": state["order_id"], "amount": state["refund_amount"]})
            update["approval"] = decision
            if decision != "approve":
                return update
        try:
            update["refund_id"] = tools.issue_refund(
                state["order_id"], state["customer_id"], state["refund_type"], state["refund_amount"]
            )
        except ToolError as exc:
            update["error"] = str(exc)
        return update

    def reconcile(state: RefundState) -> dict:
        # V3: re-read refund history after the write, for logging only; never writes state.
        fired.append("V3:reconcile_read")
        try:
            tools.get_refund_history(state["customer_id"])
        except ToolError:
            pass
        return {}

    def issue_refund(state: RefundState) -> dict:
        check_speculation(state)
        if variant == "C":
            redundant_lookup(state)
        if variant == "alt_recheck":
            try:
                tools.lookup_order(state["order_id"], state["customer_id"])
            except ToolError as exc:
                return {"error": str(exc)}
        if variant == "alt_verify":
            # Same re-read as alt_recheck, but its result is used: stop if the order changed.
            try:
                current = tools.lookup_order(state["order_id"], state["customer_id"])
            except ToolError as exc:
                return {"error": str(exc)}
            before = state["order"]["price"]
            if current is None or current["price"] != before:
                now = "missing" if current is None else f"{current['price']:.2f}"
                return {"error": f"the order changed after it was first read (price {before:.2f} -> {now}); "
                                  f"refund not issued"}
        refund_type = state["refund_type"]
        if variant == "M6":
            # M6: refund_type dropped in a refactor; the payments default "full" applies.
            if refund_type != "full":
                fired.append("M6:refund_type_dropped")
            refund_type = "full"
        try:
            refund_id = tools.issue_refund(
                state["order_id"], state["customer_id"], refund_type, state["refund_amount"]
            )
        except ToolError as exc:
            if variant != "M7":
                return {"error": str(exc)}
            # M7: one blind retry for "flaky payments", no idempotency key.
            fired.append("M7:blind_retry")
            try:
                refund_id = tools.issue_refund(
                    state["order_id"], state["customer_id"], refund_type, state["refund_amount"]
                )
            except ToolError as exc2:
                return {"error": str(exc2)}
        return {"refund_id": refund_id}

    def respond(state: RefundState) -> dict:
        false_success = (
            variant == "B"
            and state.get("error")
            and state.get("refund_amount") is not None
            and not state.get("refund_id")
        )
        if false_success:
            fired.append("B:false_success")
        partial_planned = state.get("refund_type") == "partial" and state.get("refund_amount") is not None
        if variant == "M8" and partial_planned:
            fired.append("M8:price_rendered_as_amount")
        facts = render_facts(state, status_from_plan=bool(false_success), amount_from_price=variant == "M8")
        return {"messages": [AIMessage(content=llm.text(RESPOND_SYSTEM, facts, seed=seed))]}

    routers = make_routers(variant, fired)

    if variant == "V6":
        return _assemble_v6(classify_request, gate, compute_refund, request_approval, issue_refund, respond,
                            routers, checkpointer)
    if variant == "V5":
        return _assemble_v5(classify_request, lookup_order, get_refund_history, check_eligibility,
                            compute_refund, authorize_and_issue, respond, routers, checkpointer)

    graph = StateGraph(RefundState)
    for node in (
        classify_request, lookup_order, get_refund_history, check_eligibility,
        compute_refund, request_approval, issue_refund, respond,
    ):
        graph.add_node(node.__name__, node)
    if variant == "V4":
        graph.add_node("discard_plan", discard_plan)
        graph.add_edge("discard_plan", "respond")
    if variant == "V3":
        graph.add_node("reconcile", reconcile)
    graph.add_edge(START, "classify_request")
    graph.add_conditional_edges(
        "classify_request", routers["classify_request"], ["lookup_order", "get_refund_history", "respond"]
    )
    v4 = ["discard_plan"] if variant == "V4" else []
    graph.add_conditional_edges(
        "lookup_order", routers["lookup_order"],
        ["get_refund_history", "check_eligibility", "respond"] + (["compute_refund"] if v4 else []),
    )
    graph.add_conditional_edges(
        "get_refund_history",
        routers["get_refund_history"],
        ["lookup_order", "check_eligibility", "compute_refund", "respond"] + v4,
    )
    graph.add_conditional_edges(
        "check_eligibility", routers["check_eligibility"],
        ["compute_refund", "get_refund_history", "respond"] + (v4 + ["request_approval", "issue_refund"] if v4 else []),
    )
    graph.add_conditional_edges(
        "compute_refund", routers["compute_refund"],
        ["request_approval", "issue_refund"] + (["get_refund_history"] if v4 else []),
    )
    graph.add_conditional_edges("request_approval", routers["request_approval"], ["issue_refund", "respond"])
    if variant == "V3":
        graph.add_edge("issue_refund", "reconcile")
        graph.add_edge("reconcile", "respond")
    else:
        graph.add_edge("issue_refund", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def _assemble_v6(classify_request, gate, compute_refund, request_approval, issue_refund, respond, routers,
                 checkpointer):
    graph = StateGraph(RefundState)
    for node in (classify_request, gate, compute_refund, request_approval, issue_refund, respond):
        graph.add_node(node.__name__, node)
    graph.add_edge(START, "classify_request")
    graph.add_conditional_edges("classify_request", routers["classify_request"], ["gate", "respond"])
    graph.add_conditional_edges("gate", routers["gate"], ["compute_refund", "respond"])
    graph.add_conditional_edges("compute_refund", routers["compute_refund"], ["request_approval", "issue_refund"])
    graph.add_conditional_edges("request_approval", routers["request_approval"], ["issue_refund", "respond"])
    graph.add_edge("issue_refund", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def _assemble_v5(classify_request, lookup_order, get_refund_history, check_eligibility, compute_refund,
                 authorize_and_issue, respond, routers, checkpointer):
    graph = StateGraph(RefundState)
    for node in (classify_request, lookup_order, get_refund_history, check_eligibility, compute_refund,
                 authorize_and_issue, respond):
        graph.add_node(node.__name__, node)
    graph.add_edge(START, "classify_request")
    graph.add_conditional_edges("classify_request", routers["classify_request"], ["lookup_order", "respond"])
    graph.add_conditional_edges("lookup_order", routers["lookup_order"], ["get_refund_history", "respond"])
    graph.add_conditional_edges("get_refund_history", routers["get_refund_history"],
                                ["check_eligibility", "respond"])
    graph.add_conditional_edges("check_eligibility", routers["check_eligibility"], ["compute_refund", "respond"])
    graph.add_conditional_edges("compute_refund", routers["compute_refund"], ["authorize_and_issue"])
    graph.add_edge("authorize_and_issue", "respond")
    graph.add_edge("respond", END)
    return graph.compile(checkpointer=checkpointer)


def run_agent(graph, *, request: str, customer_id: str, thread_id: str, approval: str | None) -> tuple[dict, list[str]]:
    """Run one request to completion, answering at most one approval interrupt with `approval`."""
    config = {"configurable": {"thread_id": thread_id}, "recursion_limit": 25}
    nodes: list[str] = []

    def stream(payload) -> None:
        for chunk in graph.stream(payload, config, stream_mode="updates"):
            nodes.extend(key for key in chunk if key != "__interrupt__")

    stream({"messages": [HumanMessage(content=request)], "customer_id": customer_id})
    snapshot = graph.get_state(config)
    if snapshot.interrupts:
        stream(Command(resume=approval or "reject"))
        snapshot = graph.get_state(config)
    return snapshot.values, nodes
