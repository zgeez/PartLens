"""Interaction regressions use original synthetic requirements and no external service responses."""
from decimal import Decimal
import json

import pytest

from partlens.agent import Agent,ScriptedProvider,ToolCall
from partlens.design.agent import DesignAgent
from partlens.design.cli import export
from partlens.design.interaction import clarification_plan,runtime_options,typed_answer,revise_from_owner,sourcing_triage
from partlens.design.requirements import Requirements
from partlens.design.session import DesignSession
from partlens.design.views import readable_presentation
from partlens.records import RunRecorder
from partlens.session import ToolError
from tests.test_design_generation import IDEA,DEFAULTS,SELECTED


def make(tmp_path):
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[],description=IDEA,engineering_mode=True,interaction_mode=True)
    s.start_new_design()
    for k,v in DEFAULTS.items():s.record_design_requirement(k,v)
    s.propose_design_architecture(json.dumps(SELECTED))
    return s


def test_questions_are_feature_specific_ranked_and_skip_confirmed_values():
    r=Requirements('TEST',IDEA,'user:TEST')
    initial=clarification_plan(r)
    assert initial[0]['id']=='led_type' and initial[1]['id']=='runtime'
    assert {'led_rows','led_columns','charging_use','nfc_mode','microphone_use','parts_budget'}<={g['id'] for g in initial}
    r.record('led_type','mono',source='user:TEST',quote='Monochrome',confirmed=True)
    assert 'led_type' not in {g['id'] for g in clarification_plan(r)}
    t=Requirements('TEST','Rechargeable Bluetooth temperature monitor','user:TEST')
    assert not {'led_type','nfc_mode','microphone_use'}&{g['id'] for g in clarification_plan(t)}


@pytest.mark.parametrize('answer', ['define your own','make it run 4h','4','0h'])
def test_free_form_delegation_or_untyped_numbers_are_not_auto_confirmed(answer):
    assert typed_answer('runtime',answer) is None


def test_runtime_options_are_derived_counterfactuals_without_mutation(tmp_path):
    s=make(tmp_path);before=s.context_digest()
    options=runtime_options(s.spec,s.circuit)['options']
    capacity,current,duty,power=options
    assert Decimal(capacity['necessary_bound'])==Decimal('643.6571428571428571428571429')
    assert Decimal(current['necessary_bound'])<s.spec.get('led_average_current')
    assert Decimal(duty['necessary_bound'])<1 and duty['absolute_duty_cycle'] is None
    assert all(not o['applied'] and not o['accepted'] and o['selected_component'] is None for o in options)
    assert all(o['runtime_check']['status']=='unverified' and o['assembly_cost'] is None for o in options)
    assert s.context_digest()==before
    assert next(c for c in capacity['recalculation']['checks'] if c['check']=='power.runtime_bound')['status']=='unverified'
    assert next(c for c in capacity['recalculation']['checks'] if c['check']=='power.design_budget')['status']=='fail'
    assert next(c for c in current['recalculation']['checks'] if c['check']=='power.runtime_bound')['status']=='unverified'
    s.recorder.log('user_message',text='4h',origin='user')
    s.record_design_requirement('runtime','4h',user_quote='4h')
    s.propose_design_architecture(json.dumps(SELECTED))
    assert runtime_options(s.spec,s.circuit)['options'][0]['requires_owner_confirmation']


def test_same_value_model_restatement_does_not_erase_confirmation(tmp_path):
    s=make(tmp_path)
    s.recorder.log('user_message',text='Monochrome',origin='user')
    s.record_design_requirement('led_type','mono',user_quote='Monochrome')
    before=s.spec.fingerprint
    out=s.record_design_requirement('led_type','mono')
    assert out['entry']['binding'] and s.spec.fingerprint==before


def test_owner_edit_rebuilds_checks_preserves_failures_and_stays_unaccepted(tmp_path):
    s=make(tmp_path);s.generate_design_bom();s.source_design_roles();s.qualify_design();s.design_cost_scenarios()
    a=Agent(s,ScriptedProvider([]),lambda _:None)
    before=s.circuit.fingerprint
    report=revise_from_owner(s,'runtime','6h',a._execute)
    assert s.spec.current['runtime'].binding and s.spec.current['runtime'].quote=='6h'
    assert s.circuit.fingerprint!=before and s.qualifications and s.costs
    assert s.design_history and any(c['check']=='power.design_budget' and c['status']=='fail'
                                    for h in s.design_history for c in h['circuit']['checks'])
    assert 'power.runtime_bound' in report['acceptance']['failed'] and not report['acceptance']['accepted']
    assert all(q['application_status']=='unverified' for row in report['bom'] if (q:=row.get('qualification')))
    assert s.circuit.selections['power']=='power.tps63802'


def test_invalid_owner_edit_is_non_mutating(tmp_path):
    s=make(tmp_path);before=s.context_digest()
    with pytest.raises(ToolError):revise_from_owner(s,'runtime','choose for me',lambda *a,**k:None)
    assert s.context_digest()==before


def test_readable_views_and_exports_use_authoritative_report(tmp_path):
    s=make(tmp_path);s.compare_design_alternatives();s.generate_design_bom();s.source_design_roles();s.qualify_design();s.design_cost_scenarios()
    report=s.design_report();views=readable_presentation(report)
    assert 'PROVISIONAL ASSUMPTIONS' in views['Requirements']
    assert 'NOT APPLIED' in views['Alternatives'] and 'absolute PWM duty' in views['Alternatives']
    assert 'Role equivalence: unverified | application: unverified' in views['Generated BOM']
    assert 'zero known subtotal does not mean a free BOM' in views['Cost']
    dest=export(s,tmp_path/'export')
    saved=json.loads((tmp_path/'export/report.json').read_text())
    assert saved['sourcing_triage']==report['sourcing_triage']
    assert (tmp_path/'export/design-review.md').read_text(encoding='utf-8').startswith('## Overview')


def test_sourcing_triage_separates_rejection_stock_and_unknown_terms():
    role={'name':'cell','mpn':'','package':'','parameters':[],'codes':[],'omissions':['discharge limit missing']}
    part={'stock':0,'currency':'','commercial_unknowns':['MOQ unknown']}
    report={'bom':[{'line_id':'L1','block':'battery','role':role,'component':part,
                    'qualification':{'status':'unverified','application_status':'unverified'}}],
            'sourcing_history':[{'rows':[{'line':'L1','candidate_evaluations':[
                {'candidate':'fixture:TEST-WRONG','status':'rejected','identity_matches':True}]}]}]}
    cats={r['category'] for r in sourcing_triage(report)[0]['reasons']}
    assert {'incompatible_candidate','out_of_stock','manufacturing_terms_unknown','application_unverified'}<=cats
    report['bom'][0]['component']=None
    cats={r['category'] for r in sourcing_triage(report)[0]['reasons']}
    assert {'missing_exact_identity','missing_manufacturer_evidence','missing_user_requirement'}<=cats


def test_actual_typed_answer_is_recorded_by_controller_without_model_confirmation(tmp_path):
    from partlens.records import read_events
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[],description=IDEA,engineering_mode=True,interaction_mode=True)
    provider=ScriptedProvider([[('start_new_design',{})],[('design_requirements',{})],
        [('ask_user',{'gap_id':'led_type','question':'ignored model wording'})],
        [('ask_user',{'gap_id':'runtime','question':'ignored model wording'})]])
    a=DesignAgent(s,provider,lambda q:'Monochrome' if 'Monochrome' in q else None,allow_proposals=True,max_steps=4)
    a.send('TEST description without architecture')
    assert s.spec.current['led_type'].binding and s.spec.current['led_type'].quote=='Monochrome'
    assert 'runtime' not in s.spec.current
    assert any(e['type']=='tool_call' and e['name']=='record_design_requirement' and e.get('actor')=='controller'
               for e in read_events(s.recorder.path))


def test_provider_failure_is_visible_in_structured_and_readable_results(tmp_path):
    class Unavailable:
        name='TEST-unavailable'
        def next_turn(self,*args):raise ConnectionError('TEST offline')
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[],description=IDEA,engineering_mode=True,interaction_mode=True)
    a=DesignAgent(s,Unavailable(),lambda _:None,allow_proposals=True)
    a.send('TEST generic idea')
    report=s.design_report()
    assert report['controller']['stop_reason']=='provider failure: ConnectionError'
    assert 'provider failure: ConnectionError' in readable_presentation(report)['Overview']
    assert not report['controller']['operational_pipeline_complete'] and not report['bom']


def test_native_requirement_batch_is_strict_provisional_and_preserves_owner_values(tmp_path):
    from partlens.tools import run_tool
    s=DesignSession(RunRecorder.create(tmp_path/'runs'),[],description=IDEA,engineering_mode=True,interaction_mode=True)
    s.recorder.log('user_message',text='Monochrome',origin='user')
    s.record_design_requirement('led_type','mono',user_quote='Monochrome')
    out=run_tool(s,'propose_design_requirements',{'requirements':[
        {'parameter':'led_type','value':'mono'},{'parameter':'runtime','value':'4h','rationale':'TEST proposal'}]})
    assert s.spec.current['led_type'].binding and not s.spec.current['runtime'].binding
    with pytest.raises(ToolError):run_tool(s,'propose_design_requirements',{'requirements':[
        {'parameter':'runtime','value':'4h','status':'confirmed'}]})
    with pytest.raises(ToolError):s.propose_design_requirements([{'parameter':'runtime','value':'4h'}]*2)
