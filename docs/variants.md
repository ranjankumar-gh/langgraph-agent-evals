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
| `C` | mutant | re-looks-up the order in `check_eligibility`, `compute_refund`, and `issue_refund` (4 lookups total on a refund-issuing path; 2 or 3 on a path that stops earlier) |

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
in state. On a refund-issuing path, which reaches all three nodes, that quadruples
the number of `lookup_order` calls for a single request (1 becomes 4); on a path
that stops before `issue_refund` (an ineligible order, say) only the nodes it
reaches add a lookup, so it makes 2 or 3 instead of 1.
The final outcome is identical to baseline — same refund, same amount — so
nothing about correctness distinguishes C from a valid variant by output alone.
This stands for the real-world fault class of an agent that keeps re-fetching
information it already holds: each redundant call is harmless on its own, but
compounds into avoidable tool cost and latency at scale, and a superficial
"did it get the right answer" check will never catch it.

## Part 1 addendum: alt_verify, C1, C2 and the changed_order cases

Added after the part-1 run, in response to review of the Part 1 article. None of them changes
a part-1 variant or case; results/part-1 is untouched.

- **`alt_verify` (valid).** Makes the same re-read as `alt_recheck`, directly before
  `issue_refund`, but uses the result: if the order's price changed since the first read, it
  stops and does not refund. `alt_recheck` discards the result, so its re-read only stops the
  refund when the lookup itself errors. On every part-1 case the two produce identical tool
  calls and outcomes; they differ only on the `changed_order` cases.
- **`changed_order` cases (X01-X03).** The order is repriced (a partial cancellation) between
  the first read and the refund. The correct outcome is no refund yet. Only `alt_verify` reaches
  it; the baseline never re-reads, and `alt_recheck` re-reads and ignores what it read.
- **Mutant C1.** One redundant `lookup_order`, inside `check_eligibility` only. It adds exactly
  one call, so it fits under the per-case `max_calls={"lookup_order": 2}` cap on every path.
- **Mutant C2.** One redundant `get_refund_history`, inside `check_eligibility`. It is the same
  cost fault class as C on a different tool, and no rule about `lookup_order` covers it.

## Part 2: changes under test

Part 2 measures eval *harnesses* on a change, not a fault. Two changes, fixed before the
measured run and not tuned after it:

| Change | Edits | Behaviour |
|---|---|---|
| `D` | `compute_refund` prompt | appends one line: "If the stated reason is unclear or fits more than one category, choose store_credit." |
| `E` | `compute_refund` prompt **and** the router out of `check_eligibility` | D's prompt, plus a "damaged items fast path": an ineligible order whose intent is `damaged` is routed into `compute_refund` instead of being refused |

`baseline` is also run as a change: the no-op control. Forking the unchanged agent into
itself must reproduce the baseline's verdicts up to sampling noise, so any systematic
difference is the harness, not the agent.

Every change's fork point is the checkpoint just before `compute_refund`. D touches only
that node, so a fork is valid on every case. E also changes the routing *into* that node,
so on the cases where the baseline never reached `compute_refund`, the fork has no fork
point and the regression E introduces never runs.

### What the harness is expected to show (recorded before measuring)

1. A paired fork skips `classify_request` and the three upstream tool calls, so it costs
   fewer LLM calls, tokens and seconds than a full rerun of the same change.
2. On the no-op control and on D, the paired fork's change-minus-baseline delta has a
   narrower case-clustered interval than the full rerun's, because the two runs share their
   upstream draw (common random numbers).
3. A naive fork (the thread is restored but the world is not) gives wrong verdicts on
   refund-issuing paths: the world already holds the baseline's refund, so the fork's
   refund is a second row and a second `issue_refund` call.
4. On E, the fork arm misses the refunds issued on ineligible damaged orders that a full
   rerun catches. The routing check flags exactly those cases as unforkable.

Whatever the measured numbers are, they are reported as measured.

## Sources

Citations for each fault class are given in the Part 1 article.
