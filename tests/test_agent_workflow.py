"""First end-to-end agent workflow with a scripted model (no LLM), real H-MEM memory and a run record:

import design -> identify missing information -> ask a question -> record the answer as a user-confirmed
requirement -> research a component -> verify deterministically -> evidence and decision recorded and remembered.
"""

import json

import pytest

from partlens.agent import Agent, ScriptedProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge, HMemError
from partlens.records import RunRecorder, read_events
from partlens.replay import replay
from partlens.session import Session

from .conftest import FIXTURES, NOW

BOM = str(FIXTURES / "bom_kicad.csv")


@pytest.fixture
def hmem(tmp_path):
    try:
        b = HMemBridge(tmp_path / "hmem")
    except HMemError as e:
        pytest.skip(f"H-MEM unavailable: {e}")
    yield b
    b.close()


def make_session(tmp_path, catalog, bridge, run_id):
    rec = RunRecorder.create(tmp_path / "runs", run_id)
    return Session(rec, [catalog], memory=DecisionMemory(bridge, "bom_kicad"), now=NOW)


def script():
    def pick_gap(results):
        gaps = results[0]["gaps"]
        g = next(g for g in gaps if g["id"] == "L1.applied_voltage")
        return [("ask_user", {"question": g["suggested_question"], "gap_id": g["id"]})]

    def record(results):
        assert "12" in results[0]["answer"]
        return [("record_requirement", {"subject": "L1", "parameter": "applied_voltage", "op": "<=", "value": "12V",
                                        "user_quote": "rail is 12 V"}),
                ("record_requirement", {"subject": "design", "parameter": "board_quantity", "op": "==",
                                        "value": "60", "user_quote": "60 boards"})]

    def check_all(results):
        cands = results[0]["candidates"]
        return [("check_substitute", {"line_id": "L1", "candidate_key": c["key"]}) for c in cands]

    return [
        [("import_bom", {"path": BOM})],
        [("match_parts", {}), ("find_missing_information", {})],
        lambda results: pick_gap(results[1:]),
        record,
        [("search_candidates", {"line_id": "L1"})],
        check_all,
        [("check_availability", {"part_key": "fixture:TEST-C100N-X7R-STALE", "line_id": "L1"})],
        "Done.",
    ]


def answers(question):
    assert "C1,C2,C3,C4" in question
    return "The rail is 12 V on that net, and we build 60 boards."


def test_end_to_end_agent_workflow(tmp_path, catalog, hmem):
    session = make_session(tmp_path, catalog, hmem, "run-e2e-1")
    agent = Agent(session, ScriptedProvider(script()), answers)
    assert agent.send("Here is my BOM, can we reduce cost?") == "Done."

    # The question was asked and the answer became user-confirmed requirements.
    reqs = session.requirements
    assert reqs["L1.applied_voltage"].provenance.status.value == "user_confirmed"
    assert reqs["L1.applied_voltage"].provenance.source.startswith("user:run-e2e-1#seq")
    assert reqs["L1.voltage_rating.applied"].provenance.status.value == "calculated"
    assert reqs["design.board_quantity"].binding

    by_cand = {d.candidate: d for d in session.decisions.values()}
    st = {k.split(":")[1]: d.status.value for k, d in by_cand.items()}
    assert st["TEST-C100N-X7R-50V-EXT"] == "verified"
    assert st["TEST-C100N-Y5V-16V"] == "rejected"
    assert st["TEST-C100N-X5R-25V"] == "rejected"
    assert st["TEST-C100N-X7R-6V3"] == "rejected"          # 6.3 V < 12 V applied and < 16 V original
    assert st["TEST-C100N-NODIEL"] == "unverified"
    assert st["TEST-C100N-X7R-STALE"] == "verified"       # compatible; availability is a separate verdict
    assert "TEST-C100N-X7R-0603" not in st                 # different package never offered as a candidate
    applied = next(c for c in by_cand["fixture:TEST-C100N-X7R-6V3"].checks if c.requirement_id == "L1.voltage_rating.applied")
    assert applied.status.value == "fail" and applied.evidence[1].kind.value == "calculation"

    events = read_events(session.recorder.path)
    types = [e["type"] for e in events]
    assert types.count("question") == 1 and types.count("user_message") == 2
    avail = [e for e in events if e["type"] == "tool_call" and e["name"] == "check_availability"][0]
    assert {c["check"]: c["status"] for c in avail["output"]["checks"]}["supply.freshness"] == "unverified"

    # A second session (new run, same memory) recalls the earlier rejection with its provenance.
    session2 = make_session(tmp_path, catalog, hmem, "run-e2e-2")
    session2.import_bom(BOM)
    session2.match_parts()
    out = session2.check_substitute("L1", "fixture:TEST-C100N-Y5V-16V")
    prior = out["prior_decisions_from_memory"]
    assert len(prior) == 1 and prior[0]["status"] == "rejected"
    assert prior[0]["source"].startswith("partlens:run:run-e2e-1:decision:")
    assert prior[0]["agrees_with_current"] is True

    # The run replays: every deterministic tool output reproduces.
    res = replay(session.recorder.path, [catalog])
    assert res.ok, res.mismatches
    assert res.replayed >= 10 and res.matched == res.replayed


def test_requirement_without_user_quote_is_provisional(tmp_path, catalog, hmem):
    session = make_session(tmp_path, catalog, hmem, "run-prov")
    session.import_bom(BOM)
    session.recorder.log("user_message", text="Please check the regulator.")
    out = session.record_requirement("L3", "supply_voltage_max", ">=", "5.5V",
                                     user_quote="input can reach 5.5 V")
    assert out["binding"] is False and session.requirements["L3.supply_voltage_max"].provenance.status.value == "provisional"


def test_tool_errors_are_reported_to_the_model(tmp_path, catalog, hmem):
    session = make_session(tmp_path, catalog, hmem, "run-err")
    agent = Agent(session, ScriptedProvider([[("check_substitute", {"line_id": "L1", "candidate_key": "x"})],
                                             lambda r: r[0]["error"]]), answers)
    assert agent.send("go") == "no BOM loaded; call import_bom first"
    ev = [e for e in read_events(session.recorder.path) if e["type"] == "tool_call"][0]
    assert ev["error"] and json.dumps(ev)
