"""Synthetic code-discovery, request-budget and lossless source-replay regressions."""

import json
from dataclasses import replace
from decimal import Decimal

import pytest

from partlens.agent import Agent, ScriptedProvider, ToolCall
from partlens.core.model import digest
from partlens.records import RunRecorder, read_events
from partlens.replay import replay
from partlens.session import Session
from partlens.sources.audit import AuditedCatalog, ObservationCatalog, ObservationMismatch, decode_part, encode_part
from partlens.sources.catalog import LocalCatalog
from partlens.sources.jlcpcb import JLCCatalog, JLCClient, JLCError
from tests.test_jlcpcb import CFG, CODE, Response, component, part


def test_leads_select_codes_but_never_transfer_stale_engineering_or_commercial_values(tmp_path):
    original = replace(part(), supplier="lcsc", suggested_alternates=("lcsc:C900000002",))
    stale = replace(part(), supplier="lcsc", supplier_pn="C900000002", stock=0, params={},
                    assembly_class="extended", source="fixture:TEST-old-lead", retrieved_at="2000-01-01T00:00:00Z")
    requested = []
    def transport(req, **kwargs):
        codes = json.loads(req.data)["componentCodes"]; requested.extend(codes)
        data = []
        for code in codes:
            raw = component(); raw["componentCode"] = code; data.append(raw)
        return Response({"code": 200, "success": True, "data": data})
    rec = RunRecorder.create(tmp_path / "runs")
    client = JLCClient(CFG, cache_dir=tmp_path / "cache", recorder=rec, transport=transport)
    catalogue = JLCCatalog(client, LocalCatalog([original, stale]))
    found = catalogue.discover_for(part(), "capacitor", "0402", None, 10)
    assert requested == ["C900000002"] and len(found) == 1
    fresh = found[0]
    assert fresh.supplier == "jlcpcb" and fresh.stock == 100 and fresh.assembly_class == "basic"
    assert fresh.params["capacitance"].value == Decimal("100e-9") and fresh.params["voltage_rating"].value == Decimal(25)
    assert fresh.retrieved_at != stale.retrieved_at and fresh.params["capacitance"].evidence.locator.startswith("https://open.jlcpcb.com")
    assert fresh.supplier_metadata["research_lead"]["source"] == "fixture:TEST-old-lead"
    assert any(e["type"] == "jlcpcb_discovery_leads" and not e["engineering_fields_transferred"] for e in read_events(rec.path))


def test_discovery_is_bounded_and_missing_official_results_are_not_fabricated(tmp_path):
    leads = [replace(part(), supplier="lcsc", supplier_pn=f"C{900000010+i}") for i in range(12)]
    calls = []
    def transport(req, **kwargs):
        calls.append(json.loads(req.data)["componentCodes"])
        return Response({"code": 200, "success": True, "data": []})
    cat = JLCCatalog(JLCClient(CFG, cache_dir=tmp_path, transport=transport), LocalCatalog(leads))
    assert cat.discover_for(part(), "capacitor", "0402", None, 20) == []
    assert len(calls) == 1 and len(calls[0]) == 6


def test_session_budget_blocks_network_but_allows_valid_cache(tmp_path):
    seen = []
    def transport(*a, **k):
        seen.append(1); return Response()
    client = JLCClient(CFG, cache_dir=tmp_path, max_requests=1, transport=transport)
    first = client.lookup([CODE])
    assert client.lookup([CODE]).cached
    with pytest.raises(JLCError, match="budget exhausted"):
        client.lookup([CODE], refresh=True)
    assert len(seen) == 1 and client.requests_used == 1


def test_distinct_code_budget_and_session_binding(tmp_path):
    client = JLCClient(CFG, cache_dir=tmp_path / "cache", max_distinct_codes=1, transport=lambda *a, **k: Response())
    client.lookup([CODE])
    with pytest.raises(JLCError, match="budget exhausted"):
        client.lookup(["C900000002"])
    rec = RunRecorder.create(tmp_path / "runs")
    bound = JLCCatalog(client).with_recorder(rec)
    assert bound.client.max_distinct_codes == 1 and bound.client.requests_used == 0


def test_supplier_serialization_preserves_numeric_types_source_domains_and_bounds():
    p = replace(part(), engineering_notes=("TEST-note",), suggested_alternates=("jlcpcb:C900000002",))
    assert decode_part(json.loads(json.dumps(encode_part(p)))) == p
    assert decode_part(None) is None


def test_recorded_supplier_replay_executes_engineering_and_cost_without_network(tmp_path):
    original = part()
    candidate = replace(part(), supplier_pn="C900000002", mpn="TEST-CAP-ALT")
    file = tmp_path / "TEST-bom.csv"
    file.write_text('Refs,Value,Footprint,Qty,LCSC\nC1,100nF,C_0402,1,' + CODE + '\n')
    rec = RunRecorder.create(tmp_path / "runs")
    session = Session(rec, [AuditedCatalog(LocalCatalog([original, candidate], name="TEST-official-fixture"))])
    agent = Agent(session, ScriptedProvider([]), lambda _: "")
    def call(name, **arguments):
        output = agent._execute(ToolCall("TEST-" + str(rec.seq), name, arguments))
        assert not output.get("is_error"), output
        return json.loads(output["content"])
    call("import_bom", path=str(file))
    call("match_parts")
    rec.log("user_message", text="1", synthetic_test=True)
    call("record_requirement", subject="design", parameter="board_quantity", op="==", value="1", user_quote="1")
    call("search_candidates", line_id="L1")
    call("get_part", key=candidate.key)
    assert call("check_substitute", line_id="L1", candidate_key=candidate.key)["status"] == "verified"
    call("check_availability", line_id="L1", part_key=original.key)
    call("compare_cost_scenarios", hypothetical_boards=60)
    report = replay(rec.path)
    assert report.ok and report.replayed == report.matched == 8
    assert any(e["type"] == "replay_source_mode" for e in read_events(report.audit_record))


def test_observation_replay_rejects_tampering_and_missing_inputs():
    result = encode_part(part())
    event = {"type": "catalogue_operation", "catalogue": "TEST", "bom_supplier": "jlcpcb",
             "operation": "get", "arguments": {"key": "jlcpcb:" + CODE}, "result": result,
             "result_digest": digest(result)}
    events = [event, {"type": "tool_call", "seq": 2}]
    cat = ObservationCatalog("TEST", events)
    cat.begin(2)
    with pytest.raises(ObservationMismatch, match="arguments"):
        cat.get("jlcpcb:C900000002")
    with pytest.raises(ObservationMismatch, match="missing"):
        cat.get("jlcpcb:" + CODE)
    event["result"]["part"]["stock"] = 123456
    with pytest.raises(ObservationMismatch, match="digest"):
        ObservationCatalog("TEST", events)


def test_skipped_memory_tool_observations_do_not_shift_later_supplier_reads():
    def source(stock):
        value = encode_part(replace(part(), stock=stock))
        return {"type": "catalogue_operation", "catalogue": "TEST", "bom_supplier": "jlcpcb", "operation": "get",
                "arguments": {"key": "jlcpcb:" + CODE}, "result": value, "result_digest": digest(value)}
    events = [source(1), {"type": "tool_call", "seq": 2, "name": "reverify_decision"},
              source(2), {"type": "tool_call", "seq": 4, "name": "get_part"}]
    cat = ObservationCatalog("TEST", events)
    cat.begin(4)
    assert cat.get("jlcpcb:" + CODE).stock == 2
    cat.finish()


def test_evaluation_gate_accepts_evidenced_rejections_but_no_unearned_application_pass():
    from scripts.evaluate_milestone5 import applications_supported

    unknown = {"application": {"status": "unverified", "checks": []}}
    rejected = {"application": {"status": "rejected", "checks": [{"status": "fail", "evidence": ["TEST-source"]}]}}
    assert applications_supported([unknown, rejected])
    assert not applications_supported([{"application": {"status": "verified", "checks": []}}])
    assert not applications_supported([{"application": {"status": "rejected", "checks": []}}])


def test_scenario_overview_precedes_detailed_price_evidence():
    from partlens.ui import format_view

    scenario = {"boards": 1, "scenario": "owner_confirmed", "quantity_source": "TEST-source",
                "proposed_replacements": {}, "component_subtotal_difference": None, "assembled_savings": None,
                "comparison_complete": False, "baseline": {"note": "TEST-baseline"},
                "proposed": {"note": "TEST-proposed"}, "excluded": [],
                "official_nominal_price_observations": [{"line": "L1", "part": "TEST-part", "needed": 1,
                    "unit_price": "0.1", "nominal_amount": "0.1", "currency": None,
                    "source": "TEST-source", "retrieved_at": "TEST-time", "unknowns": ["currency"]}]}
    text = format_view("Cost", {"note": "TEST-incomplete", "scenarios": [scenario,
                               {**scenario, "boards": 60, "scenario": "hypothetical"}]})
    assert text.index("1 boards | OWNER_CONFIRMED") < text.index("Official nominal price arithmetic")
    assert text.index("60 boards | HYPOTHETICAL") < text.index("Official nominal price arithmetic")
    assert "currency: UNKNOWN" in text and "TEST-source | retrieved TEST-time" in text


def test_response_metadata_logging_excludes_sensitive_headers(tmp_path):
    from tests.test_jlcpcb import CFG, Response

    response = Response()
    response.headers = {"Date": "TEST-date", "Content-Type": "application/json", "J-Trace-ID": "TEST-trace",
                        "Set-Cookie": "TEST-cookie-secret", "Authorization": "TEST-authorization-secret"}
    rec = RunRecorder.create(tmp_path / "runs")
    JLCClient(CFG, cache_dir=tmp_path / "cache", recorder=rec, transport=lambda *a, **k: response).lookup([CODE])
    event = next(e for e in read_events(rec.path) if e["type"] == "jlcpcb_response_metadata")
    assert event["headers"] == {"Date": "TEST-date", "Content-Type": "application/json"}
    assert "TEST-cookie-secret" not in rec.path.read_text() and "TEST-authorization-secret" not in rec.path.read_text()
