# Part 2 results changelog

The measured run was made at commit `625e3e9` (run tag `part-2-625e3e9`; see `metadata.json`).

## Network outage during the measured run (2026-09-24/25)

The first pass (1,650 rows, 165 groups) recorded 273 crashed rows in 43 (case, trial) groups.
272 of them were DNS failures reaching Ollama Cloud through the local Ollama app
(`dial tcp: lookup ollama.com: no such host`, surfaced as a 502), and one was
`ValueError: No data received from Ollama stream`. None were graph, recursion or grading
failures; the baseline arm (replayed from cache) had none.

Those rows measure the network, not the agent or the harness, so the 43 affected groups
(listed in `removed-groups.txt`) were removed from `runs.jsonl` and re-run with the same
command at the same commit and run tag. The original first-pass file is kept as
`runs.jsonl.pre-outage`. In the re-run, calls that succeeded the first time replay from the
run-scoped cache and only the failed calls went to the model live, so each re-run group is
what an uninterrupted run would have produced. Consequence: rows in re-run groups contain
cache hits, so the cost table counts them as excluded and cost figures come from the groups
that ran cleanly the first time.

No code, case, change or fork rule was modified.

The re-run completed all 43 groups. The final file has 1650 rows in 165 complete groups, with 2 crashed rows (`StructuredOutputError ... timed out`, Ollama Cloud timeouts). They are kept as measured.
