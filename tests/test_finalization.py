"""Original synthetic transport, interview and startup failure regressions."""
import json
import pytest

from partlens.agent import ToolCall
from partlens.local_provider import OllamaProvider, LocalProviderError
from partlens.preflight import run_preflight
from partlens.records import read_events
from partlens.design.interaction import clarification_plan, revise_from_owner
from tests.test_design_interaction import make
from partlens.agent import Agent, ScriptedProvider


def structured(monkeypatch, message):
    monkeypatch.setenv('PARTLENS_LOCAL_PROTOCOL', 'json-schema')
    p = OllamaProvider(model='TEST-local:8b')
    p.metadata = {'digest': 'TEST-digest'}
    requests = []
    def request(path, payload=None):
        requests.append(payload)
        return {'model': p.model, 'done': True, 'done_reason': 'stop', 'message': {
            'role': 'assistant', 'content': json.dumps(message)}, 'prompt_eval_count': 200}
    monkeypatch.setattr(p, '_request', request)
    return p, requests


def test_documented_schema_transport_never_invokes_native_parser_and_retains_results(monkeypatch):
    p, requests = structured(monkeypatch, {'text': 'TEST investigate', 'action': {'name': 'design_requirements', 'arguments': {}}})
    tools = [{'name': 'design_requirements', 'description': 'TEST', 'input_schema': {
        'type': 'object', 'properties': {}, 'required': [], 'additionalProperties': False}}]
    turn = p.next_turn('TEST', [{'role': 'user', 'content': 'TEST idea'}], tools)
    assert turn.tool_calls[0].name == 'design_requirements' and turn.usage['protocol'] == 'json-schema'
    assert 'tools' not in requests[0] and requests[0]['format']['type'] == 'object'
    p.next_turn('TEST', [{'role': 'assistant', 'content': turn.assistant_content}, {'role': 'user', 'content': [
        {'type': 'tool_result', 'tool_use_id': turn.tool_calls[0].id, 'content': '{"state":"unverified"}'}]}], tools)
    assert json.loads(requests[-1]['messages'][-1]['content']) == {
        'tool_result': 'design_requirements', 'data': '{"state":"unverified"}'}
    assert not any('tool_calls' in m or m['role']=='tool' for m in requests[-1]['messages'])


@pytest.mark.parametrize('message', [
    {'text': 'TEST', 'action': {'name': 'invented_tool', 'arguments': {}}},
    {'text': 'TEST', 'action': {'name': 'design_requirements', 'arguments': '{}'}},
    {'text': 'TEST', 'action': None, 'verified': True},
    ['TEST'],
])
def test_invalid_structured_action_never_becomes_tool_call(monkeypatch, message):
    p, _ = structured(monkeypatch, message)
    with pytest.raises(LocalProviderError, match='Invalid structured'):
        p.next_turn('TEST', [], [])


def test_no_automatic_protocol_fallback(monkeypatch):
    monkeypatch.setenv('PARTLENS_LOCAL_PROTOCOL', 'unsupported')
    with pytest.raises(ValueError, match='no automatic'):OllamaProvider(model='TEST-local:8b')


def test_preflight_attempts_every_service_and_redacts_exception_bodies(tmp_path):
    def failure():raise RuntimeError('TEST-secret-token-never-log')
    report = run_preflight(tmp_path, checks={'ollama': failure, 'jlcpcb': lambda: {'http_status': 200},
        'zetaris': failure, 'meterless': lambda: {'hello': 'TEST'}})
    assert not report['services_available'] and report['checks']['meterless']['available']
    assert not report['checks']['ollama']['available'] and 'Start loopback' in report['checks']['ollama']['action']
    assert 'TEST-secret-token' not in json.dumps(read_events(report['record']))
    assert len([e for e in read_events(report['record']) if e['type']=='service_check']) == 4


def test_led_interview_separates_count_geometry_brightness_and_electrical_drive(tmp_path):
    s = make(tmp_path)
    gaps = {g['id']:g for g in clarification_plan(s.spec)}
    assert {'led_count','led_arrangement','led_drive','brightness','led_rows','led_columns'} <= gaps.keys()
    assert '128' in gaps['led_count']['question']
    assert not s.spec.current.get('led_count')  # historical example is not silently confirmed


def test_actual_count_revision_exposes_mismatching_matrix_and_preserves_history(tmp_path):
    s = make(tmp_path)
    a = Agent(s, ScriptedProvider([]), lambda _: None)
    report = revise_from_owner(s, 'led_count', '32', a._execute)
    check = next(c for c in report['architecture']['checks'] if c['check']=='led.count_consistency')
    assert check['status']=='fail' and check['evidence']
    assert s.spec.current['led_count'].binding and s.spec.current['led_count'].quote == '32'
    assert s.spec.get('led_rows')*s.spec.get('led_columns') == 64
    assert s.design_history and not report['acceptance']['accepted']


@pytest.mark.parametrize('count,status', [('64','pass'),('32','fail')])
def test_conditional_count_check_requires_evidenced_consistency(tmp_path, count, status):
    s = make(tmp_path)
    s.record_design_requirement('led_count', count)
    from tests.test_design_generation import SELECTED
    s.propose_design_architecture(json.dumps(SELECTED))
    c = next(c for c in s.circuit.checks if c.check=='led.count_consistency')
    assert c.status.value==status and c.evidence
    assert not s.spec.current['led_count'].binding


def test_missing_dimensions_cannot_pass_count_consistency():
    from partlens.design.requirements import Requirements
    from partlens.design.architecture import propose
    s = Requirements('TEST', 'LED matrix', 'user:TEST')
    s.record('led_count', '32', source='model:TEST')
    c = propose(s, {})
    assert next(r for r in c.checks if r.check=='led.count_consistency').status.value == 'unverified'


def test_interview_cannot_repeat_requirements_read_instead_of_asking(tmp_path):
    from partlens.design.agent import DesignAgent
    from partlens.design.session import DesignSession
    from partlens.records import RunRecorder
    s = DesignSession(RunRecorder.create(tmp_path),[],description='Rechargeable LED matrix',
                      engineering_mode=True,interaction_mode=True)
    s.start_new_design()
    agent = DesignAgent(s,ScriptedProvider([]),lambda _:None,allow_proposals=True)
    agent.requirements_seen = True
    assert agent.permitted() == {'ask_user'}
    agent.questions.add('runtime')
    assert agent.permitted() == {'ask_user'}


def test_pattern_object_order_cannot_change_check_or_bus_replay(tmp_path):
    from tests.test_design_generation import SELECTED
    from partlens.design.architecture import propose
    from partlens.core.model import to_jsonable
    s = make(tmp_path)
    first = propose(s.spec,dict(SELECTED))
    second = propose(s.spec,dict(reversed(list(SELECTED.items()))))
    assert to_jsonable(first) == to_jsonable(second)
    # The append-only JSON journal sorts object keys; replay must reproduce the whole generated workflow.
    from partlens.design.session import DesignSession
    from partlens.records import RunRecorder
    from partlens.sources.catalog import LocalCatalog
    from partlens.sources.audit import AuditedCatalog
    from partlens.replay import replay
    from tests.test_design_generation import IDEA, DEFAULTS
    rec = RunRecorder.create(tmp_path/'replay-runs')
    session = DesignSession(rec,[AuditedCatalog(LocalCatalog([],name='fixture'))],description=IDEA,
                            engineering_mode=True,interaction_mode=True)
    runner = Agent(session,ScriptedProvider([]),lambda _:None)
    calls = [('start_new_design',{}),('propose_design_requirements',{'requirements':[
        {'parameter':k,'value':v} for k,v in {**DEFAULTS,'led_count':'64'}.items()]}),
        ('select_design_patterns',{'selections':dict(reversed(list(SELECTED.items())))}),
        *[(name,{}) for name in ('compare_design_alternatives','generate_design_bom','source_design_roles',
                                 'qualify_design','design_cost_scenarios')]]
    for i,(name,args) in enumerate(calls):
        result = runner._execute(ToolCall('TEST-'+str(i),name,args),actor='deterministic_reference')
        assert not result.get('is_error'), result['content']
    result = replay(rec.path,[LocalCatalog([],name='fixture')])
    assert result.ok and result.matched == len(calls)
