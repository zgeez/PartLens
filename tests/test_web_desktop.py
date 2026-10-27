"""Security and lifecycle boundaries of the local web bridge. Supplier records are synthetic only."""
import json
import os
from pathlib import Path
import threading
import time

import pytest

from partlens.web_desktop import DesktopBridge,allowed_input,frontend_html
from partlens.settings import AppSettings,load_settings,save_settings
from partlens.conversations import ConversationStore
from partlens.records import read_events


@pytest.fixture
def app(tmp_path,catalog,monkeypatch):
    monkeypatch.setattr(os,'environ',os.environ.copy())
    return DesktopBridge(tmp_path,AppSettings(),[catalog],token='TEST-native-token')


def call(app,action,payload=None):return app.request(action,payload,token='TEST-native-token')


def settle(app):
    end=time.monotonic()+20
    while app._busy and time.monotonic()<end:time.sleep(.02)
    assert not app._busy,'Test operation failed to finish'
    return call(app,'snapshot')['state']


def test_bridge_has_one_exposed_method_and_rejects_unknown_or_unauthenticated_calls(app):
    public=[k for k in dir(app) if not k.startswith('_') and callable(getattr(app,k))]
    assert public==['request']
    assert not app.request('snapshot',token='wrong')['ok']
    assert not app.request('snapshot')['ok']
    assert not call(app,'arbitrary_python',{'code':'TEST'})['ok']
    assert not app.request([],token='TEST-native-token')['ok']


def test_bridge_blocks_actions_after_navigation_away_from_local_document(app):
    class Window:
        def get_current_url(self):return 'https://TEST.invalid'
    app._window=Window()
    response=call(app,'settings_open')
    assert not response['ok'] and 'state' not in response


def test_existing_chat_journal_is_reused_without_rewriting_history(app):
    store=ConversationStore(app._state);chat=store.create('TEST old native conversation','design')
    store.message(chat,'user','TEST original description');before=chat.path.read_bytes()
    response=call(app,'select_chat',{'id':chat.id})
    assert response['ok'] and response['state']['messages'][0]['text']=='TEST original description'
    assert chat.path.read_bytes()==before
    call(app,'new_chat')
    assert chat.path.read_bytes()==before and len(call(app,'snapshot')['state']['history'])==1


def test_bad_journal_is_preserved_and_does_not_replace_current_conversation(app):
    store=ConversationStore(app._state);chat=store.create('TEST truncated','design')
    with chat.path.open('a') as f:f.write('{broken')
    before=chat.path.read_bytes()
    assert not call(app,'select_chat',{'id':chat.id})['ok']
    assert app._chat is None and chat.path.read_bytes()==before


def test_revision_polling_does_not_resend_unchanged_reports(app):
    state=call(app,'snapshot')['state']
    assert call(app,'snapshot',{'since':state['revision']})=={'ok':True,'unchanged':True}


def test_settings_never_return_existing_credentials_to_frontend(app):
    app._settings.credentials['JLC_SECRET_KEY']='TEST-private-existing-secret'
    result=call(app,'settings_open')
    assert result['result']['configured']['JLC_SECRET_KEY']
    assert 'TEST-private-existing-secret' not in json.dumps(result)
    assert app._error_text('Failure TEST-private-existing-secret')=='Failure [REDACTED]'


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI profile persistence')
def test_settings_blank_values_keep_encrypted_credentials_and_clear_is_explicit(app):
    app._settings.credentials={'JLC_SECRET_KEY':'TEST-owner-secret'}
    app._services={'TEST-old-connection':'previously available'}
    payload={'preferences':dict(app._settings.preferences),'credentials':{'JLC_SECRET_KEY':''}}
    result=call(app,'settings_save',payload)
    assert result['ok'] and load_settings(app._home).credentials==app._settings.credentials
    assert result['state']['services'] is None
    assert 'TEST-owner-secret' not in (app._home/'settings.json').read_text()
    result=call(app,'settings_save',{**payload,'clear':['JLC_SECRET_KEY']})
    assert result['ok'] and load_settings(app._home).credentials=={}


@pytest.mark.skipif(os.name!='nt',reason='Windows profile persistence')
def test_bad_settings_keep_previous_profile_and_cannot_enable_cloud_fallback(app):
    save_settings(app._home,app._settings);before=(app._home/'settings.json').read_bytes()
    bad={**app._settings.preferences,'PARTLENS_ALLOW_PAID_INFERENCE':'owner_authorized'}
    response=call(app,'settings_save',{'preferences':bad,'credentials':{'JLC_SECRET_KEY':'TEST-new-secret'}})
    assert not response['ok'] and 'TEST-new-secret' not in json.dumps(response)
    assert (app._home/'settings.json').read_bytes()==before


def test_file_access_requires_native_selection_and_rejects_private_paths(app,tmp_path):
    assert not call(app,'bom_load',{'path':str(tmp_path/'TEST-arbitrary.csv')})['ok']
    for name in ('experiments','benchmark-fixture','private-badge'):
        with pytest.raises(ValueError):allowed_input(tmp_path/name/'TEST.csv')
    assert allowed_input(tmp_path/'TEST-original.csv')==tmp_path/'TEST-original.csv'


def test_inline_answers_and_skip_are_forwarded_without_fabrication(app):
    received=[]
    class Engine:
        def run(self,chat,text,ask,notify,cancel,**kw):
            received.append(ask('TEST exact runtime?'))
            raise ValueError('TEST deliberately incomplete design')
    app._engine=Engine()
    assert call(app,'send',{'text':'TEST initial description','mode':'design'})['ok']
    end=time.monotonic()+3
    while not app._question and time.monotonic()<end:time.sleep(.01)
    assert not call(app,'settings_save',{})['ok']
    assert call(app,'answer',{'text':'6h'})['ok']
    state=settle(app)
    assert received==['6h'] and state['report'] is None
    assert any(m['kind']=='requirement_answer' and m['text']=='6h' for m in state['messages'])
    assert call(app,'send',{'text':'TEST try again','mode':'design'})['ok']
    end=time.monotonic()+3
    while not app._question and time.monotonic()<end:time.sleep(.01)
    assert call(app,'answer',{'text':None})['ok'];settle(app)
    assert received==['6h',None]
    assert app._messages[-2]['role']=='system' and app._messages[-2]['kind']=='unanswered'


def test_stop_releases_pending_question_and_preserves_partial_record(app):
    received=[]
    class Engine:
        def run(self,chat,text,ask,notify,cancel,**kw):
            received.append(ask('TEST pending question'));assert cancel.is_set()
            raise ValueError('TEST stopped')
    app._engine=Engine();call(app,'send',{'text':'TEST stop','mode':'design'})
    end=time.monotonic()+3
    while not app._question and time.monotonic()<end:time.sleep(.01)
    call(app,'stop');state=settle(app)
    assert received==[None] and not state['busy'] and state['report'] is None
    assert any(m['kind']=='error' for m in state['messages'])


def test_bom_import_uses_existing_deterministic_snapshot_without_model(app):
    result=call(app,'bom_load',{'demo':True});assert result['ok']
    state=settle(app)
    assert len(state['bom']['Parts']['lines'])==5
    assert not state['bom']['Qualifications']
    events=read_events(app._bom_session.recorder.path)
    assert any(e['type']=='tool_call' and e['name']=='match_parts' for e in events)
    assert not any(e['type']=='assistant_turn' for e in events)


def test_frontend_is_bundled_without_network_or_dynamic_message_html():
    html=frontend_html()
    assert '/* APP_' not in html and '{{LOGO}}' not in html and '{{HERO}}' not in html
    assert "connect-src 'none'" in html and 'script src=' not in html and 'link href=' not in html
    assert 'innerHTML' not in html and 'localStorage' not in html and 'sessionStorage' not in html
    assert 'settings-page' in html and 'bom-page' in html and 'data:image/png;base64,' in html
