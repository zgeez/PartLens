from dataclasses import replace
from decimal import Decimal

import pytest

from partlens.core.bom import Bom
from partlens.core.parts import PriceBreak
from partlens.core.model import Evidence, EvidenceKind
from partlens.optimise.cost import AssemblyFees, CostInputs, estimate
from partlens.optimise.search import Option, optimise
from partlens.checks.compat import check_substitute


KNOWN = AssemblyFees(Decimal(8), {"basic": Decimal(0), "extended": Decimal(3)}, Decimal("0.01"),
                     source="fixture:TEST-schedule", stencil_fee=Decimal("1.5"))


def one_line(bom, catalog):
    b = Bom("TEST-cost", "fixture:TEST", [bom.line("L1")])
    return b, {"L1": catalog.get("fixture:TEST-C100N-X7R-16V")}


def test_complete_total_with_all_inputs_and_stock(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    r = estimate(b, sel, CostInputs(10, KNOWN, Decimal(5), now=now))
    assert r.complete and r.component_complete
    assert r.parts_total == Decimal("0.1600")
    assert r.total == Decimal("15.0600")  # 40 parts .16 + setup 8 + stencil 1.5 + labor .4 + PCB 5


def test_unknown_class_or_fee_never_defaults_to_free(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    for cls in (None, "preferred", "TEST-unrecognised"):
        selected = {"L1": replace(sel["L1"], assembly_class=cls)}
        r = estimate(b, selected, CostInputs(10, KNOWN, Decimal(0), now=now))
        assert r.component_complete and not r.complete and r.total is None
        assert any("loading fee" in p for p in r.problems)


def test_classification_has_independent_service_provenance_and_freshness(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    evidence = Evidence(EvidenceKind.SUPPLIER_RECORD, "https://assembly.test/TEST-part", "assembly_class", "basic",
                        "2026-10-22T00:00:00Z")
    part = replace(sel["L1"], assembly_class_evidence=evidence, assembly_service="TEST-assembly")
    wrong = estimate(b, {"L1": part}, CostInputs(10, KNOWN, Decimal(0), now=now))
    assert wrong.component_complete and not wrong.complete
    fees = replace(KNOWN, service="TEST-assembly")
    correct = estimate(b, {"L1": part}, CostInputs(10, fees, Decimal(0), now=now))
    assert correct.complete
    stale = replace(part, assembly_class_evidence=replace(evidence, retrieved_at="2026-09-01T00:00:00Z"))
    assert not estimate(b, {"L1": stale}, CostInputs(10, fees, Decimal(0), now=now)).complete


def test_no_fees_still_produces_conditional_component_estimate(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    r = estimate(b, sel, CostInputs(10, AssemblyFees(), now=now))
    assert r.parts_total > 0 and r.component_complete
    assert r.total is None and r.setup_fee is None and r.placement_fees is None


def test_moq_rounding_selects_price_break_but_stock_can_block(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    p = replace(sel["L1"], moq=50, order_multiple=50, stock=75,
                price_breaks=(PriceBreak(1, Decimal(1)), PriceBreak(100, Decimal("0.5"))))
    r = estimate(b, {"L1": p}, CostInputs(15, KNOWN, Decimal(0), now=now))
    assert r.lines[0].needed == 60 and r.lines[0].ordered == 100
    assert r.lines[0].unit_price == Decimal("0.5") and r.parts_total == 50
    assert not r.complete and not r.component_complete and r.total is None


def test_same_part_pools_moq_stock_and_prices_across_lines(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    b.lines.append(replace(b.lines[0], id="L2", refs=("C99",)))
    p = replace(sel["L1"], moq=50, order_multiple=50, stock=50)
    r = estimate(b, {"L1": p, "L2": p}, CostInputs(5, KNOWN, Decimal(0), now=now))
    assert sum(l.ordered for l in r.lines) == 50  # total demand 40, a single MOQ purchase
    assert r.component_complete
    r2 = estimate(b, {"L1": p, "L2": p}, CostInputs(10, KNOWN, Decimal(0), now=now))
    assert not r2.component_complete  # combined demand 80 > stock 50


def test_solder_joints_are_not_placements(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    fees = replace(KNOWN, per_placement_fee=None, per_joint_fee=Decimal("0.0016"))
    missing = estimate(b, sel, CostInputs(10, fees, Decimal(0), now=now))
    assert missing.total is None
    known = estimate(b, sel, CostInputs(10, fees, Decimal(0), joints_per_board=8, now=now))
    assert known.complete and known.joint_fees == Decimal("0.128")


def test_optimiser_excludes_verified_but_unavailable_alternative(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    candidate = replace(catalog.get("fixture:TEST-C100N-X7R-50V-EXT"), stock=0)
    decision = check_substitute(b.line("L1"), sel["L1"], candidate)
    assert decision.status.value == "verified"
    r = optimise(b, sel, {"L1": [Option(candidate, decision)]}, CostInputs(10, KNOWN, Decimal(0), now=now))
    assert r.selection == sel and any("sourcing" in s for s in r.excluded)


def test_optimiser_checks_shared_stock_for_combined_choices(bom, catalog, now):
    b, sel = one_line(bom, catalog)
    b.lines.append(replace(b.lines[0], id="L2", refs=("C99",)))
    sel["L2"] = sel["L1"]
    candidate = replace(catalog.get("fixture:TEST-C100N-X7R-50V-EXT"), stock=30)
    options = {ln.id: [Option(candidate, check_substitute(ln, sel[ln.id], candidate))] for ln in b.lines}
    fees = replace(KNOWN, loading_fee_by_class={"basic": Decimal(0), "extended": Decimal(0)})
    r = optimise(b, sel, options, CostInputs(5, fees, Decimal(0), now=now))
    assert sum(p.key == candidate.key for p in r.selection.values()) == 1
    assert r.best.component_complete


@pytest.mark.parametrize("boards", [0, -1, 1.5, True])
def test_invalid_cost_quantities_fail(boards):
    with pytest.raises(ValueError):
        CostInputs(boards, KNOWN)
