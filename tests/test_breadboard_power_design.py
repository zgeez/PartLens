"""Tests for the Breadboard Power Supply New Design workflow, confirmed vs provisional requirements, and LDO vs buck-boost checks."""

from __future__ import annotations

from decimal import Decimal
import json

import pytest

from partlens.core.model import CheckStatus
from partlens.design.architecture import propose
from partlens.design.interaction import clarification_plan, runtime_options
from partlens.design.patterns import all_patterns, required_blocks
from partlens.design.requirements import Requirements, State, parse
from partlens.design.session import DesignSession
from partlens.records import RunRecorder

BREADBOARD_IDEA = (
    "Design a dual-rail breadboard power supply with USB-C 5V DC input (4.75V to 5.25V), "
    "a regulated 3.3V primary output rail and a 5V secondary breadboard rail, delivering "
    "500mA maximum continuous load current for 5 boards."
)


def test_breadboard_feature_detection_blocks_and_ranked_questions():
    spec = Requirements("TEST-bb", BREADBOARD_IDEA, "user:TEST#seq1")
    assert spec.features == ["breadboard_power"]
    assert required_blocks(spec.features) == {"input_power", "power", "rail_output", "indicator"}
    plan = clarification_plan(spec)
    gap_ids = {g["id"] for g in plan}
    assert {
        "input_interface", "input_voltage_min", "input_voltage_max",
        "logic_voltage", "secondary_rail_voltage", "rail_current_max",
        "rail_selection", "width", "height", "board_quantity", "parts_budget",
    } <= gap_ids
    assert plan[0]["id"] == "input_interface"


def test_breadboard_confirmed_vs_provisional_requirements_and_ldo_failure_correction(tmp_path):
    rec = RunRecorder.create(tmp_path / "runs")
    session = DesignSession(
        rec, [], description=BREADBOARD_IDEA, design_id="TEST-breadboard",
        engineering_mode=True, interaction_mode=True,
    )
    session.start_new_design()

    # Record user-confirmed requirements with verbatim quotes from the recorded user description
    confirmed = [
        ("logic_voltage", "3.3V", "3.3V"),
        ("secondary_rail_voltage", "5V", "5V"),
        ("input_voltage_min", "4.75V", "4.75V"),
        ("input_voltage_max", "5.25V", "5.25V"),
        ("rail_current_max", "500mA", "500mA"),
        ("board_quantity", "5", "5 boards"),
    ]
    for param, val, quote in confirmed:
        out = session.record_design_requirement(param, val, user_quote=quote)
        assert out["entry"]["binding"] is True
        assert session.spec.current[param].state is State.CONFIRMED

    # Record interactive answer for input_interface
    rec.log("user_message", text="usb_c", origin="user")
    out_iface = session.record_design_requirement("input_interface", "usb_c", user_quote="usb_c")
    assert out_iface["entry"]["binding"] is True

    # Propose provisional defaults for the remaining parameters (never user-confirmed)
    provisional = [
        {"parameter": "rail_selection", "value": "jumper_selectable", "rationale": "Provisional jumper selection"},
        {"parameter": "width", "value": "53mm", "rationale": "Standard MB-102 breadboard span"},
        {"parameter": "height", "value": "32mm", "rationale": "Compact module depth"},
        {"parameter": "parts_budget", "value": "4USD", "rationale": "Provisional parts target"},
    ]
    session.propose_design_requirements(provisional)
    for row in provisional:
        entry = session.spec.current[row["parameter"]]
        assert entry.binding is False
        assert entry.state is State.INFERRED

    # Select initial LDO architecture (XC6206P332MR 250mA SOT-23) -> must fail current and thermal checks at 500mA
    initial = {
        "input_power": "input_power.usb_c_5v",
        "power": "power.xc6206_ldo",
        "rail_output": "rail_output.breadboard_headers",
        "indicator": "indicator.power_led",
    }
    session.select_design_patterns(initial, justification="Initial LDO check")
    checks = {c.check: c for c in session.circuit.checks}
    assert checks["input.voltage_envelope"].status is CheckStatus.PASS
    assert checks["input.connector_compatibility"].status is CheckStatus.PASS
    assert checks["power.input_range"].status is CheckStatus.PASS
    assert checks["power.output"].status is CheckStatus.PASS
    assert checks["power.design_budget"].status is CheckStatus.FAIL
    assert checks["power.thermal_dissipation"].status is CheckStatus.FAIL
    assert checks["power.secondary_rail"].status is CheckStatus.UNVERIFIED
    assert Decimal(session.circuit.estimates["ldo_worst_case_dissipation_W"]) == Decimal("0.975975")

    # Counterfactual runtime/thermal options must compute exact SOT-23 thermal bound without mutating requirements
    opts = runtime_options(session.spec, session.circuit)
    assert opts["status"] == "conditional_analysis"
    assert Decimal(opts["options"][0]["necessary_bound"]) == Decimal("127.705")

    # Compare bounded alternatives -> TPS63031 and TPS63802 resolve both power.design_budget and power.thermal_dissipation
    comp = session.compare_design_alternatives()
    tps63031_alt = next(a for a in comp["alternatives"] if a["selections"]["power"] == "power.tps63031")
    assert set(tps63031_alt["resolved_failures"]) == {"power.design_budget", "power.thermal_dissipation"}
    assert tps63031_alt["new_failures"] == []

    # Investigate TPS63031 alternative -> preserves failed LDO trial in history and clears failed screens
    session.investigate_design_alternative(tps63031_alt["id"])
    assert len(session.design_history) == 1
    new_checks = {c.check: c for c in session.circuit.checks}
    assert new_checks["power.design_budget"].status is CheckStatus.PASS
    assert new_checks["power.thermal_dissipation"].status is CheckStatus.UNVERIFIED

    # Generate BOM, source, qualify, and compute cost scenarios (5 confirmed boards vs 60 hypothetical)
    bom_out = session.generate_design_bom()
    assert bom_out["origin"] == "generated_from_patterns" and not bom_out["manufacturing_ready"]
    session.source_design_roles()
    session.qualify_design()
    costs = session.design_cost_scenarios()
    assert costs["scenarios"][0]["boards"] == 5
    assert costs["scenarios"][0]["scenario"] == "user_confirmed"
    assert costs["scenarios"][1]["boards"] == 60
    assert costs["scenarios"][1]["scenario"] == "hypothetical"


def test_breadboard_end_to_end_agent_pipeline_and_hmem_recall(tmp_path):
    from scripts.breadboard_power_design import run_breadboard_workflow

    outcome = run_breadboard_workflow(tmp_path, sync_desktop=False)
    report = outcome["report"]
    assert report["controller"]["workflow_steps_complete"] is True
    assert report["controller"]["operational_pipeline_complete"] is True
    assert report["architecture"]["selections"]["power"] == "power.tps63031"
    assert len(report["architecture_history"]) == 1
    assert report["architecture_history"][0]["circuit"]["selections"]["power"] == "power.xc6206_ldo"
    reqs = report["requirements"]["requirements"]
    assert reqs["logic_voltage"]["binding"] is True
    assert reqs["secondary_rail_voltage"]["binding"] is True
    assert reqs["input_voltage_min"]["binding"] is True
    assert reqs["input_voltage_max"]["binding"] is True
    assert reqs["rail_current_max"]["binding"] is True
    assert reqs["board_quantity"]["binding"] is True
    assert reqs["input_interface"]["binding"] is True
    assert reqs["rail_selection"]["binding"] is False
    assert reqs["width"]["binding"] is False
    assert reqs["height"]["binding"] is False
    assert reqs["parts_budget"]["binding"] is False
    assert outcome["reverified_count"] == 5
    assert "unchanged" in outcome["reverified_outcomes"]


def test_breadboard_interactive_desktop_chat_bom_transfer_and_delete(tmp_path, catalog, monkeypatch):
    import os
    import time
    from partlens.agent import ScriptedProvider
    from partlens.settings import AppSettings
    from partlens.web_desktop import DesktopBridge
    from scripts.breadboard_power_design import load_cached_catalogs

    monkeypatch.setattr(os, "environ", os.environ.copy())
    state_dir = tmp_path / "state"
    cats = [*load_cached_catalogs(), catalog]
    app = DesktopBridge(tmp_path, AppSettings(), cats, token="TEST-bb-token")
    app._engine.provider_factory = lambda: ScriptedProvider([])

    prompt = (
        "Design a breadboard power supply with a regulated 3.3V primary rail, a 5V secondary rail, "
        "4.75V to 5.25V input voltage, 500mA maximum continuous load current, and 5 prototype boards. "
        "Propose reasonable defaults for the remaining parameters"
    )
    res = app.request("send", {"text": prompt, "mode": "design", "proposals": True}, token="TEST-bb-token")
    assert res["ok"]

    # Answer question 1 via chat text ("USB-C") and question 2 via "Let AI set requirement" (delegate=True)
    answers = [{"text": "USB-C"}, {"delegate": True}]
    ans_idx = 0
    end = time.monotonic() + 30
    while time.monotonic() < end:
        snap = app.request("snapshot", token="TEST-bb-token")["state"]
        if snap["question"] and ans_idx < len(answers):
            app.request("answer", answers[ans_idx], token="TEST-bb-token")
            ans_idx += 1
        elif not snap["busy"]:
            break
        time.sleep(0.05)

    snap = app.request("snapshot", token="TEST-bb-token")["state"]
    assert not snap["busy"], f"Timed out: {snap['status']}"
    assert snap["report"] is not None
    assert len(snap["report"]["bom"]) == 16
    assert snap["report"]["architecture"]["selections"]["power"] == "power.tps63031"
    reqs = snap["report"]["requirements"]["requirements"]
    assert reqs["input_interface"]["binding"] is True
    assert reqs["rail_selection"]["binding"] is False
    assert reqs["rail_selection"]["value"] == "jumper_selectable"
    # Verify conversational commentary messages, AI-delegated message, and rich report sections
    msgs = snap["messages"]
    assert any(m["kind"] == "commentary" and "Breadboard Power Supply" in m["text"] for m in msgs)
    assert any(m["kind"] == "commentary" and "I chose **jumper selectable** for **Rail Selection**" in m["text"] for m in msgs)
    assert any(m["kind"] == "commentary" and "TPS63031DSKR" in m["text"] for m in msgs)
    report_msg = next(m for m in msgs if m["kind"] == "report")
    assert "### Requirements" in report_msg["text"]
    assert "### Architecture" in report_msg["text"]
    assert "### Generated BOM Roles" in report_msg["text"]
    assert "### Component Cost Scenarios" in report_msg["text"]

    # Verify BOM workspace was automatically populated with all 16 lines, 14 matched parts (rail selector C49257 included), 0 unmatched placed lines, and 5 vs 60 board scenarios
    assert len(snap["bom"]["Parts"]["lines"]) == 16
    assert sum(1 for ln in snap["bom"]["Parts"]["lines"] if ln["matched_part"]) == 14
    # Unresolved roles (inductor, 2x2 rail headers) must still be fitted: unmatched, never silently DNP.
    assert all(ln["purchased"] for ln in snap["bom"]["Parts"]["lines"])
    unmatched = [ln for ln in snap["bom"]["Parts"]["lines"] if not ln["matched_part"]]
    assert len(unmatched) == 2 and any(ln["mpn"] == "LPS3015-1R5" for ln in unmatched)
    # The BOM workspace carries the owner's recorded words for quantity, never a synthesised "5" message.
    bom_events = [json.loads(l) for l in app._bom_session.recorder.path.read_text(encoding="utf-8").splitlines()]
    carried = [e for e in bom_events if e["type"] == "user_message"]
    assert carried and all(e["text"] == prompt and e.get("carried_from") for e in carried)
    assert [s["boards"] for s in snap["bom"]["Cost"]["scenarios"]] == [5, 60]

    # Verify delete_chat removes conversation from history while preserving .jsonl file on disk
    chat_id = snap["chat"]["id"]
    chat_file = state_dir / "conversations" / f"{chat_id}.jsonl"
    assert chat_file.exists()
    del_res = app.request("delete_chat", {"id": chat_id}, token="TEST-bb-token")
    assert del_res["ok"]
    assert all(c["id"] != chat_id for c in del_res["state"]["history"])
    assert chat_file.exists()


