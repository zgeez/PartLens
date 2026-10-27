from decimal import Decimal

from partlens.checks import dielectric
from partlens.checks.compat import check_availability, check_substitute
from partlens.core.model import (
    CheckResult, CheckStatus, DecisionStatus, Op, Provenance, ProvenanceStatus, Requirement, RequirementKind, decide,
)


def statuses(decision):
    return {c.check: c.status for c in decision.checks}


def test_pass_without_evidence_is_downgraded():
    r = CheckResult("x", "p", CheckStatus.PASS, "looks fine")
    assert r.status is CheckStatus.UNVERIFIED
    assert decide([]) is DecisionStatus.UNVERIFIED


def test_dielectric_rules():
    assert dielectric.replaces("X7R", "X5R")[0] is True
    assert dielectric.replaces("C0G", "X7R")[0] is True
    assert dielectric.replaces("X5R", "X7R")[0] is False      # 85 C < 125 C
    assert dielectric.replaces("Y5V", "X7R")[0] is False      # range and capacitance change
    assert dielectric.replaces("X7S", "X7R")[0] is False      # +-22 % > +-15 %
    assert dielectric.replaces("ABC", "X7R")[0] is None


def test_compatible_substitute_is_verified_with_evidence(catalog, bom):
    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    d = check_substitute(bom.line("L1"), orig, catalog.get("fixture:TEST-C100N-X7R-50V-EXT"))
    assert d.status is DecisionStatus.VERIFIED, [c.message for c in d.checks]
    assert all(c.evidence for c in d.checks)
    cap = next(c for c in d.checks if c.check == "req.capacitance")
    assert cap.evidence[0].kind.value == "datasheet" and "page=2" in cap.evidence[0].locator


def test_same_nominal_value_wrong_dielectric_is_rejected(catalog, bom):
    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    d = check_substitute(bom.line("L1"), orig, catalog.get("fixture:TEST-C100N-Y5V-16V"))
    s = statuses(d)
    assert s["req.capacitance"] is CheckStatus.PASS
    assert s["req.dielectric"] is CheckStatus.FAIL
    assert d.status is DecisionStatus.REJECTED

    d2 = check_substitute(bom.line("L1"), orig, catalog.get("fixture:TEST-C100N-X5R-25V"))
    assert statuses(d2)["req.dielectric"] is CheckStatus.FAIL and d2.status is DecisionStatus.REJECTED


def test_lower_voltage_rating_rejected(catalog, bom):
    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    d = check_substitute(bom.line("L1"), orig, catalog.get("fixture:TEST-C100N-X7R-6V3"))
    assert statuses(d)["req.voltage_rating"] is CheckStatus.FAIL
    assert d.status is DecisionStatus.REJECTED


def test_wider_capacitor_tolerance_or_missing_temperature_is_not_qualified(catalog, bom):
    from dataclasses import replace
    from partlens.sources.catalog import parse_param

    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    good = catalog.get("fixture:TEST-C100N-X7R-50V-EXT")
    params = dict(good.params, tolerance_pct=parse_param("tolerance_pct", "20%", "fixture:TEST", None))
    wider = check_substitute(bom.line("L1"), orig, replace(good, params=params))
    assert statuses(wider)["req.tolerance_pct"] is CheckStatus.FAIL
    params = {k: v for k, v in good.params.items() if k != "temp_range"}
    original_params = dict(orig.params, temp_range=parse_param("temp_range", "-55~125", "fixture:TEST", None))
    missing = check_substitute(bom.line("L1"), replace(orig, params=original_params), replace(good, params=params))
    assert statuses(missing)["req.temp_range"] is CheckStatus.UNVERIFIED


def test_package_mismatch_rejected(catalog, bom):
    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    d = check_substitute(bom.line("L1"), orig, catalog.get("fixture:TEST-C100N-X7R-0603"))
    assert statuses(d)["package"] is CheckStatus.FAIL


def test_missing_parameter_is_unverified_not_pass(catalog, bom):
    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    d = check_substitute(bom.line("L1"), orig, catalog.get("fixture:TEST-C100N-NODIEL"))
    assert statuses(d)["req.dielectric"] is CheckStatus.UNVERIFIED
    assert d.status is DecisionStatus.UNVERIFIED


def test_electrically_incompatible_ic_rejected_by_user_requirement(catalog, bom):
    req = Requirement("L3.vin_max", "L3", "supply_voltage_max", Op.GE, Decimal("5.5"), RequirementKind.HARD,
                      Provenance(ProvenanceStatus.USER_CONFIRMED, "user:turn-2", note="USB input up to 5.5 V"),
                      unit="V")
    orig, alt = catalog.get("fixture:TEST-LDO-A"), catalog.get("fixture:TEST-LDO-B")
    d = check_substitute(bom.line("L3"), orig, alt, [req])
    s = statuses(d)
    assert s["req.supply_voltage_max"] is CheckStatus.FAIL
    assert s["equivalence"] is CheckStatus.UNVERIFIED
    assert d.status is DecisionStatus.REJECTED
    # The original part satisfies the same requirement, with the user's statement as evidence.
    d0 = check_substitute(bom.line("L3"), orig, orig, [req])
    vin = next(c for c in d0.checks if c.check == "req.supply_voltage_max")
    assert vin.status is CheckStatus.PASS and vin.evidence[1].kind.value == "user_statement"


def test_provisional_requirement_never_binds(catalog, bom):
    req = Requirement("L3.vin_max", "L3", "supply_voltage_max", Op.GE, Decimal("5.5"), RequirementKind.HARD,
                      Provenance(ProvenanceStatus.PROVISIONAL, "agent:guess"), unit="V")
    assert not req.binding
    d = check_substitute(bom.line("L3"), catalog.get("fixture:TEST-LDO-A"), catalog.get("fixture:TEST-LDO-B"), [req])
    vin = next(c for c in d.checks if c.check == "req.supply_voltage_max")
    assert vin.status is CheckStatus.UNVERIFIED


def test_stale_supplier_data_is_unverified(catalog, now):
    stale = catalog.get("fixture:TEST-C100N-X7R-STALE")
    s = {c.check: c.status for c in check_availability(stale, 240, now=now)}
    assert s["supply.freshness"] is CheckStatus.UNVERIFIED
    assert s["supply.stock"] is CheckStatus.UNVERIFIED
    assert s["supply.price"] is CheckStatus.UNVERIFIED
    fresh = catalog.get("fixture:TEST-C100N-X7R-16V")
    s2 = {c.check: c.status for c in check_availability(fresh, 240, now=now)}
    assert set(s2.values()) == {CheckStatus.PASS}
    s3 = {c.check: c.status for c in check_availability(catalog.get("fixture:TEST-LDO-A"), 10**6, now=now)}
    assert s3["supply.stock"] is CheckStatus.FAIL


def test_package_naming_difference_is_unverified_not_fail(catalog, bom):
    from dataclasses import replace
    orig = catalog.get("fixture:TEST-LDO-A")
    renamed = replace(catalog.get("fixture:TEST-LDO-A"), supplier_pn="TEST-LDO-A-ALTNAME", package="SOT-23-5L")
    d = check_substitute(bom.line("L3"), orig, renamed)
    assert statuses(d)["package"] is CheckStatus.UNVERIFIED


def test_supplier_lead_with_missing_nominal_value_is_still_checked(catalog, bom, tmp_path):
    from dataclasses import replace
    from partlens.sources.catalog import LocalCatalog
    from partlens.session import Session
    from partlens.records import RunRecorder

    original = catalog.get("fixture:TEST-C100N-X7R-16V")
    lead = catalog.get("fixture:TEST-C100N-X7R-6V3")
    params = {k: v for k, v in lead.params.items() if k != "capacitance"}
    lead = replace(lead, params=params, description="")
    original = replace(original, suggested_alternates=(lead.key,))
    s = Session(RunRecorder.create(tmp_path), [LocalCatalog([original, lead])], bom=bom, baseline={"L1": original})
    hits = s.search_candidates("L1", text="100nF")["candidates"]
    assert lead.key in {p["key"] for p in hits}
    result = s.check_substitute("L1", lead.key)
    assert result["status"] == "rejected"  # rating failure remains decisive, despite a missing nominal value
