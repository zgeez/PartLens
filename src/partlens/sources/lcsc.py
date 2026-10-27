"""LCSC product records -> PartLens catalogue rows.

Historical records remain timestamped internal fixtures (``.partlens/cache``, not committed) pending licensing
review. Network collection is disabled. This module only converts previously captured or synthetic records;
each field keeps its original product page and retrieval time.

Notes on meaning:
- prices are LCSC retail price breaks (USD); an assembly service may price parts differently.
- LCSC does not state assembly-service part classes (basic/extended); those come from the assembly service.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PAGE_URL = "https://www.lcsc.com/product-detail/{code}.html"

PARAM_MAP = {
    "capacitance": "capacitance", "voltage rating": "voltage_rating", "temperature coefficient": "dielectric",
    "tolerance": "tolerance_pct", "resistance": "resistance", "power(watts)": "power_w", "power": "power_w",
    "operating temperature": "temp_range", "inductance": "inductance", "current rating": "current_rating",
    "saturation current (isat)": "saturation_current", "dc resistance (dcr)": "dcr",
    "frequency": "frequency", "output voltage": "output_voltage", "input voltage": "supply_voltage_range",
    "maximum input voltage": "supply_voltage_max", "voltage - supply": "supply_voltage_range",
}
CATEGORY_RULES = [
    (re.compile(r"capacitor", re.I), "capacitor"), (re.compile(r"resistor", re.I), "resistor"),
    (re.compile(r"inductor", re.I), "inductor"), (re.compile(r"ferrite", re.I), "ferrite_bead"),
    (re.compile(r"light emitting|led", re.I), "led"), (re.compile(r"diode", re.I), "diode"),
    (re.compile(r"crystal|oscillator|resonator", re.I), "crystal"),
    (re.compile(r"connector|usb|header", re.I), "connector"), (re.compile(r"switch", re.I), "switch"),
]
LIFECYCLE = {"normal": "active"}


class CollectionDisabled(RuntimeError):
    """Undocumented-endpoint collection is suspended pending licensing review."""


def fetch_raw(code: str, timeout: float = 30) -> dict[str, Any]:
    raise CollectionDisabled("LCSC collection is disabled; use the existing timestamped internal fixtures")


def _temp_range(text: str) -> str:
    nums = re.findall(r"[-+]?\d+", text or "")
    return f"{int(nums[0])}~{int(nums[1])}" if len(nums) >= 2 else text


def category_of(raw: dict[str, Any]) -> str:
    names = " / ".join(filter(None, [raw.get("catalogName"), raw.get("parentCatalogName")] +
                                  [c.get("catalogNameEn") for c in raw.get("parentCatalogList") or []]))
    for rx, cat in CATEGORY_RULES:
        if rx.search(names):
            return cat
    return "ic"


def row_from_raw(raw: dict[str, Any], retrieved_at: str) -> dict[str, Any]:
    code = raw["productCode"]
    page = PAGE_URL.format(code=code)
    category = category_of(raw)
    params: dict[str, Any] = {}
    for p in raw.get("paramVOList") or []:
        name = (p.get("paramNameEn") or "").strip().lower()
        value = (p.get("paramValueEn") or "").strip()
        if not value or value == "-":
            continue
        key = PARAM_MAP.get(name)
        if key == "dielectric" and category != "capacitor":
            key = None
        if key == "temp_range":
            value = _temp_range(value)
        params[key or re.sub(r"[^a-z0-9]+", "_", name).strip("_")] = {
            "value": value,
            "evidence": {"kind": "supplier_record", "locator": f"{page}#param:{p.get('paramNameEn')}",
                         "excerpt": f"{p.get('paramNameEn')}: {value}"},
        }
    breaks = [[int(b["ladder"]), str(b["usdPrice"])] for b in raw.get("productPriceList") or [] if b.get("usdPrice")]
    return {
        "supplier": "lcsc", "supplier_pn": code, "mpn": raw.get("productModel") or "",
        "manufacturer": raw.get("brandNameEn") or "", "category": category,
        "package": raw.get("encapStandard") or "", "description": raw.get("productDescEn") or raw.get("productNameEn"),
        "params": params, "stock": raw.get("stockNumber"), "moq": raw.get("minBuyNumber") or 1,
        "order_multiple": raw.get("split") or 1, "currency": "USD", "price_breaks": breaks,
        "assembly_class": None, "lifecycle": LIFECYCLE.get((raw.get("productCycle") or "").lower()),
        "datasheet_url": raw.get("pdfUrl"), "retrieved_at": retrieved_at, "source": page,
        "raw_lifecycle": raw.get("productCycle"),
        # LCSC's own suggested alternates: research leads only, never a compatibility claim.
        "alternates": [a["productCode"] for a in raw.get("alternatePartList") or [] if a.get("productCode")],
    }


def snapshot(codes: list[str], out: str | Path, delay_s: float = 1.0, alternates: int = 0) -> dict[str, Any]:
    """Historical entry point retained to fail explicitly without changing existing snapshots."""
    raise CollectionDisabled("LCSC collection is disabled; existing fixtures must be preserved unchanged")
