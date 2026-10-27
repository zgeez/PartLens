import json

import pytest

from partlens.agent import Agent, ScriptedProvider
from partlens.evaluation import evaluate_run
from partlens.records import RunRecorder, read_events
from partlens.session import Session
from partlens.ui import ReviewApp, review_snapshot


def test_ui_snapshot_keeps_unverified_cost_and_no_fake_explanation(tmp_path, catalog):
    s = Session(RunRecorder.create(tmp_path), [catalog])
    s.import_bom("tests/fixtures/bom_kicad.csv")
    s.match_parts()
    view = review_snapshot(s)
    assert len(view["Parts"]["lines"]) > 0 and view["Evidence"]
    assert view["Explanation"] == "" and "note" in view["Cost"]
    assert view["Qualifications"] == []  # importing data cannot qualify a replacement


def test_question_failure_is_preserved_without_invented_answer(tmp_path):
    def cancel(question):
        raise EOFError("TEST cancelled")
    s = Session(RunRecorder.create(tmp_path), [])
    a = Agent(s, ScriptedProvider([[("ask_user", {"question": "TEST quantity?"})]]), cancel)
    with pytest.raises(EOFError):
        a.send("TEST request")
    events = read_events(s.recorder.path)
    assert events[-1]["name"] == "ask_user" and events[-1]["error"]
    assert len(s.recorder.user_messages()) == 1


def test_outcome_evaluation_does_not_call_failed_setup_a_live_success(tmp_path):
    rec = RunRecorder.create(tmp_path)
    rec.log("baseline_setup", requested_model="claude-opus-5-5", fallback_enabled=False)
    rec.log("setup_error", message="TEST missing credentials")
    report = evaluate_run(rec.path)
    assert report["requested_model"] == "claude-opus-5-5"
    assert not report["baseline_model_confirmed"] and not report["automated_outcomes_met"]
    assert report["failures"]


def test_single_digit_quantity_has_verbatim_provenance(tmp_path):
    s = Session(RunRecorder.create(tmp_path), [])
    s.recorder.log("user_message", text="5")
    assert s.record_requirement("design", "board_quantity", "==", "5", user_quote="5")["binding"]


def test_ui_routes_bom_name_as_a_tool_argument(tmp_path, catalog):
    app = ReviewApp.__new__(ReviewApp)
    app.session = Session(RunRecorder.create(tmp_path), [catalog])
    app.agent = None
    result = app.tool("import_bom", path="tests/fixtures/bom_kicad.csv", name="TEST-design")
    assert result["design"] == "TEST-design"


def test_programmatic_task_prompt_cannot_confirm_owner_quantity(tmp_path):
    s = Session(RunRecorder.create(tmp_path), [])
    s.recorder.log("user_message", text="TEST task mentions 60 boards", origin="baseline_task")
    assert not s.record_requirement("design", "board_quantity", "==", "60", user_quote="60 boards")["binding"]


@pytest.mark.parametrize("path", ["experiments/secret.csv", "sample/benchmark.csv", "private-badge.csv"])
def test_excluded_material_is_rejected_before_file_access(tmp_path, path):
    s = Session(RunRecorder.create(tmp_path), [])
    with pytest.raises(ValueError, match="excluded"):
        s.import_bom(path)
