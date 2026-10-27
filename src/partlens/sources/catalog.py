"""Part catalogue interface and the record format shared by all sources.

A catalogue row is a flat mapping (so it can live in a CSV/Parquet table queried through Zetaris, or in a
JSON file). ``params`` and ``price_breaks`` are JSON-encoded when the row is flat:

    supplier, supplier_pn, mpn, manufacturer, category, package, description, stock, moq, order_multiple,
    currency, assembly_class, lifecycle, datasheet_url, retrieved_at, source,
    params        {"capacitance": "100nF", "dielectric": "X7R", ...}
                  or {"capacitance": {"value": "100nF", "evidence": {"kind": "datasheet", "locator": "...#page=2",
                                                                    "excerpt": "..."}}}
    price_breaks  [[1, "0.0021"], [100, "0.0012"], ...]
"""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path
from typing import Any, Protocol

from ..core.bom import normalise_lcsc, normalise_mpn
from ..core.model import Evidence, EvidenceKind
from ..core.parts import Param, PartRecord, PriceBreak
from ..core.units import UnitError, parse_percent, parse_value

PARAM_UNITS = {
    "resistance": "ohm", "capacitance": "F", "inductance": "H", "voltage_rating": "V", "current_rating": "A",
    "saturation_current": "A", "power_w": "W", "dcr": "ohm", "impedance_100mhz": "ohm", "forward_current": "A",
    "forward_voltage": "V", "frequency": "Hz", "supply_voltage_max": "V", "supply_voltage_min": "V",
    "input_voltage_absolute_max": "V", "output_voltage": "V", "output_current": "A",
    "effective_capacitance": "F", "esr": "ohm", "ripple_current": "A",
    "body_length": "m", "body_width": "m", "body_height": "m",
}
PERCENT_PARAMS = {"tolerance_pct"}


class Catalog(Protocol):
    name: str

    def get(self, key: str) -> PartRecord | None: ...

    def find_mpn(self, mpn: str) -> list[PartRecord]: ...

    def search(self, category: str, package: str | None = None, text: str | None = None,
               limit: int = 20) -> list[PartRecord]: ...


def parse_param(name: str, raw: Any, source: str, retrieved_at: str | None) -> Param:
    ev_kind, locator, excerpt = EvidenceKind.SUPPLIER_RECORD, f"{source}#params.{name}", ""
    rating_kind = None
    if isinstance(raw, dict):
        rating_kind = raw.get("rating_kind")
        ev = raw.get("evidence") or {}
        ev_kind = EvidenceKind(ev.get("kind", EvidenceKind.SUPPLIER_RECORD))
        locator = ev.get("locator", locator)
        excerpt = ev.get("excerpt", "")
        retrieved_at = ev.get("retrieved_at", retrieved_at)
        raw = raw.get("value")
    text = str(raw)
    value: Any = text
    unit = PARAM_UNITS.get(name)
    if unit:
        try:
            value, unit = parse_value(text, unit)
        except UnitError:
            value = text  # kept as text; numeric checks on it report unverified
    elif name in PERCENT_PARAMS:
        try:
            value = parse_percent(text)
        except UnitError:
            value = text
        unit = "%"
    return Param(value, unit, Evidence(ev_kind, locator, name, text, retrieved_at, excerpt), rating_kind)


def record_from_row(row: dict[str, Any]) -> PartRecord:
    def js(v: Any, default: Any) -> Any:
        if v in (None, ""):
            return default
        return json.loads(v) if isinstance(v, str) else v

    def opt_int(v: Any) -> int | None:
        if v in (None, ""):
            return None
        n = Decimal(str(v))
        if not n.is_finite() or n < 0 or n != n.to_integral_value():
            raise ValueError("supplier quantities must be finite nonnegative whole numbers")
        return int(n)

    source = str(row.get("source") or "unknown")
    retrieved_at = row.get("retrieved_at") or None
    currency = row.get("currency", "USD")  # explicitly unknown currency must stay unknown
    params = {k: parse_param(k, v, source, retrieved_at) for k, v in js(row.get("params"), {}).items()}
    breaks = tuple(sorted((PriceBreak(opt_int(b[0]), Decimal(str(b[1])), currency,
                                      opt_int(b[2]) if len(b) > 2 else None)
                           for b in js(row.get("price_breaks"), [])),
                          key=lambda b: b.min_qty))
    if any(b.min_qty is None or b.min_qty < 1 or not b.unit_price.is_finite() or b.unit_price < 0 for b in breaks):
        raise ValueError("price breaks need positive whole quantities and finite nonnegative prices")
    if any(b.max_qty is not None and b.max_qty < b.min_qty for b in breaks):
        raise ValueError("price range ends before it starts")
    if any(row.get(k) not in (None, "") and not opt_int(row[k]) for k in ("moq", "order_multiple")):
        raise ValueError("MOQ and order multiple must be positive")
    supplier = str(row.get("supplier") or "").lower()
    spn = str(row.get("supplier_pn") or "")
    if supplier == "lcsc":
        spn = normalise_lcsc(spn) or spn
    class_evidence = js(row.get("assembly_class_evidence"), None)
    if class_evidence:
        class_evidence = Evidence(**{**class_evidence, "kind": EvidenceKind(class_evidence["kind"])})
    return PartRecord(
        supplier=supplier, supplier_pn=spn, mpn=str(row.get("mpn") or ""),
        manufacturer=str(row.get("manufacturer") or ""), category=str(row.get("category") or ""),
        package=str(row.get("package") or ""), source=source, retrieved_at=retrieved_at,
        description=str(row.get("description") or ""), params=params, stock=opt_int(row.get("stock")),
        moq=opt_int(row.get("moq")) or 1, order_multiple=opt_int(row.get("order_multiple")) or 1,
        price_breaks=breaks, assembly_class=row.get("assembly_class") or None,
        lifecycle=row.get("lifecycle") or None, datasheet_url=row.get("datasheet_url") or None,
        suggested_alternates=tuple(f"{supplier}:{pn}" if ":" not in pn else pn
                                   for pn in js(row.get("alternates"), [])),
        commercial_unknowns=tuple(js(row.get("commercial_unknowns"), [])),
        supplier_metadata=js(row.get("supplier_metadata"), {}),
        assembly_service=row.get("assembly_service") or None,
        assembly_class_evidence=class_evidence,
    )


class LocalCatalog:
    """Catalogue held in memory, loaded from a JSON list of rows. Used for fixtures and offline snapshots;
    every record keeps the ``source`` and ``retrieved_at`` it was captured with."""

    def __init__(self, records: list[PartRecord], name: str = "local") -> None:
        self.name = name
        self._by_key = {r.key: r for r in records}
        self.bom_supplier = "jlcpcb" if records and all(r.supplier == "jlcpcb" for r in records) else "lcsc"

    @classmethod
    def from_json(cls, path: str | Path, name: str | None = None) -> LocalCatalog:
        import hashlib

        data = Path(path).read_bytes()
        rows = json.loads(data)
        catalog = cls([record_from_row(r) for r in rows], name or Path(path).stem)
        catalog.provenance = {"path": str(path), "sha256": hashlib.sha256(data).hexdigest(), "records": len(rows)}
        return catalog

    def get(self, key: str) -> PartRecord | None:
        return self._by_key.get(key)

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        want = normalise_mpn(mpn)
        return [r for r in self._by_key.values() if normalise_mpn(r.mpn) == want]

    def search(self, category: str, package: str | None = None, text: str | None = None,
               limit: int = 20) -> list[PartRecord]:
        out = []
        for r in sorted(self._by_key.values(), key=lambda r: r.key):
            if r.category != category:
                continue
            if package and r.package.lower() != package.lower():
                continue
            if text and text.lower() not in f"{r.mpn} {r.description}".lower():
                continue
            out.append(r)
        return out[:limit]

    def all(self) -> list[PartRecord]:
        return list(self._by_key.values())


FLAT_COLUMNS = ["supplier", "supplier_pn", "mpn", "manufacturer", "category", "package", "description", "stock",
                "moq", "order_multiple", "currency", "assembly_class", "lifecycle", "datasheet_url", "retrieved_at",
                "source", "params", "price_breaks", "alternates", "commercial_unknowns", "supplier_metadata",
                "assembly_service", "assembly_class_evidence"]


def export_flat_csv(rows: list[dict[str, Any]], out: str | Path) -> int:
    """Write catalogue rows as a flat CSV (params and price_breaks JSON-encoded), e.g. for a Zetaris file
    source. Reading it back with ``record_from_row`` gives the same records."""
    import csv

    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FLAT_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            flat = dict(r)
            flat["params"] = json.dumps(r.get("params") or {}, ensure_ascii=False, sort_keys=True)
            flat["price_breaks"] = json.dumps(r.get("price_breaks") or [])
            flat["alternates"] = json.dumps(r.get("alternates") or [])
            for key, default in (("commercial_unknowns", []), ("supplier_metadata", {}),
                                 ("assembly_class_evidence", None)):
                flat[key] = json.dumps(r.get(key) or default) if r.get(key) else ""
            w.writerow(flat)
    return len(rows)
