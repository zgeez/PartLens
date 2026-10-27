"""Assembled-cost model for a production quantity, with exact decimal arithmetic and derivations.

Every amount in a ``CostReport`` has a derivation string, so a reviewer can recompute it by hand.

Model (all inputs explicit, none hidden):

- parts: per line, ``needed = qty_per_board * boards + attrition``; ``ordered`` is raised to the MOQ and the
  order multiple; unit price is the price break at ``ordered``; extended = unit price * ordered.
- assembly: a fixed setup fee, a per-unique-part loading fee by assembly class (e.g. extended parts), and a
  per-joint/per-placement fee if configured.
- PCB fabrication: an explicit amount supplied by the user or a quote (never estimated silently).
"""

from __future__ import annotations

import math
import json
from dataclasses import dataclass, field, replace
from decimal import ROUND_HALF_UP, Decimal
from datetime import UTC, datetime
from pathlib import Path

from ..core.bom import Bom, BomLine
from ..core.parts import PartRecord
from ..checks.compat import check_availability
from ..core.model import CheckStatus, to_jsonable

CENT = Decimal("0.01")


@dataclass(frozen=True)
class AssemblyFees:
    """Fee schedule of an assembly service. ``source`` says where the numbers came from."""
    setup_fee: Decimal | None = None
    loading_fee_by_class: dict[str, Decimal] = field(default_factory=dict)  # per unique part, e.g. {"extended": 3}
    per_placement_fee: Decimal | None = None                              # per placed component per board
    attrition_pct: Decimal = Decimal("0")                                  # extra parts ordered, % of needed
    attrition_min: int = 0                                                 # minimum extra parts per line
    currency: str = "USD"
    source: str = "unspecified"
    stencil_fee: Decimal | None = None
    per_joint_fee: Decimal | None = None
    additional_unknowns: tuple[str, ...] = ()
    retrieved_at: str | None = None
    service: str | None = None
    process_fees: dict[str, Decimal | None] = field(default_factory=dict)


def load_fees(path: str | Path | None) -> AssemblyFees | None:
    """Load an explicit operator-selected schedule; missing fields remain unknown."""
    if path is None:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"), parse_float=Decimal)
    for key in ("setup_fee", "per_placement_fee", "stencil_fee", "per_joint_fee", "attrition_pct"):
        if data.get(key) is not None:
            data[key] = Decimal(str(data[key]))
    data["loading_fee_by_class"] = {k: Decimal(str(v)) for k, v in data.get("loading_fee_by_class", {}).items()}
    data["additional_unknowns"] = tuple(data.get("additional_unknowns", []))
    data["process_fees"] = {k: Decimal(str(v)) if v is not None else None
                            for k, v in data.get("process_fees", {}).items()}
    return AssemblyFees(**data)


def classification_problem(part: PartRecord, fees: AssemblyFees, now: datetime | None = None) -> str | None:
    """Assembly classification has its own service-specific evidence, independent of supplier prices."""
    if part.assembly_class is None:
        return "assembly class unknown; loading fee not computed"
    if part.supplier == "fixture" and part.assembly_class_evidence is None:
        return None  # synthetic fixtures explicitly declare their test classifications
    if part.assembly_class_evidence is None or part.assembly_service is None:
        return "assembly classification has no service/source evidence"
    if fees.service != part.assembly_service:
        return "assembly classification and fee schedule refer to different or unspecified services"
    try:
        time = datetime.fromisoformat((part.assembly_class_evidence.retrieved_at or "").replace("Z", "+00:00"))
        age = ((now or datetime.now(UTC)) - time).total_seconds() / 86400
    except (ValueError, TypeError):
        return "assembly classification timestamp is invalid or missing"
    if not 0 <= age <= 7:
        return "assembly classification must be refreshed before relying on its fees"
    return None


@dataclass(frozen=True)
class CostInputs:
    boards: int
    fees: AssemblyFees
    pcb_fabrication: Decimal | None = None   # total for all boards; None -> reported as missing
    pcb_source: str = ""
    joints_per_board: int | None = None
    now: datetime | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.boards, int) or isinstance(self.boards, bool) or self.boards <= 0:
            raise ValueError("boards must be a positive whole number")
        numbers = [self.fees.setup_fee, self.fees.per_placement_fee, self.fees.stencil_fee,
                   self.fees.per_joint_fee, self.fees.attrition_pct, self.pcb_fabrication,
                   *self.fees.loading_fee_by_class.values(), *self.fees.process_fees.values()]
        if any(v is not None and (not v.is_finite() or v < 0) for v in numbers):
            raise ValueError("cost inputs must be finite and nonnegative")
        if (type(self.fees.attrition_min) is not int or self.fees.attrition_min < 0
                or (self.joints_per_board is not None and
                    (type(self.joints_per_board) is not int or self.joints_per_board < 0))):
            raise ValueError("attrition and solder-joint counts must be nonnegative")


@dataclass(frozen=True)
class LineCost:
    line_id: str
    part_key: str | None
    assembly_class: str | None
    needed: int
    ordered: int | None
    unit_price: Decimal | None
    extended: Decimal | None
    derivation: str
    problem: str | None = None
    sourcing: tuple[dict, ...] = ()
    source: str = ""
    retrieved_at: str | None = None


@dataclass(frozen=True)
class CostReport:
    boards: int
    lines: tuple[LineCost, ...]
    parts_total: Decimal
    loading_fees: Decimal
    loading_detail: tuple[str, ...]
    setup_fee: Decimal | None
    placement_fees: Decimal | None
    pcb_fabrication: Decimal | None
    total: Decimal | None
    per_board: Decimal | None
    currency: str
    complete: bool
    problems: tuple[str, ...]
    derivation: tuple[str, ...]
    component_complete: bool
    known_subtotal: Decimal
    stencil_fee: Decimal | None
    joint_fees: Decimal | None
    fee_source: str
    fee_retrieved_at: str | None
    process_fees: dict[str, Decimal | None]


def attrition(needed: int, fees: AssemblyFees) -> int:
    if needed == 0:
        return 0
    pct = math.ceil(Decimal(needed) * fees.attrition_pct / Decimal(100))
    return max(pct, fees.attrition_min)


def line_cost(line: BomLine, part: PartRecord | None, boards: int, fees: AssemblyFees,
              *, now: datetime | None = None) -> LineCost:
    needed = line.qty_per_board * boards
    if part is None:
        return LineCost(line.id, None, None, needed, 0, None, None, "no part selected", "no part selected")
    extra = attrition(needed, fees)
    want = needed + extra
    ordered = part.order_quantity(want)
    pb = part.price_at(ordered)
    if part.commercial_unknowns:
        return LineCost(line.id, part.key, part.assembly_class, needed, None,
                        pb.unit_price if pb else None, None,
                        "purchase quantity/cost cannot be established from incomplete supplier terms",
                        "unknown supplier terms: " + ", ".join(part.commercial_unknowns),
                        source=part.source, retrieved_at=part.retrieved_at)
    if pb is None:
        return LineCost(line.id, part.key, part.assembly_class, needed, ordered, None, None,
                        f"no price break at {ordered}", f"{part.key}: no price break at {ordered} units")
    if pb.currency != fees.currency:
        return LineCost(line.id, part.key, part.assembly_class, needed, ordered, pb.unit_price, None,
                        f"price in {pb.currency}", f"{part.key}: currency {pb.currency} != {fees.currency}")
    if not pb.unit_price.is_finite() or pb.unit_price < 0:
        return LineCost(line.id, part.key, part.assembly_class, needed, ordered, None, None,
                        "invalid price", f"{part.key}: price must be finite and nonnegative")
    ext = pb.unit_price * ordered
    deriv = (f"{line.qty_per_board}/board x {boards} = {needed} + attrition {extra} -> order {ordered}"
             f"{' (MOQ/multiple)' if ordered != want else ''}; {ordered} x {pb.unit_price} "
             f"(break >= {pb.min_qty}) = {ext}")
    checks = check_availability(part, ordered, now=now)
    problem = "; ".join(c.message for c in checks if c.status is not CheckStatus.PASS) or None
    return LineCost(line.id, part.key, part.assembly_class, needed, ordered, pb.unit_price, ext, deriv,
                    problem, tuple(to_jsonable(c) for c in checks), part.source, part.retrieved_at)


def estimate(bom: Bom, selection: dict[str, PartRecord | None], inputs: CostInputs) -> CostReport:
    """Cost of building ``inputs.boards`` boards with ``selection`` (line id -> part)."""
    fees = inputs.fees
    lines: list[LineCost] = []
    problems: list[str] = []
    groups: dict[str, list[BomLine]] = {}
    for ln in bom.placed_lines:
        part = selection.get(ln.id)
        if part:
            groups.setdefault(part.key, []).append(ln)
    charged: set[str] = set()
    for ln in bom.placed_lines:
        part = selection.get(ln.id)
        group = groups.get(part.key, []) if part else []
        pooled = replace(ln, qty_per_board=sum(l.qty_per_board for l in group)) if len(group) > 1 else ln
        lc = line_cost(pooled, part, inputs.boards, fees, now=inputs.now or datetime.now(UTC))
        if len(group) > 1:
            first = group[0].id
            lc = replace(lc, needed=ln.qty_per_board * inputs.boards,
                         derivation=f"pooled purchase for {','.join(l.id for l in group)} charged on {first}: "
                                    + lc.derivation)
            if part.key in charged:
                lc = replace(lc, ordered=0, extended=Decimal(0) if lc.extended is not None else None)
            charged.add(part.key)
        lines.append(lc)
        if lc.problem:
            problems.append(f"{ln.id}: {lc.problem}")

    parts_total = sum((lc.extended for lc in lines if lc.extended is not None), Decimal(0))
    component_complete = not problems

    # Loading fees are charged once per unique part, not per line.
    unique = {p.key: p for ln in bom.placed_lines if (p := selection.get(ln.id)) is not None}
    loading = Decimal(0)
    loading_detail: list[str] = []
    for key, part in sorted(unique.items()):
        cls = part.assembly_class
        if problem := classification_problem(part, fees, inputs.now):
            problems.append(f"{key}: {problem}")
            continue
        fee = fees.loading_fee_by_class.get(cls)
        if fee is None:
            problems.append(f"{key}: loading fee for {cls} unknown")
            continue
        if fee:
            loading += fee
            loading_detail.append(f"{key} ({cls}) {fee}")

    placements = sum(ln.qty_per_board for ln in bom.placed_lines) * inputs.boards
    placement_fees = fees.per_placement_fee * placements if fees.per_placement_fee is not None else None
    joint_fees = (fees.per_joint_fee * inputs.joints_per_board * inputs.boards
                  if fees.per_joint_fee is not None and inputs.joints_per_board is not None else None)
    if fees.setup_fee is None:
        problems.append("assembly setup fee unknown")
    if fees.stencil_fee is None:
        problems.append("stencil fee unknown")
    if placement_fees is None and joint_fees is None:
        problems.append("assembly labor unknown: need a sourced rate and its placement or solder-joint count")
    if fees.per_joint_fee is not None and inputs.joints_per_board is None:
        problems.append("solder-joint count unknown; placements cannot substitute for joints")
    if fees.source in {"", "unspecified"}:
        problems.append("assembly fee source not provided")
    problems.extend(fees.additional_unknowns)
    for name, amount in sorted(fees.process_fees.items()):
        if amount is None:
            problems.append(f"process fee {name} unknown or applicability unresolved")
    if fees.source.startswith("https://"):
        try:
            at = datetime.fromisoformat((fees.retrieved_at or "").replace("Z", "+00:00"))
            age = ((inputs.now or datetime.now(UTC)) - at).total_seconds() / 86400
            if not 0 <= age <= 7:
                problems.append("assembly fee schedule stale; refresh before claiming a complete total")
        except (TypeError, ValueError):
            problems.append("assembly fee schedule retrieval time missing or invalid")

    if inputs.pcb_fabrication is None:
        problems.append("PCB fabrication cost not provided")
    complete = not problems
    total = None
    per_board = None
    partial = (parts_total + loading + (fees.setup_fee or Decimal(0)) + (placement_fees or Decimal(0))
               + (fees.stencil_fee or Decimal(0)) + (joint_fees or Decimal(0))
               + (inputs.pcb_fabrication or Decimal(0))
               + sum((v for v in fees.process_fees.values() if v is not None), Decimal(0)))
    if complete:
        total = partial
        per_board = (total / inputs.boards).quantize(Decimal("0.0001"), ROUND_HALF_UP)

    derivation = (
        f"parts: sum of {len([lc for lc in lines if lc.extended is not None])} priced lines = {parts_total}",
        f"loading fees: {len(loading_detail)} unique part(s) with fees = {loading}",
        f"setup fee: {fees.setup_fee} ({fees.source})",
        f"placement: {placements} placements x {fees.per_placement_fee} = {placement_fees}",
        f"stencil: {fees.stencil_fee}; solder-joint labor: {joint_fees} ({inputs.joints_per_board} joints/board)",
        f"other process fees: {dict(sorted(fees.process_fees.items()))} (None remains unknown)",
        f"PCB fabrication: {inputs.pcb_fabrication if inputs.pcb_fabrication is not None else 'missing'}"
        + (f" ({inputs.pcb_source})" if inputs.pcb_source else ""),
        f"total: {total if total is not None else f'incomplete (known part: {partial})'}",
    )
    return CostReport(inputs.boards, tuple(lines), parts_total, loading, tuple(loading_detail), fees.setup_fee,
                      placement_fees, inputs.pcb_fabrication, total, per_board, fees.currency, complete,
                      tuple(problems), derivation, component_complete, partial, fees.stencil_fee, joint_fees,
                      fees.source, fees.retrieved_at, dict(fees.process_fees))


def money(d: Decimal | None) -> str:
    return "n/a" if d is None else str(d.quantize(CENT, ROUND_HALF_UP))
