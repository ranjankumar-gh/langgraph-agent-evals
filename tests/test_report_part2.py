from evals.report_part2 import (
    case_bootstrap_mean, cost_table, forkable_pairs, full_control_identical_reply_rate, paired_delta,
    render_markdown_part2, routing_change, summarize_part2, variance_ratio, wrong_verdicts,
)


def usage(calls=1, hits=0, unmetered=0, tin=100, tout=20, seconds=1.0):
    return {"calls": calls, "hits": hits, "input_tokens": tin, "output_tokens": tout,
            "unmetered": unmetered, "seconds": seconds}


SAME_DECISION = {"refund_type": "full", "refund_amount": 149.0}


def row(arm, change, case, trial=0, *, end=True, cons=True, answer=True, judge=5, inherited=False,
        routing_ok=True, hits=0, unmetered=0, calls=3, elapsed=2.0, crashed=None, grading_error=None,
        baseline_crashed=False, decision=SAME_DECISION, final_message="ok"):
    fork = None
    if arm.startswith("fork"):
        fork = {"fork_point_step": None if inherited else 4, "inherited": inherited, "routing_ok": routing_ok,
                "routing_detail": "ok" if routing_ok else "after check_eligibility: ...", "carried_limit": 20,
                "baseline_crashed": baseline_crashed, "decision": None if crashed else decision}
    return {
        "arm": arm, "change": change, "case_id": case, "trial": trial, "crashed": crashed,
        "grading_error": grading_error, "answer_pass": answer, "end_state_pass": end, "constraints_pass": cons,
        "mode_pass": {"strict": True, "unordered": True, "subset": True, "superset": True},
        "judge_score": judge, "elapsed_s": elapsed, "mutations_fired": [], "final_message": final_message,
        "cost": {"policy": usage(calls=calls, hits=hits, unmetered=unmetered), "judge": usage()}, "fork": fork,
    }


def test_forkable_pairs_skip_inherited_rows():
    rows = [row("fork", "D", "A1"), row("fork", "D", "A2", inherited=True), row("fork", "E", "A3")]
    assert forkable_pairs(rows, "D") == [("A1", 0)]


def test_cost_table_counts_only_metered_forkable_rows():
    rows = [
        row("fork", "D", "A1", calls=2, elapsed=1.0), row("full", "D", "A1", calls=4, elapsed=3.0),
        row("fork", "D", "A2", calls=2, elapsed=1.0), row("full", "D", "A2", hits=1),
        row("fork", "D", "A3", inherited=True), row("full", "D", "A3", calls=4),
        row("fork", "D", "A4", unmetered=1), row("full", "D", "A4", calls=4, elapsed=5.0),
    ]
    table = cost_table(rows, "D")
    assert (table["fork"]["n"], table["fork"]["excluded"]) == (2, 1)
    assert (table["full"]["n"], table["full"]["excluded"]) == (2, 1)
    assert table["full"]["policy_calls"] == 8 and table["fork"]["policy_calls"] == 4
    assert table["full"]["wall_s_total"] == 8.0 and table["full"]["wall_s_median"] == 4.0
    assert table["fork"]["input_tokens"] == 400  # (100 policy + 100 judge) x 2 rows


def test_case_bootstrap_mean_is_degenerate_on_constant_units():
    assert case_bootstrap_mean([("A", 0.0), ("B", 0.0)]) == (0.0, 0.0)
    assert case_bootstrap_mean([]) == (0.0, 0.0)


def test_paired_delta_width_reflects_the_spread_of_differences():
    rows = []
    for i, full_end in enumerate([True, False, True, False, True, False]):
        case = f"C{i}"
        rows += [row("baseline", "baseline", case), row("fork", "baseline", case),
                 row("full", "baseline", case, end=full_end)]
    fork = paired_delta(rows, "baseline", "fork", "three_artifact")
    full = paired_delta(rows, "baseline", "full", "three_artifact")
    assert fork["n"] == full["n"] == 6
    assert fork["mean"] == 0.0 and fork["width"] == 0.0
    assert full["mean"] == -0.5 and full["width"] > 0


def test_paired_delta_skips_grading_errors():
    rows = [row("baseline", "baseline", "C1"), row("fork", "D", "C1", grading_error="boom"),
            row("baseline", "baseline", "C2"), row("fork", "D", "C2", judge=3)]
    out = paired_delta(rows, "D", "fork", "judge_score")
    assert out["n"] == 1 and out["mean"] == -2.0


def test_wrong_verdicts_counts_direction_per_layer():
    rows = [
        row("fork", "baseline", "C1"), row("fork_naive", "baseline", "C1", end=False, cons=False),
        row("fork", "baseline", "C2"), row("fork_naive", "baseline", "C2"),
        row("fork", "baseline", "C3", end=False), row("fork_naive", "baseline", "C3"),
    ]
    out = wrong_verdicts(rows, "baseline")
    assert out["end_state"] == {"n": 3, "agree": 1, "naive_fail_paired_pass": 1, "naive_pass_paired_fail": 1, "excluded": 0}
    assert out["constraints"] == {"n": 3, "agree": 2, "naive_fail_paired_pass": 1, "naive_pass_paired_fail": 0, "excluded": 0}
    assert out["answer"] == {"n": 3, "agree": 3, "naive_fail_paired_pass": 0, "naive_pass_paired_fail": 0, "excluded": 0}


def test_wrong_verdicts_excludes_pairs_whose_decisions_disagree():
    rows = [
        row("fork", "baseline", "C1"), row("fork_naive", "baseline", "C1"),  # same decision (default)
        row("fork", "baseline", "C2", decision={"refund_type": "full", "refund_amount": 149.0}),
        row("fork_naive", "baseline", "C2", end=False, decision={"refund_type": "partial", "refund_amount": 74.5}),
    ]
    out = wrong_verdicts(rows, "baseline")
    for layer in ("end_state", "constraints", "answer", "three_artifact"):
        assert out[layer]["n"] == 1
        assert out[layer]["excluded"] == 1  # C2's disagreeing decision is excluded, not counted as a wrong verdict


def test_wrong_verdicts_excludes_a_crashed_row_even_with_a_matching_decision():
    rows = [
        row("fork", "baseline", "C1"), row("fork_naive", "baseline", "C1"),
        row("fork", "baseline", "C2", crashed="RuntimeError: boom"), row("fork_naive", "baseline", "C2"),
    ]
    out = wrong_verdicts(rows, "baseline")
    assert out["end_state"]["n"] == 1 and out["end_state"]["excluded"] == 1


def test_routing_change_finds_a_regression_the_fork_hides_and_the_check_flags():
    rows = [
        row("baseline", "baseline", "I1"), row("full", "E", "I1", end=False),
        row("fork", "E", "I1", inherited=True, routing_ok=False),
        row("baseline", "baseline", "H1"), row("full", "E", "H1"), row("fork", "E", "H1"),
    ]
    out = routing_change(rows, "E")
    assert out["full_regressions"] == ["I1/t0"]
    assert out["fork_regressions"] == []
    assert out["hidden_by_fork"] == ["I1/t0"]
    assert out["routing_flagged"] == ["I1/t0"]
    assert out["hidden_and_flagged"] == ["I1/t0"]


def test_routing_change_excludes_a_baseline_crashed_pair_from_flagged():
    rows = [
        row("baseline", "baseline", "I1"), row("full", "E", "I1", end=False),
        row("fork", "E", "I1", inherited=True, routing_ok=False, baseline_crashed=True),
    ]
    out = routing_change(rows, "E")
    assert out["routing_flagged"] == []  # baseline crashed, not a routing-check catch


def test_routing_change_reports_hidden_by_fast_path():
    rows = [
        row("baseline", "baseline", "I1"), row("full", "E", "I1", end=False),
        row("fork", "E", "I1", inherited=True),
    ]
    rows[1]["mutations_fired"] = ["E:damaged_fast_path"]
    out = routing_change(rows, "E")
    assert out["hidden_by_fork"] == ["I1/t0"]
    assert out["hidden_by_fast_path"] == ["I1/t0"]


def test_variance_ratio_point_estimate_and_ci_shape():
    rows = []
    for i, (fork_end, full_end) in enumerate([(True, True), (False, True), (True, False), (False, False)]):
        case = f"C{i}"
        rows += [row("baseline", "baseline", case), row("fork", "baseline", case, end=fork_end),
                 row("full", "baseline", case, end=full_end)]
    out = variance_ratio(rows, "baseline", "three_artifact")
    assert out["n"] == 4
    assert out["point"] is not None
    low, high = out["ci95_case"]
    assert low is None or low <= out["point"] * 4 + 1  # sane shape, not a precise value check
    assert out["skipped_resamples"] >= 0


def test_variance_ratio_degenerate_with_fewer_than_two_pairs():
    rows = [row("baseline", "baseline", "C1"), row("fork", "baseline", "C1"), row("full", "baseline", "C1")]
    out = variance_ratio(rows, "baseline", "three_artifact")
    assert out == {"n": 1, "point": None, "ci95_case": [None, None], "skipped_resamples": 0}


def test_full_control_identical_reply_rate():
    rows = [
        row("baseline", "baseline", "C1", final_message="hi"), row("full", "baseline", "C1", final_message="hi"),
        row("baseline", "baseline", "C2", final_message="hi"), row("full", "baseline", "C2", final_message="bye"),
    ]
    out = full_control_identical_reply_rate(rows)
    assert out == {"k": 1, "n": 2, "rate": 0.5}


def test_summary_and_markdown_cover_every_section():
    rows = [row("baseline", "baseline", "C1")]
    for change in ("baseline", "D", "E"):
        rows += [row("full", change, "C1"), row("fork", change, "C1"), row("fork_naive", change, "C1", end=False)]
    summary = summarize_part2(rows)
    assert summary["changes"] == ["baseline", "D", "E"]
    assert summary["per_change"]["D"]["forkable_pairs"] == 1
    md = render_markdown_part2(summary, {"git_commit": "abc", "langgraph": "1.2.12", "k": 3,
                                         "policy_model": {"name": "p"}, "judge_model": {"name": "j"}})
    for heading in ("# Part 2 results", "## Cost", "## Paired delta", "## Naive fork vs paired fork", "## Routing change"):
        assert heading in md
