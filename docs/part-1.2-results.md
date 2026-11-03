# Part 1.2 results against the pre-registration

Run: `results/part-1.2/` at commit `5a2dc9b`, k=3, 1980 runs, 6 crashes (5 empty policy replies
on A05, 1 network error on X03; all on valid variants and excluded), 0 grading errors.
Predictions: `docs/part-1.2-preregistration.md`, committed in `5c8b827` before the mutants were
implemented. Numbers: `results/part-1.2/independent-mutants.md`.

## Where each mutant fired

| Mutant | Predicted cases | Observed fired cases | Fired runs | End state wrong |
|---|---|---|---|---|
| M1 | I03 | I03 | 3 | 3 |
| M2 | every run reaching `check_eligibility`; outcome changes on I06, I07, J07 | 45 cases | 135 | 27 |
| M3 | N04 | N01, N02, N03, N04 | 12 | 3 (N04) |
| M4 | R01-R06 | R01-R06 | 18 | 18 |
| M5 | H02, H03, I03, H04 | H02, H03, H04, F03 | 12 | 9 |
| M6 | any non-`full` decision | 13 cases | 38 | 27 |
| M7 | tool-failure refunds | F01-F05 | 15 | 0 (excluded, as pre-registered) |
| M8 | any partial | A06, R04, X02, H03, H04, H10, F03 | 21 | 3 |

M1 cannot fire on I03 *and* leave M5 to fire there: I03 is ineligible, so `compute_refund` never
runs; the pre-registration listed I03 for M5 by mistake. F03 (a partial on a failing
`issue_refund`) was not listed for M5 or M8.

## Expectations

1. **Direction table predicts every mode verdict: held.** 0 mismatches.
2. **Every counted mutant collides with a valid variant: held** (7 of 7). M2's eligible-path runs
   are a pure reordering (87 runs), the same direction as `alt_history_early` (124 runs).
   `unordered`, `subset` and `superset` pass all 87. `strict` passes none, and rejects 94% of
   `alt_history_early`. The per-case ordering constraint (`get_refund_history` before
   `check_eligibility`) fails all 135 fired M2 runs and none of the `alt_history_early` runs whose
   end state and answer pass.
3. **Per-case constraints catch M1, M2, M3, M4 and miss M5, M6, M8: held for M1, M2, M4, M5,
   M6, M8; partly for M3.** The constraints fail M3 on N04 (a refund the case forbids) but pass
   it on N01-N03, where the not-found cases cap nothing and the second lookup also finds no order.
   Constraints alone pass M5 12/12, M6 32/38, M8 18/21.
4. **M8 is the only three-layer survivor, if any: failed as written.** Survivors: M3 9/12
   (N01-N03), M5 3/12 (F03), M6 8/28 (F02, F03, A04), M8 2/18 (F03). In every M3, M5 and M6
   survivor the fault fired without changing the outcome: the fallback found nothing, the refund
   then failed on an injected error, or `full` was an acceptable end state (A04). On fired runs
   where the end state was wrong, three-layer survival is 0 for every mutant. The two M8
   survivors are a real miss: the reply told the F03 customer the partial refund was 49.00 (the
   price; the planned amount was 24.50) and the judge scored it 5 of 5. The F03 answer reference
   is about the failure, not the amount.
5. **Position rules add nothing except on M3: held, with one exception.** `lookup_only` and
   `any_read` reject all 12 M3 runs, including the 9 harmless N01-N03 repeats. `any_read_or_stop`
   rejects N04 only, so it matches the per-case constraints on every mutant. This is the first
   test of `any_read_or_stop` against faults it was not written for: it lets nothing through that
   the constraints catch, and catches nothing they miss.

## What the pre-registration got wrong

The "fired" definitions were looser than the per-case predictions. "The fallback runs" (M3) and
"the type is not `full`" / "`int()` changes the amount" (M6/M5) are true before anything checks
whether the fault reaches the outcome. Counting those runs as survivors is what the
pre-registered rule says, so the table above keeps them; the per-run breakdown is how a reader
can tell a harmless fire from a missed fault.
