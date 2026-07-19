"""Shared assessment-check dataclass. Each check module exposes check(data, ...) -> CheckResult."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    name: str
    verdict: str  # "ok" | "flag" | "info" | "unknown"
    detail: str
    data: dict[str, Any] = field(default_factory=dict)
