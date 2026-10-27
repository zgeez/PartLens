"""Lossless supplier-operation journal for offline re-execution of deterministic engineering tools.

Replay uses recorded supplier inputs, never asserts a new network/memory operation occurred, and rejects
missing, altered or differently ordered observations. Model text is not accepted as supplier evidence.
"""

from __future__ import annotations

from dataclasses import asdict
from decimal import Decimal
from typing import Any

from ..core.model import Evidence, EvidenceKind, digest, to_jsonable
from ..core.parts import Param, PartRecord, PriceBreak
from ..records import RunRecorder


def encode_part(part: PartRecord | None) -> dict | None:
    if part is None:
        return None
    return {"part": to_jsonable(part), "decimal_parameters": [k for k, p in part.params.items()
                                                              if isinstance(p.value, Decimal)]}


def decode_part(value: dict | None) -> PartRecord | None:
    if value is None:
        return None
    raw = dict(value["part"])
    def evidence(ev):
        return Evidence(**{**ev, "kind": EvidenceKind(ev["kind"])})
    raw["params"] = {name: Param(Decimal(p["value"]) if name in value["decimal_parameters"] else p["value"],
                                 p["unit"], evidence(p["evidence"]), p["rating_kind"])
                     for name, p in raw["params"].items()}
    raw["price_breaks"] = tuple(PriceBreak(**{**p, "unit_price": Decimal(p["unit_price"])})
                                for p in raw["price_breaks"])
    for name in ("engineering_notes", "suggested_alternates", "commercial_unknowns"):
        raw[name] = tuple(raw[name])
    if raw["assembly_class_evidence"]:
        raw["assembly_class_evidence"] = evidence(raw["assembly_class_evidence"])
    return PartRecord(**raw)


class AuditedCatalog:
    def __init__(self, base, recorder: RunRecorder | None = None) -> None:
        self.base, self.recorder = base, recorder
        self.name = base.name
        self.bom_supplier = getattr(base, "bom_supplier", "lcsc")
        self.provenance = {**getattr(base, "provenance", {"name": base.name}), "supplier_operations_journaled": True}

    def with_recorder(self, recorder: RunRecorder) -> AuditedCatalog:
        bind = getattr(self.base, "with_recorder", None)
        return AuditedCatalog(bind(recorder) if bind else self.base, recorder)

    def _call(self, operation: str, arguments: dict, function):
        try:
            result = function()
        except Exception as exc:
            if self.recorder:
                self.recorder.log("catalogue_operation", catalogue=self.name, bom_supplier=self.bom_supplier,
                                  operation=operation, arguments=arguments, error_type=type(exc).__name__,
                                  error=str(exc), result=None, result_digest=digest(None))
            raise
        encoded = [encode_part(p) for p in result] if isinstance(result, list) else encode_part(result)
        if self.recorder:
            self.recorder.log("catalogue_operation", catalogue=self.name, bom_supplier=self.bom_supplier,
                              operation=operation, arguments=arguments, result=encoded, result_digest=digest(encoded))
        return result

    def prepare(self, codes: list[str]) -> None:
        prepare = getattr(self.base, "prepare", None)
        self._call("prepare", {"codes": codes}, lambda: prepare(codes) if prepare else None)

    def get(self, key: str) -> PartRecord | None:
        return self._call("get", {"key": key}, lambda: self.base.get(key))

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        return self._call("find_mpn", {"mpn": mpn}, lambda: self.base.find_mpn(mpn))

    def search(self, category: str, package=None, text=None, limit=20) -> list[PartRecord]:
        return self._call("search", dict(category=category, package=package, text=text, limit=limit),
                          lambda: self.base.search(category, package, text, limit))

    def discover_for(self, original: PartRecord, category: str, package, text, limit) -> list[PartRecord]:
        discover = getattr(self.base, "discover_for", None)
        return self._call("discover_for", dict(original=original.key, category=category, package=package, text=text, limit=limit),
                          lambda: discover(original, category, package, text, limit) if discover else
                          self.base.search(category, package, text, limit))


class ObservationMismatch(ValueError):
    pass


class ObservationCatalog:
    """Step-specific source inputs. No network access, model inference or live memory claims."""
    def __init__(self, name: str, events: list[dict]) -> None:
        self.name = name
        self.steps: dict[int, list[dict]] = {}
        pending: list[dict] = []
        self.bom_supplier = "lcsc"
        for event in events:
            if event["type"] == "catalogue_operation" and event["catalogue"] == name:
                if digest(event["result"]) != event["result_digest"]:
                    raise ObservationMismatch("supplier observation digest differs from its recorded content")
                self.bom_supplier = event["bom_supplier"]
                pending.append(event)
            elif event["type"] == "tool_call":
                self.steps[event["seq"]] = pending
                pending = []
        self.pending: list[dict] = []

    def begin(self, seq: int) -> None:
        self.pending = list(self.steps.get(seq, []))

    def finish(self) -> None:
        if self.pending:
            raise ObservationMismatch("not all recorded supplier operations were consumed by the deterministic tool")

    def _read(self, operation: str, arguments: dict):
        if not self.pending:
            raise ObservationMismatch("required supplier observation is missing")
        event = self.pending.pop(0)
        if event["operation"] != operation or event["arguments"] != arguments:
            raise ObservationMismatch("supplier operation/arguments differ from the recorded observation")
        if event.get("error"):
            # Reproduce a recorded transport failure as data; no server is contacted.
            error_type = event.get("error_type", "RuntimeError")
            if not error_type.isidentifier():
                raise ObservationMismatch("invalid recorded error type")
            raise type(error_type, (RuntimeError,), {})(event["error"])
        result = event["result"]
        return [decode_part(p) for p in result] if isinstance(result, list) else decode_part(result)

    def prepare(self, codes: list[str]) -> None:
        self._read("prepare", {"codes": codes})

    def get(self, key: str) -> PartRecord | None:
        return self._read("get", {"key": key})

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        return self._read("find_mpn", {"mpn": mpn})

    def search(self, category: str, package=None, text=None, limit=20) -> list[PartRecord]:
        return self._read("search", dict(category=category, package=package, text=text, limit=limit))

    def discover_for(self, original: PartRecord, category: str, package, text, limit) -> list[PartRecord]:
        return self._read("discover_for", dict(original=original.key, category=category, package=package, text=text, limit=limit))


def observations_from_events(events: list[dict]) -> list[ObservationCatalog]:
    names = list(dict.fromkeys(e["catalogue"] for e in events if e["type"] == "catalogue_operation"))
    if not names:
        raise ObservationMismatch("run has no supplier-operation journal; use its original pinned catalogue instead")
    return [ObservationCatalog(name, events) for name in names]
