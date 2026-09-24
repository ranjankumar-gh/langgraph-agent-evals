"""Resume/provenance checks shared by the measured-run CLIs.

A results directory holds runs from one commit and one policy/judge model pair. Refuse to
measure uncommitted code (unless explicitly allowed, for smoke runs), to mix commits or
models in one directory, or to resume runs whose provenance is unknown."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def guard(out: Path, *, commit: str, dirty: bool, allow_dirty: bool, policy_model: str, judge_model: str,
          changes: list[str] | None = None) -> dict | None:
    """Return the previous metadata.json when resuming into `out`, else None; exit on any conflict.

    `changes` is optional and only checked when given and the previous metadata records its own
    "changes" list (run_part1 never passes it, so its behaviour is unchanged): a resume at a
    different --changes would otherwise silently wipe runs.jsonl's provenance for the changes
    already recorded there, so it is refused instead."""
    runs_path = out / "runs.jsonl"
    meta_path = out / "metadata.json"
    if dirty and not allow_dirty:
        sys.exit("agent/, env/ or evals/ has uncommitted changes; commit before a measured run")
    previous = None
    if meta_path.exists():
        previous = json.loads(meta_path.read_text())
        if previous["git_commit"] != commit:
            sys.exit(f"{out} holds runs from {previous['git_commit']}; use a new --out or delete it")
        if previous["policy_model"]["name"] != policy_model:
            sys.exit(
                f"{out} holds runs graded by policy model {previous['policy_model']['name']!r}; "
                f"use a new --out or delete it"
            )
        if previous["judge_model"]["name"] != judge_model:
            sys.exit(
                f"{out} holds runs graded by judge model {previous['judge_model']['name']!r}; "
                f"use a new --out or delete it"
            )
        if changes is not None and "changes" in previous and previous["changes"] != changes:
            sys.exit(f"{out} holds runs for changes {previous['changes']}; use a new --out or delete it")
    elif runs_path.exists() and runs_path.read_text(encoding="utf-8").strip():
        sys.exit(
            f"{out} holds runs in runs.jsonl but no metadata.json; provenance unknown; "
            f"use a new --out or delete it"
        )
    return previous
