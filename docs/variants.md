# Agent variants

The refund agent graph is built once from `agent.graph.build_graph`, selected by
`variant` name. Every variant shares one code path except the lines that define
it, so a diff between variants is a diff of intent, not of scaffolding.

| Variant | Kind | Behaviour |
|---|---|---|
| `baseline` | valid | classify -> lookup_order -> get_refund_history -> check_eligibility -> compute_refund -> [request_approval if > 1000] -> issue_refund -> respond |
| `alt_history_early` | valid | fetches refund history before the order (a legitimate reordering of two independent reads) |
| `alt_recheck` | valid | re-reads the order immediately before `issue_refund` (a legitimate safety re-read before money moves) |
| `A` | mutant | skips `check_eligibility` when the classified intent is `damaged` ("sounds valid") |
| `B` | mutant | when `issue_refund` fails, `respond` reports refund status from the plan (`refund_amount`) instead of the observation (`refund_id`) |
| `C` | mutant | re-looks-up the order in `check_eligibility`, `compute_refund`, and `issue_refund` (4 lookups total) |

## Mutant A: skipped precondition check on a "confident" path

A skips the eligibility check outright when the classifier's intent looks
unambiguous ("damaged" reads as obviously valid), and only for that one intent —
every other intent still runs the check. This stands for the real-world fault
class where an agent (or a human reviewer) short-circuits a required
precondition because a case "looks like" it doesn't need it. The
`A:skipped_eligibility` marker records every damaged-intent run under A: the
skip itself is the fault, whether or not eligibility would have failed had it
run. The end state is only wrong on the subset of those runs where the order
was in fact ineligible — on a case where eligibility would have passed anyway,
the skip changes nothing observable in the outcome and only shows up in an
audit of which checks actually ran.

## Mutant B: final message written from the plan rather than the observed result

B does not corrupt any tool call. The refund genuinely fails at `issue_refund`.
The fault is entirely in `respond`: instead of reporting what actually happened
(no `refund_id`, an error), it reports what was planned to happen
(`refund_amount`, `refund_type`) as if it had succeeded. This stands for the
real-world fault class where a response-generation step reads from an agent's
working plan instead of from the ground-truth observation of what a tool
actually returned — a customer told a refund is "issued" when the database has
no such row.

## Mutant C: redundant reads that make the loop cost and latency grow

C re-looks-up the same order in three separate nodes that all already have it
in state, quadrupling the number of `lookup_order` calls for a single request.
The final outcome is identical to baseline — same refund, same amount — so
nothing about correctness distinguishes C from a valid variant by output alone.
This stands for the real-world fault class of an agent that keeps re-fetching
information it already holds: each redundant call is harmless on its own, but
compounds into avoidable tool cost and latency at scale, and a superficial
"did it get the right answer" check will never catch it.

## Sources

Filled in from the Part 1 research brief.
