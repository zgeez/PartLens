"""Choose parts per line to minimise assembled cost, using only verified substitutes.

The search is exact (exhaustive) when the option space is small and falls back to coordinate descent
otherwise; the report says which was used. Loading fees are per unique part, so the lines interact: replacing
one extended part only removes its fee if no other line still uses it.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from decimal import Decimal

from ..core.bom import Bom
from ..core.model import Decision, DecisionStatus
from ..core.parts import PartRecord
from .cost import CostInputs, CostReport, classification_problem, estimate

EXHAUSTIVE_LIMIT = 50_000


@dataclass(frozen=True)
class Option:
    part: PartRecord
    decision: Decision | None  # None for the baseline (original) part


@dataclass(frozen=True)
class LineChoice:
    line_id: str
    chosen: str
    baseline: str | None
    explanation: str


@dataclass(frozen=True)
class OptimisationResult:
    baseline: CostReport
    best: CostReport
    selection: dict[str, PartRecord | None]
    choices: tuple[LineChoice, ...]
    excluded: tuple[str, ...]        # candidates not allowed (not verified), with reason
    method: str
    savings: Decimal | None
    comparison_complete: bool = True


def comparable(report: CostReport) -> Decimal:
    """Cost terms that depend on the selection (PCB fabrication and setup are constant)."""
    return report.parts_total + report.loading_fees + (report.placement_fees or Decimal(0))


def optimise(bom: Bom, baseline: dict[str, PartRecord | None], alternatives: dict[str, list[Option]],
             inputs: CostInputs) -> OptimisationResult:
    excluded: list[str] = []
    options: dict[str, list[PartRecord | None]] = {}
    for ln in bom.placed_lines:
        opts: list[PartRecord | None] = [baseline.get(ln.id)]
        for o in alternatives.get(ln.id, []):
            if o.decision is None or o.decision.status is not DecisionStatus.VERIFIED:
                status = o.decision.status.value if o.decision else "no decision"
                excluded.append(f"{ln.id}: {o.part.key} excluded ({status})")
                continue
            base = baseline.get(ln.id)
            if (base is None or o.decision.subject != ln.id or o.decision.original != base.key
                    or o.decision.candidate != o.part.key):
                excluded.append(f"{ln.id}: {o.part.key} excluded (decision identity/line does not match this option)")
                continue
            from .cost import line_cost

            purchase = line_cost(ln, o.part, inputs.boards, inputs.fees, now=inputs.now)
            base = baseline.get(ln.id)
            if purchase.problem:
                excluded.append(f"{ln.id}: {o.part.key} excluded (sourcing: {purchase.problem})")
                continue
            if any(p is None or classification_problem(p, inputs.fees, inputs.now)
                   or p.assembly_class not in inputs.fees.loading_fee_by_class
                   for p in (base, o.part)):
                excluded.append(f"{ln.id}: {o.part.key} excluded (unknown assembly classification/loading fee)")
                continue
            if o.part.key not in {p.key for p in opts if p}:
                opts.append(o.part)
        options[ln.id] = opts

    base_report = estimate(bom, baseline, inputs)
    line_ids = list(options)
    space = 1
    for lid in line_ids:
        space *= len(options[lid])

    def cost_of(sel: dict[str, PartRecord | None]) -> tuple[tuple[int, Decimal], CostReport]:
        rep = estimate(bom, sel, inputs)
        # Sourcing failures take precedence over any saving, including pooled-stock failures across lines.
        violations = sum(lc.extended is None or lc.problem is not None for lc in rep.lines)
        return (violations, comparable(rep)), rep

    best_sel = dict(baseline)
    best_cost, best_rep = cost_of(best_sel)
    if space <= EXHAUSTIVE_LIMIT:
        method = f"exhaustive over {space} combinations"
        varying = [lid for lid in line_ids if len(options[lid]) > 1]
        for combo in itertools.product(*(options[lid] for lid in varying)):
            sel = dict(baseline)
            sel.update(zip(varying, combo))
            c, rep = cost_of(sel)
            if c < best_cost:
                best_cost, best_sel, best_rep = c, sel, rep
    else:
        method = f"coordinate descent ({space} combinations exceed exhaustive limit)"
        improved = True
        while improved:
            improved = False
            for lid in line_ids:
                for p in options[lid]:
                    sel = dict(best_sel)
                    sel[lid] = p
                    c, rep = cost_of(sel)
                    if c < best_cost:
                        best_cost, best_sel, best_rep, improved = c, sel, rep, True

    choices = tuple(_explain(bom, lid, baseline, best_sel, options, inputs) for lid in line_ids)
    comparison_complete = (base_report.complete and best_rep.complete
                           and all(lc.extended is not None and not lc.problem for lc in best_rep.lines)
                           and all(lc.extended is not None and not lc.problem for lc in base_report.lines)
                           and all(p is not None and not classification_problem(p, inputs.fees, inputs.now)
                                   and p.assembly_class in inputs.fees.loading_fee_by_class
                                   for p in list(best_sel.values()) + list(baseline.values())))
    return OptimisationResult(base_report, best_rep, best_sel, choices, tuple(excluded), method,
                              base_report.total - best_rep.total if comparison_complete else None,
                              comparison_complete)


def _explain(bom: Bom, lid: str, baseline: dict[str, PartRecord | None], best: dict[str, PartRecord | None],
             options: dict[str, list[PartRecord | None]], inputs: CostInputs) -> LineChoice:
    chosen = best.get(lid)
    base = baseline.get(lid)
    ref = comparable(estimate(bom, best, inputs))
    notes = []
    for p in options[lid]:
        if p is chosen:
            continue
        trial = dict(best)
        trial[lid] = p
        rep = estimate(bom, trial, inputs)
        delta = comparable(rep) - ref
        lc = next(x for x in rep.lines if x.line_id == lid)
        notes.append(f"{p.key if p else 'none'} would cost {delta:+} in known variable costs "
                     f"(parts line {lc.extended}, class {p.assembly_class if p else '-'})")
    head = "kept baseline" if (chosen and base and chosen.key == base.key) else \
        f"replaced {base.key if base else 'none'}"
    return LineChoice(lid, chosen.key if chosen else "none", base.key if base else None,
                      f"{head}; " + ("; ".join(notes) if notes else "no verified alternatives"))
