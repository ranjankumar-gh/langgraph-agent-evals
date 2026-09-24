# Part 1 results

Commit `cc1b6f8b0fad2b79d51ed4e9694dcee34e3fd073` - langgraph 1.2.12 - policy `nemotron-3-nano:30b-cloud` - judge `gpt-oss:20b-cloud` - k=3 - 936 runs, 0 crashed, 0 grading errors

Every cell: rate (k/n; per-run Wilson 95% CI; by-case bootstrap 95% CI). Outcomes cluster by case, so the per-run interval understates uncertainty; the by-case interval is the one to cite.

## Mutant survival, conditioned on baseline passing (primary; lower is better)

Among (case, trial) pairs where the mutant's fault fired and the baseline run for the same (case, trial) passes the harness, the fraction where the mutant's run also passes.

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 59% (35/59; per-run 47%-71%; by case 37%-80%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) | 59% (35/59; per-run 47%-71%; by case 37%-80%) | 0% (0/59; per-run 0%-6%; by case 0%-0%) |
| B | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) | 0% (0/14; per-run 0%-22%; by case 0%-0%) |
| C | 100% (111/111; per-run 97%-100%; by case 100%-100%) | 35% (39/111; per-run 27%-44%; by case 19%-51%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 0% (0/111; per-run 0%-3%; by case 0%-0%) | 100% (111/111; per-run 97%-100%; by case 100%-100%) |

Fired pairs excluded from the table above (baseline run fails the harness / no baseline row):

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 8 / 0 | 8 / 0 | 8 / 0 | 8 / 0 | 8 / 0 | 8 / 0 |
| B | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 | 1 / 0 |
| C | 15 / 0 | 15 / 0 | 15 / 0 | 15 / 0 | 15 / 0 | 15 / 0 |

## Mutant survival, unconditional (secondary; lower is better)

Among fired runs of the mutant, the fraction that pass the harness, ignoring the baseline.

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 52% (35/67; per-run 40%-64%; by case 33%-73%) | 0% (0/67; per-run 0%-5%; by case 0%-0%) | 0% (0/67; per-run 0%-5%; by case 0%-0%) | 0% (0/67; per-run 0%-5%; by case 0%-0%) | 52% (35/67; per-run 40%-64%; by case 33%-73%) | 0% (0/67; per-run 0%-5%; by case 0%-0%) |
| B | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| C | 88% (111/126; per-run 81%-93%; by case 79%-96%) | 31% (39/126; per-run 24%-39%; by case 17%-45%) | 0% (0/126; per-run 0%-3%; by case 0%-0%) | 0% (0/126; per-run 0%-3%; by case 0%-0%) | 0% (0/126; per-run 0%-3%; by case 0%-0%) | 88% (111/126; per-run 81%-93%; by case 79%-96%) |

## Trajectory-Blind Pass rate

| Variant | TBP rate |
|---|---|
| baseline | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_history_early | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_recheck | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| A | 31% (35/112; per-run 23%-40%; by case 17%-46%) |
| B | 0% (0/122; per-run 0%-3%; by case 0%-0%) |
| C | 53% (72/136; per-run 45%-61%; by case 38%-66%) |
| all | 14% (107/778; per-run 12%-16%; by case 10%-18%) |

## Brittle-fail rate on valid variants (lower is better)

| Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|
| baseline | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_history_early | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 93% (127/136; per-run 88%-96%; by case 85%-100%) | 12% (16/136; per-run 7%-18%; by case 4%-21%) | 12% (16/136; per-run 7%-18%; by case 4%-21%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) |
| alt_recheck | 0% (0/136; per-run 0%-3%; by case 0%-0%) | 40% (55/136; per-run 33%-49%; by case 26%-54%) | 40% (55/136; per-run 33%-49%; by case 26%-54%) | 40% (55/136; per-run 33%-49%; by case 26%-54%) | 0% (0/136; per-run 0%-3%; by case 0%-0%) |

## By slice

Mutant survival pools every fired run of A, B and C in the slice.

| Slice | Mutant survival, answer-only (conditioned on baseline) | Mutant survival, three-artifact (conditioned on baseline) | Mutant survival, answer-only (unconditional) | Mutant survival, three-artifact (unconditional) | TBP rate |
|---|---|---|---|---|---|
| ambiguous | 100% (11/11; per-run 74%-100%; by case 100%-100%) | 0% (0/11; per-run 0%-26%; by case 0%-0%) | 85% (11/13; per-run 58%-96%; by case 67%-100%) | 0% (0/13; per-run 0%-23%; by case 0%-0%) | 11% (11/102; per-run 6%-18%; by case 3%-21%) |
| approval_rejected | 100% (26/26; per-run 87%-100%; by case 100%-100%) | 0% (0/26; per-run 0%-13%; by case 0%-0%) | 96% (26/27; per-run 82%-99%; by case 88%-100%) | 0% (0/27; per-run 0%-12%; by case 0%-0%) | 25% (26/102; per-run 18%-35%; by case 19%-31%) |
| happy | 100% (45/45; per-run 92%-100%; by case 100%-100%) | 0% (0/45; per-run 0%-8%; by case 0%-0%) | 100% (45/45; per-run 92%-100%; by case 100%-100%) | 0% (0/45; per-run 0%-8%; by case 0%-0%) | 25% (45/180; per-run 19%-32%; by case 20%-30%) |
| ineligible | 62% (24/39; per-run 46%-75%; by case 53%-80%) | 62% (24/39; per-run 46%-75%; by case 53%-80%) | 62% (24/39; per-run 46%-75%; by case 53%-80%) | 62% (24/39; per-run 46%-75%; by case 53%-80%) | 0% (0/129; per-run 0%-3%; by case 0%-0%) |
| injection | 67% (12/18; per-run 44%-84%; by case 50%-100%) | 50% (9/18; per-run 29%-71%; by case 20%-80%) | 33% (12/36; per-run 20%-50%; by case 10%-60%) | 25% (9/36; per-run 14%-41%; by case 7%-46%) | 5% (3/66; per-run 2%-13%; by case 0%-13%) |
| missing_data | 67% (6/9; per-run 35%-88%; by case 50%-100%) | 67% (6/9; per-run 35%-88%; by case 50%-100%) | 67% (6/9; per-run 35%-88%; by case 50%-100%) | 67% (6/9; per-run 35%-88%; by case 50%-100%) | 0% (0/87; per-run 0%-4%; by case 0%-0%) |
| tool_failure | 61% (22/36; per-run 45%-75%; by case 53%-67%) | 0% (0/36; per-run 0%-10%; by case 0%-0%) | 56% (22/39; per-run 41%-71%; by case 47%-64%) | 0% (0/39; per-run 0%-9%; by case 0%-0%) | 20% (22/112; per-run 13%-28%; by case 7%-32%) |

## Brittle-fail rate by slice (valid variants; lower is better)

| Slice | Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|---|
| ambiguous | baseline | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| ambiguous | alt_history_early | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| ambiguous | alt_recheck | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 47% (8/17; per-run 26%-69%; by case 12%-83%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | baseline | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | alt_history_early | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 100% (17/17; per-run 82%-100%; by case 100%-100%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| approval_rejected | alt_recheck | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) | 0% (0/17; per-run 0%-18%; by case 0%-0%) |
| happy | baseline | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_history_early | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| happy | alt_recheck | 0% (0/30; per-run 0%-11%; by case 0%-0%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 100% (30/30; per-run 89%-100%; by case 100%-100%) | 0% (0/30; per-run 0%-11%; by case 0%-0%) |
| ineligible | baseline | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_history_early | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 100% (24/24; per-run 86%-100%; by case 100%-100%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| ineligible | alt_recheck | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) | 0% (0/24; per-run 0%-14%; by case 0%-0%) |
| injection | baseline | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| injection | alt_history_early | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 100% (12/12; per-run 76%-100%; by case 100%-100%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| injection | alt_recheck | 0% (0/12; per-run 0%-24%; by case 0%-0%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 25% (3/12; per-run 9%-53%; by case 0%-75%) | 0% (0/12; per-run 0%-24%; by case 0%-0%) |
| missing_data | baseline | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| missing_data | alt_history_early | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 100% (15/15; per-run 80%-100%; by case 100%-100%) | 60% (9/15; per-run 36%-80%; by case 17%-100%) | 60% (9/15; per-run 36%-80%; by case 17%-100%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| missing_data | alt_recheck | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) | 0% (0/15; per-run 0%-20%; by case 0%-0%) |
| tool_failure | baseline | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_history_early | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 100% (21/21; per-run 85%-100%; by case 100%-100%) | 33% (7/21; per-run 17%-55%; by case 0%-70%) | 33% (7/21; per-run 17%-55%; by case 0%-70%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |
| tool_failure | alt_recheck | 0% (0/21; per-run 0%-15%; by case 0%-0%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 67% (14/21; per-run 45%-83%; by case 30%-100%) | 0% (0/21; per-run 0%-15%; by case 0%-0%) |

## Harness pass rate by variant

| Variant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| baseline | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) |
| alt_history_early | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 6% (9/156; per-run 3%-11%; by case 0%-12%) | 77% (120/156; per-run 70%-83%; by case 65%-87%) | 77% (120/156; per-run 70%-83%; by case 65%-87%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) |
| alt_recheck | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 52% (81/156; per-run 44%-60%; by case 38%-65%) | 52% (81/156; per-run 44%-60%; by case 38%-65%) | 52% (81/156; per-run 44%-60%; by case 38%-65%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) |
| A | 72% (112/156; per-run 64%-78%; by case 60%-83%) | 49% (77/156; per-run 42%-57%; by case 36%-62%) | 49% (77/156; per-run 42%-57%; by case 36%-62%) | 49% (77/156; per-run 42%-57%; by case 36%-62%) | 72% (112/156; per-run 64%-78%; by case 60%-83%) | 49% (77/156; per-run 42%-57%; by case 36%-62%) |
| B | 78% (122/156; per-run 71%-84%; by case 67%-88%) | 78% (122/156; per-run 71%-84%; by case 67%-88%) | 78% (122/156; per-run 71%-84%; by case 67%-88%) | 78% (122/156; per-run 71%-84%; by case 67%-88%) | 78% (122/156; per-run 71%-84%; by case 67%-88%) | 78% (122/156; per-run 71%-84%; by case 67%-88%) |
| C | 87% (136/156; per-run 81%-92%; by case 79%-95%) | 41% (64/156; per-run 34%-49%; by case 28%-54%) | 16% (25/156; per-run 11%-23%; by case 7%-26%) | 16% (25/156; per-run 11%-23%; by case 7%-26%) | 16% (25/156; per-run 11%-23%; by case 7%-26%) | 87% (136/156; per-run 81%-92%; by case 79%-95%) |

Judge endorsed a reply the database contradicts: 0% (0/936; per-run 0%-0%; by case 0%-0%)
