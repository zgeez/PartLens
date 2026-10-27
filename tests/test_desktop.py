"""Desktop settings and packaging boundaries use synthetic credentials and no network calls."""
import json
import os
from pathlib import Path
import sys

import pytest

from partlens.settings import AppSettings,load_settings,save_settings,import_env
from partlens.desktop import catalogs
from partlens.paths import resource_root,app_home


@pytest.mark.parametrize('key,value',[
    ('supplier_mode','invented'),('PARTLENS_LOCAL_PROTOCOL','automatic-fallback'),
    ('PARTLENS_LOCAL_URL','https://example.test'),('PARTLENS_LOCAL_URL','http://secret@localhost:11434'),
    ('PARTLENS_LOCAL_MODEL','TEST-model:cloud'),('PARTLENS_LOCAL_CONTEXT','1'),
    ('PARTLENS_LOCAL_TIMEOUT','601'),('PARTLENS_LOCAL_TIMEOUT','not-a-number'),
    ('JLC_APP_NAME','TEST\nInjected')])
def test_invalid_settings_never_save(tmp_path,key,value):
    s=AppSettings();s.preferences[key]=value
    with pytest.raises(ValueError):save_settings(tmp_path,s)
    assert not (tmp_path/'settings.json').exists()


@pytest.mark.skipif(os.name!='nt',reason='Windows DPAPI credential storage')
def test_credentials_round_trip_are_encrypted_and_corruption_fails_closed(tmp_path):
    s=AppSettings(credentials={'JLC_SECRET_KEY':'TEST-credential-123'})
    save_settings(tmp_path,s)
    payload=(tmp_path/'settings.json').read_text()
    assert 'TEST-credential-123' not in payload and 'TEST-credential-123' not in repr(s)
    assert load_settings(tmp_path).credentials==s.credentials
    value=json.loads(payload);value['credentials']='INVALID!'
    (tmp_path/'settings.json').write_text(json.dumps(value))
    before=(tmp_path/'settings.json').read_bytes()
    with pytest.raises(ValueError,match='could not be loaded'):load_settings(tmp_path)
    assert (tmp_path/'settings.json').read_bytes()==before


def test_atomic_save_preserves_previous_settings_on_encryption_failure(tmp_path,monkeypatch):
    import partlens.settings as module
    save_settings(tmp_path,AppSettings());before=(tmp_path/'settings.json').read_bytes()
    def failure(*a,**kw):raise RuntimeError('TEST crypto unavailable')
    monkeypatch.setattr(module,'_dpapi',failure)
    with pytest.raises(RuntimeError):save_settings(tmp_path,AppSettings(credentials={'JLC_SECRET_KEY':'TEST'}))
    assert (tmp_path/'settings.json').read_bytes()==before


def test_env_import_is_allowlisted_does_not_apply_and_selects_official_mode(tmp_path,monkeypatch):
    monkeypatch.setenv('JLC_SECRET_KEY','TEST-current-secret')
    path=tmp_path/'.env.local'
    path.write_text('JLC_APP_ID=TEST-app\nJLC_ACCESS_KEY=TEST-key\nJLC_SECRET_KEY=TEST-new-secret\n'
                    'PARTLENS_LOCAL_MODEL=TEST-model:8b\nANTHROPIC_API_KEY=TEST-ignored\nUNKNOWN=TEST-ignored\n')
    s=import_env(path,AppSettings())
    assert s.preferences['supplier_mode']=='jlc' and s.credentials['JLC_SECRET_KEY']=='TEST-new-secret'
    assert os.environ['JLC_SECRET_KEY']=='TEST-current-secret'
    assert 'ANTHROPIC_API_KEY' not in s.credentials and 'UNKNOWN' not in s.preferences


def test_settings_apply_clears_removed_credentials_and_forces_local(monkeypatch):
    monkeypatch.setattr(os,'environ',os.environ.copy())
    monkeypatch.setenv('JLC_SECRET_KEY','TEST-old');monkeypatch.setenv('PARTLENS_LLM_PROVIDER','anthropic')
    AppSettings().apply()
    assert os.environ['JLC_SECRET_KEY']=='' and os.environ['PARTLENS_LLM_PROVIDER']=='ollama'
    assert os.environ['PARTLENS_ALLOW_PAID_INFERENCE']=='disabled'


def test_invalid_supplier_configuration_does_not_change_environment(tmp_path,monkeypatch):
    monkeypatch.setenv('PARTLENS_LOCAL_MODEL','TEST-before:8b')
    s=AppSettings();s.preferences['supplier_mode']='jlc'
    for name in ('JLC_APP_ID','JLC_ACCESS_KEY','JLC_SECRET_KEY'):monkeypatch.delenv(name,raising=False)
    with pytest.raises(ValueError,match='missing'):catalogs(s,tmp_path)
    assert os.environ['PARTLENS_LOCAL_MODEL']=='TEST-before:8b'


def test_frozen_resources_and_data_are_separate(monkeypatch,tmp_path):
    monkeypatch.setattr(sys,'frozen',True,raising=False);monkeypatch.setattr(sys,'_MEIPASS',str(tmp_path/'resources'),raising=False)
    monkeypatch.setenv('PARTLENS_APP_HOME',str(tmp_path/'data'))
    assert resource_root()==tmp_path/'resources' and app_home()==tmp_path/'data'


def test_offline_catalog_is_labeled_synthetic_and_never_constructs_network_client(monkeypatch,tmp_path):
    import partlens.sources.jlcpcb as jlc
    monkeypatch.setattr(jlc,'JLCClient',lambda *a,**kw:pytest.fail('unexpected network client'))
    result=catalogs(AppSettings(),tmp_path)
    assert result[0].get('fixture:TEST-C100N-X7R-16V')


def test_packaged_demo_input_survives_bundle_cleanup_and_preserves_old_revision(tmp_path,monkeypatch):
    from partlens import paths
    from partlens.core.bom import import_bom_csv
    resources=tmp_path/'resources';source=resources/'tests/fixtures/bom_kicad.csv'
    source.parent.mkdir(parents=True);(resources/'LICENSE').write_text('TEST original synthetic license')
    first='Reference,Value,Footprint,MPN\nC1,100nF,0402,TEST-CAP\n'
    source.write_text(first);monkeypatch.setattr(paths,'resource_root',lambda:resources)
    saved=paths.example_bom(tmp_path/'data',synthetic=True)
    source.unlink()
    assert import_bom_csv(saved).line('L1').mpn=='TEST-CAP'
    assert saved.with_name('LICENSE.txt').is_file()
    source.write_text(first.replace('TEST-CAP','TEST-CAP-2'))
    revised=paths.example_bom(tmp_path/'data',synthetic=True)
    assert revised!=saved and import_bom_csv(saved).line('L1').mpn=='TEST-CAP'


@pytest.mark.skipif(os.name!='nt',reason='Windows desktop widgets')
def test_desktop_and_settings_construct_without_credentials_or_model(tmp_path):
    from tests.native_widgets import isolated_case
    if isolated_case('tests/test_desktop.py::test_desktop_and_settings_construct_without_credentials_or_model',tmp_path):return
    from partlens.ui import ReviewApp
    from partlens.settings_ui import open_settings
    from partlens.sources.catalog import LocalCatalog
    app=ReviewApp([LocalCatalog([],name='fixture')],tmp_path/'state')
    app.root.withdraw()
    win=open_settings(app,tmp_path,AppSettings(),lambda *a,**kw:[])
    assert win is not None
    win.withdraw();app.root.update_idletasks();win.destroy();app.close()
