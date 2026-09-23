# langgraph-agent-evals

Companion code for the guide series **Evaluating LangGraph Agents in Production**
(https://ranjankumar.in/guides/langgraph-agent-evals).

One refund-processing LangGraph agent, a set of deliberately seeded faults, and an eval
harness that measures how often each layer of the eval stack is wrong. The agent runs
on a local Ollama model; the measured run's judge runs on Ollama Cloud through that
same local Ollama app. Setup and results are filled in as each part's stage lands.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)
- [Ollama](https://ollama.com), running locally. The policy model (`qwen3:4b`) always
  runs locally:

  ```bash
  ollama pull qwen3:4b
  ```

- The measured run's judge, `gpt-oss:20b-cloud`, runs on Ollama Cloud rather than on
  this machine — a 20B model is too slow on CPU-only hardware to grade a full run in a
  reasonable time. It is still called through the same local Ollama app on
  `http://localhost:11434`; nothing in this repo talks to a remote endpoint directly,
  and no API key is needed or stored anywhere in the repo. Sign in once and pull the
  cloud model tag:

  ```bash
  ollama signin
  ollama pull gpt-oss:20b-cloud
  ```

  To run everything fully locally instead (different judge, different numbers — see
  below), pull `gemma3:4b` and pass `--judge-model gemma3:4b` to
  `scripts.run_part1`:

  ```bash
  ollama pull gemma3:4b
  uv run python -m scripts.run_part1 --judge-model gemma3:4b ...
  ```

## Quickstart

```bash
uv sync
uv run pytest -m "not ollama" -q      # offline unit suite, no Ollama needed
uv run python -m scripts.run_part1 --ids H01,F01,R01 --k 1 --out results/smoke --allow-dirty
```

The last command is a small smoke run: one happy refund, one tool failure, and one
rejected approval, across all six agent variants, one trial each. It writes
`results/smoke/{metadata.json,runs.jsonl,summary.json,summary.md}` and a handful of
transcripts. It needs a running Ollama server signed in to Ollama Cloud (for the
judge) with `qwen3:4b` pulled locally, and takes a few minutes on CPU. Add
`--judge-model gemma3:4b` (after pulling it) to run the judge locally too, with no
Ollama Cloud dependency.

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
   run — either way, a different model family from the policy model) scoring 1-5
   against a reference description of the correct outcome.

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
  digest, temperature, `num_predict`, prompt, schema, and seed, and caches the
  response in a local SQLite file. Re-running an unchanged case replays instead of
  calling the model, and classification/refund-decision calls are shared across
  variants of the same case and trial, so `--out` reuse is cheap.
- **Frozen clock.** Every case's environment fixes "today" at `2026-06-15`
  (`env/fixtures.py`); nothing reads the system clock for policy decisions.
- **Recorded provenance.** Every `metadata.json` records the git commit, whether the
  tree was dirty, and both models' names, digests, temperatures, and whether each ran
  hosted (`"hosted": true` for a `-cloud` tag) or locally, so a results directory is
  traceable back to the exact code and model weights that produced it.
- **Cloud models can be retired.** Ollama Cloud tags such as `gpt-oss:20b-cloud` are
  not guaranteed to stay available indefinitely, unlike a locally pulled model file.
  Every result therefore also records the judge's name and the run date
  (`started_at`/`finished_at` in `metadata.json`), so a later reader can tell which
  judge produced a given number even if that judge tag is gone by the time they read
  it, and can reproduce with `--judge-model gemma3:4b` if the original judge is no
  longer reachable.
- **A changed judge needs a fresh `--out`.** `scripts/run_part1.py` refuses to resume
  into a `--out` directory whose recorded `policy_model`/`judge_model` name doesn't
  match the current run's, so switching `--judge-model` (or the policy model) never
  silently mixes rows graded by two different judges into one results directory.

## Part 1 results

Filled in after the measured run (Task 10).
