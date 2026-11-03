# Part 1 results

Commit `08061db3ad17f3e78d93c74c28a31b60583cdae1` - langgraph 1.2.12 - policy `nemotron-3-nano:30b-cloud` - judge `gpt-oss:20b-cloud` - k=3 - 1155 runs, 0 crashed, 0 grading errors

Every cell: rate (k/n; per-run Wilson 95% CI; by-case bootstrap 95% CI). Outcomes cluster by case, so the per-run interval understates uncertainty; the by-case interval is the one to cite.

## Mutant survival, conditioned on baseline passing (primary; lower is better)

Among (case, trial) pairs where the mutant's fault fired and the baseline run for the same (case, trial) passes the harness, the fraction where the mutant's run also passes.

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|

Fired pairs excluded from the table above (baseline run fails the harness / no baseline row):

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|

## Mutant survival, unconditional (secondary; lower is better)

Among fired runs of the mutant, the fraction that pass the harness, ignoring the baseline.

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|

## Trajectory-Blind Pass rate

| Variant | TBP rate |
|---|---|
| baseline | 1% (2/142; per-run 0%-5%; by case 0%-4%) |
| all | 1% (14/994; per-run 1%-2%; by case 0%-4%) |

## Brittle-fail rate on valid variants (lower is better)

| Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|
| baseline | 0% (0/140; per-run 0%-3%; by case 0%-0%) | 0% (0/140; per-run 0%-3%; by case 0%-0%) | 0% (0/140; per-run 0%-3%; by case 0%-0%) | 0% (0/140; per-run 0%-3%; by case 0%-0%) | 0% (0/140; per-run 0%-3%; by case 0%-0%) |

## By slice

Mutant survival pools every fired run of A, B and C in the slice.

| Slice | Mutant survival, answer-only (conditioned on baseline) | Mutant survival, three-artifact (conditioned on baseline) | Mutant survival, answer-only (unconditional) | Mutant survival, three-artifact (unconditional) | TBP rate |
|---|---|---|---|---|---|
| ambiguous | - | - | - | - | 0% (0/119; per-run 0%-3%; by case 0%-0%) |
| approval_rejected | - | - | - | - | 0% (0/112; per-run 0%-3%; by case 0%-0%) |
| changed_order | - | - | - | - | - |
| happy | - | - | - | - | 0% (0/210; per-run 0%-2%; by case 0%-0%) |
| ineligible | - | - | - | - | 0% (0/168; per-run 0%-2%; by case 0%-0%) |
| injection | - | - | - | - | 13% (14/105; per-run 8%-21%; by case 0%-46%) |
| missing_data | - | - | - | - | 0% (0/126; per-run 0%-3%; by case 0%-0%) |
| tool_failure | - | - | - | - | 0% (0/154; per-run 0%-2%; by case 0%-0%) |

## Brittle-fail rate by slice (valid variants; lower is better)

| Slice | Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|---|
| ambiguous | baseline | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | baseline | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) |
| happy | baseline | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| ineligible | baseline | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| injection | baseline | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) |
| missing_data | baseline | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) |
| tool_failure | baseline | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) |

## Harness pass rate by variant

| Variant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| baseline | 86% (142/165; per-run 80%-91%; by case 78%-94%) | 85% (140/165; per-run 79%-90%; by case 76%-93%) | 85% (140/165; per-run 79%-90%; by case 76%-93%) | 85% (140/165; per-run 79%-90%; by case 76%-93%) | 85% (140/165; per-run 79%-90%; by case 76%-93%) | 85% (140/165; per-run 79%-90%; by case 76%-93%) |

Judge endorsed a reply the database contradicts: 1% (14/1155; per-run 1%-2%; by case 0%-4%)
