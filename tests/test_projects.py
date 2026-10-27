"""Transactional project/review boundaries using original synthetic fixtures only."""
from contextlib import nullcontext
import csv
import hashlib
import json
from pathlib import Path
import sqlite3
import time

import pytest

from partlens.projects import ProjectStore, qualification_scope
from partlens.records import read_events
from partlens.settings import AppSettings
from partlens.web_desktop import DesktopBridge

FIXTURE = Path(__file__).parent/'fixtures/bom_kicad.csv'


@pytest.fixture
def app(tmp_path,catalog,monkeypatch):
    monkeypatch.setattr(DesktopBridge,'_bom_memory',lambda self:nullcontext())
    bridge=DesktopBridge(tmp_path,AppSettings(),[catalog])
    yield bridge
    bridge._projects.close()


def call(app,action,payload=None):
    result=app.request(action,payload)
    assert result['ok'],result
    return result


def settle(app):
    end=time.monotonic()+8
    while app._busy and time.monotonic()<end:time.sleep(.01)
    assert not app._busy
    state=call(app,'snapshot')['state']
    assert not state['status'].startswith(('Operation incomplete','Checkpoint incomplete')),state['status']
    return state


def checked(app):
    call(app,'bom_load',{'demo':True});settle(app)
    # This is a synthetic test answer through the actual recorded user-message path.
    app._ask=lambda question:'1'
    app._bom_agent=None
    call(app,'bom_manual');state=settle(app)
    assert {d['status'] for d in state['bom']['Qualifications']} >= {'verified','rejected','unverified'}
    return state


def accept(app,state):
    d=next(d for d in state['bom']['Qualifications'] if d['status']=='verified')
    payload={'decision_id':d['decision_id'],'action':'accept','reviewer':'TEST Engineer','reason':'Synthetic attribute evidence reviewed; application remains unresolved.','acknowledge':True}
    call(app,'bom_human_review',payload)
    return d,payload


def test_immutable_revisions_and_failed_import_keep_previous_revision(tmp_path):
    store=ProjectStore(tmp_path/'state')
    try:
        p=store.create('TEST original');r1=store.add_revision(p,FIXTURE)
        original=store.input_path(r1).read_bytes()
        bad=tmp_path/'TEST-invalid.csv';bad.write_text('not a BOM')
        with pytest.raises(ValueError):store.add_revision(p,bad)
        assert store.select(p)==r1
        r2=store.add_revision(p,FIXTURE)
        assert r2!=r1 and [r['number'] for r in store.revisions(p)]==[2,1]
        assert store.input_path(r1).read_bytes()==original==FIXTURE.read_bytes()
        assert store.select(p,r1)==r1
        foreign=store.create('TEST other')
        with pytest.raises(ValueError):store.select(foreign,r1)
    finally:store.close()


def test_profile_lease_prevents_two_writers_and_recovers_interrupted_job(tmp_path):
    state=tmp_path/'state';store=ProjectStore(state)
    p=store.create('TEST recovery');r=store.add_revision(p,FIXTURE)
    job=store.start_job(r,'TEST-aborted-run');store.finish_job(job,'waiting')
    with pytest.raises(RuntimeError,match='already open'):ProjectStore(state)
    store.close()
    reopened=ProjectStore(state)
    try:
        assert reopened.jobs(r)[0]['status']=='interrupted'
        with sqlite3.connect(reopened.path) as db:
            assert [v[0] for v in db.execute('SELECT status FROM job_events WHERE job_id=? ORDER BY seq',(job,))]==['running','waiting','interrupted']
    finally:reopened.close()


def test_changed_input_copy_blocks_without_overwriting_evidence(tmp_path):
    store=ProjectStore(tmp_path/'state')
    try:
        r=store.add_revision(store.create('TEST integrity'),FIXTURE);path=store.input_path(r)
        path.write_text('TEST changed')
        with pytest.raises(ValueError,match='changed'):store.input_path(r)
        assert path.read_text()=='TEST changed'
    finally:store.close()


def test_reopening_results_is_historical_and_does_not_call_sources(app,catalog,monkeypatch):
    state=checked(app);d,payload=accept(app,state);home=app._home
    record=app._bom_session.recorder.path;before=record.read_bytes()
    app._projects.close()
    def forbidden(*args,**kwargs):raise AssertionError('Reopen must not query a supplier')
    monkeypatch.setattr(type(catalog),'get',forbidden)
    reopened=DesktopBridge(home,AppSettings(),[catalog])
    try:
        saved=call(reopened,'snapshot')['state']
        assert saved['project']['historical']
        assert all(d['current_context'] is False for d in saved['bom']['Qualifications'])
        assert not reopened._bom_session.decisions and record.read_bytes()==before
        assert not reopened.request('bom_human_review',payload)['ok']
        assert not reopened.request('bom_export')['ok']
    finally:reopened._projects.close()


def test_recheck_reuses_exact_original_quantity_provenance_and_keeps_review_historical(app):
    state=checked(app);d,payload=accept(app,state)
    source=app._bom_session.requirements['design.board_quantity'].provenance.source
    project=state['project']['id']
    call(app,'project_select',{'id':project})
    app._ask=lambda question:pytest.fail('Existing quantity should be restored, never asked/fabricated')
    call(app,'bom_manual');fresh=settle(app)
    req=app._bom_session.requirements['design.board_quantity']
    assert req.provenance.source==source
    assert not fresh['project']['historical']
    assert any(e['type']=='quantity_restored' and e['new_owner_confirmation'] is False for e in read_events(app._bom_session.recorder.path))
    assert not app.request('bom_export')['ok'],'An old approval must not authorize a new run'
    # A second recovery must still point to the original user message, not the intervening run.
    call(app,'project_select',{'id':project});call(app,'bom_manual');settle(app)
    assert app._bom_session.requirements['design.board_quantity'].provenance.source==source


@pytest.mark.parametrize('status',['rejected','unverified'])
def test_human_accept_cannot_override_check_status_or_client_forgery(app,status):
    state=checked(app)
    d=next(d for d in state['bom']['Qualifications'] if d['status']==status)
    response=app.request('bom_human_review',{'decision_id':d['decision_id'],'action':'accept','reviewer':'TEST','reason':'TEST forging status','acknowledge':True,'status':'verified','checks':[]})
    assert not response['ok'] and not app._projects.reviews(app._bom_revision)
    assert app._bom_session.decisions[d['decision_id']].status.value==status


def test_review_requires_scope_acknowledgement_and_reason(app):
    state=checked(app)
    d=next(d for d in state['bom']['Qualifications'] if d['status']=='verified')
    payload={'decision_id':d['decision_id'],'action':'accept','reviewer':'TEST','reason':'TEST','acknowledge':False}
    assert not app.request('bom_human_review',payload)['ok']
    assert not app.request('bom_human_review',{**payload,'reason':'','acknowledge':True})['ok']
    call(app,'bom_human_review',{**payload,'acknowledge':True})
    assert 'NOT approved' in app._projects.reviews(app._bom_revision)[0]['scope']


def test_review_export_preserves_original_and_contains_hashes_and_application_gaps(app):
    state=checked(app);d,payload=accept(app,state)
    source=app._projects.input_path(app._bom_revision);before=source.read_bytes()
    exported=call(app,'bom_export')['result'];folder=Path(exported['path'])
    manifest=json.loads((folder/'manifest.json').read_text())
    assert exported['manufacturing_ready'] is False
    for name,sha in manifest['sha256'].items():assert hashlib.sha256((folder/name).read_bytes()).hexdigest()==sha
    assert (folder/'original.csv').read_bytes()==before==source.read_bytes()
    packet=json.loads((folder/'review.json').read_text())
    assert packet['manufacturing_ready'] is False and packet['accepted_decisions'][d['line']]['application']['status']=='unverified'
    rows=list(csv.DictReader((folder/'reviewed-proposal.csv').open(encoding='utf-8-sig')))
    assert len(rows)==len(state['bom']['Parts']['lines'])
    assert next(r for r in rows if r['Line']==d['line'])['MPN']==d['comparison']['candidate']['mpn']
    # A later rejection supersedes acceptance, without deleting either review.
    call(app,'bom_human_review',{**payload,'action':'reject','reason':'TEST later decision'})
    assert len(app._projects.reviews(app._bom_revision))==2
    assert not app.request('bom_export')['ok']


def test_new_bom_revision_does_not_inherit_approvals_or_confirmed_quantity(app):
    state=checked(app);d,payload=accept(app,state);old=app._bom_revision
    call(app,'bom_load',{'demo':True});fresh=settle(app)
    assert fresh['project']['revision']!=old and not fresh['project']['reviews']
    assert not app._bom_session.requirements.get('design.board_quantity')
    assert app._projects.reviews(old)
    assert not app.request('bom_human_review',payload)['ok']


def test_tampered_run_prefix_blocks_recovery_and_review(app):
    state=checked(app);d,payload=accept(app,state)
    path=app._bom_session.recorder.path;raw=path.read_bytes()
    path.write_bytes(raw.replace(b'ui_session',b'XX_session',1))
    assert not app.request('bom_export')['ok']
    assert not app.request('bom_human_review',payload)['ok']
    assert not app.request('project_select',{'id':state['project']['id']})['ok']


def test_export_csv_quotes_formula_cells_and_keeps_raw_original(tmp_path):
    from partlens.projects import _write_csv
    path=tmp_path/'TEST.csv'
    _write_csv(path,['Value'],[['=HYPERLINK("TEST")'],['  @TEST'],['\tTEST'],['TESTCAP']])
    rows=list(csv.reader(path.open(encoding='utf-8-sig')))
    assert [r[0] for r in rows[1:]]==['\'=HYPERLINK("TEST")',"'  @TEST","'\tTEST",'TESTCAP']


def test_failed_job_and_changed_report_cannot_be_reviewed(app):
    state=checked(app);d,payload=accept(app,state)
    with sqlite3.connect(app._projects.path) as db:
        job=db.execute('SELECT id FROM jobs ORDER BY rowid DESC LIMIT 1').fetchone()[0]
    app._projects.finish_job(job,'failed','TEST post-check failure')
    assert not app.request('bom_export')['ok']
    assert not app.request('bom_human_review',payload)['ok']
    app._projects.finish_job(job,'completed')
    with sqlite3.connect(app._projects.path) as db:
        db.execute("UPDATE checkpoints SET report='{}' WHERE seq=(SELECT MAX(seq) FROM checkpoints)")
    assert not app.request('bom_export')['ok']


def test_changed_requirements_require_new_human_review(app):
    state=checked(app);d,payload=accept(app,state)
    app._bom_session.recorder.log('user_message',text='2')
    app._bom_tool('record_requirement',subject='design',parameter='board_quantity',op='==',value='2',user_quote='2')
    call(app,'bom_manual');settle(app)
    assert not app.request('bom_export')['ok'],'Approval cannot survive a different quantity/context'


def test_future_database_schema_is_preserved_instead_of_reset(tmp_path):
    state=tmp_path/'state';store=ProjectStore(state);path=store.path;store.close()
    with sqlite3.connect(path) as db:db.execute('PRAGMA user_version=100')
    with pytest.raises(ValueError,match='compatible'):ProjectStore(state)
    with sqlite3.connect(path) as db:assert db.execute('PRAGMA user_version').fetchone()[0]==100


def test_scope_discloses_policy_coverage_and_unqualified_application():
    scope=qualification_scope()
    assert 'dielectric' in scope['families']['capacitor']['required']
    assert 'ic' not in scope['families'] and scope['manufacturing_ready'] is False
    assert len(scope['policy_sha256'])==64


def test_new_conflicting_observation_invalidates_review_without_a_model_recheck(app):
    from dataclasses import replace
    state=checked(app);d,payload=accept(app,state)
    part=app._bom_session.observed_parts[d['candidate']]
    app._bom_session.observed_parts[part.key]=replace(part,params={})
    assert not app.request('bom_human_review',payload)['ok']
    assert not app.request('bom_export')['ok']
    app._publish_bom()
    shown=next(v for v in app._bom_snapshot['Qualifications'] if v['decision_id']==d['decision_id'])
    assert shown['current_context'] is False
    assert not app.request('bom_export')['ok']
