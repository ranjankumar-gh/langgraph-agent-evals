# Part 1.3: independently authored valid alternates - pre-registered predictions

Written 2026-11-03, **before** the alternates were implemented or run, and committed ahead of
the measured run so the predictions cannot be fitted to the results.

## Why this run exists

Part 1.2 tested the fault side with mutants from an author who never saw the evaluation. The
valid side still had only alternates written by the person who wrote the constraints
(`alt_history_early`, `alt_recheck`, `alt_verify`), so "the constraints rejected 0 valid runs"
only showed that they fit the alternates their author thought of. This run adds valid
alternates from an author who never saw the evaluation, and asks how many of them each check
wrongly rejects.

## How the alternates were authored

A fresh model session, told not to use any tools (no repository, no file reads, no web), was
given only: the graph's nodes and routing, the four tool signatures and their semantics, the
state fields, the refund policy, two environment facts (an injected tool failure persists for
the rest of the request; an order can change while a request is handled, and policy says not to
refund then), and the three valid alternates that already exist. It was told explicitly that it
had not been shown how the agent is evaluated and should not design around it. It was **not**
shown the cases, constraints, reference paths, match modes, position rules, the article, or any
results. It was asked for six alternatives a reasonable engineer would ship that produce the
same world outcome and the same reply facts on every request.

| Id | Author's design | Tool calls differ from the baseline on |
|---|---|---|
| V1 | retry each read tool once on a tool error (never the write) | F06-F08 (`lookup_order` fails): `lookup_order, lookup_order` |
| V2 | fetch order and refund history together, order result takes priority | N01-N04 (order not found) and F06-F08 (lookup fails): `lookup_order, get_refund_history` |
| V3 | after `issue_refund` (success or error), re-read refund history for logging only | every run that reaches `issue_refund`: `..., issue_refund, get_refund_history` |
| V4 | compute the refund speculatively while history and eligibility are read; discard it if not eligible | nowhere (extra LLM calls only) |
| V5 | one approve-and-issue node with a replay guard | nowhere |
| V6 | one gate node for lookup, history and eligibility, with a typed outcome | nowhere |

Adaptations to this repo: V2 runs the two reads sequentially in that order (the tools are
synchronous); it writes `prior_refunds` only when it routes to eligibility, as specified. V4
runs `compute_refund` directly after `lookup_order` and clears the planned refund at a join
node if eligibility fails or errors. Its compute call uses the same prompt as the baseline's.
V3's reconcile read never writes state. Nothing else was changed, and no design was dropped.

The author noted, correctly, that all six inherit the baseline's changed-order gap: each reads
the order once, so on the three `changed_order` cases (X01-X03) they refund the stale amount
like the baseline does. Those runs fail the end state and are outside every brittle-fail count
below, which counts only runs whose end state and answer pass.

**Fired** markers: V1 when a read is retried; V2 when history is read on a path that then stops
at the lookup; V3 when the reconcile read runs; V4 when a speculative compute is discarded. V5
and V6 never fire: they are controls whose tool calls are identical to the baseline's.

## Predictions

Brittle-fail = a check rejects a valid run whose end state and answer pass. Predictions by
check (references from the case files; direction sets from `scripts/direction_table.py`):

| Check | V1 (F06-F08) | V2 (N01-N04, F06-F08) | V3 (refund paths) | V4-V6 |
|---|---|---|---|---|
| direction set on fired runs | `insertion` | `insertion` | `insertion` | `()`, same as baseline |
| `strict`, `unordered`, `subset` | reject all | reject all | reject all | same verdicts as baseline |
| `superset` | accept all | accept all | accept all | same as baseline |
| per-case constraints as authored | accept all (lookup-failure cases cap nothing) | accept all (history is not forbidden there) | accept all (history is uncapped; ordering uses first occurrences) | same as baseline |
| + `lookup_only` | **reject all** (repeat lookup, not before a refund) | accept | accept | same as baseline |
| + `any_read` | **reject all** | accept | **reject all** (repeat history after the refund) | same as baseline |
| + `any_read_or_stop` | accept (repeat is the last call) | accept | accept (repeat is the last call) | same as baseline |

Pre-registered expectations:

1. **The direction table predicts every mode verdict** on every non-crashed run (arithmetic; a
   mismatch would be an analysis bug).
2. **Per-case constraints as authored reject none of V1-V6's runs** whose end state and answer
   pass.
3. **`lookup_only` rejects every V1 run on F06-F08, and `any_read` rejects every V1 run there
   and every V3 run that reaches `issue_refund`** (whose end state and answer pass). These are
   valid paths their author did not write the rules against.
4. **`any_read_or_stop` rejects none of them**, but only through its last-call allowance: V1's
   and V3's repeats are each the run's last tool call.
5. **V4-V6 have the same tool calls as the baseline on every run**, so every trajectory verdict
   equals the baseline's on the same (case, trial).
6. **End state and answer:** V1-V6 match the baseline's end state on every non-crashed run
   except where an LLM decision differs, and V4 never leaves a planned refund in the reply facts
   on an ineligible or error path.
