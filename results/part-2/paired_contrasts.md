# Paired contrasts (part-2 run)

Generated offline by `uv run python -m scripts.paired_contrasts --runs results/part-2` (no model calls). Case-clustered bootstrap, seed 0, 2000 resamples, as in summary.md.

## Variance ratio, var(fork diff) / var(full diff)

Over all 165 groups, the 69 inherited pairs have a fork-arm delta of exactly 0.

| Change | Score | 96 forked pairs | All 165 groups |
|---|---|---|---|
| baseline | three_artifact | 0.8068 (0.2582 to 1.0000), 24 skipped | 0.3071 (0.0000 to 0.6817), 0 skipped |
| baseline | judge_score | 1.4083 (0.9829 to 2.8517), 0 skipped | 0.4545 (0.1430 to 1.0810), 0 skipped |
| D | three_artifact | 0.8374 (0.3816 to 1.6306), 1 skipped | 0.3573 (0.1016 to 0.7452), 0 skipped |
| D | judge_score | 1.1843 (0.6829 to 2.2934), 0 skipped | 0.6419 (0.2535 to 1.1791), 0 skipped |

## D with H03/t1 excluded (429 timeout in both D arms)

| Score | Full delta | Fork delta | Variance ratio |
|---|---|---|---|
| three_artifact | +0.0316 (-0.0105 to 0.0745) | +0.0211 (-0.0208 to 0.0638) | 0.8069 (0.2500 to 2.0211) |
| judge_score | +0.0737 (-0.0521 to 0.2188) | +0.2421 (0.0947 to 0.4167) | 1.2168 (0.6006 to 2.7117) |

95 pairs kept of 96.

## Pair-by-pair contrasts on the judge score

- D fork minus no-op fork, all forked pairs: +0.0417 (-0.0938 to 0.1771)
- D fork minus no-op fork, H03/t1 excluded: +0.0842 (0.0000 to 0.1915)
- no-op fork minus no-op full: +0.0833 (-0.0521 to 0.2711)

## Judge-score lower bound across bootstrap seeds 0-19

- no-op fork: lower bound <= 0 on 14 of 20 seeds (range -0.0104 to 0.0104)
- D fork: lower bound <= 0 on 0 of 20 seeds (range 0.0104 to 0.0208)
- D fork, H03/t1 excluded: lower bound <= 0 on 0 of 20 seeds (range 0.0842 to 0.1042)

## No-op control, forked pairs

- baseline judge scores: {1: 18, 2: 3, 3: 3, 4: 6, 5: 66}
- full: answer flipped 5, end_state flipped 1, judge score changed 13, path to fork point matched 96, reply identical 0, three_artifact down 1, three_artifact up 4
- fork: answer flipped 6, end_state flipped 1, judge score changed 17, path to fork point matched 96, reply identical 0, three_artifact down 1, three_artifact up 3
