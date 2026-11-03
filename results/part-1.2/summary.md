# Part 1 results

Commit `5a2dc9b2a47621aff0f4eb3eb53dd22dd6e9c8b5` - langgraph 1.2.12 - policy `nemotron-3-nano:30b-cloud` - judge `gpt-oss:20b-cloud` - k=3 - 1980 runs, 6 crashed, 0 grading errors

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
| baseline | 1% (2/140; per-run 0%-5%; by case 0%-4%) |
| alt_history_early | 1% (2/140; per-run 0%-5%; by case 0%-4%) |
| alt_recheck | 1% (2/141; per-run 0%-5%; by case 0%-4%) |
| alt_verify | 1% (2/150; per-run 0%-5%; by case 0%-4%) |
| all | 9% (147/1652; per-run 8%-10%; by case 6%-12%) |

## Brittle-fail rate on valid variants (lower is better)

| Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|
| baseline | 0% (0/138; per-run 0%-3%; by case 0%-0%) | 0% (0/138; per-run 0%-3%; by case 0%-0%) | 0% (0/138; per-run 0%-3%; by case 0%-0%) | 0% (0/138; per-run 0%-3%; by case 0%-0%) | 0% (0/138; per-run 0%-3%; by case 0%-0%) |
| alt_history_early | 0% (0/138; per-run 0%-3%; by case 0%-0%) | 94% (130/138; per-run 89%-97%; by case 87%-100%) | 14% (19/138; per-run 9%-21%; by case 5%-25%) | 14% (19/138; per-run 9%-21%; by case 5%-25%) | 0% (0/138; per-run 0%-3%; by case 0%-0%) |
| alt_recheck | 0% (0/139; per-run 0%-3%; by case 0%-0%) | 41% (57/139; per-run 33%-49%; by case 27%-56%) | 41% (57/139; per-run 33%-49%; by case 27%-56%) | 41% (57/139; per-run 33%-49%; by case 27%-56%) | 0% (0/139; per-run 0%-3%; by case 0%-0%) |
| alt_verify | 0% (0/148; per-run 0%-3%; by case 0%-0%) | 39% (58/148; per-run 32%-47%; by case 26%-53%) | 39% (58/148; per-run 32%-47%; by case 26%-53%) | 39% (58/148; per-run 32%-47%; by case 26%-53%) | 0% (0/148; per-run 0%-3%; by case 0%-0%) |

## By slice

Mutant survival pools every fired run of A, B and C in the slice.

| Slice | Mutant survival, answer-only (conditioned on baseline) | Mutant survival, three-artifact (conditioned on baseline) | Mutant survival, answer-only (unconditional) | Mutant survival, three-artifact (unconditional) | TBP rate |
|---|---|---|---|---|---|
| ambiguous | - | - | - | - | 6% (12/196; per-run 4%-10%; by case 1%-12%) |
| approval_rejected | - | - | - | - | 10% (17/174; per-run 6%-15%; by case 9%-11%) |
| changed_order | - | - | - | - | 0% (0/8; per-run 0%-32%; by case 0%-0%) |
| happy | - | - | - | - | 13% (45/342; per-run 10%-17%; by case 10%-16%) |
| ineligible | - | - | - | - | 6% (18/279; per-run 4%-10%; by case 3%-9%) |
| injection | - | - | - | - | 19% (34/177; per-run 14%-26%; by case 5%-47%) |
| missing_data | - | - | - | - | 3% (6/213; per-run 1%-6%; by case 0%-6%) |
| tool_failure | - | - | - | - | 6% (15/263; per-run 3%-9%; by case 2%-8%) |

## Brittle-fail rate by slice (valid variants; lower is better)

| Slice | Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|---|
| ambiguous | baseline | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| ambiguous | alt_history_early | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 47% (7/15; per-run 25%-70%; by case 7%-87%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| ambiguous | alt_recheck | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 50% (8/16; per-run 28%-72%; by case 12%-88%) | 50% (8/16; per-run 28%-72%; by case 12%-88%) | 50% (8/16; per-run 28%-72%; by case 12%-88%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) |
| ambiguous | alt_verify | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 53% (9/17; per-run 31%-74%; by case 17%-88%) | 53% (9/17; per-run 31%-74%; by case 17%-88%) | 53% (9/17; per-run 31%-74%; by case 17%-88%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | baseline | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) |
| approval_rejected | alt_history_early | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 100% (16/16; per-run 81%-100%; by case 100%-100%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) |
| approval_rejected | alt_recheck | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) |
| approval_rejected | alt_verify | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) | 0% (0/16; per-run 0%-19%; by case 0%-0%) |
| changed_order | alt_verify | 0% (0/8; per-run 0%-32%; by case 0%-0%) | 0% (0/8; per-run 0%-32%; by case 0%-0%) | 0% (0/8; per-run 0%-32%; by case 0%-0%) | 0% (0/8; per-run 0%-32%; by case 0%-0%) | 0% (0/8; per-run 0%-32%; by case 0%-0%) |
| happy | baseline | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_history_early | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_recheck | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_verify | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| ineligible | baseline | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_history_early | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 100% (24/24; per-run 86%-100%; by case 100%-100%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_recheck | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_verify | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| injection | baseline | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) |
| injection | alt_history_early | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 100% (13/13; per-run 77%-100%; by case 100%-100%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) |
| injection | alt_recheck | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 31% (4/13; per-run 13%-58%; by case 0%-73%) | 31% (4/13; per-run 13%-58%; by case 0%-73%) | 31% (4/13; per-run 13%-58%; by case 0%-73%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) |
| injection | alt_verify | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 31% (4/13; per-run 13%-58%; by case 0%-73%) | 31% (4/13; per-run 13%-58%; by case 0%-73%) | 31% (4/13; per-run 13%-58%; by case 0%-73%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) |
| missing_data | baseline | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) |
| missing_data | alt_history_early | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 100% (18/18; per-run 82%-100%; by case 100%-100%) | 67% (12/18; per-run 44%-84%; by case 33%-100%) | 67% (12/18; per-run 44%-84%; by case 33%-100%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) |
| missing_data | alt_recheck | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) |
| missing_data | alt_verify | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) | 0% (0/18; per-run 0%-18%; by case 0%-0%) |
| tool_failure | baseline | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_history_early | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 100% (22/22; per-run 85%-100%; by case 100%-100%) | 32% (7/22; per-run 16%-53%; by case 0%-70%) | 32% (7/22; per-run 16%-53%; by case 0%-70%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_recheck | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 68% (15/22; per-run 47%-84%; by case 30%-100%) | 68% (15/22; per-run 47%-84%; by case 30%-100%) | 68% (15/22; per-run 47%-84%; by case 30%-100%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_verify | 0% (0/22; per-run 0%-15%; by case 0%-0%) | 68% (15/22; per-run 47%-84%; by case 30%-100%) | 68% (15/22; per-run 47%-84%; by case 30%-100%) | 68% (15/22; per-run 47%-84%; by case 30%-100%) | 0% (0/22; per-run 0%-15%; by case 0%-0%) |

## Harness pass rate by variant

| Variant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| baseline | 85% (140/165; per-run 79%-90%; by case 76%-93%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) |
| alt_history_early | 85% (140/165; per-run 79%-90%; by case 76%-93%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) | 5% (8/165; per-run 2%-9%; by case 0%-11%) | 72% (119/165; per-run 65%-78%; by case 61%-83%) | 72% (119/165; per-run 65%-78%; by case 61%-83%) | 84% (138/165; per-run 77%-89%; by case 75%-92%) |
| alt_recheck | 85% (141/165; per-run 79%-90%; by case 77%-93%) | 84% (139/165; per-run 78%-89%; by case 76%-93%) | 50% (82/165; per-run 42%-57%; by case 37%-62%) | 50% (82/165; per-run 42%-57%; by case 37%-62%) | 50% (82/165; per-run 42%-57%; by case 37%-62%) | 84% (139/165; per-run 78%-89%; by case 76%-93%) |
| alt_verify | 91% (150/165; per-run 86%-94%; by case 84%-96%) | 90% (148/165; per-run 84%-93%; by case 82%-96%) | 55% (90/165; per-run 47%-62%; by case 41%-67%) | 55% (90/165; per-run 47%-62%; by case 41%-67%) | 55% (90/165; per-run 47%-62%; by case 41%-67%) | 90% (148/165; per-run 84%-93%; by case 82%-96%) |

Judge endorsed a reply the database contradicts: 2% (43/1980; per-run 2%-3%; by case 1%-5%)
