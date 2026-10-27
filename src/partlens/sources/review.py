"""Read-only manufacturer evidence overlays, supplied by the operator rather than the language model."""

from __future__ import annotations

import json
from copy import copy
from dataclasses import replace
from pathlib import Path

from ..core.model import Evidence, EvidenceKind, digest
from ..core.parts import PartRecord
from ..records import RunRecorder
from .catalog import Catalog, parse_param


class ReviewedCatalog:
    def __init__(self, base: Catalog, path: str | Path) -> None:
        self.base = base
        entries = json.loads(Path(path).read_text(encoding="utf-8"))
        self.reviews = {r["part_key"]: r for r in entries}
        self.name = f"{base.name}+review:{digest(entries)[:16]}"
        self.provenance = {"base": getattr(base, "provenance", {"name": base.name}),
                           "review_path": str(path), "review_digest": digest(entries)}

    def with_recorder(self, recorder: RunRecorder) -> ReviewedCatalog:
        """Keep reviewed evidence while binding the underlying remote source to its session audit."""
        bound = copy(self)
        bind = getattr(self.base, "with_recorder", None)
        bound.base = bind(recorder) if bind else self.base
        return bound

    @property
    def bom_supplier(self) -> str:
        return getattr(self.base, "bom_supplier", "lcsc")

    def prepare(self, codes: list[str]) -> None:
        prepare = getattr(self.base, "prepare", None)
        if prepare:
            prepare(codes)

    def _review(self, part: PartRecord | None) -> PartRecord | None:
        if part is None or part.key not in self.reviews:
            return part
        review = self.reviews[part.key]
        if (review["mpn"] != part.mpn or
                review["manufacturer"].strip().casefold() != part.manufacturer.strip().casefold()):
            raise ValueError("manufacturer/MPN mismatch in reviewed evidence; review cannot be transferred")
        params = dict(part.params)
        for field, raw in review.get("params", {}).items():
            param = parse_param(field, raw, "review", review["reviewed_at"])
            if param.evidence.kind is not EvidenceKind.DATASHEET or not param.evidence.locator.startswith("https://"):
                raise ValueError("reviewed parameters require a manufacturer datasheet locator")
            if field in {"supply_voltage_min", "supply_voltage_max"} and param.rating_kind != "recommended_operating":
                raise ValueError("operating limits require explicit recommended_operating evidence")
            params[field] = param
        changes = {}
        if classification := review.get("assembly_classification"):
            if classification["class"] not in {"basic", "preferred", "extended"}:
                raise ValueError("unknown assembly classification")
            if not classification["source"].startswith("https://") or not classification.get("service"):
                raise ValueError("assembly classification needs service and source evidence")
            changes = {"assembly_class": classification["class"], "assembly_service": classification["service"],
                       "assembly_class_evidence": Evidence(
                           EvidenceKind.SUPPLIER_RECORD, classification["source"], "assembly_class",
                           classification["class"], review["reviewed_at"])}
        return replace(part, params=params, engineering_notes=part.engineering_notes + tuple(review.get("notes", [])),
                       **changes)

    def get(self, key: str) -> PartRecord | None:
        return self._review(self.base.get(key))

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        return [self._review(p) for p in self.base.find_mpn(mpn)]

    def search(self, category: str, package: str | None = None, text: str | None = None,
               limit: int = 20) -> list[PartRecord]:
        return [self._review(p) for p in self.base.search(category, package, text, limit)]
