"""Supplier/catalogue part records with per-field evidence and price breaks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from .model import Evidence, EvidenceKind


@dataclass(frozen=True)
class PriceBreak:
    min_qty: int
    unit_price: Decimal
    currency: str = "USD"
    max_qty: int | None = None


@dataclass(frozen=True)
class Param:
    """A part parameter as stated by a source. ``value`` is a Decimal (base SI unit) or a string."""
    value: Any
    unit: str | None
    evidence: Evidence
    rating_kind: str | None = None  # recommended_operating | absolute_maximum; never interchangeable


@dataclass(frozen=True)
class PartRecord:
    supplier: str                 # e.g. "lcsc"
    supplier_pn: str              # e.g. "C1525"
    mpn: str
    manufacturer: str
    category: str                 # resistor | capacitor | inductor | led | diode | ic | connector | ...
    package: str                  # normalised package/footprint class, e.g. "0402"
    source: str                   # locator of the record (URL, Zetaris query id, fixture path)
    retrieved_at: str | None      # when the supplier data was retrieved (ISO 8601 UTC)
    description: str = ""
    params: dict[str, Param] = field(default_factory=dict)
    stock: int | None = None
    moq: int = 1
    order_multiple: int = 1
    price_breaks: tuple[PriceBreak, ...] = ()
    assembly_class: str | None = None   # basic | preferred | extended (assembly-service classification)
    lifecycle: str | None = None        # active | nrnd | obsolete | None (unknown)
    datasheet_url: str | None = None
    engineering_notes: tuple[str, ...] = ()
    suggested_alternates: tuple[str, ...] = ()  # supplier research leads; never compatibility verdicts
    assembly_class_evidence: Evidence | None = None
    assembly_service: str | None = None
    commercial_unknowns: tuple[str, ...] = ()
    supplier_metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.supplier}:{self.supplier_pn}"

    def record_evidence(self, field_name: str, value: Any) -> Evidence:
        """Evidence that a top-level record field (stock, price, package...) has this value."""
        return Evidence(EvidenceKind.SUPPLIER_RECORD, self.source, field_name, str(value), self.retrieved_at)

    def price_at(self, qty: int) -> PriceBreak | None:
        """Price break that applies to an order of ``qty`` units (highest min_qty <= qty)."""
        applicable = [b for b in self.price_breaks if b.min_qty <= qty
                      and (b.max_qty is None or qty <= b.max_qty)]
        return max(applicable, key=lambda b: b.min_qty) if applicable else None

    def order_quantity(self, needed: int) -> int:
        """Whole purchasing units, including MOQ and order-multiple rounding."""
        if needed < 0 or self.moq < 1 or self.order_multiple < 1:
            raise ValueError("quantities must be nonnegative; MOQ and order multiple must be positive")
        if needed == 0:
            return 0
        return ((max(needed, self.moq) + self.order_multiple - 1) // self.order_multiple) * self.order_multiple

    def age_days(self, now: datetime) -> float | None:
        if not self.retrieved_at:
            return None
        try:
            t = datetime.fromisoformat(self.retrieved_at.replace("Z", "+00:00"))
            return (now - t).total_seconds() / 86400
        except (ValueError, TypeError):
            return None
