"""Double-click desktop entry point with one settings surface; developer CLI remains available."""
import argparse
import json
import os
from pathlib import Path
from types import SimpleNamespace

from .paths import app_home,resource_root,example_bom
from .settings import AppSettings,load_settings,import_env,save_settings,MODES


def catalogs(settings, state):
    if settings.preferences['supplier_mode']=='offline':
        from .sources.catalog import LocalCatalog
        return [LocalCatalog.from_json(resource_root()/'tests/fixtures/catalog.json')]
    # Build clients from validated settings, restoring current environment even on an invalid configuration.
    from .cli import catalogs_from_args
    before=dict(os.environ)
    try:
        settings.apply();mode=settings.preferences['supplier_mode']
        import sys
        exe_dir=Path(sys.executable).resolve().parent
        search_roots=[Path.cwd(),exe_dir,exe_dir.parent,resource_root(),Path(r"E:\Coding Proj\Cirquill")]
        lead_file=next((r/'.partlens/cache/lcsc-easyduino.json' for r in search_roots if (r/'.partlens/cache/lcsc-easyduino.json').is_file()),None)
        cats=catalogs_from_args(SimpleNamespace(jlc=mode in {'jlc','jlc_zetaris'},
            zetaris=mode in {'zetaris','jlc_zetaris'},
            jlc_leads=str(lead_file) if lead_file and mode in {'jlc','jlc_zetaris'} else None),state=state)
        if mode=='jlc_zetaris' and cats and hasattr(cats[0],'base'):
            return [cats[0],cats[0].base]
        return cats
    except SystemExit:
        raise ValueError('Selected supplier mode is missing its required configuration. Fill its Settings tab.') from None
    finally:
        os.environ.clear();os.environ.update(before)


def self_test(home):
    """Offline packaged acceptance: actual native memory, synthetic engineering and persistent settings."""
    from .memory.hmem import HMemBridge,DecisionMemory
    from .core.bom import import_bom_csv
    from .checks.compat import check_substitute
    from .sources.catalog import LocalCatalog
    from .records import new_run_id
    root=Path(home)/'self-tests'/new_run_id();root.mkdir(parents=True)
    catalog=LocalCatalog.from_json(resource_root()/'tests/fixtures/catalog.json')
    bom=import_bom_csv(example_bom(root,synthetic=True))
    original=catalog.get('fixture:TEST-C100N-X7R-16V')
    decisions=[check_substitute(bom.line('L1'),original,catalog.get(key)) for key in (
        'fixture:TEST-C100N-X7R-50V-EXT','fixture:TEST-C100N-X7R-6V3','fixture:TEST-C100N-NODIEL')]
    assert [d.status.value for d in decisions]==['verified','rejected','unverified']
    with HMemBridge(root/'memory') as bridge:
        info=bridge.info;stored=DecisionMemory(bridge,'TEST-packaging').remember(decisions[1],run_id='TEST-packaging')
    with HMemBridge(root/'memory') as bridge:
        recalled=DecisionMemory(bridge,'TEST-packaging').recall(decisions[1].original,decisions[1].candidate)
        assert recalled and recalled[0].decision_id==decisions[1].id
    test=AppSettings(credentials={'JLC_SECRET_KEY':'TEST-only-packaging-secret'})
    save_settings(root/'settings',test)
    assert load_settings(root/'settings').credentials==test.credentials
    assert 'TEST-only-packaging-secret' not in (root/'settings/settings.json').read_text()
    from .design.session import DesignSession
    from .design.patterns import PATTERNS
    from .design.cli import export
    from .records import RunRecorder
    design=DesignSession(RunRecorder.create(root/'design-runs'),[],engineering_mode=True,interaction_mode=True,
        description='Rechargeable smart LED matrix with Bluetooth, NFC, microphone and IMU')
    design.start_new_design()
    choices={'led_rows':'4','led_columns':'8','led_count':'32','led_type':'mono','nfc_mode':'tag',
        'microphone_use':'sound_reactive','logic_voltage':'3.3V','battery_min':'3.0V','battery_max':'4.2V',
        'battery_capacity':'500mAh','runtime':'8h','board_quantity':'1','led_average_current':'10mA',
        'charging_use':'off_while_charging'}
    design.propose_design_requirements([{'parameter':k,'value':v} for k,v in choices.items()])
    design.select_design_patterns({p.block:p.id for p in PATTERNS.values()})
    design.generate_design_bom();design.source_design_roles();design.qualify_design();design.design_cost_scenarios()
    design_report=design.design_report()
    assert design_report['bom'] and not design_report['acceptance']['accepted']
    assert not any(e['binding'] for e in design_report['requirements']['requirements'].values())
    export(design,root/'design-export')
    from .web_acceptance import renderer_acceptance
    renderer=renderer_acceptance(root/'web-ui',catalog)
    return {'success':True,'mode':'offline synthetic packaging check; no model or supplier call',
        'decision_statuses':[d.status.value for d in decisions],'memory_engine':info['engine'],
        'memory_entry':info['entry'],'cold_recall_count':len(recalled),'credential_encryption':'DPAPI round-trip passed',
        'bundled_demo_present':(resource_root()/'examples/easyduino-rp2040/bom.csv').is_file(),
        'new_design_generated_roles':len(design_report['bom']),'new_design_accepted':False,
        'desktop_renderer':renderer}


def main(argv=None):
    parser=argparse.ArgumentParser(description='PartLens desktop')
    parser.add_argument('--self-test',action='store_true',help='Offline packaged acceptance; requires --report')
    parser.add_argument('--check-services',action='store_true',help='Headless live service checks; requires --report')
    parser.add_argument('--report',type=Path)
    parser.add_argument('--import-env',type=Path,help='Import owner-authorized local configuration without displaying values')
    parser.add_argument('--data-dir',type=Path,help='Explicit local data directory for portable/testing use')
    args=parser.parse_args(argv);home=args.data_dir.resolve() if args.data_dir else app_home();home.mkdir(parents=True,exist_ok=True)
    if args.self_test:
        if not args.report:parser.error('--self-test requires --report')
        try:result=self_test(home)
        except Exception as exc:
            result={'success':False,'error_type':type(exc).__name__}
        with args.report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        return 0 if result['success'] else 1
    if args.check_services:
        if not args.report:parser.error('--check-services requires --report')
        settings=load_settings(home)
        if args.import_env:
            settings=import_env(args.import_env,settings);save_settings(home,settings)
        settings.apply()
        from .preflight import run_preflight
        result=run_preflight(home/'state')
        with args.report.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
        return 0 if result['services_available'] else 1
    try:
        if not (home/'settings.json').exists() and Path('.env.local').is_file():
            try:save_settings(home,import_env(Path('.env.local'),AppSettings()))
            except Exception:pass
        settings=load_settings(home)
        if args.import_env:
            settings=import_env(args.import_env,settings);save_settings(home,settings)
        settings.apply()
        import threading
        from .local_provider import ensure_local_ollama
        threading.Thread(target=ensure_local_ollama,args=(settings.preferences['PARTLENS_LOCAL_URL'],),daemon=True).start()
        state=home/'state'
        try:initial_catalogs=catalogs(settings,state)
        except ValueError:
            # A missing optional service does not stop the settings screen from opening.
            initial_catalogs=[]
        from .web_desktop import launch
        launch(home,settings,initial_catalogs)
    except Exception as exc:
        # Never log configuration exception bodies, which may contain credentials or personal paths.
        from .records import RunRecorder
        RunRecorder.create(home/'state/startup-errors').log('desktop_startup_error',error_type=type(exc).__name__)
        if os.name=='nt':
            import ctypes
            from .projects import ProfileInUse
            message=('This PartLens profile is already open. Close its other window normally, then reopen it. Existing evidence was preserved.'
                if isinstance(exc,ProfileInUse) else 'PartLens needs Microsoft WebView2 Runtime and .NET Framework 4.6.2+. Check your local configuration if these are installed. Existing settings and evidence were preserved.')
            ctypes.windll.user32.MessageBoxW(None,message,'PartLens could not start',0x10)
        return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
