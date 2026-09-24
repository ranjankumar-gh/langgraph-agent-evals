# Part 1 results changelog

The measured run was made at commit `cc1b6f8` (see `metadata.json`). `runs.jsonl` and
`metadata.json` have not changed since. Everything below changed only how the
recorded runs are summarised or described.

## After the measured run

- **Report: conditional mutant survival, case-clustered intervals, per-slice
  brittle-fail.** `evals/report.py` now reports mutant survival conditioned on the
  baseline as the primary figure: for mutant M and harness H, among (case, trial)
  pairs where M's fault fired and the baseline run for the same (case, trial) passes
  H, the fraction where M's run passes H. Pairs whose baseline fails H, or that have
  no baseline row, are excluded and counted. The previous figure is kept as
  `mutant_survival_unconditional`. Every rate now also carries `ci95_case`, a
  case-clustered percentile bootstrap interval (`random.Random(0)`, 2000 resamples
  of case ids), beside the per-run Wilson `ci95`. The summary adds the brittle-fail
  rate per trajectory layer for each valid variant within each slice. Report code
  and its tests only: `runs.jsonl` is unchanged, and `summary.json`, `summary.md`
  and `transcripts/` were regenerated offline with
  `python -m scripts.run_part1 --summarize-only --out results/part-1`.
- **`agent/llm.py` module docstring corrected.** It said the trial seed makes every
  variant see the same draw. Ollama Cloud does not honour the seed; for hosted models
  it is the record/replay cache that pairs variants. Docstring only: no executable
  change (the module's AST minus its docstring is identical), and the docstring is
  not part of any cache key, so every cached entry and every recorded run is
  unaffected.
