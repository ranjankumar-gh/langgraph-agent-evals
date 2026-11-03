# Part 1.3 results against the pre-registration

Run: `results/part-1.3/` at commit `08061db`, k=3, 55 cases x 7 variants = 1155 runs, 0 crashes,
0 grading errors. Same model digests as part-1.2 (`2fd759a`, `9a01793`); 26 live policy calls
(V4's speculative computes on ineligible paths), everything else replayed from the part-1.2 run's
cache. Predictions: `docs/part-1.3-preregistration.md`, committed in `017e5df` before the
alternates were implemented. Numbers: `results/part-1.3/independent-valid.md`.

Brittle-fail counts are runs rejected among runs whose end state and answer pass (140 per
variant).

| Check | V1 | V2 | V3 | V4-V6 |
|---|---|---|---|---|
| `strict`, `unordered`, `subset` | 7 | 19 | 58 | 0 |
| `superset` | 0 | 0 | 0 | 0 |
| per-case constraints | 0 | 0 | 0 | 0 |
| + `lookup_only` | 7 | 0 | 0 | 0 |
| + `any_read` | 7 | 0 | 58 | 0 |
| + `any_read_or_stop` | 0 | 0 | 0 | 0 |

## Expectations

1. **Direction table predicts every mode verdict: held.** 0 mismatches.
2. **Per-case constraints reject none of V1-V6: held.** 0 of 840.
3. **`lookup_only` rejects V1's retries; `any_read` rejects V1's retries and V3's reconcile reads:
   held.** 7 of 7 and 58 of 58 (fired runs whose end state and answer pass).
4. **`any_read_or_stop` rejects none, only through its last-call allowance: held.** V1's retry and
   V3's reconcile read are each the run's last tool call.
5. **V4-V6 make the baseline's tool calls on every run: held.** 0 differences.
6. **End state matches the baseline's on every run: held.** 0 differences.

## What it shows, and what it does not

- The per-case constraints accepted every valid alternate an independent author wrote. They did so
  partly because they are loose: `get_refund_history` has no cap, which is also why mutant C2 (one
  redundant history read) survived them 111 of 111 in part-1.1. V3 and C2 differ only in where the
  extra read sits.
- `any_read`, the rule that closed C2, rejected all 58 qualifying V3 runs. `any_read_or_stop`
  accepted them only because the reconcile read happens to be the last tool call.
- Three of six designs (V4-V6) never changed the tool calls, so they test nothing about trajectory
  checks; they confirm the harness treats refactors with identical calls identically.
