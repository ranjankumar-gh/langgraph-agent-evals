# Part 1.2: independently authored mutants - pre-registered predictions

Written 2026-11-03, **before** the mutants were implemented or run. Committed ahead of the
measured run so the predictions cannot be fitted to the results.

## Why this run exists

Every mutant in `part-1` and `part-1.1` (A, B, C, C1, C2) was written by the same person who
wrote the trajectory constraints and the position rules, and C1/C2 were written knowing the
rules they were probing. Blind reviewers of the Part 1 article named that as the main weakness
of its evidence. This run adds a mutant family whose author never saw the evaluation.

## How the mutants were authored

A fresh model session (no repository access, no file reads, no web) was given only:
the graph's node order and routing, the tool signatures, the state fields, and the refund
policy in plain language. It was told which three faults were already taken (skipped
eligibility, false-success reply, redundant re-reads) and told explicitly that it had not been
shown how the agent is evaluated and should not guess. It was **not** shown the case schema,
the per-case constraints, the reference paths, the match modes, the position rules, the
article, or any results. Its eight designs are implemented below as specified, with the
adaptations listed; none was dropped or altered to make it easier or harder to catch.

| Id | Author's fault | Node | Adaptation to this repo |
|---|---|---|---|
| M1 | 30-day window off by one (`> 31`) | `check_eligibility` tool | applied inside the tool for variant M1 only |
| M2 | eligibility runs before refund history, using `prior_refunds or 0` | routing | lookup -> eligibility -> history -> compute |
| M3 | "guest order" fallback: re-look-up the order without the owner filter when it is not found | `lookup_order` | `Tools.lookup_order(order_id, None)` means no owner filter; only M3 passes None |
| M4 | approval router compares against `"rejected"`; the interrupt resumes with `"reject"` | `after_approval` | as specified |
| M5 | refund amount truncated with `int()` | `compute_refund` | as specified |
| M6 | `refund_type` dropped in a refactor, tool default `"full"` applies | `issue_refund` | passes `"full"` (the tool has no default) |
| M7 | blind retry of `issue_refund` on ToolError, no idempotency | `issue_refund` | as specified |
| M8 | fact sheet renders the order price instead of the planned amount | `respond` | as specified |

**Fired** means the faulty line changed behaviour on that run: M1 when a 31-day-old delivery
is let through; M2 whenever eligibility is checked before history; M3 when the fallback lookup
runs; M4 on a rejected approval that is routed to `issue_refund`; M5 when `int()` changes the
amount; M6 when the decided type is not `full`; M7 when the retry runs; M8 on a partial refund.

**M7 is excluded from the survival aggregate, decided now.** In this environment an injected
tool error fires before the refund row is written, so a blind retry can never create a second
refund. Its runs are reported, but as a fault it is harmless here.

## Which cases can fire each mutant (from the case files, before running)

- M1: I03 (delivered exactly 31 days ago, correct outcome: not eligible).
- M2: every run that reaches `check_eligibility`; it changes the outcome only on I06, I07, J07
  (customer at the 2-refund limit).
- M3: N04 (order id exists but belongs to another customer).
- M4: R01-R06 (approval rejected).
- M5: H02, H03, I03 (prices with cents) and odd-priced partial refunds (H03, H04).
- M6: any run where `compute_refund` picks `partial` or `store_credit`.
- M7: the tool-failure cases where `issue_refund` errors.
- M8: any run with a planned partial refund (A06, H03, H04, H10, J03 when partial is chosen).

## Predictions, by edit direction (the Mode-Shaped Blind Spot test)

Each mode's verdict is a pure function of the edit-direction set against the case's reference
path. Predicted direction sets on fired runs, and what follows:

| Mutant | Predicted direction set | Modes predicted to pass it | Collides with a valid variant? |
|---|---|---|---|
| M1 | `('insertion',)` (an `issue_refund` the not-eligible reference lacks) | superset | yes: `alt_recheck` and `alt_history_early` (insertion) |
| M2 | eligible paths: `('reordering',)`; not-eligible paths: `('omission',)` (history never read) | reordering: unordered, subset, superset; omission: subset | **yes: `alt_history_early` (reordering)** |
| M3 | `('insertion',)` (second `lookup_order`, then a refund) | superset | yes (insertion) |
| M4 | `('insertion',)` (`issue_refund` after a rejection) | superset | yes (insertion) |
| M5 | `()` - arguments only | all four | yes: every valid run with an empty set |
| M6 | `()` - arguments only | all four | yes |
| M8 | `()` - reply only | all four | yes |

Pre-registered expectations:

1. **The direction table predicts each mode's survival exactly** for every mutant. A mode
   passes a fired run if and only if its direction set is in that mode's pass set. This is
   arithmetic, so a mismatch would mean a bug in the analysis, not a finding.
2. **The substantive prediction is the collision count.** Of the 7 counted mutants, 7 share a
   direction set with at least one valid variant on fired runs, so for each of them at least one
   mode that rejects no valid path passes it. In particular M2 collides with `alt_history_early`:
   `unordered`, `subset` and `superset` pass M2 on every eligible-path run where the baseline
   passes, and only `strict` catches it, at the cost of rejecting most `alt_history_early` runs.
3. **Per-case constraints as authored** (no position rule): catch M1, M3, M4 (a forbidden or
   uncapped `issue_refund` on a no-refund case) and M2 (the `get_refund_history ->
   check_eligibility` ordering), and miss M5, M6, M8 (no tool-call difference).
4. **The three-layer harness:** M1, M2 (on I06/I07/J07), M3, M4, M5, M6 are caught by the
   end-state layer on fired runs where the outcome changes; M8 can only be caught by the answer
   layer. Predicted: M8 is the one with nonzero three-layer survival, if any is.
5. **The position rules** (`lookup_only`, `any_read`, `any_read_or_stop`) add nothing for
   M1, M2, M4-M8, because none of them repeats a read. M3 does: its fallback `lookup_order`
   comes directly after the first one, with history and eligibility between it and
   `issue_refund`. Predicted: all three position rules reject M3, which the constraints
   already catch.
