"""Synthetic API responses test baseline controls; these are not live-provider evidence."""

from types import SimpleNamespace as NS

import pytest

from partlens.agent import Agent, AnthropicProvider, ModelMismatch
from partlens.records import RunRecorder, read_events
from partlens.session import Session
from partlens.workflow import WorkflowRequest


@pytest.fixture
def api(monkeypatch):
    anthropic = pytest.importorskip("anthropic")
    monkeypatch.setenv("PARTLENS_ALLOW_PAID_INFERENCE", "owner_authorized")
    monkeypatch.setenv("PARTLENS_ANTHROPIC_MODEL", "claude-opus-5-5")

    requests = []
    response = NS(id="TEST-response", model="claude-opus-5-5", stop_reason="end_turn",
                  content=[NS(type="text", text="TEST completion")],
                  usage=NS(input_tokens=10, output_tokens=3))

    def create(**kwargs):
        requests.append(kwargs)
        return response

    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: NS(beta=NS(messages=NS(create=create))))
    return requests, response


def test_baseline_omits_fallback_and_records_actual_model(api, monkeypatch):
    monkeypatch.setenv("PARTLENS_MODEL_FALLBACK", "disabled")
    provider = AnthropicProvider()
    turn = provider.next_turn("TEST", [{"role": "user", "content": "TEST"}], [])
    assert "fallbacks" not in api[0][0] and "betas" not in api[0][0]
    assert turn.usage["model"] == turn.usage["requested_model"] == "claude-opus-5-5"
    assert turn.usage["response_id"] == "TEST-response"


def test_fallback_is_opt_in_and_baseline_can_force_it_off(api, monkeypatch):
    monkeypatch.setenv("PARTLENS_MODEL_FALLBACK", "default")
    AnthropicProvider().next_turn("TEST", [], [])
    assert api[0][0]["fallbacks"] == "default"
    AnthropicProvider(fallback=False).next_turn("TEST", [], [])
    assert "fallbacks" not in api[0][1]


def test_wrong_response_model_cannot_execute_tools(api, tmp_path):
    api[1].model = "TEST-unexpected-model"
    session = Session(RunRecorder.create(tmp_path), [])
    agent = Agent(session, AnthropicProvider(fallback=False), lambda q: pytest.fail("must not ask"))
    result = agent.send("TEST request", workflow=WorkflowRequest("tests/fixtures/bom_kicad.csv"))
    assert "partial" in result
    events = read_events(session.recorder.path)
    failure = next(e for e in events if e["type"] == "provider_error")
    assert failure["actual_model"] == "TEST-unexpected-model"
    assert not any(e["type"] == "tool_call" for e in events)


def test_refusal_preserves_model_usage(api):
    api[1].stop_reason = "refusal"
    turn = AnthropicProvider().next_turn("TEST", [], [])
    assert turn.stop_reason == "refusal" and turn.usage["model"] == "claude-opus-5-5"


def test_logs_redact_secret_values_and_authorization(tmp_path, monkeypatch):
    monkeypatch.setenv("TEST_API_KEY", "TEST-super-secret")
    rec = RunRecorder.create(tmp_path)
    rec.log("test", message="TEST-super-secret Bearer abcdefghijk https://example.test?apiKey=other-secret",
            api_key="TEST-super-secret")
    text = rec.path.read_text()
    assert "TEST-super-secret" not in text and "abcdefghijk" not in text and "other-secret" not in text
    assert read_events(rec.path)[0]["api_key"] == "[REDACTED]"
