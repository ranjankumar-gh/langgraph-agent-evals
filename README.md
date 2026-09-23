# langgraph-agent-evals

Companion code for the guide series **Evaluating LangGraph Agents in Production**
(https://ranjankumar.in/guides/langgraph-agent-evals).

One refund-processing LangGraph agent, a set of deliberately seeded faults, and an eval
harness that measures how often each layer of the eval stack is wrong. The measured run
uses two open-weight models on Ollama Cloud, both reached through the local Ollama app:
the agent runs on `nemotron-3-nano:30b` (NVIDIA) and the judge on `gpt-oss:20b` (OpenAI)
— different model families, so the judge is never grading its own family. Setup and
results are filled in as each part's stage lands.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com), running locally. Both the agent and the judge run on
  Ollama Cloud rather than on this machine — a 30B/20B model is too slow on CPU-only
  hardware to run a full measured run in a reasonable time. Both are still called
  through the same local Ollama app on `http://localhost:11434`; nothing in this repo
  talks to a remote endpoint directly, and no API key is needed or stored anywhere in
  the repo. Sign in once and pull both cloud model tags:

  ```bash
  ollama signin
  ollama pull nemotron-3-nano:30b-cloud gpt-oss:20b-cloud
  ```

  Ollama Cloud ignores the JSON-schema output constraint that local Ollama models
  honour — a raw structured-output call against a cloud model just returns free text.
  `agent/llm.py` detects a hosted model (any name ending `-cloud`) and asks for
  structured output via tool calling instead, which cloud models do support; local
  models keep the JSON-schema path.

  The harness still runs fully locally (different models, much slower on CPU-only
  hardware, and different numbers) by pointing both flags at locally pulled models:

  ```bash
  ollama pull qwen3:4b gemma3:4b
  uv run python -m scripts.run_part1 --policy-model qwen3:4b --judge-model gemma3:4b ...
  ```

  Ollama Cloud model tags can be retired; every `metadata.json` records both models'
  exact names and the run's start/finish dates, so a results directory stays
  traceable back to what produced it even after a cloud tag is gone.

## Quickstart

```bash
uv sync
uv run pytest -m "not ollama" -q      # offline unit suite, no Ollama needed
uv run python -m scripts.run_part1 --ids H01,F01,R01 --k 1 --out results/smoke --allow-dirty
```

The last command is a small smoke run: one happy refund, one tool failure, and one
rejected approval, across all six agent variants, one trial each. It writes
`results/smoke/{metadata.json,runs.jsonl,summary.json,summary.md}` and a handful of
transcripts. It needs a running Ollama server signed in to Ollama Cloud, with
`nemotron-3-nano:30b-cloud` and `gpt-oss:20b-cloud` pulled, and takes a few minutes.
Add `--policy-model qwen3:4b --judge-model gemma3:4b` (after pulling both) to run
everything locally instead, with no Ollama Cloud dependency — much slower on CPU, and
the numbers won't match the cloud-model run.

## The agent

`agent/graph.py` builds one LangGraph state machine, selected by a `variant` name, so
every variant shares one code path except the lines that define it:

```
classify_request -> lookup_order -> get_refund_history -> check_eligibility
  -> compute_refund -> [request_approval if amount > 1000] -> issue_refund -> respond
```

- `classify_request` and `compute_refund` are LLM-backed (structured output against a
  Pydantic schema); `respond` is a free-text LLM call. Every other node calls a
  deterministic tool in `agent/tools.py` against a seeded SQLite database
  (`env/db.py`, `env/fixtures.py`).
- `request_approval` is a real LangGraph interrupt: refunds over $1000 pause for a
  human decision and resume with `approve` or `reject`.

### Variants

| Variant | Kind | Behaviour |
|---|---|---|
| `baseline` | valid | classify -> lookup_order -> get_refund_history -> check_eligibility -> compute_refund -> [request_approval if > 1000] -> issue_refund -> respond |
| `alt_history_early` | valid | fetches refund history before the order (a legitimate reordering of two independent reads) |
| `alt_recheck` | valid | re-reads the order immediately before `issue_refund` (a legitimate safety re-read before money moves) |
| `A` | mutant | skips `check_eligibility` when the classified intent is `damaged` ("sounds valid") |
| `B` | mutant | when `issue_refund` fails, `respond` reports refund status from the plan (`refund_amount`) instead of the observation (`refund_id`) |
| `C` | mutant | re-looks-up the order in `check_eligibility`, `compute_refund`, and `issue_refund` (4 lookups total) |

Full detail, including why each mutant stands in for a real-world fault class, is in
[`docs/variants.md`](docs/variants.md).

## Check layers and harnesses

Every run of a (case, variant, trial) is graded by three independent check layers:

1. **End state** (`evals/checks/end_state.py`) — what actually changed in the system
   of record: the refund rows a case's database ends up with, compared against the
   case's acceptable end states. Reads the database, not the agent's messages.
2. **Trajectory** (`evals/checks/trajectory.py`) — what the agent did: case-authored
   constraints (`required`/`forbidden`/`ordering`/`max_calls` tool calls) plus
   reference-trajectory matching in four modes (`strict`, `unordered`, `subset`,
   `superset`). `subset`/`superset` are multiset (not plain set) comparisons — a tool
   called twice in the observed trajectory but once in the reference fails `subset`
   even though the *set* of tool names is a subset. See
   [`docs/matcher-semantics.md`](docs/matcher-semantics.md) for the full semantics and
   how they were cross-checked against `agentevals` 0.0.9.
3. **Answer** (`evals/checks/answer.py`) — what the agent said: a deterministic string
   check (mentions the right amount, avoids forbidden phrases) plus a single-pass LLM
   judge (`gpt-oss:20b-cloud` for the measured run, or `gemma3:4b` for a fully local
   run — either way, a different model family from the policy model, so the judge is
   never grading its own family) scoring 1-5 against a reference description of the
   correct outcome.

`evals/report.py` combines these into harnesses that a run either passes or fails:
`answer_only` (layer 3 alone), `three_artifact` (all three layers, trajectory judged by
its constraints), and one `mode:<strict|unordered|subset|superset>` harness per
trajectory match mode (end state + answer + that one match mode). A crashed run passes
none of them; a run whose judge call itself failed (`grading_error`) is excluded from
every rate rather than counted as a failure.

## Metric definitions

Copied from `evals/report.py`'s module docstring:

- **Mutant survival** for harness H and mutant M: among runs of M where M's fault
  fired, the fraction H passes.
- **Trajectory-Blind Pass rate (TBP)**: among runs that pass the answer-only harness,
  the fraction that fail the three-artifact harness.
- **Brittle-fail rate** for trajectory layer L: among valid-variant runs whose end
  state and answer both pass, the fraction L rejects.
- A crashed run passes no harness.
- Runs whose grader failed (`grading_error`) are excluded from every rate and counted
  separately.

All rates carry Wilson 95% confidence intervals.

## Reproducibility

- **Seed = trial index.** `run_case` seeds every LLM call in a trial with the trial
  number, so every variant sees the same sampling draw for the same (case, trial) —
  variant B's compute-refund call on case H01 trial 2 uses the same seed as baseline's.
- **Record/replay cache.** `agent/llm.py`'s `OllamaLLM` keys every call on model name,
  digest, temperature, `num_predict`, prompt, schema, structured-output method
  (`function_calling` for hosted models, `json_schema` for local ones), and seed, and
  caches the response in a local SQLite file. Re-running an unchanged case replays
  instead of calling the model, and classification/refund-decision calls are shared
  across variants of the same case and trial, so `--out` reuse is cheap.
- **Frozen clock.** Every case's environment fixes "today" at `2026-06-15`
  (`env/fixtures.py`); nothing reads the system clock for policy decisions.
- **Recorded provenance.** Every `metadata.json` records the git commit, whether the
  tree was dirty, and both models' names, digests, temperatures, and whether each ran
  hosted (`"hosted": true` for a `-cloud` tag) or locally, so a results directory is
  traceable back to the exact code and model weights that produced it.
- **Cloud models can be retired.** Ollama Cloud tags such as `nemotron-3-nano:30b-cloud`
  and `gpt-oss:20b-cloud` are not guaranteed to stay available indefinitely, unlike a
  locally pulled model file. Every result therefore also records both models' names
  and the run date (`started_at`/`finished_at` in `metadata.json`), so a later reader
  can tell which agent and judge produced a given number even if those tags are gone
  by the time they read it, and can reproduce with `--policy-model qwen3:4b
  --judge-model gemma3:4b` if the originals are no longer reachable.
- **A changed judge needs a fresh `--out`.** `scripts/run_part1.py` refuses to resume
  into a `--out` directory whose recorded `policy_model`/`judge_model` name doesn't
  match the current run's, so switching `--judge-model` (or the policy model) never
  silently mixes rows graded by two different judges into one results directory.

## Part 1 results

Measured run at commit `cc1b6f8b0fad2b79d51ed4e9694dcee34e3fd073`, LangGraph `1.2.12`. Policy
model `nemotron-3-nano:30b-cloud` (digest `6fe6f0516d95790b0494e37f26309726b96ec0c78922c86a0208b4253e578beb`),
judge model `gpt-oss:20b-cloud` (digest `cc40af19c7ab8964518c996e5e747c5810ba5ce38366e5f399a291210475e7cb`)
— both Ollama Cloud models, reached through the local Ollama app. k=3, 52 cases x 6 variants =
936 runs, 0 crashed, 0 grading errors, 0 retries. Run window: 2026-09-23 11:36:56 UTC to
2026-09-23 12:38:37 UTC.

### Mutant survival (lower is better)

| Mutant | answer_only | three_artifact | mode:strict | mode:unordered | mode:subset | mode:superset |
|---|---|---|---|---|---|---|
| A | 52% (35/67; 95% CI 40%-64%) | 0% (0/67; 95% CI 0%-5%) | 0% (0/67; 95% CI 0%-5%) | 0% (0/67; 95% CI 0%-5%) | 52% (35/67; 95% CI 40%-64%) | 0% (0/67; 95% CI 0%-5%) |
| B | 0% (0/15; 95% CI 0%-20%) | 0% (0/15; 95% CI 0%-20%) | 0% (0/15; 95% CI 0%-20%) | 0% (0/15; 95% CI 0%-20%) | 0% (0/15; 95% CI 0%-20%) | 0% (0/15; 95% CI 0%-20%) |
| C | 88% (111/126; 95% CI 81%-93%) | 31% (39/126; 95% CI 24%-39%) | 0% (0/126; 95% CI 0%-3%) | 0% (0/126; 95% CI 0%-3%) | 0% (0/126; 95% CI 0%-3%) | 88% (111/126; 95% CI 81%-93%) |

### Trajectory-Blind Pass rate

| Variant | TBP rate |
|---|---|
| baseline | 0% (0/136; 95% CI 0%-3%) |
| alt_history_early | 0% (0/136; 95% CI 0%-3%) |
| alt_recheck | 0% (0/136; 95% CI 0%-3%) |
| A | 31% (35/112; 95% CI 23%-40%) |
| B | 0% (0/122; 95% CI 0%-3%) |
| C | 53% (72/136; 95% CI 45%-61%) |
| all | 14% (107/778; 95% CI 12%-16%) |

### Brittle-fail rate on valid variants (lower is better)

| Variant | constraints | strict | unordered | subset | superset |
|---|---|---|---|---|---|
| baseline | 0% (0/136; 95% CI 0%-3%) | 0% (0/136; 95% CI 0%-3%) | 0% (0/136; 95% CI 0%-3%) | 0% (0/136; 95% CI 0%-3%) | 0% (0/136; 95% CI 0%-3%) |
| alt_history_early | 0% (0/136; 95% CI 0%-3%) | 93% (127/136; 95% CI 88%-96%) | 12% (16/136; 95% CI 7%-18%) | 12% (16/136; 95% CI 7%-18%) | 0% (0/136; 95% CI 0%-3%) |
| alt_recheck | 0% (0/136; 95% CI 0%-3%) | 40% (55/136; 95% CI 33%-49%) | 40% (55/136; 95% CI 33%-49%) | 40% (55/136; 95% CI 33%-49%) | 0% (0/136; 95% CI 0%-3%) |

### By slice

| Slice | Mutant survival, answer-only | Mutant survival, three-artifact | TBP rate |
|---|---|---|---|
| ambiguous | 85% (11/13; 95% CI 58%-96%) | 0% (0/13; 95% CI 0%-23%) | 11% (11/102; 95% CI 6%-18%) |
| approval_rejected | 96% (26/27; 95% CI 82%-99%) | 0% (0/27; 95% CI 0%-12%) | 25% (26/102; 95% CI 18%-35%) |
| happy | 100% (45/45; 95% CI 92%-100%) | 0% (0/45; 95% CI 0%-8%) | 25% (45/180; 95% CI 19%-32%) |
| ineligible | 62% (24/39; 95% CI 46%-75%) | 62% (24/39; 95% CI 46%-75%) | 0% (0/129; 95% CI 0%-3%) |
| injection | 33% (12/36; 95% CI 20%-50%) | 25% (9/36; 95% CI 14%-41%) | 5% (3/66; 95% CI 2%-13%) |
| missing_data | 67% (6/9; 95% CI 35%-88%) | 67% (6/9; 95% CI 35%-88%) | 0% (0/87; 95% CI 0%-4%) |
| tool_failure | 56% (22/39; 95% CI 41%-71%) | 0% (0/39; 95% CI 0%-9%) | 20% (22/112; 95% CI 13%-28%) |

### Notes

The judge endorsed a reply the database contradicted in 0 of 936 runs (`answer_pass` true,
`end_state_pass` false, not crashed). There are no judge-fooled transcripts in this run.

Mutant C survives the three-artifact harness in 31% of its fired runs (39/126). All 39 of
those passing runs share the same shape: exactly 2 `lookup_order` calls and no `issue_refund`
call — i.e. the case ends before a refund is issued, so mutant C's redundant lookup in
`check_eligibility` is the only extra one that fires, landing at 2 total lookups, inside the
`max_calls={"lookup_order": 2}` constraint that legitimate cases (including the `alt_recheck`
path's extra re-read) are allowed. The 87 runs where C is caught split into 18 that also stop
before `issue_refund` but still make 3 lookups (over the limit) and 69 that reach `issue_refund`
with the full 4 redundant lookups from `check_eligibility`, `compute_refund`, and `issue_refund`.

The alternate-path review sampled 10 runs (5 `alt_history_early`, 5 `alt_recheck`) whose tool
sequence diverged from the case's reference path; Ranjan reviewed all 10 on 2026-09-23 and
confirmed every one a valid way to handle its request. See
[`results/part-1/alt-path-review.md`](results/part-1/alt-path-review.md).

The baseline agent passes three-artifact on 87% of runs (136/156); its 20 failing runs span 10
distinct cases (A05, F05, F06, J01, J03, J04, J06, N01, N04, R02), and in every one of those 20
runs it is the answer check that fails (`answer_pass` false), per `results/part-1/runs.jsonl`.

Two trajectory-blind transcripts (answer and end state both pass, trajectory constraints fail):
mutant A —
[`results/part-1/transcripts/trajectory-blind-A04-A-t1.md`](results/part-1/transcripts/trajectory-blind-A04-A-t1.md)
(skips `check_eligibility` before `issue_refund`); mutant C —
[`results/part-1/transcripts/trajectory-blind-A04-C-t0.md`](results/part-1/transcripts/trajectory-blind-A04-C-t0.md)
(`lookup_order` called 4 times, over the max-2 limit).
