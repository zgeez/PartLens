from dataclasses import replace
from decimal import Decimal

import pytest

from partlens.checks.compat import check_application, check_availability, check_substitute
from partlens.core.model import Evidence, EvidenceKind, Op, Provenance, ProvenanceStatus, Requirement, RequirementKind
from partlens.core.parts import Param
from partlens.records import RunRecorder
from partlens.session import Session, ToolError


def test_mpn_requires_same_known_manufacturer(catalog, bom):
    original = catalog.get("fixture:TEST-LDO-A")
    for manufacturer in ("TEST-other-vendor", ""):
        other = replace(original, manufacturer=manufacturer)
        result = check_substitute(bom.line("L3"), original, other)
        assert result.status.value == "unverified"
        assert not any(c.check == "identity.mpn" and c.status.value == "pass" for c in result.checks)


def test_absolute_maximum_does_not_satisfy_operating_requirement(catalog, bom):
    original = catalog.get("fixture:TEST-LDO-A")
    params = dict(original.params, supply_voltage_max=Param(Decimal(9), "V", Evidence(
        EvidenceKind.DATASHEET, "fixture:TEST-datasheet#page=3", "absolute_maximum_input", "9 V")))
    candidate = replace(original, params=params)
    req = Requirement("TEST-op", "L3", "supply_voltage_max", Op.GE, Decimal(8), RequirementKind.HARD,
                      Provenance(ProvenanceStatus.USER_CONFIRMED, "user:TEST"), unit="V")
    result = check_substitute(bom.line("L3"), original, candidate, [req])
    assert next(c for c in result.checks if c.check == "req.supply_voltage_max").status.value == "unverified"


def test_lower_rating_can_cover_actual_voltage_without_full_application_qualification(catalog, bom):
    original = catalog.get("fixture:TEST-C100N-X7R-16V")
    candidate = catalog.get("fixture:TEST-C100N-X7R-6V3")
    req = Requirement("TEST-voltage", "L1", "voltage_rating", Op.GE, Decimal("3.3"), RequirementKind.HARD,
                      Provenance(ProvenanceStatus.CALCULATED, "calc:TEST-rail"), unit="V")
    assert check_substitute(bom.line("L1"), original, candidate, [req]).status.value == "rejected"
    application = check_application(bom.line("L1"), original, candidate, [req])
    assert next(c for c in application.checks if c.check == "req.voltage_rating").status.value == "pass"
    assert application.status.value == "unverified"  # DC bias / ESR / load not established


def test_stock_checks_moq_and_order_multiple(catalog, now):
    part = replace(catalog.get("fixture:TEST-LDO-A"), moq=50, order_multiple=50, stock=60)
    checks = {c.check: c for c in check_availability(part, 60, now=now)}
    assert part.order_quantity(60) == 100
    assert checks["supply.stock"].status.value == "fail"
    assert checks["supply.stock"].expected == ">= 100"


@pytest.mark.parametrize("timestamp", [None, "garbage", "2026-10-30T00:00:00Z", "2026-10-22"])
def test_unreliable_timestamps_fail_closed(catalog, now, timestamp):
    p = replace(catalog.get("fixture:TEST-LDO-A"), retrieved_at=timestamp)
    assert next(c for c in check_availability(p, 1, now=now) if c.check == "supply.stock").status.value == "unverified"


def test_quantity_quote_must_be_verbatim_and_state_the_value(tmp_path):
    s = Session(RunRecorder.create(tmp_path), [])
    s.recorder.log("user_message", text="Build 60 boards")
    for value, quote in (("60", "build 60 boards"), ("100", "Build 60 boards"), ("60", "Build")):
        assert not s.record_requirement("design", "board_quantity", "==", value, user_quote=quote)["binding"]
    assert s.record_requirement("design", "board_quantity", "==", "60", user_quote="Build 60 boards")["binding"]


@pytest.mark.parametrize("value", ["0", "-1", "1.5", "NaN", "Infinity"])
def test_invalid_quantity_rejected(tmp_path, value):
    s = Session(RunRecorder.create(tmp_path), [])
    with pytest.raises(ToolError):
        s.record_requirement("design", "board_quantity", "==", value)
