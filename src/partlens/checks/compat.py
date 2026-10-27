"""Deterministic substitution and sourcing checks.

A substitute is judged against requirements, never against the opinion of a model:

1. ``derive_substitution_requirements`` turns the original part's stated parameters into hard requirements
   (policy "no downgrade": equal nominal value, ratings not lower, tolerance not wider, dielectric at least as
   stable). Their provenance is the original part's evidence.
2. Design/user requirements for the same line (e.g. an applied voltage confirmed by the user) are added.
3. ``check_requirement`` compares one requirement with the candidate's stated value and evidence.

Anything the sources do not state yields ``unverified``.
"""

from __future__ import annotations

import re
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from typing import Any

from ..core.bom import BomLine, normalise_mpn
from ..core.model import (
    CheckResult, CheckStatus, Decision, Evidence, EvidenceKind, Op, Provenance, ProvenanceStatus, Requirement,
    RequirementKind,
)
from ..core.parts import PartRecord
from ..core.units import format_value
from . import dielectric

DIELECTRIC = "dielectric"

# parameter -> (op, required): required=True means a substitution cannot be verified unless the original
# states the value; False means it is only checked when the original states it.
POLICY: dict[str, list[tuple[str, Op | str, bool]]] = {
    "resistor": [("resistance", Op.EQ, True), ("tolerance_pct", Op.LE, True), ("power_w", Op.GE, True),
                 ("voltage_rating", Op.GE, False), ("temp_range", Op.COVERS, False)],
    "capacitor": [("capacitance", Op.EQ, True), ("voltage_rating", Op.GE, True), (DIELECTRIC, DIELECTRIC, True),
                  ("tolerance_pct", Op.LE, True), ("temp_range", Op.COVERS, False)],
    "inductor": [("inductance", Op.EQ, True), ("current_rating", Op.GE, True), ("saturation_current", Op.GE, False),
                 ("dcr", Op.LE, False), ("tolerance_pct", Op.LE, False)],
    "ferrite_bead": [("impedance_100mhz", Op.EQ, True), ("current_rating", Op.GE, True), ("dcr", Op.LE, False)],
    "led": [("color", Op.EQ, True), ("forward_current", Op.GE, False)],
}
PASSIVE_CATEGORIES = set(POLICY)

# Operating conditions describe the circuit, not the part. They are never compared with part parameters
# directly; requirements derived from them (e.g. voltage_rating >= applied_voltage) are.
CONDITION_PARAMETERS = {"applied_voltage", "derating_factor", "board_quantity"}


def derive_substitution_requirements(line: BomLine, original: PartRecord) -> list[Requirement]:
    reqs: list[Requirement] = []
    for param, op, required in POLICY.get(original.category, []):
        p = original.params.get(param)
        rid = f"{line.id}.{param}.no_downgrade"
        if p is None:
            if required:
                reqs.append(Requirement(
                    rid, line.id, param, Op.EQ if op == DIELECTRIC else Op(op), None, RequirementKind.UNRESOLVED,
                    Provenance(ProvenanceStatus.PROVISIONAL, f"part:{original.key}",
                               note=f"original part record does not state {param}"),
                    rationale=f"original {original.key} does not state {param}",
                ))
            continue
        value = p.value
        rop = Op.ONE_OF if op == DIELECTRIC else Op(op)
        if op == DIELECTRIC:
            value = (str(p.value),)  # stored as the original code; compared with dielectric.replaces()
        reqs.append(Requirement(
            rid, line.id, param, rop, value, RequirementKind.HARD,
            Provenance(ProvenanceStatus.DOCUMENT_DERIVED, p.evidence.locator,
                       recorded_at=p.evidence.retrieved_at or "", note=f"no-downgrade from {original.key}"),
            unit=p.unit, rationale=f"substitute must not be worse than {original.key} ({param})",
        ))
    return reqs


def check_requirement(req: Requirement, cand: PartRecord) -> CheckResult | None:
    name = f"req.{req.parameter}"
    if req.kind is RequirementKind.OBJECTIVE or req.parameter in CONDITION_PARAMETERS:
        return None
    if req.kind is RequirementKind.UNRESOLVED or req.value is None:
        return CheckResult(name, cand.key, CheckStatus.UNVERIFIED,
                           f"{req.parameter}: requirement not established ({req.rationale or req.provenance.note})",
                           requirement_id=req.id)
    if req.provenance.status is ProvenanceStatus.PROVISIONAL:
        return CheckResult(name, cand.key, CheckStatus.UNVERIFIED,
                           f"{req.parameter}: requirement is provisional and not binding until confirmed",
                           requirement_id=req.id, expected=_fmt_req(req))
    p = cand.params.get(req.parameter)
    if p is None:
        return CheckResult(name, cand.key, CheckStatus.UNVERIFIED,
                           f"{req.parameter}: {cand.key} does not state this parameter",
                           requirement_id=req.id, expected=_fmt_req(req))
    if req.parameter in {"supply_voltage_min", "supply_voltage_max"} and (
        p.rating_kind != "recommended_operating" or "absolute" in p.evidence.field.lower()
        or "absolute" in p.evidence.excerpt.lower()):
        return CheckResult(name, cand.key, CheckStatus.UNVERIFIED,
                           "a recommended operating limit needs explicit rating-domain evidence; "
                           "absolute maximum or unspecified ratings cannot establish it",
                           requirement_id=req.id, evidence=(p.evidence,))
    ok, observed, why = _compare(req, p.value, p.unit)
    status = CheckStatus.UNVERIFIED if ok is None else (CheckStatus.PASS if ok else CheckStatus.FAIL)
    return CheckResult(name, cand.key, status, f"{req.parameter}: {why}", requirement_id=req.id,
                       expected=_fmt_req(req), observed=observed,
                       evidence=(p.evidence, _requirement_evidence(req)))


def _requirement_evidence(req: Requirement) -> Evidence:
    kind = {
        ProvenanceStatus.USER_CONFIRMED: EvidenceKind.USER_STATEMENT,
        ProvenanceStatus.CALCULATED: EvidenceKind.CALCULATION,
    }.get(req.provenance.status, EvidenceKind.SUPPLIER_RECORD)
    return Evidence(kind, req.provenance.source, f"requirement:{req.id}", _fmt_req(req),
                    req.provenance.recorded_at or None, req.provenance.note)


def _fmt_req(req: Requirement) -> str:
    v = req.value
    if isinstance(v, Decimal):
        v = format_value(v, req.unit) if v.is_finite() else str(v)
    elif isinstance(v, tuple) and len(v) == 2 and all(isinstance(x, Decimal) for x in v):
        v = f"{v[0]}..{v[1]}"
    elif isinstance(v, tuple):
        v = "/".join(map(str, v))
    return f"{req.op.value} {v}"


def _compare(req: Requirement, value: Any, unit: str | None) -> tuple[bool | None, str, str]:
    if req.parameter == DIELECTRIC:
        orig = req.value[0]
        ok, why = dielectric.replaces(str(value), orig)
        return ok, str(value), why
    if req.op is Op.COVERS:
        lo, hi = _as_range(value)
        rlo, rhi = _as_range(req.value)
        if lo is None or rlo is None:
            return None, str(value), f"cannot compare ranges {value!r} and {req.value!r}"
        ok = lo <= rlo and hi >= rhi
        return ok, f"{lo}..{hi}", f"{lo}..{hi} {'covers' if ok else 'does not cover'} {rlo}..{rhi}"
    if req.op is Op.ONE_OF:
        ok = str(value).strip().lower() in {str(x).strip().lower() for x in req.value}
        return ok, str(value), f"{value} {'in' if ok else 'not in'} {list(req.value)}"
    if isinstance(req.value, Decimal):
        try:
            v = value if isinstance(value, Decimal) else Decimal(str(value))
        except InvalidOperation:
            return None, str(value), f"non-numeric value {value!r}"
        if not v.is_finite() or not req.value.is_finite():
            return None, str(value), "non-finite engineering values cannot be verified"
        if unit and req.unit and unit != req.unit:
            return None, str(value), f"unit mismatch {unit} vs {req.unit}"
        shown = format_value(v, unit or req.unit)
        want = format_value(req.value, req.unit)
        ok = {Op.EQ: v == req.value, Op.GE: v >= req.value, Op.LE: v <= req.value}[req.op]
        rel = {Op.EQ: "equals" if ok else "differs from", Op.GE: ">=" if ok else "<", Op.LE: "<=" if ok else ">"}
        return ok, shown, f"{shown} {rel[req.op]} {want}"
    if req.op is not Op.EQ:
        return None, str(value), "ordered comparison needs numeric values with established units"
    ok = str(value).strip().lower() == str(req.value).strip().lower()
    return ok, str(value), f"{value!r} {'matches' if ok else 'does not match'} {req.value!r}"


def _as_range(v: Any) -> tuple[Decimal | None, Decimal | None]:
    if isinstance(v, tuple) and len(v) == 2:
        try:
            lo, hi = Decimal(str(v[0])), Decimal(str(v[1]))
            return (lo, hi) if lo.is_finite() and hi.is_finite() and lo <= hi else (None, None)
        except InvalidOperation:
            return None, None
    s = str(v).replace("°C", "").replace("C", "").replace(" ", "")
    for sep in ("~", "..", "to"):
        if sep in s:
            a, b = s.split(sep, 1)
            try:
                lo, hi = Decimal(a), Decimal(b)
                return (lo, hi) if lo.is_finite() and hi.is_finite() and lo <= hi else (None, None)
            except InvalidOperation:
                return None, None
    return None, None


def check_substitute(line: BomLine, original: PartRecord, cand: PartRecord,
                     line_requirements: list[Requirement] | None = None) -> Decision:
    """All compatibility checks for replacing ``original`` with ``cand`` on ``line``."""
    checks: list[CheckResult] = []
    if any(not p.mpn.strip() or not p.manufacturer.strip() for p in (original, cand)):
        checks.append(CheckResult("identity.incomplete", cand.key, CheckStatus.UNVERIFIED,
                                  "original and candidate manufacturer/MPN identities must be established"))
    checks.append(_field_check("category", original, cand, original.category, cand.category))
    checks.append(_package_check(original, cand))
    if original.category in PASSIVE_CATEGORIES:
        for req in derive_substitution_requirements(line, original) + list(line_requirements or []):
            r = check_requirement(req, cand)
            if r:
                checks.append(r)
    else:
        same = (bool(normalise_mpn(original.mpn)) and normalise_mpn(original.mpn) == normalise_mpn(cand.mpn)
                and bool(original.manufacturer.strip())
                and original.manufacturer.strip().casefold() == cand.manufacturer.strip().casefold())
        if same:
            checks.append(CheckResult("identity.mpn", cand.key, CheckStatus.PASS,
                                      f"same manufacturer part number {cand.mpn} (different supplier listing)",
                                      evidence=(original.record_evidence("mpn", original.mpn),
                                                cand.record_evidence("mpn", cand.mpn),
                                                original.record_evidence("manufacturer", original.manufacturer),
                                                cand.record_evidence("manufacturer", cand.manufacturer))))
        else:
            checks.append(CheckResult(
                "equivalence", cand.key, CheckStatus.UNVERIFIED,
                f"{original.category}: no deterministic equivalence check between {original.mpn} and {cand.mpn}; "
                "pinout and electrical equivalence need datasheet evidence",
            ))
            for field, needed in (("operating", "recommended supply range, load/current and temperature"),
                                  ("pinout", "pin functions, exposed pad and land-pattern dimensions"),
                                  ("function", "interfaces, timing, command set and relevant functionality")):
                checks.append(CheckResult("equivalence." + field, cand.key, CheckStatus.UNVERIFIED,
                                          f"manufacturer datasheet comparison needed: {needed}"))
        for req in line_requirements or []:
            r = check_requirement(req, cand)
            if r:
                checks.append(r)
    return Decision.from_checks(line.id, original.key, cand.key, checks)


def check_application(line: BomLine, original: PartRecord, cand: PartRecord,
                      requirements: list[Requirement]) -> Decision:
    """Evaluate stated circuit conditions separately; equivalence failure is not a safety verdict.

    Circuit qualification currently remains unverified unless all relevant operating characteristics can be
    checked. In particular, a voltage pass alone cannot qualify a ceramic capacitor under DC bias.
    """
    checks = [_field_check("category", original, cand, original.category, cand.category),
              _package_check(original, cand)]
    for req in derive_substitution_requirements(line, original):
        if req.parameter not in {"voltage_rating", "power_w", "current_rating"}:
            result = check_requirement(req, cand)
            if result:
                checks.append(result)
    operating = [r for r in requirements if r.parameter not in CONDITION_PARAMETERS]
    for req in operating:
        result = check_requirement(req, cand)
        if result:
            checks.append(result)
    if not operating:
        checks.append(CheckResult("application.conditions", cand.key, CheckStatus.UNVERIFIED,
                                  "actual circuit operating conditions are not established"))
    checks.append(CheckResult(
        "application.characteristics", cand.key, CheckStatus.UNVERIFIED,
        "application qualification needs effective capacitance under DC bias, ESR, ripple and temperature evidence"
        if original.category == "capacitor" else
        "application qualification needs circuit load, thermal, transient and functional evidence",
    ))
    checks.append(CheckResult("application.footprint", cand.key, CheckStatus.UNVERIFIED,
                              "a package label alone does not establish land pattern, termination or height clearance"))
    if original.category == "capacitor":
        for field in ("effective_capacitance", "esr", "ripple_current"):
            checks.append(CheckResult("application." + field, cand.key, CheckStatus.UNVERIFIED,
                                      f"{field}: need operating-point requirements and manufacturer evidence "
                                      "at the actual bias, frequency and temperature"))
    return Decision.from_checks(line.id, original.key, cand.key, checks)


def _field_check(name: str, original: PartRecord, cand: PartRecord, want: Any, got: Any) -> CheckResult:
    if not want or not got:
        return CheckResult(name, cand.key, CheckStatus.UNVERIFIED,
                           f"{name}: not stated ({original.key}: {want!r}, {cand.key}: {got!r})")
    ok = str(want).lower() == str(got).lower()
    return CheckResult(name, cand.key, CheckStatus.PASS if ok else CheckStatus.FAIL,
                       f"{name}: {got} {'matches' if ok else 'differs from'} {want}",
                       expected=str(want), observed=str(got),
                       evidence=(original.record_evidence(name, want), cand.record_evidence(name, got)))


CHIP_SIZES = {"01005", "0201", "0402", "0603", "0805", "1206", "1210", "1812", "2010", "2512"}


def _norm_package(p: str) -> str:
    return re.sub(r"\s+", "", p or "").upper()


def _package_check(original: PartRecord, cand: PartRecord) -> CheckResult:
    """Identical package names pass; two different standard chip sizes fail; any other difference is
    unverified, because supplier package names are not footprints (e.g. 'USON-8(2x3)' vs 'USON-8-EP(2x3)')."""
    a, b = _norm_package(original.package), _norm_package(cand.package)
    if not a or not b:
        return CheckResult("package", cand.key, CheckStatus.UNVERIFIED,
                           f"package: not stated ({original.key}: {original.package!r}, {cand.key}: {cand.package!r})")
    ev = (original.record_evidence("package", original.package), cand.record_evidence("package", cand.package))
    if a == b:
        return CheckResult("package", cand.key, CheckStatus.PASS, f"package: {cand.package} matches",
                           expected=original.package, observed=cand.package, evidence=ev)
    if a in CHIP_SIZES and b in CHIP_SIZES:
        return CheckResult("package", cand.key, CheckStatus.FAIL,
                           f"package: {cand.package} differs from {original.package}",
                           expected=original.package, observed=cand.package, evidence=ev)
    return CheckResult("package", cand.key, CheckStatus.UNVERIFIED,
                       f"package: '{cand.package}' vs '{original.package}' named differently; land-pattern "
                       "compatibility needs footprint or datasheet evidence",
                       expected=original.package, observed=cand.package, evidence=ev)


def check_availability(part: PartRecord, needed_qty: int, *, now: datetime | None = None,
                       max_age_days: float = 7.0) -> list[CheckResult]:
    """Sourcing checks: data freshness, stock for the order, lifecycle, price at the order quantity."""
    now = now or datetime.now(UTC)
    out: list[CheckResult] = []
    age = part.age_days(now)
    if part.commercial_unknowns:
        out.append(CheckResult("supply.commercial_terms", part.key, CheckStatus.UNVERIFIED,
                               "supplier terms unknown: " + ", ".join(part.commercial_unknowns)))
    fresh = age is not None and 0 <= age <= max_age_days
    ordered = part.order_quantity(needed_qty)
    if age is None:
        out.append(CheckResult("supply.freshness", part.key, CheckStatus.UNVERIFIED,
                               "supplier data has no retrieval time"))
    elif not fresh:
        out.append(CheckResult("supply.freshness", part.key, CheckStatus.UNVERIFIED,
                               f"supplier data is {age:.1f} days old (limit {max_age_days:g}); refresh before relying on "
                               "stock or price", observed=part.retrieved_at))
    else:
        out.append(CheckResult("supply.freshness", part.key, CheckStatus.PASS,
                               f"supplier data retrieved {age:.1f} days ago", observed=part.retrieved_at,
                               evidence=(part.record_evidence("retrieved_at", part.retrieved_at),)))

    if part.stock is None:
        out.append(CheckResult("supply.stock", part.key, CheckStatus.UNVERIFIED, "stock not stated"))
    elif not fresh:
        out.append(CheckResult("supply.stock", part.key, CheckStatus.UNVERIFIED,
                               f"stock {part.stock} reported by stale or undated data", observed=str(part.stock)))
    elif part.stock >= needed_qty and any(x in part.commercial_unknowns for x in
                                         ("minimum order quantity", "order multiple")):
        out.append(CheckResult("supply.stock", part.key, CheckStatus.UNVERIFIED,
                               f"stock {part.stock} covers nominal demand {needed_qty}; actual purchase quantity "
                               "unknown until MOQ/multiple are established", observed=str(part.stock),
                               evidence=(part.record_evidence("stock", part.stock),)))
    else:
        ok = part.stock >= ordered
        out.append(CheckResult("supply.stock", part.key, CheckStatus.PASS if ok else CheckStatus.FAIL,
                               f"stock {part.stock} {'>=' if ok else '<'} order {ordered} (needed {needed_qty}, MOQ/multiple)",
                               expected=f">= {ordered}", observed=str(part.stock),
                               evidence=(part.record_evidence("stock", part.stock),)))

    lc = (part.lifecycle or "").lower()
    if not lc:
        out.append(CheckResult("supply.lifecycle", part.key, CheckStatus.UNVERIFIED, "lifecycle status not stated"))
    else:
        ok = lc == "active"
        out.append(CheckResult("supply.lifecycle", part.key, CheckStatus.PASS if ok else CheckStatus.FAIL,
                               f"lifecycle {lc}", observed=lc,
                               evidence=(part.record_evidence("lifecycle", lc),)))

    pb = part.price_at(ordered)
    if pb is None:
        out.append(CheckResult("supply.price", part.key, CheckStatus.UNVERIFIED,
                               f"no price break applies at {needed_qty} units"))
    else:
        out.append(CheckResult("supply.price", part.key, CheckStatus.PASS if fresh and pb.currency else CheckStatus.UNVERIFIED,
                               f"{pb.unit_price} {pb.currency}/unit from {pb.min_qty} units"
                               + ("" if fresh else " (stale data)") + ("" if pb.currency else " (currency unknown)"),
                               observed=str(pb.unit_price),
                               evidence=(part.record_evidence("price_break", f"{pb.min_qty}:{pb.unit_price}"),)))
    return out
