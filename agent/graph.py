"""The refund agent graph, its valid variants, and its seeded mutants.

Variants are selected by name so every variant shares one code path except the
lines that define it. Mutants record when their fault actually fired, so the eval
report can separate "the mutant ran" from "the mutant's fault happened".
"""
from __future__ import annotations

from langchain_core.messages import AIMessage, HumanMessage
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from agent.llm import LLM
from agent.prompts import (
    CLASSIFY_SYSTEM,
    COMPUTE_SYSTEM,
    RESPOND_SYSTEM,
    Classification,
    RefundDecision,
)
from agent.state import RefundState
from agent.tools import ToolError, Tools

APPROVAL_THRESHOLD = 1000.0
VALID_VARIANTS = ("baseline", "alt_history_early", "alt_recheck")
MUTANTS = ("A", "B", "C")
VARIANTS = VALID_VARIANTS + MUTANTS


def refund_amount(refund_type: str, price: float) -> float:
    return round(price * 0.5, 2) if refund_type == "partial" else round(price, 2)


def render_facts(state: dict, *, status_from_plan: bool = False) -> str:
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
        lines.append(f"Planned refund: {state['refund_type']} of {state['refund_amount']:.2f}")
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


def build_graph(variant: str, llm: LLM, tools: Tools, *, seed: int, fired: list[str], checkpointer):
    if variant not in VARIANTS:
        raise ValueError(f"unknown variant {variant!r}; expected one of {VARIANTS}")

    def redundant_lookup(state: RefundState) -> None:
        fired.append("C:redundant_lookup")
        try:
            tools.lookup_order(state["order_id"], state["customer_id"])
        except ToolError:
            pass

    def classify_request(state: RefundState) -> dict:
        result = llm.structured(CLASSIFY_SYSTEM, state["messages"][-1].content, Classification, seed=seed)
        return {"intent": result.intent, "order_id": result.order_id}

    def lookup_order(state: RefundState) -> dict:
        try:
            order = tools.lookup_order(state["order_id"], state["customer_id"])
        except ToolError as exc:
            return {"order": None, "error": str(exc)}
        if order is None:
            return {"order": None, "error": f"no order {state['order_id']} was found for this customer"}
        return {"order": order}

    def get_refund_history(state: RefundState) -> dict:
        try:
            return {"prior_refunds": tools.get_refund_history(state["customer_id"])}
        except ToolError as exc:
            return {"error": str(exc)}

    def check_eligibility(state: RefundState) -> dict:
        if variant == "C":
            redundant_lookup(state)
        return {"eligibility": tools.check_eligibility(state["order"], state["prior_refunds"])}

    def compute_refund(state: RefundState) -> dict:
        if variant == "C":
            redundant_lookup(state)
        order = state["order"]
        user = (
            f"Customer message: {state['messages'][0].content}\n"
            f"Order: {order['item']} ({order['category']}), price {order['price']:.2f}\n"
            f"Order notes: {order['notes'] or '(none)'}"
        )
        decision = llm.structured(COMPUTE_SYSTEM, user, RefundDecision, seed=seed)
        return {
            "refund_type": decision.refund_type,
            "refund_amount": refund_amount(decision.refund_type, order["price"]),
        }

    def request_approval(state: RefundState) -> dict:
        # No tool calls in this node: its body re-runs from the top when the interrupt resumes.
        decision = interrupt({"order_id": state["order_id"], "amount": state["refund_amount"]})
        return {"approval": decision}

    def issue_refund(state: RefundState) -> dict:
        if variant == "C":
            redundant_lookup(state)
        if variant == "alt_recheck":
            try:
                tools.lookup_order(state["order_id"], state["customer_id"])
            except ToolError as exc:
                return {"error": str(exc)}
        try:
            refund_id = tools.issue_refund(
                state["order_id"], state["customer_id"], state["refund_type"], state["refund_amount"]
            )
        except ToolError as exc:
            return {"error": str(exc)}
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
        facts = render_facts(state, status_from_plan=bool(false_success))
        return {"messages": [AIMessage(content=llm.text(RESPOND_SYSTEM, facts, seed=seed))]}

    def after_classify(state: RefundState) -> str:
        if not state.get("order_id"):
            return "respond"
        return "get_refund_history" if variant == "alt_history_early" else "lookup_order"

    def after_lookup(state: RefundState) -> str:
        if state.get("error"):
            return "respond"
        return "check_eligibility" if variant == "alt_history_early" else "get_refund_history"

    def after_history(state: RefundState) -> str:
        if state.get("error"):
            return "respond"
        if variant == "alt_history_early":
            return "lookup_order"
        if variant == "A" and state.get("intent") == "damaged":
            fired.append("A:skipped_eligibility")
            return "compute_refund"
        return "check_eligibility"

    def after_eligibility(state: RefundState) -> str:
        return "compute_refund" if state["eligibility"]["eligible"] else "respond"

    def after_compute(state: RefundState) -> str:
        return "request_approval" if state["refund_amount"] > APPROVAL_THRESHOLD else "issue_refund"

    def after_approval(state: RefundState) -> str:
        return "issue_refund" if state.get("approval") == "approve" else "respond"

    graph = StateGraph(RefundState)
    for node in (
        classify_request, lookup_order, get_refund_history, check_eligibility,
        compute_refund, request_approval, issue_refund, respond,
    ):
        graph.add_node(node.__name__, node)
    graph.add_edge(START, "classify_request")
    graph.add_conditional_edges("classify_request", after_classify, ["lookup_order", "get_refund_history", "respond"])
    graph.add_conditional_edges("lookup_order", after_lookup, ["get_refund_history", "check_eligibility", "respond"])
    graph.add_conditional_edges(
        "get_refund_history", after_history, ["lookup_order", "check_eligibility", "compute_refund", "respond"]
    )
    graph.add_conditional_edges("check_eligibility", after_eligibility, ["compute_refund", "respond"])
    graph.add_conditional_edges("compute_refund", after_compute, ["request_approval", "issue_refund"])
    graph.add_conditional_edges("request_approval", after_approval, ["issue_refund", "respond"])
    graph.add_edge("issue_refund", "respond")
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
