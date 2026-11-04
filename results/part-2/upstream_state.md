# Upstream state at the fork point (part-2 run)

Generated offline by `uv run python -m scripts.upstream_state --runs results/part-2` (no model calls). It recovers each classify_request output from the record/replay cache keys, because runs.jsonl does not record the classification. Per-pair rows are in `upstream_state.jsonl`. Fork arms start after classify_request, so only the baseline and each full rerun are covered. E shares D's namespaces.

"Ceiling estimate" is the share of the full rerun's squared delta deviation (change minus baseline, same case and trial) that sits on pairs whose upstream state differed. It estimates the largest fraction of the delta's variance a fork from this point could remove.

```text
baseline: 96 forkable pairs, 0 without a cached classification, 2 with a different upstream state (A04/t0, A04/t2)
  ceiling estimate, three_artifact: n=96, share on mismatched pairs 0.0398%
  ceiling estimate, judge_score: n=96, share on mismatched pairs 0.0239%
D: 96 forkable pairs, 0 without a cached classification, 2 with a different upstream state (A04/t2, A05/t2)
  ceiling estimate, three_artifact: n=95, share on mismatched pairs 0.0407%
  ceiling estimate, judge_score: n=95, share on mismatched pairs 0.0215%
```
