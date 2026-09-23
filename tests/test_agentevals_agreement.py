import pytest

match = pytest.importorskip("agentevals.trajectory.match")

from evals.checks.trajectory import MATCH_MODES, match_trajectory  # noqa: E402

FIXTURES = [
    (["a", "b", "c"], ["a", "b", "c"]),
    (["b", "a", "c"], ["a", "b", "c"]),
    (["a", "b", "b", "c"], ["a", "b", "c"]),
    (["a", "c"], ["a", "b", "c"]),
    (["a", "b", "c", "d"], ["a", "b", "c"]),
    (["a", "a"], ["a"]),
    (["a", "d"], ["a", "b"]),
    ([], ["a"]),
]


def as_messages(calls: list[str]) -> list[dict]:
    messages: list[dict] = [{"role": "user", "content": "refund please"}]
    for i, name in enumerate(calls):
        messages.append({
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": "{}"}}],
        })
        messages.append({"role": "tool", "content": "ok", "tool_call_id": f"call_{i}"})
    messages.append({"role": "assistant", "content": "done"})
    return messages


@pytest.mark.parametrize("mode", MATCH_MODES)
@pytest.mark.parametrize(("observed", "reference"), FIXTURES)
def test_agrees_with_agentevals(mode, observed, reference):
    evaluator = match.create_trajectory_match_evaluator(trajectory_match_mode=mode, tool_args_match_mode="ignore")
    theirs = evaluator(outputs=as_messages(observed), reference_outputs=as_messages(reference))
    assert bool(theirs["score"]) == match_trajectory(observed, reference, mode), (mode, observed, reference)
