"""Typed requirements, evidence and check results.

Rules enforced here (not left to callers):

- Every requirement carries provenance. A ``provisional`` requirement is never binding.
- A check result of ``pass`` must carry evidence; a pass without evidence is downgraded to ``unverified``.
- A decision is ``verified`` only if every check passed with evidence. Any ``fail`` rejects; anything else
  (including no checks at all) is ``unverified``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


def utc_now() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


class ProvenanceStatus(StrEnum):
    USER_CONFIRMED = "user_confirmed"
    DOCUMENT_DERIVED = "document_derived"
    CALCULATED = "calculated"
    PROVISIONAL = "provisional"


class RequirementKind(StrEnum):
    HARD = "hard"            # must hold; violated -> fail
    OBJECTIVE = "objective"  # optimise (e.g. cost); never a pass/fail gate
    UNRESOLVED = "unresolved"  # known to matter, value not established yet


class Op(StrEnum):
    GE = ">="
    LE = "<="
    EQ = "=="
    ONE_OF = "one_of"
    COVERS = "covers"  # candidate range must cover the required [min, max] range


@dataclass(frozen=True)
class Provenance:
    status: ProvenanceStatus
    source: str  # e.g. "user:turn-3", "datasheet:https://...#p4", "bom:import-1/line-7", "calc:rail*1.5"
    recorded_at: str = field(default_factory=utc_now)
    note: str = ""


@dataclass(frozen=True)
class Requirement:
    id: str
    subject: str        # "design", a BOM line id (e.g. "L3"), or a function name
    parameter: str      # e.g. "voltage_rating", "capacitance", "dielectric", "board_quantity"
    op: Op
    value: Any          # Decimal, str, tuple[str, ...] or (Decimal, Decimal) for COVERS
    kind: RequirementKind
    provenance: Provenance
    unit: str | None = None
    rationale: str = ""

    @property
    def binding(self) -> bool:
        return self.kind is RequirementKind.HARD and self.provenance.status is not ProvenanceStatus.PROVISIONAL


class EvidenceKind(StrEnum):
    DATASHEET = "datasheet"
    SUPPLIER_RECORD = "supplier_record"
    USER_STATEMENT = "user_statement"
    CALCULATION = "calculation"
    BOM = "bom"


@dataclass(frozen=True)
class Evidence:
    kind: EvidenceKind
    locator: str            # URL, record key or run-record reference
    field: str              # which value this evidence supports
    value: str              # the value as stated by the source
    retrieved_at: str | None = None
    excerpt: str = ""

    @property
    def key(self) -> str:
        return digest(asdict(self))[:12]


class CheckStatus(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class CheckResult:
    check: str
    subject: str
    status: CheckStatus
    message: str
    requirement_id: str | None = None
    expected: str | None = None
    observed: str | None = None
    evidence: tuple[Evidence, ...] = ()

    def __post_init__(self) -> None:
        if self.status is CheckStatus.PASS and not self.evidence:
            object.__setattr__(self, "status", CheckStatus.UNVERIFIED)
            object.__setattr__(self, "message", f"{self.message} [downgraded: pass without evidence]")


class DecisionStatus(StrEnum):
    VERIFIED = "verified"
    REJECTED = "rejected"
    UNVERIFIED = "unverified"


@dataclass(frozen=True)
class Decision:
    subject: str            # BOM line or function
    original: str | None    # original part key, if substituting
    candidate: str          # candidate part key
    status: DecisionStatus
    checks: tuple[CheckResult, ...]
    decided_at: str = field(default_factory=utc_now)

    @classmethod
    def from_checks(cls, subject: str, original: str | None, candidate: str,
                    checks: list[CheckResult] | tuple[CheckResult, ...]) -> Decision:
        return cls(subject, original, candidate, decide(checks), tuple(checks))

    @property
    def failures(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status is CheckStatus.FAIL]

    @property
    def gaps(self) -> list[CheckResult]:
        return [c for c in self.checks if c.status is CheckStatus.UNVERIFIED]

    @property
    def id(self) -> str:
        return digest({"subject": self.subject, "original": self.original, "candidate": self.candidate,
                       "checks": [to_jsonable(c) for c in self.checks]})[:16]


def decide(checks: list[CheckResult] | tuple[CheckResult, ...]) -> DecisionStatus:
    if not checks:
        return DecisionStatus.UNVERIFIED
    if any(c.status is CheckStatus.FAIL for c in checks):
        return DecisionStatus.REJECTED
    if all(c.status is CheckStatus.PASS and c.evidence for c in checks):
        return DecisionStatus.VERIFIED
    return DecisionStatus.UNVERIFIED


def to_jsonable(obj: Any) -> Any:
    if isinstance(obj, Decimal):
        return str(obj)
    if isinstance(obj, StrEnum):
        return obj.value
    if hasattr(obj, "__dataclass_fields__"):
        return {k: to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, dict):
        return {str(k): to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_jsonable(v) for v in obj]
    return obj


def digest(obj: Any) -> str:
    return hashlib.sha256(json.dumps(to_jsonable(obj), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
