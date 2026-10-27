from decimal import Decimal

from partlens.checks.compat import check_substitute
from partlens.optimise.cost import AssemblyFees, CostInputs, estimate
from partlens.optimise.search import Option, optimise

FEES = AssemblyFees(setup_fee=Decimal(0), per_placement_fee=Decimal(0), stencil_fee=Decimal(0),
                    loading_fee_by_class={"basic": Decimal(0), "extended": Decimal("3.00")},
                    source="test fee schedule")


def baseline(catalog):
    return {"L1": catalog.get("fixture:TEST-C100N-X7R-16V"), "L2": catalog.get("fixture:TEST-R10K-1-0402"),
            "L3": catalog.get("fixture:TEST-LDO-A"), "L4": None}


def test_cost_is_exact_and_reproducible(catalog, bom):
    inputs = CostInputs(60, FEES, pcb_fabrication=Decimal("45.00"), pcb_source="test quote")
    r = estimate(bom, baseline(catalog), inputs)
    lines = {lc.line_id: lc for lc in r.lines}
    # Hand calculation: 240 x 0.0020, 360 x 0.0015, 60 x 0.08 (break >= 100 not reached -> 0.12)
    assert lines["L1"].extended == Decimal("0.4800")
    assert lines["L2"].extended == Decimal("0.5400")
    assert lines["L3"].unit_price == Decimal("0.1200") and lines["L3"].extended == Decimal("7.2000")
    assert r.parts_total == Decimal("8.2200")
    assert r.loading_fees == Decimal("3.00")
    assert r.total is None and r.per_board is None  # missing L4 cannot yield an assembled total
    assert r.known_subtotal == Decimal("56.2200")
    assert not r.complete and "L4: no part selected" in r.problems
    assert estimate(bom, baseline(catalog), inputs) == r


def test_missing_pcb_cost_is_reported_not_guessed(catalog, bom):
    r = estimate(bom, baseline(catalog), CostInputs(60, FEES))
    assert r.total is None and "PCB fabrication cost not provided" in r.problems


def test_quantity_dependent_price_breaks(catalog, bom):
    r60 = estimate(bom, baseline(catalog), CostInputs(60, FEES, Decimal(0)))
    r100 = estimate(bom, baseline(catalog), CostInputs(100, FEES, Decimal(0)))
    l2_60 = next(lc for lc in r60.lines if lc.line_id == "L2")
    l2_100 = next(lc for lc in r100.lines if lc.line_id == "L2")
    assert l2_60.unit_price == Decimal("0.0015")   # 360 units -> break 100
    assert l2_100.unit_price == Decimal("0.0008")  # 600 units -> break 500


def test_attrition_and_moq():
    from partlens.optimise.cost import attrition
    assert attrition(240, AssemblyFees(attrition_pct=Decimal(2), attrition_min=5)) == 5
    assert attrition(1000, AssemblyFees(attrition_pct=Decimal(2), attrition_min=5)) == 20


def _alternatives(catalog, bom):
    l1, l2 = bom.line("L1"), bom.line("L2")
    c0, r0 = catalog.get("fixture:TEST-C100N-X7R-16V"), catalog.get("fixture:TEST-R10K-1-0402")
    alts = {"L1": [], "L2": []}
    for key in ("fixture:TEST-C100N-X7R-50V-EXT", "fixture:TEST-C100N-Y5V-16V"):
        p = catalog.get(key)
        alts["L1"].append(Option(p, check_substitute(l1, c0, p)))
    p = catalog.get("fixture:TEST-R10K-1-0402-ALT")
    alts["L2"].append(Option(p, check_substitute(l2, r0, p)))
    return alts


def test_assembly_fee_outweighs_unit_price_saving_at_60_boards(catalog, bom):
    res = optimise(bom, baseline(catalog), _alternatives(catalog, bom), CostInputs(60, FEES, Decimal(0)))
    sel = {k: (v.key if v else None) for k, v in res.selection.items()}
    assert sel["L1"] == "fixture:TEST-C100N-X7R-16V"          # cheaper per unit but +3.00 loading fee
    assert sel["L2"] == "fixture:TEST-R10K-1-0402-ALT"         # verified and cheaper, same class
    assert any("TEST-C100N-Y5V-16V excluded (rejected)" in e for e in res.excluded)
    assert res.savings is None  # missing L4 prevents a complete savings claim
    assert res.baseline.parts_total - res.best.parts_total == Decimal("0.1800")
    why = next(c for c in res.choices if c.line_id == "L1").explanation
    assert "TEST-C100N-X7R-50V-EXT would cost +2.808" in why    # -0.192 parts + 3.00 fee


def test_fee_is_worth_paying_at_high_volume(catalog, bom):
    res = optimise(bom, baseline(catalog), _alternatives(catalog, bom), CostInputs(10_000, FEES, Decimal(0)))
    assert res.selection["L1"].key == "fixture:TEST-C100N-X7R-50V-EXT"
