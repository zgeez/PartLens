"""Synthetic sources and from-scratch requirements only; no private designs or supplier snapshots."""

from dataclasses import replace
from decimal import Decimal
import json

import pytest

from partlens.core.model import CheckStatus
from partlens.design.architecture import propose
from partlens.design.patterns import PATTERNS, Role
from partlens.design.requirements import Requirements, State, parse
from partlens.design.session import DesignSession
from partlens.records import RunRecorder
from partlens.session import ToolError
from partlens.sources.catalog import LocalCatalog

IDEA="Design a rechargeable smart display with Bluetooth phone control, an LED matrix, NFC, microphone and IMU."
DEFAULTS={"led_rows":"8","led_columns":"8","led_type":"mono","nfc_mode":"tag",
          "microphone_use":"sound_reactive","logic_voltage":"3.3V","battery_min":"3.0V",
          "battery_max":"4.2V","battery_capacity":"500mAh","runtime":"4h","board_quantity":"1",
          "width":"50mm","height":"50mm","led_average_current":"3.2mA","charging_use":"off_while_charging"}
SELECTED={p.block:p.id for p in PATTERNS.values()}


def spec():
    s=Requirements("TEST-design",IDEA,"user:TEST#seq1")
    for k,v in DEFAULTS.items():s.record(k,v,source="TEST-agent")
    return s


def test_incomplete_description_has_decision_relevant_gaps_and_feature_provenance():
    s=Requirements("TEST",IDEA,"user:TEST#seq1")
    assert {g['id'] for g in s.gaps()} >= {'led_rows','led_columns','led_type','nfc_mode','microphone_use','runtime','board_quantity'}
    assert s.features==['ble','led_matrix','nfc','microphone','imu','rechargeable']
    assert all(g['state']=='unanswered' for g in s.gaps())


@pytest.mark.parametrize('parameter,value',[
    ('logic_voltage','3.3'),('logic_voltage','3.3mA'),('runtime','4'),('battery_capacity','0mAh'),
    ('led_rows','8mm'),('board_quantity','1.5'),('width','NaNmm'),('battery_min','-1V')])
def test_units_and_finite_positive_counts_are_enforced(parameter,value):
    with pytest.raises(ValueError):parse(parameter,value)


def test_delegation_is_not_confirmation_and_conflicting_requirements_keep_history():
    s=spec()
    assert all(not e.binding and e.state is State.INFERRED for e in s.entries)
    s.record('board_quantity','10',source='user:TEST#2',quote='10',confirmed=True)
    assert s.current['board_quantity'].binding
    s.record('board_quantity','20',source='user:TEST#3',quote='20',confirmed=True)
    assert s.current['board_quantity'].state is State.CONFLICTING and s.get('board_quantity') is None
    assert len([e for e in s.entries if e.parameter=='board_quantity'])==3
    s.record('board_quantity','1',source='TEST-agent',replace=True)
    assert not s.current['board_quantity'].binding


def test_model_cannot_turn_an_unrelated_quote_into_a_number():
    s=Requirements('TEST',IDEA,'user:TEST#1')
    assert not s.record('battery_capacity','500mAh',source='user:TEST#2',quote='define your own',confirmed=True).binding


def test_architecture_checks_domains_channels_power_and_unknown_clocks():
    s=spec(); circuit=propose(s,SELECTED)
    by_name={c.check:c for c in circuit.checks}
    assert by_name['voltage.controller'].status is CheckStatus.PASS
    assert by_name['led.capacity'].status is CheckStatus.PASS
    assert by_name['power.design_budget'].status is CheckStatus.FAIL
    assert by_name['power.runtime'].status is CheckStatus.UNVERIFIED
    assert by_name['clock.contracts'].status is CheckStatus.UNVERIFIED
    assert by_name['i2c.addresses'].status is CheckStatus.UNVERIFIED
    s.record('logic_voltage','5V',source='TEST',replace=True)
    assert next(c for c in propose(s,SELECTED).checks if c.check=='voltage.controller').status is CheckStatus.FAIL
    s.record('led_columns','32',source='TEST',replace=True)
    assert next(c for c in propose(s,SELECTED).checks if c.check=='led.capacity').status is CheckStatus.FAIL


def test_insufficient_gpio_and_i2c_address_conflict_fail(monkeypatch):
    monkeypatch.setitem(PATTERNS,'ble.esp32c3_mini',replace(PATTERNS['ble.esp32c3_mini'],gpio_pins=('GPIO0',)))
    for pid in ('imu.lsm6dso','led.is31fl3731'):
        monkeypatch.setitem(PATTERNS,pid,replace(PATTERNS[pid],addresses=(0x40,)))
    checks={c.check:c for c in propose(spec(),SELECTED).checks}
    assert checks['mcu.gpio_budget'].status is CheckStatus.FAIL
    assert checks['i2c.addresses'].status is CheckStatus.FAIL


def test_missing_pattern_evidence_never_passes(monkeypatch):
    monkeypatch.setitem(PATTERNS,'imu.lsm6dso',replace(PATTERNS['imu.lsm6dso'],reviewed=False,reference=''))
    checks={c.check:c for c in propose(spec(),SELECTED).checks}
    assert checks['pattern.imu'].status is CheckStatus.UNVERIFIED
    assert checks['voltage.imu'].status is CheckStatus.UNVERIFIED


def session(tmp_path,catalogs=()):
    return DesignSession(RunRecorder.create(tmp_path/'runs'),list(catalogs),description=IDEA,design_id='TEST-design')


def populate(s):
    s.start_new_design()
    for key,value in DEFAULTS.items():s.record_design_requirement(key,value)
    s.propose_design_architecture(json.dumps(SELECTED))
    return s.generate_design_bom()


def test_generated_bom_is_not_an_import_and_includes_support_and_unresolved_lines(tmp_path):
    s=session(tmp_path); out=populate(s)
    assert out['origin']=='generated_from_patterns' and not out['imported_bom'] and not out['manufacturing_ready']
    roles={r.role.name:r for r in s.circuit.roles}
    assert roles['led_elements'].role.quantity==64
    assert {'enable_pullup','inductor','charge_program','protection_fets','antenna','programming_header'} <= set(roles)
    assert roles['protection_fets'].role.quantity==2
    assert all(c['pin'] is None for n in s.circuit.connections for c in n['endpoints'])
    refs=[ref for row in s.circuit.roles for ref in row.refs]
    assert len(refs)==len(set(refs))
    assert not s.requirements and s._boards() is None  # no Easyduino quantity transfer


def test_unavailable_identity_footprint_and_prices_stay_unknown(tmp_path):
    s=session(tmp_path);populate(s)
    s.source_design_roles();out=s.qualify_design();cost=s.design_cost_scenarios()
    assert all(q['status']=='unverified' for q in out['qualifications'])
    assert all(not r['cost']['component_complete'] and r['cost']['total']=='n/a' for r in cost['scenarios'])
    assert cost['scenarios'][0]['scenario']=='provisional_hypothetical'
    assert not s.design_report()['manufacturing_ready']


def test_revision_invalidates_current_results_and_rejects_old_context(tmp_path):
    s=session(tmp_path);populate(s);s.source_design_roles();s.qualify_design();s.design_cost_scenarios()
    old=s._memory_context()
    s.record_design_requirement('led_columns','16',action='replace')
    assert s.bom is None and s.circuit is None and not s.decisions and not s.qualifications and s.costs is None
    s.propose_design_architecture(json.dumps(SELECTED));s.generate_design_bom()
    assert s._memory_context()!=old
    with pytest.raises(ToolError):s.restore_quantity('TEST-never-read.jsonl')


def test_confirmation_uses_the_existing_session_provenance_gate(tmp_path):
    s=session(tmp_path)
    s.recorder.log('user_message',text='Build 5 boards',origin='user')
    out=s.record_design_requirement('board_quantity','5',user_quote='Build 5 boards')
    assert out['entry']['binding'] and s._boards()==5
    s.record_design_requirement('runtime','4h',user_quote='Build 5 boards')
    assert not s.spec.current['runtime'].binding
    s.recorder.log('user_message',text='8',origin='design_evaluation_task')
    assert not s.record_design_requirement('board_quantity','8',user_quote='8')['entry']['binding']


def test_existing_compatibility_engine_qualifies_only_evidenced_synthetic_role(tmp_path,catalog,monkeypatch):
    part=catalog.get('fixture:TEST-C100N-X7R-16V')
    role=Role('TEST-cap','C',1,'capacitor','100nF','0402',part.manufacturer,part.mpn,('TEST-C100N-X7R-16V',),
              (('capacitance','100nF'),('voltage_rating','16V'),('dielectric','X7R'),('tolerance_pct','10%')),
              reference='fixture://TEST-manufacturer-reviewed')
    monkeypatch.setitem(PATTERNS,'debug.uart',replace(PATTERNS['debug.uart'],roles=(role,)))
    catalog.bom_supplier='fixture'
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[catalog],description='A TEST indicator',design_id='TEST-design')
    s.start_new_design();s.record_design_requirement('board_quantity','1')
    s.propose_design_architecture(json.dumps({'debug':'debug.uart'}));s.generate_design_bom()
    s.source_design_roles();out=s.qualify_design()['qualifications'][0]
    assert out['status']=='verified' and all(c['evidence'] for c in out['checks'])
    assert out['application_status']=='unverified' and not s.design_report()['manufacturing_ready']


def test_batch_validates_all_inputs_before_mutation(tmp_path):
    s=session(tmp_path)
    with pytest.raises(ToolError):
        s.record_design_requirements(json.dumps([{'parameter':'led_rows','value':'8'},
                                                {'parameter':'board_quantity','value':'0'}]))
    assert not s.spec.entries
    s.record_design_requirements(json.dumps([{'parameter':'led_rows','value':'8'},
                                            {'parameter':'board_quantity','value':'1'}]))
    assert s.spec.get('led_rows')==8 and s.spec.get('board_quantity')==1 and s._boards() is None


def test_generation_cannot_drop_required_support_components(tmp_path):
    s=session(tmp_path)
    for k,v in DEFAULTS.items():s.record_design_requirement(k,v)
    s.propose_design_architecture(json.dumps(SELECTED))
    s.circuit.roles=[r for r in s.circuit.roles if r.role.name!='inductor']
    with pytest.raises(ToolError,match='support roles'):
        s.generate_design_bom()


def test_delegation_and_revision_budget_do_not_hide_failed_engineering(tmp_path):
    from partlens.design.agent import DesignAgent
    from partlens.agent import ScriptedProvider
    s=session(tmp_path);populate(s)
    agent=DesignAgent(s,ScriptedProvider([]),lambda q:None,allow_proposals=True)
    agent.requirements_seen=True;agent.patterns_seen=True;agent.design_cycles=2
    assert 'ask_user' not in agent.permitted()
    assert agent.permitted()=={'source_design_roles'}
    assert any(c.check=='power.design_budget' and c.status is CheckStatus.FAIL for c in s.circuit.checks)


def test_new_agent_budget_uses_provider_input_output_keys(tmp_path):
    from partlens.agent import Turn, ToolCall
    from partlens.design.agent import DesignAgent
    class Provider:
        name='TEST-provider';count=0
        def next_turn(self,*args):
            self.count+=1
            return Turn('',[ToolCall('TEST-call','start_new_design',{})],[],'tool_use',{'input':25,'output':10})
    p=Provider();agent=DesignAgent(session(tmp_path),p,lambda q:None,allow_proposals=True,max_total_tokens=1)
    text=agent.send('TEST task')
    assert p.count==1 and agent.last_report['controller']['total_tokens']==35
    assert agent.last_report['controller']['stop_reason']=='token budget'
    assert 'no BOM generated' in text and not agent.last_report['bom_origin']


def test_new_design_source_observations_replay_without_an_import(tmp_path):
    from partlens.agent import Agent, ScriptedProvider, ToolCall
    from partlens.sources.audit import AuditedCatalog
    from partlens.replay import replay
    rec=RunRecorder.create(tmp_path/'runs')
    s=DesignSession(rec,[AuditedCatalog(LocalCatalog([],name='TEST-empty'))],description=IDEA,design_id='TEST-new')
    a=Agent(s,ScriptedProvider([]),lambda q:None)
    def call(name,**args):
        out=a._execute(ToolCall('TEST-'+str(rec.seq),name,args))
        assert not out.get('is_error'),out
    call('start_new_design');call('record_design_requirements',requirements_json=json.dumps([
        {'parameter':k,'value':v} for k,v in DEFAULTS.items()]))
    call('propose_design_architecture',selections_json=json.dumps(SELECTED))
    call('generate_design_bom');call('source_design_roles');call('qualify_design');call('design_cost_scenarios')
    out=replay(rec.path)
    assert out.ok and out.matched==out.replayed==7


def test_real_hmem_recall_rechecks_changed_new_design_requirements(tmp_path,catalog,monkeypatch):
    from copy import deepcopy
    from partlens.memory.hmem import HMemBridge,DecisionMemory,HMemError
    part=catalog.get('fixture:TEST-C100N-X7R-16V');catalog.bom_supplier='fixture'
    role=Role('TEST-cap','C',1,'capacitor','100nF','0402',part.manufacturer,part.mpn,('TEST-C100N-X7R-16V',),
              (('capacitance','100nF'),('voltage_rating','16V'),('dielectric','X7R'),('tolerance_pct','10%')),
              reference='fixture://TEST-manufacturer-reviewed')
    monkeypatch.setitem(PATTERNS,'debug.uart',replace(PATTERNS['debug.uart'],roles=(role,)))
    store=tmp_path/'hmem'
    try:bridge=HMemBridge(store)
    except HMemError as exc:pytest.skip(str(exc))
    with bridge:
        a=DesignSession(RunRecorder.create(tmp_path/'a'),[catalog],description='A TEST indicator',design_id='TEST-new',
                        memory=DecisionMemory(bridge,'TEST-new'))
        a.start_new_design();a.record_design_requirement('board_quantity','1')
        a.propose_design_architecture(json.dumps({'debug':'debug.uart'}));a.generate_design_bom()
        a.source_design_roles();a.qualify_design();stored=a.remember_design()
        assert len(stored['stored'])==1
    with HMemBridge(store) as cold:
        b=DesignSession(RunRecorder.create(tmp_path/'b'),[catalog],description='A TEST indicator',design_id='TEST-new',
                        memory=DecisionMemory(cold,'TEST-new'))
        b.spec=deepcopy(a.spec)
        b.propose_design_architecture(json.dumps({'debug':'debug.uart'}));b.generate_design_bom()
        assert b.reverify_design(a.recorder.run_id)['comparisons'][0]['outcome']=='unchanged'
        b.record_design_requirement('board_quantity','2',action='replace')
        assert not b.qualifications and b.bom is None
        b.propose_design_architecture(json.dumps({'debug':'debug.uart'}));b.generate_design_bom()
        check=b.reverify_design(a.recorder.run_id)['comparisons'][0]
        assert check['outcome']=='changed_context' and check['fresh_checks_executed']


def test_snapshot_restoration_validates_original_confirmation_and_typed_values(tmp_path):
    from copy import deepcopy
    from partlens.agent import Agent,ScriptedProvider,ToolCall
    from partlens.design.restore import restore_requirements
    from partlens.records import read_events
    s=session(tmp_path)
    s.recorder.log('user_message',text='5 boards',origin='user')
    a=Agent(s,ScriptedProvider([]),lambda q:None)
    a._execute(ToolCall('TEST-confirm','record_design_requirement',{'parameter':'board_quantity','value':'5','user_quote':'5 boards'}))
    snapshot=s.design_requirements();events=read_events(s.recorder.path)
    restored=restore_requirements(snapshot,events)
    assert restored.current['board_quantity'].binding and restored.view()==s.spec.view()
    corrupt=deepcopy(snapshot);corrupt['history'][0]['value']=50
    with pytest.raises(ValueError,match='original successful'):
        restore_requirements(corrupt,events)


def test_new_design_cancellation_stops_before_inference(tmp_path):
    from partlens.agent import ScriptedProvider
    from partlens.design.agent import DesignAgent
    a=DesignAgent(session(tmp_path),ScriptedProvider([]),lambda q:None,should_stop=lambda:True)
    a.send('TEST')
    assert a.last_report['controller']['stop_reason']=='cancelled by operator'


def test_charge_setpoint_and_optimistic_runtime_fail_without_inventing_cell_qualification():
    s=spec()
    checks={c.check:c for c in propose(s,SELECTED).checks}
    assert checks['charging.setpoint'].status is CheckStatus.UNVERIFIED
    assert checks['power.runtime_bound'].status is CheckStatus.FAIL
    assert checks['power.runtime_bound'].evidence
    s.record('battery_max','3.6V',source='TEST',replace=True)
    checks={c.check:c for c in propose(s,SELECTED).checks}
    assert checks['charging.setpoint'].status is CheckStatus.FAIL
    assert checks['charging.setpoint'].evidence
    s.record('runtime','0.1h',source='TEST',replace=True)
    checks={c.check:c for c in propose(s,SELECTED).checks}
    assert checks['power.runtime_bound'].status is CheckStatus.UNVERIFIED  # sufficient bound is no runtime proof


def test_requested_controller_recall_runs_before_forced_workflow_phase(tmp_path,monkeypatch):
    from partlens.agent import ScriptedProvider
    from partlens.design.agent import DesignAgent
    s=session(tmp_path);populate(s)
    a=DesignAgent(s,ScriptedProvider([]),lambda q:None,allow_proposals=True,max_steps=1)
    a.requirements_seen=a.patterns_seen=True;a.design_cycles=2
    operations=[]
    monkeypatch.setattr(s,'recall_design',lambda run_id: operations.append('recall') or {'memories':[]})
    monkeypatch.setattr(s,'reverify_design',lambda run_id: operations.append('reverify') or {'comparisons':[]})
    a.send('TEST recall',recall_run='TEST-prior')
    assert operations==['recall','reverify']


def test_same_mpn_from_another_manufacturer_cannot_inherit_reference_evidence(tmp_path,catalog,monkeypatch):
    part=catalog.get('fixture:TEST-C100N-X7R-16V');catalog.bom_supplier='fixture'
    role=Role('TEST-cap','C',1,'capacitor','100nF','0402','TEST-other-manufacturer',part.mpn,
              ('TEST-C100N-X7R-16V',),reference='fixture://TEST-other-manufacturer-datasheet')
    monkeypatch.setitem(PATTERNS,'debug.uart',replace(PATTERNS['debug.uart'],roles=(role,)))
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[catalog],description='A TEST indicator',design_id='TEST')
    s.propose_design_architecture(json.dumps({'debug':'debug.uart'}));s.generate_design_bom()
    row=s.source_design_roles()['rows'][0]
    assert row['observations'] and row['selected'] is None
    assert s.qualify_design()['qualifications'][0]['status']=='unverified'
