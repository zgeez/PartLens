"""Chat journals and adapters retain the independent engineering authority. No supplier/network calls."""
import hashlib
import json
import os
import threading

import pytest

from partlens.agent import ScriptedProvider
from partlens.chat_engine import ChatEngine,ObservedProvider,UserCancelled,design_summary
from partlens.conversations import ConversationStore
from partlens.records import read_events
from tests.test_design_generation import IDEA,DEFAULTS,SELECTED


def test_history_is_append_only_and_keeps_prior_artifacts(tmp_path):
    store=ConversationStore(tmp_path);chat=store.create('TEST conversation','design')
    store.message(chat,'user','Monochrome');before=chat.path.read_bytes()
    store.append(chat,'chat_artifact',report=str(tmp_path/'first.json'))
    store.append(chat,'chat_artifact',report=str(tmp_path/'second.json'))
    assert chat.path.read_bytes().startswith(before)
    assert store.latest_artifact(chat)['report'].endswith('second.json')
    assert store.list()==[chat]
    assert len([e for e in store.events(chat) if e['type']=='chat_artifact'])==2


def test_history_paths_and_untrusted_report_shape_fail_closed(tmp_path):
    store=ConversationStore(tmp_path/'state');chat=store.create('TEST','bom')
    with pytest.raises(ValueError):store.path('../outside')
    with pytest.raises(ValueError):store.owned_path(tmp_path/'outside.json')
    report=tmp_path/'state/report.json';report.write_text('[]')
    store.append(chat,'chat_artifact',report=str(report))
    with pytest.raises(ValueError,match='Unsupported'):store.report(chat)
    with pytest.raises(ValueError):store.create('TEST','invented')


def test_commentary_is_toolless_and_does_not_mutate_engineering(tmp_path):
    store=ConversationStore(tmp_path);chat=store.create('TEST','design')
    report=tmp_path/'report.json';report.write_text(json.dumps({'mode':'new_design','requirements':{'requirements':{}},'bom':[]}))
    store.append(chat,'chat_artifact',report=str(report));before=report.read_bytes()
    class Provider(ScriptedProvider):
        def next_turn(self,system,messages,tools):
            assert tools==[] and 'read-only' in system and 'no qualification/cost overrides' in system
            return super().next_turn(system,messages,tools)
    engine=ChatEngine(tmp_path,[],store,provider_factory=lambda:Provider(['TEST model claims verified']))
    assert 'claims verified' in engine.explain(chat,'TEST explain',lambda *a:None,threading.Event())
    assert report.read_bytes()==before and store.report(chat).get('acceptance') is None
    events=read_events(next((tmp_path/'chat-runs').glob('*.jsonl')))
    assert events[-1]['authority']=='none'


def test_commentary_rejects_model_tool_request(tmp_path):
    store=ConversationStore(tmp_path);chat=store.create('TEST','bom')
    report=tmp_path/'report.json';report.write_text('{"mode":"bom_review"}')
    store.append(chat,'chat_artifact',report=str(report))
    engine=ChatEngine(tmp_path,[],store,provider_factory=lambda:ScriptedProvider([[('check_substitute',{})]]))
    with pytest.raises(ValueError,match='no engineering state changed'):
        engine.explain(chat,'TEST',lambda *a:None,threading.Event())
    assert json.loads(report.read_text())=={'mode':'bom_review'}


def test_cancellation_prevents_next_model_call():
    cancel=threading.Event();cancel.set();provider=ScriptedProvider(['must not run'])
    with pytest.raises(UserCancelled):ObservedProvider(provider,lambda *a:None,cancel).next_turn('',[],[])
    assert provider.step==0


def test_negative_partial_summary_does_not_claim_complete_design():
    text=design_summary({'bom':[],'controller':{'stop_reason':'TEST model unavailable'}})
    assert 'partial' in text and 'No architecture' in text and 'not a manufacturing-ready' in text


def test_context_chain_detects_changed_original_record(tmp_path):
    from partlens.records import RunRecorder
    store=ConversationStore(tmp_path);engine=ChatEngine(tmp_path,[],store)
    original=RunRecorder.create(tmp_path/'records');original.log('user_message',text='Monochrome')
    restore=RunRecorder.create(tmp_path/'records')
    restore.log('design_context_restored',source_record=str(original.path),source_sha256=hashlib.sha256(original.path.read_bytes()).hexdigest())
    assert any(e.get('text')=='Monochrome' for e in engine._original_events(restore.path))
    original.log('TEST_appended')
    with pytest.raises(ValueError,match='changed'):engine._original_events(restore.path)


def test_scripted_chat_design_and_typed_revalidation_use_real_memory(tmp_path):
    store=ConversationStore(tmp_path);chat=store.create('TEST original idea','design')
    script=[[('start_new_design',{})],[('design_requirements',{})],
        [('ask_user',{'gap_id':'led_type','question':'TEST'})],[('ask_user',{'gap_id':'runtime','question':'TEST'})],
        [('propose_design_requirements',{'requirements':[{'parameter':k,'value':v} for k,v in DEFAULTS.items()]})],
        [('design_patterns',{})],[('select_design_patterns',{'selections':SELECTED})],
        [('compare_design_alternatives',{})],
        lambda results:[('investigate_design_alternative',{'alternative_id':next(a['id'] for a in results[0]['alternatives'] if a['resolved_failures'] and not a['new_failures'])})]]
    # No cloud provider, no supplier records. This is a deterministic adapter test, not live-model evidence.
    class TestProvider(ScriptedProvider):
        def next_turn(self,system,messages,tools):
            # The real controller appends status text after tool output. ScriptedProvider's callable
            # helper expects that output last; adapt only this deterministic test provider.
            results=[m for m in messages if m['role']=='user' and isinstance(m['content'],list)]
            return super().next_turn(system,results[-1:] or messages,tools)
    engine=ChatEngine(tmp_path,[],store,provider_factory=lambda:TestProvider(script))
    activity=[];result=engine.run(chat,IDEA,lambda q:'Monochrome' if 'Monochrome' in q else None,
        lambda k,v:activity.append((k,v)),threading.Event())
    store.append(chat,'chat_artifact',**{k:v for k,v in result.items() if k!='text'})
    first=store.report(chat)
    assert first['bom'] and first['costs'] and first['controller']['workflow_steps_complete']
    assert first['requirements']['requirements']['led_type']['binding']
    assert first['requirements']['requirements']['led_type']['quote']=='Monochrome'
    assert any(k=='activity' and v['actor']=='controller' for k,v in activity)
    before=engine.store.owned_path(result['report']).read_bytes()
    revised=engine.revalidate(chat,lambda *a:None,threading.Event(),parameter='runtime',answer='6h')
    store.append(chat,'chat_artifact',**{k:v for k,v in revised.items() if k!='text'})
    second=store.report(chat)
    assert second['requirements']['requirements']['runtime']['binding']
    assert second['requirements']['requirements']['runtime']['quote']=='6h'
    assert second['requirements']['requirements']['led_type']['binding']
    assert not second['acceptance']['accepted']
    assert engine.store.owned_path(result['report']).read_bytes()==before
    # A second cold recheck must retain both actual original and edited user quotations.
    again=engine.revalidate(chat,lambda *a:None,threading.Event())
    assert json.loads(engine.store.owned_path(again['report']).read_text())['requirements']['requirements']['runtime']['binding']


def test_existing_bom_chat_exports_checker_decisions_instead_of_model_claims(tmp_path,catalog):
    from tests.conftest import FIXTURES
    path=tmp_path/'TEST-single-capacitor.csv'
    path.write_text('\n'.join((FIXTURES/'bom_kicad.csv').read_text().splitlines()[:2])+'\n')
    store=ConversationStore(tmp_path);chat=store.create('TEST BOM review','bom')
    script=[[('import_bom',{'path':str(path)})],[('find_missing_information',{})],
        [('ask_user',{'gap_id':'design.board_quantity','question':'TEST quantity?'})],
        [('record_requirement',{'subject':'design','parameter':'board_quantity','op':'==','value':'1','user_quote':'1'})],
        [('match_parts',{})],[('search_candidates',{'line_id':'L1'})],
        [('check_substitute',{'line_id':'L1','candidate_key':'fixture:'+mpn}) for mpn in
            ['TEST-C100N-X7R-50V-EXT','TEST-C100N-X7R-6V3','TEST-C100N-NODIEL']],
        'TEST model says everything is safe and free.']
    engine=ChatEngine(tmp_path,[catalog],store,provider_factory=lambda:ScriptedProvider(script))
    result=engine.run(chat,'TEST synthetic BOM review',lambda q:'1',lambda *a:None,threading.Event(),bom_path=path)
    store.append(chat,'chat_artifact',**{k:v for k,v in result.items() if k!='text'})
    report=store.report(chat)
    assert {r['status'] for r in report['Qualifications']}=={'verified','rejected','unverified'}
    assert 'safe and free' not in report['Explanation'] and 'safe and free' not in result['text']
    assert '1 specification-equivalent' in result['text'] and '1 rejected' in result['text']
    assert report['Requirements']['requirements'][0]['binding']


@pytest.mark.skipif(os.name!='nt',reason='Native Windows chat widgets')
def test_chat_history_questions_evidence_and_settings_construct(tmp_path):
    from tests.native_widgets import isolated_case
    if isolated_case('tests/test_chat.py::test_chat_history_questions_evidence_and_settings_construct',tmp_path):return
    from partlens.chat_ui import ChatApp
    from partlens.settings import AppSettings
    from partlens.settings_ui import open_settings
    app=ChatApp([],tmp_path);app.root.withdraw()
    try:
        chat=app.store.create('TEST visual fixture','design');app.store.message(chat,'user','TEST idea')
        app.select(chat);app.events.put(('question','TEST requirement?'));app.pump()
        app.input.insert('1.0','Monochrome');app.send()
        assert app.answer=='Monochrome' and app.answer_ready.is_set()
        app.toggle_inspector();app.root.update_idletasks()
        assert app.inspector_open and app.views and len(app.message_labels)==3
        assert app.inspector.winfo_width()<=360
        app.store.message(chat,'assistant','TEST long synthetic message\n'*80)
        app.render_messages();app.root.update_idletasks()
        assert app.canvas.yview()[1]>=0.99
        win=open_settings(app,tmp_path/'settings',AppSettings(),lambda *a,**k:[])
        assert win is not None
        win.withdraw();win.destroy()
    finally:app.close()
