from dataclasses import dataclass


@dataclass(frozen=True)
class CheckResult:
    passed: bool
    detail: str
