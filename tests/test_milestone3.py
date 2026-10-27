"""Synthetic regressions for submission workflow, evidence gaps and bounded iteration."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from partlens.agent import Agent, ScriptedProvider, Turn
from partlens.checks.compat import check_application, check_substitute
from partlens.core.bom import Bom
from partlens.core.model import Op, Provenance, ProvenanceStatus, Requirement, RequirementKind, to_jsonable
from partlens.core.parts import Param
from partlens.optimise.cost import AssemblyFees, CostInputs, estimate
from partlens.optimise.search import Option, optimise
from partlens.records import RunRecorder, read_events
from partlens.session import Session, ToolError
from partlens.sources.catalog import LocalCatalog, record_from_row
from partlens.ui import failure_message, format_view, review_snapshot


def session(tmp_path, catalog):
    s = Session(RunRecorder.create(tmp_path), [catalog])
    s.import_bom("tests/fixtures/bom_kicad.csv")
    s.match_parts()
    return s


def confirmed_quantity(s, value="1"):
    s.recorder.log("user_message", text=value)
    args = dict(subject="design", parameter="board_quantity", op="==", value=value, user_quote=value)
    output = s.record_requirement(**args)
    s.recorder.log("tool_call", name="record_requirement", input=args, output=output, error=None)
    return output


def test_unavailable_catalogue_keeps_scenario_incomplete_without_crashing(tmp_path):
    s = Session(RunRecorder.create(tmp_path), [])
    s.import_bom("tests/fixtures/bom_kicad.csv")
    confirmed_quantity(s)
    comparison = s.compare_cost_scenarios()
    assert s._boards() == 1
    for scenario in comparison["scenarios"]:
        assert not scenario["comparison_complete"]
        assert scenario["baseline"]["total"] == "n/a" and not scenario["baseline"]["component_complete"]
        assert all(line["problem"] for line in scenario["baseline"]["lines"])


def test_restore_keeps_original_owner_provenance(tmp_path, catalog):
    first = session(tmp_path, catalog)
    confirmed_quantity(first)
    second = session(tmp_path, catalog)
    restored = second.restore_quantity(first.recorder.path)
    assert restored["source"] == first.list_requirements()["requirements"][0]["source"]
    assert second._boards() == 1
    assert not second.recorder.user_messages()  # no new owner answer fabricated
    assert read_events(second.recorder.path)[-1]["new_owner_confirmation"] is False


def test_task_text_cannot_overwrite_the_owner_quantity(tmp_path, catalog):
    s = session(tmp_path, catalog)
    confirmed_quantity(s)
    original = s.design_requirement("board_quantity")
    s.recorder.log("user_message", text="Try 60 boards", origin="scenario_task")
    with pytest.raises(ToolError, match="cannot overwrite"):
        s.record_requirement("design", "board_quantity", "==", "60", user_quote="60 boards")
    assert s.design_requirement("board_quantity") is original and s._boards() == 1


def test_forged_prior_source_cannot_restore_confirmation(tmp_path, catalog):
    s = session(tmp_path, catalog)
    output = confirmed_quantity(s)
    output["recorded"]["source"] = "user:TEST-forged#seq99"
    s.recorder.log("tool_call", name="record_requirement", input=dict(subject="design", parameter="board_quantity",
                   op="==", value="1", user_quote="1"), output=output, error=None)
    with pytest.raises(ToolError, match="valid original user provenance"):
        session(tmp_path, catalog).restore_quantity(s.recorder.path)


def test_reimport_clears_prior_alternatives_and_decisions(tmp_path, catalog):
    s = session(tmp_path, catalog)
    confirmed_quantity(s)
    s.check_substitute("L1", "fixture:TEST-C100N-X7R-50V-EXT")
    assert s.decisions and s.alternatives
    s.import_bom("tests/fixtures/bom_kicad.csv")
    assert not s.decisions and not s.alternatives and not s.observed_parts
    assert s._boards() == 1  # same design retains its confirmed quantity
    changed = tmp_path / "TEST-other.csv"
    changed.write_text("Refs,Value,Footprint,Qty\nR1,10k,0402,1\n")
    s.import_bom(str(changed))
    assert s._boards() is None


def test_supplier_listing_must_not_override_explicit_bom_identity(tmp_path, catalog, bom):
    part = replace(catalog.get("fixture:TEST-LDO-A"), supplier="lcsc", supplier_pn="TEST-listing")
    line = replace(bom.line("L3"), supplier_pn="TEST-listing", mpn="TEST-other", manufacturer="TEST-other-vendor")
    s = Session(RunRecorder.create(tmp_path), [LocalCatalog([part])], bom=Bom("TEST", "fixture:TEST", [line]))
    result = s.match_parts()
    assert result["unmatched"] == [line.id]


def test_ui_snapshot_is_read_only_and_includes_observed_candidates(tmp_path, catalog, monkeypatch):
    s = session(tmp_path, catalog)
    s.get_part("fixture:TEST-C100N-X7R-50V-EXT")
    monkeypatch.setattr(catalog, "get", lambda key: pytest.fail("UI refresh must not requery a supplier"))
    view = review_snapshot(s)
    assert "fixture:TEST-C100N-X7R-50V-EXT" in view["Evidence"]
    text = format_view("Evidence", view["Evidence"])
    assert "MOQ" in text and "Price breaks" in text and "Retrieved" in text


def test_comparison_shows_identities_scope_requirements_and_gaps(tmp_path, catalog):
    s = session(tmp_path, catalog)
    output = s.check_substitute("L1", "fixture:TEST-C100N-X7R-6V3")
    text = format_view("Qualifications", [output])
    assert "Original: TestCo" in text and "Candidate: TestCo" in text
    assert "Required:" in text and "observed:" in text
    assert "Original-specification equivalence: REJECTED" in text and "Application: UNVERIFIED" in text
    assert "effective_capacitance" in text and "land pattern" in text


def test_scenarios_do_not_modify_confirmed_quantity(tmp_path, catalog):
    s = session(tmp_path, catalog)
    confirmed_quantity(s)
    before = to_jsonable(s.requirements)
    result = s.compare_cost_scenarios()
    assert [(r["boards"], r["scenario"]) for r in result["scenarios"]] == [(1, "owner_confirmed"), (60, "hypothetical")]
    assert to_jsonable(s.requirements) == before and s._boards() == 1
    assert all(not r["comparison_complete"] and r["assembled_savings"] == "n/a" for r in result["scenarios"])
    assert all(r["official_manufacturer_quotation"] is None for r in result["scenarios"])


def test_scenario_cli_accepts_bom_name_and_preserves_quantity(tmp_path, catalog, monkeypatch, capsys):
    from pathlib import Path
    from partlens import cli, demo
    s = session(tmp_path, catalog)
    confirmed_quantity(s)
    monkeypatch.setattr(cli, "STATE", tmp_path / "TEST-state")
    monkeypatch.setattr(demo, "DEMO_BOM", Path("tests/fixtures/bom_kicad.csv"))
    cli.main(["cost-scenarios", "--catalog", "tests/fixtures/catalog.json", "--quantity-record", str(s.recorder.path)])
    data = json.loads(capsys.readouterr().out)
    report = data["report"]
    assert [x["boards"] for x in report["scenarios"]] == [1, 60]
    from partlens.replay import replay
    assert replay(data["record"], [catalog]).ok


@pytest.mark.parametrize("value", [0, -1, True, 1.5])
def test_invalid_hypothetical_quantity_does_not_change_owner(tmp_path, catalog, value):
    s = session(tmp_path, catalog)
    confirmed_quantity(s)
    with pytest.raises(ValueError):
        s.compare_cost_scenarios(value)
    assert s._boards() == 1


def known_fees(**kwargs):
    return AssemblyFees(setup_fee=Decimal(0), stencil_fee=Decimal(0), per_placement_fee=Decimal(0),
                        loading_fee_by_class={"basic": Decimal(0)}, source="fixture:TEST-fees", **kwargs)


def test_unknown_process_fee_blocks_assembled_savings(catalog, bom, now):
    b = Bom("TEST", "fixture:TEST", [bom.line("L1")])
    selection = {"L1": catalog.get("fixture:TEST-C100N-X7R-16V")}
    inputs = CostInputs(1, known_fees(process_fees={"xray_applicability": None}), Decimal(0), now=now)
    result = optimise(b, selection, {}, inputs)
    assert result.baseline.component_complete and result.baseline.total is None
    assert result.savings is None and not result.comparison_complete
    assert any("xray_applicability" in p for p in result.baseline.problems)


def test_sourced_process_fee_is_separate_and_exact(catalog, bom, now):
    b = Bom("TEST", "fixture:TEST", [bom.line("L1")])
    sel = {"L1": catalog.get("fixture:TEST-C100N-X7R-16V")}
    r = estimate(b, sel, CostInputs(1, known_fees(process_fees={"TEST-confirmation": Decimal("0.45")}),
                                  Decimal(0), now=now))
    assert r.complete and r.total == r.parts_total + Decimal("0.45")


def test_process_fee_key_order_cannot_change_replay_results(catalog, bom, now):
    b = Bom("TEST", "fixture:TEST", [bom.line("L1")])
    sel = {"L1": catalog.get("fixture:TEST-C100N-X7R-16V")}
    a = known_fees(process_fees={"TEST-z": None, "TEST-a": None})
    z = known_fees(process_fees={"TEST-a": None, "TEST-z": None})
    assert estimate(b, sel, CostInputs(1, a, now=now)) == estimate(b, sel, CostInputs(1, z, now=now))


def test_stale_manufacturing_schedule_cannot_yield_complete_total(catalog, bom, now):
    b = Bom("TEST", "fixture:TEST", [bom.line("L1")])
    fees = replace(known_fees(), source="https://assembly.test/fees", retrieved_at="2026-09-01T00:00:00Z")
    r = estimate(b, {"L1": catalog.get("fixture:TEST-C100N-X7R-16V")}, CostInputs(1, fees, Decimal(0), now=now))
    assert not r.complete and any("schedule stale" in p for p in r.problems)


@pytest.mark.parametrize("field,value", [("stock", "1.5"), ("moq", 0), ("order_multiple", "2.5"), ("stock", "NaN")])
def test_supplier_quantities_never_get_silently_truncated(field, value):
    with pytest.raises(ValueError):
        record_from_row({"supplier": "fixture", "supplier_pn": "TEST-part", field: value})


def test_nonfinite_electrical_parameter_is_unverified(catalog, bom):
    original = catalog.get("fixture:TEST-C100N-X7R-16V")
    p = original.params["voltage_rating"]
    candidate = replace(original, params=dict(original.params, voltage_rating=replace(p, value=Decimal("NaN"))))
    assert check_substitute(bom.line("L1"), original, candidate).status.value == "unverified"


def test_subpercent_tolerance_is_not_displayed_with_an_si_prefix():
    from partlens.core.units import format_value
    assert format_value(Decimal("0.1"), "%") == "0.1%"


def test_unspecified_operating_rating_and_ic_gaps_stay_unverified(catalog, bom):
    original, candidate = catalog.get("fixture:TEST-LDO-A"), catalog.get("fixture:TEST-LDO-B")
    p = candidate.params["supply_voltage_max"]
    candidate = replace(candidate, params=dict(candidate.params, supply_voltage_max=replace(p, rating_kind=None)))
    req = Requirement("TEST-vin", "L3", "supply_voltage_max", Op.GE, Decimal(4), RequirementKind.HARD,
                      Provenance(ProvenanceStatus.USER_CONFIRMED, "user:TEST"), unit="V")
    result = check_substitute(bom.line("L3"), original, candidate, [req])
    assert next(c for c in result.checks if c.check == "req.supply_voltage_max").status.value == "unverified"
    assert {"equivalence.pinout", "equivalence.operating", "equivalence.function"} <= {c.check for c in result.gaps}


@pytest.mark.parametrize("limits,expected_calls", [({"max_repeated_calls": 2}, 2), ({"max_tool_calls": 1}, 1)])
def test_agent_stops_unproductive_or_overbudget_tool_loops(tmp_path, limits, expected_calls):
    s = Session(RunRecorder.create(tmp_path), [])
    script = [[("list_requirements", {})] * 5]
    result = Agent(s, ScriptedProvider(script), lambda q: "", **limits).send("TEST bounded review")
    assert "Incomplete" in result
    events = read_events(s.recorder.path)
    assert sum(e["type"] == "tool_call" for e in events) == expected_calls
    assert events[-1]["type"] == "agent_stopped"


def test_truncated_model_output_is_not_a_completed_analysis(tmp_path):
    class Truncated(ScriptedProvider):
        def next_turn(self, *args):
            return Turn("TEST partial", [], [], "max_tokens")
    s = Session(RunRecorder.create(tmp_path), [])
    assert "Incomplete" in Agent(s, Truncated([]), lambda q: "").send("TEST")
    assert read_events(s.recorder.path)[-1]["type"] == "agent_incomplete"


def test_ui_credit_failure_is_actionable_without_raw_provider_json():
    text = failure_message(RuntimeError("Error 400 {'message': 'Your credit balance is too low'}"))
    assert "insufficient API credit" in text and "Restore access locally" in text
    assert "{'" not in text


def test_changed_engineering_requirement_invalidates_old_approval(tmp_path, catalog):
    s = session(tmp_path, catalog)
    output = s.check_substitute("L1", "fixture:TEST-C100N-X7R-50V-EXT")
    assert output["status"] == "verified" and s.alternatives["L1"]
    s.recorder.log("tool_call", name="check_substitute", output=output)
    s.recorder.log("user_message", text="Require 100 V")
    s.record_requirement("L1", "voltage_rating", ">=", "100V", user_quote="Require 100 V")
    assert "L1" not in s.alternatives and output["decision_id"] not in s.decisions
    assert "HISTORICAL" in format_view("Qualifications", review_snapshot(s)["Qualifications"])
    assert s.check_substitute("L1", "fixture:TEST-C100N-X7R-50V-EXT")["status"] == "rejected"


def test_changed_derating_rederives_applied_voltage(tmp_path, catalog):
    s = session(tmp_path, catalog)
    s.recorder.log("user_message", text="12 V")
    s.record_requirement("L1", "applied_voltage", "==", "12V", user_quote="12 V")
    assert s.requirements["L1.voltage_rating.applied"].value == 12
    s.recorder.log("user_message", text="factor 2")
    s.record_requirement("design", "derating_factor", "==", "2", user_quote="factor 2")
    assert s.requirements["L1.voltage_rating.applied"].value == 24


def test_optimizer_rejects_approval_for_a_different_part(catalog, bom, now):
    b = Bom("TEST", "fixture:TEST", [bom.line("L1")])
    original = catalog.get("fixture:TEST-C100N-X7R-16V")
    approved = catalog.get("fixture:TEST-C100N-X7R-50V-EXT")
    wrong = catalog.get("fixture:TEST-C100N-Y5V-16V")
    result = optimise(b, {"L1": original}, {"L1": [Option(wrong, check_substitute(b.line("L1"), original, approved))]},
                      CostInputs(60, known_fees(), Decimal(0), now=now))
    assert result.selection["L1"] == original and any("identity/line" in x for x in result.excluded)
