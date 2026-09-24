# Part 1 results

Commit `55b34b3df18d8288691d63c8c61218371b56be61` - langgraph 1.2.12 - policy `nemotron-3-nano:30b-cloud` - judge `gpt-oss:20b-cloud` - k=3 - 1485 runs, 0 crashed, 0 grading errors

Every cell: rate (k/n; per-run Wilson 95% CI; by-case bootstrap 95% CI). Outcomes cluster by case, so the per-run interval understates uncertainty; the by-case interval is the one to cite.

## Mutant survival, conditioned on baseline passing (primary; lower is better)

Among (case, trial) pairs where the mutant's fault fired and the baseline run for the same (case, trial) passes the harness, the fraction where the mutant's run also passes.

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 59% (35/59; per-run 47%-71%; by case 37%-80%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) | 59% (35/59; per-run 47%-71%; by case 37%-80%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) |
| B | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) |
| C | 100% (111/111; per-run 97%-100%; by case 100%-100%) | 35% (39/111; per-run 27%-44%; by case 19%-51%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 100% (111/111; per-run 97%-100%; by case 100%-100%) |
| C1 | 100% (111/111; per-run 97%-100%; by case 100%-100%) | 100% (111/111; per-run 97%-100%; by case 100%-100%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 100% (111/111; per-run 97%-100%; by case 100%-100%) |
| C2 | 100% (111/111; per-run 97%-100%; by case 100%-100%) | 100% (111/111; per-run 97%-100%; by case 100%-100%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 100% (111/111; per-run 97%-100%; by case 100%-100%) |

Fired pairs excluded from the table above (baseline run fails the harness / no baseline row):

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 11 / 0 | 11 / 0 | 11 / 0 | 11 / 0 | 11 / 0 | 11 / 0 |
| B | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 |
| C | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 |
| C1 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 |
| C2 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 | 24 / 0 |

## Mutant survival, unconditional (secondary; lower is better)

Among fired runs of the mutant, the fraction that pass the harness, ignoring the baseline.

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 50% (35/70; per-run 39%-61%; by case 31%-70%) | 0% (0/70; per-run 0%-5%; by case 0%-0%) | 0% (0/70; per-run 0%-5%; by case 0%-0%) | 0% (0/70; per-run 0%-5%; by case 0%-0%) | 50% (35/70; per-run 39%-61%; by case 31%-70%) | 0% (0/70; per-run 0%-5%; by case 0%-0%) |
| B | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| C | 82% (111/135; per-run 75%-88%; by case 72%-92%) | 29% (39/135; per-run 22%-37%; by case 16%-42%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 82% (111/135; per-run 75%-88%; by case 72%-92%) |
| C1 | 82% (111/135; per-run 75%-88%; by case 72%-92%) | 82% (111/135; per-run 75%-88%; by case 72%-92%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 82% (111/135; per-run 75%-88%; by case 72%-92%) |
| C2 | 82% (111/135; per-run 75%-88%; by case 72%-92%) | 82% (111/135; per-run 75%-88%; by case 72%-92%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 0% (0/135; per-run 0%-3%; by case 0%-0%) | 82% (111/135; per-run 75%-88%; by case 72%-92%) |

## Trajectory-Blind Pass rate

| Variant | TBP rate |
|---|---|
| baseline | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_history_early | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_recheck | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_verify | 0% (0/140; per-run 0%-3%; by case 0%-0%) |
| A | 31% (35/112; per-run 23%-40%; by case 17%-46%) |
| B | 0% (0/122; per-run 0%-3%; by case 0%-0%) |
| C | 53% (72/136; per-run 45%-61%; by case 38%-66%) |
| C1 | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| C2 | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| all | 9% (107/1190; per-run 7%-11%; by case 6%-12%) |

## Brittle-fail rate on valid variants (lower is better)

| Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|
| baseline | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_history_early | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 93% (127/136; per-run 88%-96%; by case 85%-100%) | 12% (16/136; per-run 7%-18%; by case 4%-21%) | 12% (16/136; per-run 7%-18%; by case 4%-21%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_recheck | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 40% (55/136; per-run 33%-49%; by case 26%-54%) | 40% (55/136; per-run 33%-49%; by case 26%-54%) | 40% (55/136; per-run 33%-49%; by case 26%-54%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_verify | 0% (0/140; per-run 0%-3%; by case 0%-0%) | 39% (55/140; per-run 32%-48%; by case 26%-53%) | 39% (55/140; per-run 32%-48%; by case 26%-53%) | 39% (55/140; per-run 32%-48%; by case 26%-53%) | 0% (0/140; per-run 0%-3%; by case 0%-0%) |

## By slice

Mutant survival pools every fired run of A, B and C in the slice.

| Slice | Mutant survival, answer-only (conditioned on baseline) | Mutant survival, three-artifact (conditioned on baseline) | Mutant survival, answer-only (unconditional) | Mutant survival, three-artifact (unconditional) | TBP rate |
|---|---|---|---|---|---|
| ambiguous | 100% (27/27; per-run 88%-100%; by case 100%-100%) | 59% (16/27; per-run 41%-75%; by case 50%-67%) | 87% (27/31; per-run 71%-95%; by case 67%-100%) | 52% (16/31; per-run 35%-68%; by case 33%-67%) | 7% (11/153; per-run 4%-12%; by case 2%-14%) |
| approval_rejected | 100% (60/60; per-run 94%-100%; by case 100%-100%) | 57% (34/60; per-run 44%-68%; by case 52%-63%) | 95% (60/63; per-run 87%-98%; by case 85%-100%) | 54% (34/63; per-run 42%-66%; by case 48%-60%) | 17% (26/153; per-run 12%-24%; by case 13%-21%) |
| changed_order | - | - | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/4; per-run 0%-49%; by case 0%-0%) |
| happy | 100% (105/105; per-run 96%-100%; by case 100%-100%) | 57% (60/105; per-run 48%-66%; by case 53%-62%) | 100% (105/105; per-run 96%-100%; by case 100%-100%) | 57% (60/105; per-run 48%-66%; by case 53%-62%) | 17% (45/270; per-run 13%-22%; by case 13%-20%) |
| ineligible | 83% (72/87; per-run 73%-89%; by case 77%-92%) | 83% (72/87; per-run 73%-89%; by case 77%-92%) | 83% (72/87; per-run 73%-89%; by case 77%-92%) | 83% (72/87; per-run 73%-89%; by case 77%-92%) | 0% (0/201; per-run 0%-2%; by case 0%-0%) |
| injection | 86% (36/42; per-run 72%-93%; by case 75%-100%) | 79% (33/42; per-run 64%-88%; by case 69%-92%) | 43% (36/84; per-run 33%-54%; by case 12%-72%) | 39% (33/84; per-run 30%-50%; by case 11%-68%) | 3% (3/102; per-run 1%-8%; by case 0%-9%) |
| missing_data | 86% (18/21; per-run 65%-95%; by case 75%-100%) | 86% (18/21; per-run 65%-95%; by case 75%-100%) | 86% (18/21; per-run 65%-95%; by case 75%-100%) | 86% (18/21; per-run 65%-95%; by case 75%-100%) | 0% (0/132; per-run 0%-3%; by case 0%-0%) |
| tool_failure | 78% (50/64; per-run 67%-86%; by case 76%-80%) | 44% (28/64; per-run 32%-56%; by case 40%-48%) | 72% (50/69; per-run 61%-82%; by case 61%-79%) | 41% (28/69; per-run 30%-52%; by case 32%-48%) | 13% (22/175; per-run 8%-18%; by case 5%-20%) |

## Brittle-fail rate by slice (valid variants; lower is better)

| Slice | Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|---|
| ambiguous | baseline | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| ambiguous | alt_history_early | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| ambiguous | alt_recheck | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| ambiguous | alt_verify | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | baseline | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | alt_history_early | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 100% (17/17; per-run 82%-100%; by case 100%-100%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | alt_recheck | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | alt_verify | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| changed_order | alt_verify | 0% (0/4; per-run 0%-49%; by case 0%-0%) | 0% (0/4; per-run 0%-49%; by case 0%-0%) | 0% (0/4; per-run 0%-49%; by case 0%-0%) | 0% (0/4; per-run 0%-49%; by case 0%-0%) | 0% (0/4; per-run 0%-49%; by case 0%-0%) |
| happy | baseline | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_history_early | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_recheck | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_verify | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| ineligible | baseline | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_history_early | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 100% (24/24; per-run 86%-100%; by case 100%-100%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_recheck | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_verify | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| injection | baseline | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| injection | alt_history_early | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 100% (12/12; per-run 76%-100%; by case 100%-100%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| injection | alt_recheck | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| injection | alt_verify | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| missing_data | baseline | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| missing_data | alt_history_early | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 100% (15/15; per-run 80%-100%; by case 100%-100%) | 60% (9/15; per-run 36%-80%; by case 17%-100%) | 60% (9/15; per-run 36%-80%; by case 17%-100%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| missing_data | alt_recheck | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| missing_data | alt_verify | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| tool_failure | baseline | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_history_early | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 100% (21/21; per-run 85%-100%; by case 100%-100%) | 33% (7/21; per-run 17%-55%; by case 0%-70%) | 33% (7/21; per-run 17%-55%; by case 0%-70%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_recheck | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_verify | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |

## Harness pass rate by variant

| Variant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| baseline | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) |
| alt_history_early | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 5% (9/165; per-run 3%-10%; by case 0%-13%) | 73% (120/165; per-run 65%-79%; by case 62%-84%) | 73% (120/165; per-run 65%-79%; by case 62%-84%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) |
| alt_recheck | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 49% (81/165; per-run 42%-57%; by case 36%-62%) | 49% (81/165; per-run 42%-57%; by case 36%-62%) | 49% (81/165; per-run 42%-57%; by case 36%-62%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) |
| alt_verify | 85% (140/165; per-run 79%-90%; by case 76%-92%) | 85% (140/165; per-run 79%-90%; by case 76%-92%) | 52% (85/165; per-run 44%-59%; by case 38%-64%) | 52% (85/165; per-run 44%-59%; by case 38%-64%) | 52% (85/165; per-run 44%-59%; by case 38%-64%) | 85% (140/165; per-run 79%-90%; by case 76%-92%) |
| A | 68% (112/165; per-run 60%-75%; by case 56%-79%) | 47% (77/165; per-run 39%-54%; by case 34%-60%) | 47% (77/165; per-run 39%-54%; by case 34%-60%) | 47% (77/165; per-run 39%-54%; by case 34%-60%) | 68% (112/165; per-run 60%-75%; by case 56%-79%) | 47% (77/165; per-run 39%-54%; by case 34%-60%) |
| B | 74% (122/165; per-run 67%-80%; by case 62%-84%) | 74% (122/165; per-run 67%-80%; by case 62%-84%) | 74% (122/165; per-run 67%-80%; by case 62%-84%) | 74% (122/165; per-run 67%-80%; by case 62%-84%) | 74% (122/165; per-run 67%-80%; by case 62%-84%) | 74% (122/165; per-run 67%-80%; by case 62%-84%) |
| C | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 39% (64/165; per-run 32%-46%; by case 25%-52%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) |
| C1 | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) |
| C2 | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 15% (25/165; per-run 10%-21%; by case 7%-25%) | 82% (136/165; per-run 76%-87%; by case 73%-92%) |

Judge endorsed a reply the database contradicts: 0% (0/1485; per-run 0%-0%; by case 0%-0%)
