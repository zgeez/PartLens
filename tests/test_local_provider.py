"""Synthetic protocol checks; actual local-model evaluations are separate run records."""

import pytest

from partlens.agent import Agent, AnthropicProvider, ModelMismatch, provider_from_env
from partlens.evaluation import evaluate_run
from partlens.local_provider import LocalProviderError, OllamaProvider
from partlens.records import RunRecorder, read_events
from partlens.session import Session
from partlens.tools import run_tool
from partlens.workflow import WorkflowRequest


@pytest.fixture
def local(monkeypatch):
    monkeypatch.setenv("PARTLENS_LOCAL_MODEL", "TEST-local:8b")
    monkeypatch.setenv("PARTLENS_LOCAL_URL", "http://127.0.0.1:11434")
    provider = OllamaProvider()
    requests = []
    response = {"model": provider.model, "done": True, "done_reason": "stop",
                "message": {"role": "assistant", "content": "TEST completion"},
                "prompt_eval_count": 100, "eval_count": 10}

    def request(path, payload=None):
        requests.append((path, payload))
        if path == "/api/tags":
            return {"models": [{"name": provider.model, "digest": "TEST-digest"}]}
        if path == "/api/show":
            return {"capabilities": ["completion", "tools"], "details": {"quantization_level": "TEST-Q4"}}
        return response
    monkeypatch.setattr(provider, "_request", request)
    return provider, requests, response


def test_factory_defaults_to_local_without_anthropic_sdk_or_key(monkeypatch):
    monkeypatch.delenv("PARTLENS_LLM_PROVIDER", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.setattr(AnthropicProvider, "__init__", lambda *a, **kw: pytest.fail("paid provider constructed"))
    assert isinstance(provider_from_env(), OllamaProvider)


@pytest.mark.parametrize("name,args", [("match_parts", {"design": "TEST"}),
                                       ("check_substitute", {"line_id": "TEST-L1"}),
                                       ("compare_cost_scenarios", {"hypothetical_boards": True})])
def test_tool_schema_errors_are_actionable_before_dispatch(name, args):
    from partlens.session import ToolError
    with pytest.raises(ToolError, match="Allowed arguments"):
        run_tool(None, name, args)


def test_cloud_default_is_sonnet(monkeypatch):
    monkeypatch.setenv("PARTLENS_ALLOW_PAID_INFERENCE", "owner_authorized")
    anthropic = pytest.importorskip("anthropic")
    monkeypatch.setattr(anthropic, "Anthropic", lambda **kw: None)
    monkeypatch.delenv("PARTLENS_ANTHROPIC_MODEL", raising=False)
    assert AnthropicProvider().model == "claude-sonnet-5-5"


@pytest.mark.parametrize("url", ["https://api.example.test", "http://127.0.0.1:11434/path",
                                      "http://secret@localhost:11434", "http://192.168.1.5:11434"])
def test_local_mode_refuses_remote_or_credentialed_origins(url):
    with pytest.raises(ValueError):
        OllamaProvider(base_url=url)


def test_cloud_tag_refused():
    with pytest.raises(ValueError):
        OllamaProvider(model="TEST-model:cloud")


def test_native_tools_and_results_round_trip(local):
    provider, requests, response = local
    response["message"] = {"role": "assistant", "content": "", "tool_calls": [
        {"function": {"name": "describe_design", "arguments": {}}}]}
    turn = provider.next_turn("TEST system", [{"role": "user", "content": "TEST user"}], [
        {"name": "describe_design", "description": "TEST", "input_schema": {"type": "object"}}])
    assert turn.stop_reason == "tool_use" and len(turn.tool_calls) == 1
    call = turn.tool_calls[0]
    provider.next_turn("TEST system", [{"role": "assistant", "content": turn.assistant_content},
        {"role": "user", "content": [{"type": "tool_result", "tool_use_id": call.id,
                                       "content": '{"error":"TEST failure"}', "is_error": True}]}], [])
    payload = requests[-1][1]
    assert payload["messages"][-1] == {"role": "tool", "tool_name": "describe_design",
                                       "content": '{"error":"TEST failure"}'}
    assert payload["think"] is False and payload["stream"] is False
    assert turn.usage["local_model"]["digest"] == "TEST-digest"
    assert turn.usage["fallback_enabled"] is False


@pytest.mark.parametrize("case", ["wrong_model", "malformed_arguments", "incomplete"])
def test_invalid_response_cannot_execute_tools(local, tmp_path, case):
    provider, _, response = local
    response["message"]["tool_calls"] = [{"function": {"name": "describe_design", "arguments": {}}}]
    if case == "wrong_model":
        response["model"] = "TEST-other"
    elif case == "malformed_arguments":
        response["message"]["tool_calls"][0]["function"]["arguments"] = "{}"
    else:
        response["done"] = False
    session = Session(RunRecorder.create(tmp_path), [])
    agent = Agent(session, provider, lambda q: pytest.fail("unexpected question"))
    text = agent.send("TEST request", workflow=WorkflowRequest("tests/fixtures/bom_kicad.csv"))
    assert "partial" in text
    assert any(e["type"] == "provider_error" for e in read_events(session.recorder.path))
    assert not any(e["type"] == "tool_call" for e in read_events(session.recorder.path))


def test_truncated_tool_request_never_executes(local):
    provider, _, response = local
    response["done_reason"] = "length"
    response["message"]["tool_calls"] = [{"function": {"name": "describe_design", "arguments": {}}}]
    turn = provider.next_turn("TEST", [], [])
    assert turn.stop_reason == "length" and not turn.tool_calls


def test_exhausted_context_never_executes_tools(local):
    provider, _, response = local
    response["prompt_eval_count"] = provider.context
    response["message"]["tool_calls"] = [{"function": {"name": "describe_design", "arguments": {}}}]
    with pytest.raises(LocalProviderError, match="context budget"):
        provider.next_turn("TEST", [], [])


def test_local_tool_capability_and_remote_model_fail_closed(local, monkeypatch):
    provider, _, _ = local
    for info in ({"capabilities": ["completion"]},
                 {"capabilities": ["tools"], "remote_host": "https://example.test"}):
        monkeypatch.setattr(provider, "_request", lambda path, payload=None: info if path == "/api/show" else
                            {"models": [{"name": provider.model, "digest": "TEST-digest"}]})
        with pytest.raises(LocalProviderError):
            provider.next_turn("TEST", [], [])


def test_evaluation_uses_requested_model_and_incomplete_is_failure(tmp_path):
    rec = RunRecorder.create(tmp_path)
    rec.log("agent_start", provider="ollama:TEST-local", requested_model="TEST-local", fallback_enabled=False)
    rec.log("assistant_turn", text="TEST", usage={"model": "TEST-local"})
    assert evaluate_run(rec.path)["baseline_model_confirmed"]
    rec.log("agent_incomplete", reason="length")
    assert evaluate_run(rec.path)["failures"]
    rec.log("assistant_turn", text="TEST", usage={"model": "TEST-other"})
    assert not evaluate_run(rec.path)["baseline_model_confirmed"]


def test_recall_without_current_check_cannot_pass_reverification(tmp_path):
    prior = RunRecorder.create(tmp_path)
    prior.log("tool_call", name="check_substitute", error=None,
              output={"stored_in_memory": "TEST-mem", "status": "rejected", "checks": []})
    rec = RunRecorder.create(tmp_path)
    rec.log("agent_start", provider="ollama:TEST", requested_model="TEST", fallback_enabled=False)
    rec.log("tool_call", name="recall_decisions", error=None,
            output={"memories": [{"id": "TEST-mem", "source": "TEST-source"}]})
    rec.log("assistant_turn", text="TEST recalled", tool_calls=[], stop_reason="end_turn", usage={"model": "TEST"})
    result = evaluate_run(rec.path, prior_path=prior.path)
    assert result["criteria"]["recalled_first_session_decision"]
    assert not result["criteria"]["recalled_pair_rechecked"]


def test_partial_model_commentary_is_not_a_final_explanation(tmp_path):
    rec = RunRecorder.create(tmp_path)
    rec.log("assistant_turn", text="TEST I will investigate", stop_reason="tool_use",
            tool_calls=[{"name": "get_part"}])
    assert not evaluate_run(rec.path)["criteria"]["explanation_present"]


def test_live_demo_cli_rejects_recall_without_reverification(monkeypatch):
    from types import SimpleNamespace
    from partlens import cli, demo
    reports = [{"automated_outcomes_met": True, "baseline_model_confirmed": True, "failures": []},
               {"criteria": {"recalled_first_session_decision": True, "recalled_pair_rechecked": False},
                "baseline_model_confirmed": True, "failures": []}]
    monkeypatch.setattr(demo, "run_live_demo", lambda *a, **kw: reports)
    monkeypatch.setattr(cli, "catalogs_from_args", lambda args: [])
    with pytest.raises(SystemExit) as error:
        cli.cmd_live_demo(SimpleNamespace(fees=None))
    assert error.value.code == 1
