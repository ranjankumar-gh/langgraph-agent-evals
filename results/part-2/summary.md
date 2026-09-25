# Part 2 results

Commit `625e3e93950a0b861ce2e2b0ee16f8b8f127c2e4` - langgraph 1.2.12 - policy `nemotron-3-nano:30b-cloud` - judge `gpt-oss:20b-cloud` - k=3 - 1650 rows, 2 crashed, 0 grading errors

`baseline` as a change is the no-op control: the unchanged agent forked into itself.

| Change | Forkable pairs | Inherited pairs (no fork point) | Routing check flagged | Baseline crashed |
|---|---|---|---|---|
| baseline | 96 | 69 | 0 | 0 |
| D | 96 | 69 | 0 | 0 |
| E | 96 | 69 | 24 | 0 |

## Cost: full rerun vs paired fork

Over the change's forkable pairs; only metered rows (no cache hit, token usage reported). "Policy calls" and "judge calls" count attempts, retries included.

| Change | Arm | Metered runs (excluded) | Wall-clock total s | Median s/run | Policy calls | Judge calls | Input tokens | Output tokens |
|---|---|---|---|---|---|---|---|---|
| baseline | full | 95 (1) | 1894.8 | 18.63 | 286 | 95 | 105859 | 68313 |
| baseline | fork | 95 (1) | 1495.9 | 14.51 | 190 | 95 | 76744 | 55637 |
| D | full | 96 (0) | 2338.5 | 18.47 | 287 | 97 | 107658 | 66799 |
| D | fork | 95 (1) | 1756.2 | 14.34 | 189 | 94 | 77757 | 56988 |
| E | full | 1 (95) | 15.2 | 15.2 | 3 | 1 | 1106 | 483 |
| E | fork | 0 (96) | 0 | None | 0 | 0 | 0 | 0 |

## Paired delta vs baseline

Change score minus baseline score for the same (case, trial), over the forkable pairs. `three_artifact` is 0/1; `judge_score` is 1-5. By-case bootstrap 95% CI.

| Change | Score | Arm | n | Mean | SD | By-case 95% CI | CI width |
|---|---|---|---|---|---|---|---|
| baseline | three_artifact | full | 96 | 0.0312 | 0.2273 | 0.0 to 0.0625 | 0.0625 |
| baseline | three_artifact | fork | 96 | 0.0208 | 0.2041 | 0.0 to 0.0521 | 0.0521 |
| baseline | judge_score | full | 96 | 0.0729 | 0.6843 | -0.0312 to 0.2083 | 0.2396 |
| baseline | judge_score | fork | 96 | 0.1562 | 0.8121 | 0.0104 to 0.3438 | 0.3333 |
| D | three_artifact | full | 96 | 0.0208 | 0.2504 | -0.0208 to 0.0729 | 0.0938 |
| D | three_artifact | fork | 96 | 0.0104 | 0.2292 | -0.0312 to 0.0625 | 0.0938 |
| D | judge_score | full | 96 | 0.0312 | 0.8392 | -0.125 to 0.1875 | 0.3125 |
| D | judge_score | fork | 96 | 0.1979 | 0.9133 | 0.0208 to 0.3958 | 0.375 |
| E | three_artifact | full | 96 | 0.0312 | 0.2273 | -0.0104 to 0.0729 | 0.0833 |
| E | three_artifact | fork | 96 | 0.0208 | 0.2041 | -0.0208 to 0.0625 | 0.0833 |
| E | judge_score | full | 96 | 0.0729 | 0.729 | -0.0521 to 0.2188 | 0.2708 |
| E | judge_score | fork | 96 | 0.2396 | 0.8045 | 0.0938 to 0.4167 | 0.3229 |

E shares D's cache namespaces, so on forkable pairs E's full and fork rows replay D's draws: its cost rows are excluded and its deltas equal D's by construction. E is the routing demonstration only.


## Variance ratio: fork vs full (var(fork diff) / var(full diff))

Case-clustered bootstrap; a value near 1 means the fork isn't adding measurement noise relative to a full rerun. Resamples where the full-arm variance is 0 are skipped.

- baseline / three_artifact: point 0.8068, 95% CI 0.2582 to 1.0 (n=96, 24 resamples skipped)
- baseline / judge_score: point 1.4083, 95% CI 0.9829 to 2.8517 (n=96, 0 resamples skipped)
- D / three_artifact: point 0.8374, 95% CI 0.3816 to 1.6306 (n=96, 1 resamples skipped)
- D / judge_score: point 1.1843, 95% CI 0.6829 to 2.2934 (n=96, 0 resamples skipped)
- E / three_artifact: point 0.8068, 95% CI 0.25 to 2.0211 (n=96, 6 resamples skipped)
- E / judge_score: point 1.2179, 95% CI 0.6006 to 2.7141 (n=96, 0 resamples skipped)

## Naive fork vs paired fork

Pairs are compared only when both forks made the same compute_refund decision. End state differs only through the world. Constraints differ through the carried tool log, which is part of the world snapshot. Answer can also differ by sampling, because the refund id in the reply facts differs.

| Change | Layer | n | Agree | Naive fail, paired pass | Naive pass, paired fail | Excluded (different decision) |
|---|---|---|---|---|---|---|
| baseline | end_state | 96 | 51 | 45 | 0 | 0 |
| baseline | constraints | 96 | 42 | 54 | 0 | 0 |
| baseline | answer | 96 | 93 | 1 | 2 | 0 |
| baseline | three_artifact | 96 | 54 | 42 | 0 | 0 |
| D | end_state | 95 | 52 | 43 | 0 | 1 |
| D | constraints | 95 | 42 | 53 | 0 | 1 |
| D | answer | 95 | 93 | 2 | 0 | 1 |
| D | three_artifact | 95 | 55 | 40 | 0 | 1 |
| E | end_state | 96 | 52 | 44 | 0 | 0 |
| E | constraints | 96 | 42 | 54 | 0 | 0 |
| E | answer | 96 | 94 | 2 | 0 | 0 |
| E | three_artifact | 96 | 55 | 41 | 0 | 0 |

## Routing change

Three-artifact regressions (baseline passes, the arm fails) seen by a full rerun vs by the fork arm, whose inherited rows reuse the baseline's verdict. A pair whose baseline crashed is excluded from the routing-flagged count.

### baseline

- Full-rerun regressions: 5 (F08/t0, F08/t1, F08/t2, N03/t1, R02/t0)
- Fork-arm regressions: 1 (R02/t0)
- Hidden by the fork (full fails, fork passes): 4 (F08/t0, F08/t1, F08/t2, N03/t1)
- Hidden by the fast path (E:damaged_fast_path): 0
- Routing check flagged as not forkable: 0
- Hidden and flagged: 0

### D

- Full-rerun regressions: 6 (A01/t2, F01/t0, F08/t1, H03/t1, N02/t0, N03/t1)
- Fork-arm regressions: 2 (A06/t1, H03/t1)
- Hidden by the fork (full fails, fork passes): 5 (A01/t2, F01/t0, F08/t1, N02/t0, N03/t1)
- Hidden by the fast path (E:damaged_fast_path): 0
- Routing check flagged as not forkable: 0
- Hidden and flagged: 0

### E

- Full-rerun regressions: 29 (A01/t2, F01/t0, F08/t1, I01/t0, I01/t1, I01/t2, I03/t0, I03/t1, I03/t2, I05/t0, I05/t1, I05/t2, I06/t0, I06/t1, I06/t2, I08/t0, I08/t1, I08/t2, J02/t0, J02/t1, J02/t2, J07/t0, J07/t1, J07/t2, N02/t0, N03/t1, N05/t0, N05/t1, N05/t2)
- Fork-arm regressions: 1 (A06/t1)
- Hidden by the fork (full fails, fork passes): 29 (A01/t2, F01/t0, F08/t1, I01/t0, I01/t1, I01/t2, I03/t0, I03/t1, I03/t2, I05/t0, I05/t1, I05/t2, I06/t0, I06/t1, I06/t2, I08/t0, I08/t1, I08/t2, J02/t0, J02/t1, J02/t2, J07/t0, J07/t1, J07/t2, N02/t0, N03/t1, N05/t0, N05/t1, N05/t2)
- Hidden by the fast path (E:damaged_fast_path): 24 (I01/t0, I01/t1, I01/t2, I03/t0, I03/t1, I03/t2, I05/t0, I05/t1, I05/t2, I06/t0, I06/t1, I06/t2, I08/t0, I08/t1, I08/t2, J02/t0, J02/t1, J02/t2, J07/t0, J07/t1, J07/t2, N05/t0, N05/t1, N05/t2)
- Routing check flagged as not forkable: 24 (I01/t0, I01/t1, I01/t2, I03/t0, I03/t1, I03/t2, I05/t0, I05/t1, I05/t2, I06/t0, I06/t1, I06/t2, I08/t0, I08/t1, I08/t2, J02/t0, J02/t1, J02/t2, J07/t0, J07/t1, J07/t2, N05/t0, N05/t1, N05/t2)
- Hidden and flagged: 24 (I01/t0, I01/t1, I01/t2, I03/t0, I03/t1, I03/t2, I05/t0, I05/t1, I05/t2, I06/t0, I06/t1, I06/t2, I08/t0, I08/t1, I08/t2, J02/t0, J02/t1, J02/t2, J07/t0, J07/t1, J07/t2, N05/t0, N05/t1, N05/t2)


Full-arm reply identical to the baseline reply, on change=baseline (the no-op control): 0/165 (0%). This should be low: Ollama Cloud ignores seeds, and the full arm draws fresh.
