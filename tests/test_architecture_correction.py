"""Synthetic-only regressions for iteration, target protection and honest acceptance gates."""
import json
from copy import deepcopy
from dataclasses import replace

import pytest

from partlens.design.session import DesignSession
from partlens.design.validation import validate,MODULE_PINS,acceptance
from partlens.design.patterns import PATTERNS,required_blocks
from partlens.design.requirements import Requirements
from partlens.design.ui import presentation
from partlens.design.agent import render,DesignAgent
from partlens.agent import ScriptedProvider
from partlens.records import RunRecorder
from partlens.session import ToolError

IDEA='A rechargeable Bluetooth LED matrix with NFC, microphone and IMU'
VALUES={'led_rows':'8','led_columns':'8','led_type':'mono','nfc_mode':'tag','microphone_use':'sound_reactive',
    'logic_voltage':'3.3V','battery_min':'3.0V','battery_max':'4.2V','battery_capacity':'500mAh',
    'runtime':'6h','board_quantity':'10','led_average_current':'3mA','charging_use':'off_while_charging'}


def make(tmp_path,idea=IDEA):
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[],description=idea,design_id='TEST-correction',engineering_mode=True)
    for k,v in VALUES.items():s.record_design_requirement(k,v)
    needed=required_blocks(s.spec.features)
    s.propose_design_architecture(json.dumps({p.block:p.id for p in PATTERNS.values() if p.block in needed}))
    return s


def test_recorded_failure_gets_real_alternative_without_changing_inputs(tmp_path):
    s=make(tmp_path);fingerprint=s.spec.fingerprint
    before=s.circuit.fingerprint
    out=s.compare_design_alternatives()
    alternative=next(a for a in out['alternatives'] if 'power.design_budget' in a['resolved_failures'])
    assert alternative['acceptance']['accepted'] is False
    assert 'power.runtime_bound' in alternative['failed_constraints']
    assert out['energy_remedies'][0]['minimum_ideal_LED_only_capacity_mAh']=='905.1428571428571428571428571'
    s.generate_design_bom();s.source_design_roles();s.qualify_design();s.design_cost_scenarios()
    s.investigate_design_alternative(alternative['id'])
    assert s.spec.fingerprint==fingerprint and s.circuit.fingerprint!=before
    assert s.bom is None and not s.qualifications and not s.decisions and s.costs is None
    assert s.design_history and 'power.design_budget' in [c['check'] for c in s.design_history[-1]['circuit']['checks'] if c['status']=='fail']
    checks={c.check:c.status.value for c in s.circuit.checks}
    assert checks['power.design_budget']=='pass' and checks['power.runtime_bound']=='fail'
    assert not s.design_report()['acceptance']['accepted']


@pytest.mark.parametrize('parameter,value',[('runtime','1h'),('battery_capacity','5000mAh'),('led_average_current','0.1mA'),('led_rows','1')])
def test_model_cannot_arbitrarily_change_targets_to_clear_failure(tmp_path,parameter,value):
    s=make(tmp_path);before=s.spec.fingerprint
    with pytest.raises(ToolError,match='actual user answer'):
        s.record_design_requirement(parameter,value,action='replace',rationale='make the failing constraint pass')
    assert s.spec.fingerprint==before and s.circuit


def test_actual_new_answer_revises_and_invalidates_with_provenance(tmp_path):
    s=make(tmp_path);s.generate_design_bom();s.source_design_roles();s.qualify_design()
    s.recorder.log('user_message',text='Make the runtime 8h',origin='user')
    out=s.record_design_requirement('runtime','8h',user_quote='Make the runtime 8h',action='replace')
    assert out['entry']['binding'] and s.bom is None and s.circuit is None and not s.qualifications
    assert s.architecture_alternatives is None and s.design_history
    with pytest.raises(ToolError):s.record_design_requirement('runtime','1h',action='replace')


def test_stale_or_non_improving_alternative_cannot_be_adopted(tmp_path):
    s=make(tmp_path);out=s.compare_design_alternatives()
    with pytest.raises(ToolError,match='change an architecture'):
        s.investigate_design_alternative(out['alternatives'][0]['id'])
    better=out['alternatives'][1]['id']
    s.recorder.log('user_message',text='Make the runtime 8h',origin='user')
    s.record_design_requirement('runtime','8h',user_quote='Make the runtime 8h',action='replace')
    with pytest.raises(ToolError,match='compare alternatives'):
        s.investigate_design_alternative(better)


def test_sourced_support_choices_do_not_hide_unknown_safety_or_connectivity(tmp_path):
    s=make(tmp_path);s.generate_design_bom()
    roles={r.role.name:r.role for r in s.circuit.roles}
    assert roles['input_bypass'].mpn=='CL10A475KO8NNNC'
    assert roles['enable_delay'].mpn=='CL05A105KA5NQNC'
    delay=next(row for row in s.circuit.roles if row.role.name=='enable_delay')
    assert s._reference(delay).params['capacitance'].evidence.retrieved_at=='2026-10-24'
    assert not roles['cell'].mpn and not roles['charge_program'].mpn
    assert roles['i2c_sda_pullup'].nets==('3V3','I2C_SDA')
    assert roles['i2c_scl_pullup'].nets==('3V3','I2C_SCL')
    for row in s.circuit.roles:
        for ref in row.refs:
            observed={net['net'] for net in s.circuit.connections if any(p['reference']==ref for p in net['endpoints'])}
            assert observed==set(row.role.nets)
    assert all(p['pin'] is None for n in s.circuit.connections for p in n['endpoints'])
    assert not s.design_report()['acceptance']['accepted']


def test_temperature_product_has_its_own_feature_and_no_matrix(tmp_path):
    s=make(tmp_path,'A rechargeable Bluetooth temperature monitor')
    choices={p.block:p.id for p in PATTERNS.values() if p.block in required_blocks(s.spec.features)}
    choices['temperature']='temperature.tmp117'
    s.propose_design_architecture(json.dumps(choices));s.generate_design_bom()
    assert 'temperature' in s.spec.features and 'led_matrix' not in s.spec.features
    roles={r.role.name for r in s.circuit.roles}
    assert {'sensor','local_bypass','i2c_sda_pullup','i2c_scl_pullup'}<=roles
    assert 'led_elements' not in roles
    checks={c.check:c.status.value for c in s.circuit.checks}
    assert checks['power.runtime_bound']=='unverified' and checks['temperature.interface']=='unverified'


def test_module_pin_check_rejects_alias_and_reserved_or_duplicate_gpio(tmp_path):
    s=make(tmp_path)
    assert MODULE_PINS['GPIO0']==12
    s.circuit.assignments={'I2C_SDA':'GPIO9','I2C_SCL':'GPIO9'}
    validate(s.spec,s.circuit)
    assert next(c for c in s.circuit.checks if c.check=='mcu.module_pin_existence').status.value=='fail'


def test_ui_and_cli_share_authoritative_checks_sources_and_explanation(tmp_path):
    s=make(tmp_path);s.generate_design_bom();s.source_design_roles();s.qualify_design();s.design_cost_scenarios()
    report=s.design_report();view=presentation(report)
    assert view['Explanation']==render(report)
    assert view['Generated BOM']==report['bom'] and view['Checks']==report['architecture']['checks']
    assert view['Sourcing']['research_history']==report['sourcing_history']
    assert view['Cost']==report['costs'] and view['Alternatives']['acceptance']==report['acceptance']


def test_controller_requires_questions_and_independent_comparison(tmp_path):
    s=make(tmp_path);a=DesignAgent(s,ScriptedProvider([]),lambda q:None,allow_proposals=True)
    s.started=True;a.requirements_seen=True;a.patterns_seen=True
    assert a.permitted()=={'ask_user','design_requirements'}
    a.questions={'runtime','board_quantity'}
    assert a.permitted()=={'compare_design_alternatives'}
    s.compare_design_alternatives();a.compared=True
    assert a.permitted()=={'investigate_design_alternative'}


def test_complete_block_selection_and_actual_monochrome_answer(tmp_path):
    s=make(tmp_path)
    with pytest.raises(ToolError,match='all required blocks'):
        s.select_design_patterns({'controller':'ble.esp32c3_mini'})
    s.recorder.log('user_message',text='Monochrome',origin='user')
    assert s.record_design_requirement('led_type','mono',user_quote='Monochrome',action='replace')['entry']['binding']
    with pytest.raises(ToolError,match='actual user answer'):
        s.record_design_requirement('led_type','rgb',action='replace')


def test_incompatible_official_candidate_stays_rejected_and_unselected(tmp_path,catalog,monkeypatch):
    from partlens.design.patterns import Role
    bad=catalog.get('fixture:TEST-C100N-X7R-6V3');catalog.bom_supplier='fixture'
    role=Role('TEST-cap','C',1,'capacitor','100nF','0402',bad.manufacturer,bad.mpn,
        ('TEST-C100N-X7R-6V3',),(('capacitance','100nF'),('voltage_rating','16V'),('dielectric','X7R'),('tolerance_pct','10%')),
        reference='fixture://TEST-independent-16V-requirement')
    monkeypatch.setitem(PATTERNS,'debug.uart',replace(PATTERNS['debug.uart'],roles=(role,)))
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[catalog],description='TEST indicator',engineering_mode=True)
    s.propose_design_architecture(json.dumps({'debug':'debug.uart'}));s.generate_design_bom()
    row=s.source_design_roles()['rows'][0]
    assert row['selected'] is None and row['candidate_evaluations'][0]['status']=='rejected'
    assert row['observations'] and s.sourcing_history[-1]['rows'][0]['candidate_evaluations']
    assert s.qualify_design()['qualifications'][0]['status']=='unverified'


def test_model_selection_is_followed_by_mandatory_controller_checks(tmp_path):
    from partlens.agent import Turn,ToolCall
    from partlens.records import read_events
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[],description=IDEA,design_id='TEST-pipeline',engineering_mode=True)
    choices={p.block:p.id for p in PATTERNS.values()}
    class Provider:
        name='TEST-synthetic-provider';count=0
        def next_turn(self,system,messages,tools):
            names={t['name'] for t in tools}
            if self.count==0:name,args='start_new_design',{}
            elif self.count==1:name,args='design_requirements',{}
            elif self.count in (2,3):name,args='ask_user',{'gap_id':'runtime' if self.count==2 else 'led_type','question':'TEST question'}
            elif self.count==4:name,args='record_design_requirements',{'requirements_json':json.dumps([{'parameter':k,'value':v} for k,v in VALUES.items()])}
            elif self.count==5:name,args='design_patterns',{}
            elif self.count==6:
                name,args='select_design_patterns',{'selections':choices}
                schema=next(t for t in tools if t['name']==name)['input_schema']['properties']['selections']
                assert set(schema['required'])==required_blocks(s.spec.features)
            elif self.count==7:name,args='compare_design_alternatives',{}
            else:
                name='investigate_design_alternative'
                args={'alternative_id':next(a['id'] for a in s.architecture_alternatives['alternatives'] if a['resolved_failures'])}
            assert name in names
            self.count+=1
            return Turn('',[ToolCall('TEST-'+str(self.count),name,args)],[],'tool_use',{'input':1,'output':1})
    provider=Provider();a=DesignAgent(s,provider,lambda q:None,allow_proposals=True)
    a.send('TEST original generic task')
    assert s.bom and s.source_attempted and s.qualification_attempted and s.costs is not None
    assert provider.count==9 and a.last_report['controller']['workflow_steps_complete']
    assert not a.last_report['acceptance']['accepted']
    final=[e['name'] for e in read_events(s.recorder.path) if e['type']=='tool_call' and e.get('actor')=='controller']
    assert final==['generate_design_bom','source_design_roles','qualify_design','design_cost_scenarios']
