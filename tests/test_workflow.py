"""Synthetic historical-failure regressions; live local-model evidence is recorded separately."""

import json
from dataclasses import replace
from pathlib import Path

import pytest

from partlens.agent import Agent, ScriptedProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge, HMemError
from partlens.records import RunRecorder, read_events
from partlens.results import FinalResult
from partlens.session import Session
from partlens.ui import review_snapshot, format_view
from partlens.workflow import WorkflowController, WorkflowRequest
from .conftest import NOW

BOM = "tests/fixtures/bom_kicad.csv"
GOOD = "fixture:TEST-C100N-X7R-50V-EXT"
BAD = "fixture:TEST-C100N-X7R-6V3"


def make(tmp_path, catalog, memory=None):
    s = Session(RunRecorder.create(tmp_path / "runs"), [catalog], memory=memory, now=NOW)
    s.recorder.log("user_message", text="1", origin="user")
    s.record_requirement("design", "board_quantity", "==", "1", user_quote="1")
    return s


def request(**kwargs):
    return WorkflowRequest(BOM, design="bom_kicad", lines=("L1",), require_memory=False,
                           desired_outcomes=("verified",), **kwargs)


def research_script(final="TEST finished"):
    return [[("import_bom", {"path": BOM})], [("find_missing_information", {})], [("match_parts", {})],
            [("search_candidates", {"line_id": "L1"})],
            [("check_substitute", {"line_id": "L1", "candidate_key": GOOD})], final]


def test_premature_final_recovers_then_replaces_unsafe_narrative(tmp_path, catalog):
    s = make(tmp_path, catalog)
    script = research_script("The user ordered 60 boards; this replacement is safe and JLCPCB quoted $4.")
    script.insert(3, "TEST premature complete")
    a = Agent(s, ScriptedProvider(script), lambda q: None)
    text = a.send("TEST research", workflow=request())
    assert a.last_result.status == "completed_preliminary"
    assert "ordered 60" not in text and "quoted $4" not in text and "is safe" not in text
    assert "Application: unverified" in text and "Equivalence: verified" in text
    assert any(e["type"] == "controller_recovery" for e in read_events(s.recorder.path))
    assert a.last_result.narrative_validation["action"] == "deterministic_replacement"


def test_small_model_cannot_skip_checks_and_claim_success(tmp_path, catalog):
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider(["Everything is verified"] * 10), lambda q: None)
    text = a.send("TEST research", workflow=replace(request(), max_recoveries=2))
    assert a.last_result.status == "partial"
    assert "import" in a.last_result.workflow["missing_actions"]
    assert "Everything is verified" not in text and not s.decisions


def test_unanswered_electrical_question_stays_unresolved(tmp_path, catalog):
    s = make(tmp_path, catalog)
    script = research_script()
    script.insert(2, [("ask_user", {"question": "TEST actual capacitor voltage?", "gap_id": "L1.applied_voltage"})])
    a = Agent(s, ScriptedProvider(script), lambda q: None)
    before = len(s.recorder.user_messages())
    text = a.send("TEST clarify", origin="test_task", workflow=request(clarify_electrical=True))
    assert "L1.applied_voltage" in a.last_result.workflow["unanswered_questions"]
    assert "L1.applied_voltage" not in s.requirements
    assert len(s.recorder.user_messages()) == before + 1  # task only, no fabricated owner reply
    assert a.last_result.status == "partial" and "Unanswered owner questions" in text


@pytest.mark.parametrize("budget", [1, 2])
def test_tool_budget_returns_useful_partial_result(tmp_path, catalog, budget):
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider(research_script()), lambda q: None, max_tool_calls=budget)
    assert "partial" in a.send("TEST", workflow=request())
    assert a.last_result.stopped_reason and a.last_result.workflow["missing_actions"]


def test_controller_blocks_checks_before_supplier_evidence(tmp_path, catalog):
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider([[('check_substitute', {'line_id': 'L1', 'candidate_key': GOOD})], "TEST"]), lambda q: None)
    a.send("TEST", workflow=replace(request(), max_recoveries=0))
    calls = [e for e in read_events(s.recorder.path) if e["type"] == "tool_call"]
    assert calls[0]["controller_blocked"] and not s.decisions
    from partlens.replay import replay
    audit = replay(s.recorder.path, [catalog])
    assert audit.ok and audit.skipped == 1


@pytest.mark.parametrize("draft", ["The user ordered 60 boards", "JLCPCB quoted $99", "This replacement is safe",
                                  '{"price": "1.00"}', '{"decision_refs":["TEST-invented"]}'])
def test_authoritative_result_never_accepts_model_facts(tmp_path, catalog, draft):
    s = make(tmp_path, catalog)
    result = FinalResult.build(WorkflowController(request()), s, draft)
    assert not result.narrative_validation["accepted"]
    assert draft not in result.render()
    assert s._boards() == 1


def test_cost_result_separates_hypothetical_and_unknown_fees(tmp_path, catalog):
    s = make(tmp_path, catalog)
    script = research_script()
    script.insert(-1, [("check_availability", {"line_id": "L1", "part_key": "fixture:TEST-C100N-X7R-16V"})])
    script.insert(-1, [("compare_cost_scenarios", {"hypothetical_boards": 60})])
    a = Agent(s, ScriptedProvider(script), lambda q: None)
    text = a.send("TEST cost", workflow=request(costs=True))
    assert "Hypothetical scenario: 60" in text and "User-confirmed requirement: 1" in text
    assert "Official manufacturer quotation: unavailable" in text
    assert "complete: False" in text and "Estimated assembled cost: n/a" in text
    assert s._boards() == 1
    view = format_view("Cost", a.last_result.costs)
    assert "60 boards" in view and "HYPOTHETICAL" in view and "OWNER_CONFIRMED" in view


def test_ui_hides_raw_model_draft_and_marks_changed_result_historical(tmp_path, catalog):
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider(research_script("The user ordered 60 boards")), lambda q: None)
    a.send("TEST", workflow=request())
    assert "ordered 60" not in review_snapshot(s)["Explanation"]
    s.recorder.log("user_message", text="maximum voltage is 5 V")
    s.record_requirement("L1", "applied_voltage", "<=", "5V", user_quote="maximum voltage is 5 V")
    assert "historical" in review_snapshot(s)["Explanation"]


@pytest.fixture
def memory_store(tmp_path):
    path = tmp_path / "memory"
    try:
        b = HMemBridge(path)
    except HMemError as exc:
        pytest.skip(str(exc))
    b.close()
    return path


def test_controller_reverifies_when_model_omits_historical_recheck(tmp_path, catalog, memory_store):
    with HMemBridge(memory_store) as b:
        first = make(tmp_path, catalog, DecisionMemory(b, "bom_kicad"))
        first.import_bom(BOM)
        first.match_parts()
        d = first.check_substitute("L1", BAD)
    with HMemBridge(memory_store) as b:
        s = make(tmp_path, catalog, DecisionMemory(b, "bom_kicad"))
        script = [[("import_bom", {"path": BOM})], [("find_missing_information", {})], [("match_parts", {})],
                  [("recall_decisions", {"query": "TEST", "run_id": first.recorder.run_id})], "TEST memory means approved"]
        a = Agent(s, ScriptedProvider(script), lambda q: None)
        a.send("TEST recall", workflow=replace(request(), research=False, recall_run=first.recorder.run_id))
        assert a.last_result.workflow["operations_complete"]
        actual = a.last_result.reverifications[0]
        assert actual["outcome"] == "unchanged" and actual["current_decision"]["status"] == "rejected"
        assert actual["memory_id"] == d["stored_in_memory"] and actual["context_matches"]
        calls = [e for e in read_events(s.recorder.path) if e["type"] == "tool_call"]
        assert any(e["name"] == "reverify_decision" and e["actor"] == "controller" for e in calls)


def test_changed_or_missing_memory_context_is_never_inherited(tmp_path, catalog, memory_store):
    with HMemBridge(memory_store) as b:
        s = make(tmp_path, catalog, DecisionMemory(b, "bom_kicad"))
        s.import_bom(BOM)
        s.match_parts()
        d = s.check_substitute("L1", BAD)
        s.recorder.log("user_message", text="applied voltage is 12 V")
        s.record_requirement("L1", "applied_voltage", "<=", "12V", user_quote="applied voltage is 12 V")
        changed = s.reverify_decision(d["stored_in_memory"])
        assert changed["outcome"] == "changed_context" and not changed["context_matches"]
        assert changed["current_decision"]["status"] == "rejected"
        with pytest.raises(ValueError):
            other = replace(s, memory=DecisionMemory(b, "TEST-other-design"))
            other.reverify_decision(d["stored_in_memory"])


def test_narrative_reference_selection_accepts_only_actual_ids(tmp_path, catalog):
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider(research_script()), lambda q: None)
    a.send("TEST", workflow=request())
    d = a.last_result.decisions[0]
    result = FinalResult.build(a.controller, s, json.dumps({"decision_refs": [d["decision_id"]]}))
    assert result.narrative_validation["accepted"]


def test_model_cannot_change_electrical_value_while_reusing_a_real_quote(tmp_path, catalog):
    s = make(tmp_path, catalog)
    s.import_bom(BOM)
    s.recorder.log("user_message", text="The applied voltage is 5 V for 60 boards.")
    result = s.record_requirement("L1", "applied_voltage", "<=", "60V",
                                  user_quote="The applied voltage is 5 V for 60 boards.")
    assert not result["binding"]


def test_explicit_voltage_units_confirm_only_the_stated_value(tmp_path, catalog):
    s = make(tmp_path, catalog)
    s.import_bom(BOM)
    s.recorder.log("user_message", text="The applied voltage is 500 mV.")
    result = s.record_requirement("L1", "applied_voltage", "<=", "0.5V", user_quote="500 mV")
    assert result["binding"]


def test_total_token_budget_is_enforced_before_another_model_request(tmp_path, catalog):
    class TokenProvider(ScriptedProvider):
        def next_turn(self, *args):
            turn = super().next_turn(*args)
            turn.usage = {"input": 100, "output": 1}
            return turn
    s = make(tmp_path, catalog)
    provider = TokenProvider(research_script())
    a = Agent(s, provider, lambda q: None, max_total_tokens=50)
    a.send("TEST", workflow=request())
    assert provider.step == 1 and a.last_result.stopped_reason == "token budget exhausted"


def test_missing_question_gap_id_never_crashes_or_fulfils_clarification(tmp_path, catalog):
    s = make(tmp_path, catalog)
    script = [[("import_bom", {"path": BOM})], [("find_missing_information", {})],
              [("ask_user", {"question": "TEST voltage?"})], "TEST finished"]
    a = Agent(s, ScriptedProvider(script), lambda q: pytest.fail("unmapped question should not be dispatched"))
    a.send("TEST", workflow=replace(request(clarify_electrical=True), max_recoveries=0))
    assert a.last_result.status == "partial"
    assert "clarification" in a.last_result.workflow["missing_actions"]


def test_cancelled_controlled_question_returns_honest_partial(tmp_path, catalog):
    s = make(tmp_path, catalog)
    def cancel(q):
        raise EOFError("TEST no reply")
    script = [[("import_bom", {"path": BOM})], [("find_missing_information", {})],
              [("ask_user", {"question": "TEST voltage?", "gap_id": "L1.applied_voltage"})], "TEST finished"]
    a = Agent(s, ScriptedProvider(script), cancel)
    text = a.send("TEST", workflow=replace(request(clarify_electrical=True), max_recoveries=0))
    assert a.last_result.status == "partial" and "Unanswered owner questions" in text


def test_paid_inference_is_blocked_before_client_creation(monkeypatch):
    from partlens.agent import AnthropicProvider
    monkeypatch.delenv("PARTLENS_ALLOW_PAID_INFERENCE", raising=False)
    with pytest.raises(ValueError, match="Paid inference disabled"):
        AnthropicProvider()


def test_live_provider_cannot_return_raw_facts_by_omitting_controller_scope(tmp_path, catalog):
    from partlens.local_provider import OllamaProvider
    s = make(tmp_path, catalog)
    a = Agent(s, OllamaProvider(), lambda q: None)
    with pytest.raises(ValueError, match="explicit WorkflowRequest"):
        a.send("TEST skip the controller")


def test_unmatched_requested_line_cannot_disappear_from_completion_gate(tmp_path, catalog):
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider(research_script()), lambda q: None)
    a.send("TEST", workflow=replace(request(), lines=("L1", "L4"), max_recoveries=0))
    assert a.last_result.status == "partial"
    assert "L4" in a.last_result.workflow["unmatched_requested_lines"]
    assert "identities" in a.last_result.workflow["missing_actions"]


def test_wrong_hypothetical_quantity_cannot_fulfil_requested_cost_task(tmp_path, catalog):
    s = make(tmp_path, catalog)
    script = research_script()
    script.insert(-1, [("check_availability", {"line_id": "L1", "part_key": "fixture:TEST-C100N-X7R-16V"})])
    script.insert(-1, [("compare_cost_scenarios", {"hypothetical_boards": 61})])
    a = Agent(s, ScriptedProvider(script), lambda q: None)
    a.send("TEST one versus sixty", workflow=replace(request(costs=True), max_recoveries=0))
    assert a.last_result.status == "partial" and "costs" in a.last_result.workflow["missing_actions"]
    assert a.last_result.costs is None and s._boards() == 1


def test_unitless_numeric_requirement_cannot_change_a_quoted_number(tmp_path, catalog):
    s = make(tmp_path, catalog)
    s.recorder.log("user_message", text="derating factor 1.5")
    result = s.record_requirement("design", "derating_factor", ">=", "2", user_quote="derating factor 1.5")
    assert not result["binding"]


def test_model_cannot_substitute_a_different_dielectric_in_a_real_quote(tmp_path, catalog):
    s = make(tmp_path, catalog)
    s.import_bom(BOM)
    s.recorder.log("user_message", text="Use X7R dielectric")
    result = s.record_requirement("L1", "dielectric", "==", "Y5V", user_quote="Use X7R dielectric")
    assert not result["binding"]


def test_model_reimport_keeps_identities_and_typed_quantity_is_recorded_verbatim(tmp_path, catalog):
    # Regression for a live run: qwen paraphrased the owner's "1" into a non-verbatim quote, the quantity stayed
    # unrecorded and the controller blocked every later phase, so the re-imported BOM was never matched.
    s = Session(RunRecorder.create(tmp_path / "runs"), [catalog], now=NOW)
    s.import_bom(BOM);s.match_parts()
    script = [[("import_bom", {"path": BOM})], [("find_missing_information", {})],
              [("ask_user", {"question": "How many boards will be assembled?", "gap_id": "design.board_quantity"})],
              *research_script()[2:]]
    a = Agent(s, ScriptedProvider(script), lambda q: "1")
    a.send("TEST review", workflow=request(costs=True))
    assert s.baseline.get("L1")
    quantity = s.requirements["design.board_quantity"]
    assert quantity.binding and str(quantity.value) == "1"
    assert any(e["type"] == "controller_action" and e["tool"] == "record_requirement" for e in read_events(s.recorder.path))


def test_unmatched_line_does_not_deadlock_discovery_or_checks(tmp_path, catalog):
    # Regression for a live run: discovery demanded a search on unmatched L4, which line_choices refused.
    s = make(tmp_path, catalog)
    script = [[("import_bom", {"path": BOM})], [("find_missing_information", {})], [("match_parts", {})],
              [("search_candidates", {"line_id": "L1"})],
              [("check_substitute", {"line_id": "L1", "candidate_key": GOOD})], "TEST finished"]
    a = Agent(s, ScriptedProvider(script), lambda q: None)
    a.send("TEST research", workflow=replace(request(), lines=("L1", "L4")))
    snap = a.last_result.workflow
    assert "discovery" not in snap["missing_actions"] and "checks" not in snap["missing_actions"]
    assert snap["unmatched_requested_lines"] == ["L4"] and a.last_result.status == "partial"
    assert not any(e["type"] == "controller_recovery" for e in read_events(s.recorder.path))


def test_stalled_model_cannot_block_no_input_deterministic_steps(tmp_path, catalog):
    # Regression for a live chat review: qwen answered with text only while just find_missing_information
    # was allowed, exhausted recoveries and the chat still reported a recorded review.
    s = make(tmp_path, catalog)
    a = Agent(s, ScriptedProvider([[("import_bom", {"path": BOM})]] + ["TEST stalled"] * 8), lambda q: None)
    a.send("TEST", workflow=replace(request(), max_recoveries=2))
    actions = [e["tool"] for e in read_events(s.recorder.path) if e["type"] == "controller_action"]
    assert actions[:2] == ["find_missing_information", "match_parts"]
    assert a.last_result.status == "partial" and "discovery" in a.last_result.workflow["missing_actions"]
