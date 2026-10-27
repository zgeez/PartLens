"""Build one audited Windows executable from explicit public inputs; never bundle local configuration."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from importlib.metadata import distribution
from urllib.request import urlopen
from html.parser import HTMLParser

from partlens.cli import load_env_file
from partlens.records import RunRecorder
from partlens.secrets import redact

HMEM='1742dec56a66e58eef9dda2d2b865823758ca8cd'


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--console',action='store_true',help='Diagnostic build instead of the normal windowed app');args=p.parse_args()
    if os.name!='nt':raise SystemExit('Build this Windows executable on Windows')
    load_env_file();root=Path.cwd().resolve();rec=RunRecorder.create(root/'.partlens/desktop-builds')
    work=root/'.partlens/desktop-builds'/rec.run_id;work.mkdir(parents=True)
    assets=work/'assets';licenses=assets/'licenses';licenses.mkdir(parents=True)
    env={k:v for k,v in os.environ.items() if not k.startswith(('JLC_','ZETARIS_','ANTHROPIC_','PARTLENS_','MOUSER_','NVIDIA_','DIGIKEY_'))}
    def run(label,command,cwd=root):
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace',
                              creationflags=subprocess.CREATE_NO_WINDOW)
        rec.log('desktop_build_command',label=label,exit_code=result.returncode,output=redact(result.stdout+result.stderr))
        print(label+': '+str(result.returncode),flush=True)
        if result.returncode:raise SystemExit(result.returncode)
        return result.stdout.strip()
    node=shutil.which('node');esbuild=root/'integrations/hmem-bridge/node_modules/@esbuild/win32-x64/esbuild.exe'
    if not node or not esbuild.exists():raise SystemExit('Install Node and run npm ci / npm run setup in integrations/hmem-bridge first')
    node_version=run('Inspect existing Node runtime',[node,'--version'])
    if not node_version.startswith('v') or not all(c in 'v0123456789.' for c in node_version):raise SystemExit('Unexpected Node version')
    sources=[*sorted((root/'src/partlens').rglob('*.py')),root/'integrations/hmem-bridge/bridge.ts']
    secrets=[v.encode() for k,v in os.environ.items() if len(v)>=8 and any(s in k.upper() for s in ('API_KEY','SECRET_KEY','ACCESS_KEY','APP_ID','PASSWORD','TOKEN'))]
    for source in sources:
        if any(s in source.read_bytes() for s in secrets):raise SystemExit('Configured credential match in build source; value omitted')
    rec.log('desktop_build_started',source_inputs=[str(s.relative_to(root)) for s in sources],hmem_commit=HMEM,
            node_version=node_version,configuration_bundled=False,paid_provider_bundled=False)
    memory=assets/'memory';memory.mkdir()
    shutil.copyfile(node,memory/'node.exe')
    run('Bundle real pinned H-MEM bridge',[str(esbuild),'integrations/hmem-bridge/bridge.ts','--bundle','--platform=node',
        '--format=esm','--target=node20','--legal-comments=inline','--outfile='+str(memory/'bridge.mjs')])
    def official_license(name,url):
        cache=root/'.partlens/desktop-license-cache'/name;cache.parent.mkdir(parents=True,exist_ok=True)
        if not cache.exists():
            with urlopen(url,timeout=45) as response:data=response.read(4*1024*1024)
            if len(data)<100:raise SystemExit('Official license text unavailable: '+name)
            with cache.open('xb') as f:f.write(data)
        destination=licenses/name
        if name.endswith('.html'):
            class LicenseText(HTMLParser):
                def __init__(self):super().__init__();self.inside=False;self.parts=[]
                def handle_starttag(self,tag,attrs):
                    if tag=='pre':self.inside=True
                def handle_endtag(self,tag):
                    if tag=='pre':self.inside=False
                def handle_data(self,data):
                    if self.inside:self.parts.append(data)
            parsed=LicenseText();parsed.feed(cache.read_text(encoding='utf-8'))
            content=''.join(parsed.parts).strip()
            if 'Microsoft Corporation' not in content or 'Redistribution' not in content:raise SystemExit('Official SDK license could not be extracted')
            destination=licenses/(Path(name).stem+'.txt');destination.write_text(content+'\n',encoding='utf-8')
        else:shutil.copyfile(cache,destination)
        rec.log('license_included',name=destination.name,source=url,sha256=hashlib.sha256(destination.read_bytes()).hexdigest())
    official_license('Node-'+node_version+'-LICENSE.txt','https://raw.githubusercontent.com/nodejs/node/'+node_version+'/LICENSE')
    official_license('Meterless-'+HMEM+'-LICENSE.txt','https://raw.githubusercontent.com/Meterless/Meterless/'+HMEM+'/LICENSE')
    pyinstaller=distribution('pyinstaller')
    copying=next(pyinstaller.locate_file(f) for f in pyinstaller.files if str(f).endswith('licenses/COPYING.txt'))
    copies=[(root/'LICENSE','PartLens-LICENSE.txt'),(root/'NOTICE','PartLens-NOTICE.txt'),
        (root/'THIRD_PARTY.md','THIRD_PARTY.md'),(Path(sys.base_prefix)/'LICENSE.txt','Python-LICENSE.txt'),
        (copying,'PyInstaller-COPYING.txt'),
        (root/'integrations/hmem-bridge/node_modules/esbuild/LICENSE.md','esbuild-LICENSE.md')]
    for package in ['pywebview','pythonnet','clr_loader','bottle','cffi','pycparser','typing_extensions']:
        info=distribution(package)
        license_file=next(info.locate_file(f) for f in info.files if '/licenses/LICENSE' in str(f))
        copies.append((license_file,package+'-'+info.version+'-LICENSE.txt'))
    for source,name in copies:
        if not source.is_file():raise SystemExit('Required license missing: '+name)
        shutil.copyfile(source,licenses/name)
    official_license('proxy_tools-0.1.0-LICENSE.txt','https://raw.githubusercontent.com/jtushman/proxy_tools/master/LICENSE.txt')
    official_license('Microsoft-WebView2-SDK-1.0.3856.49-LICENSE.html','https://www.nuget.org/packages/Microsoft.Web.WebView2/1.0.3856.49/License')
    # Explicit original/open example inputs only. No directory-wide data collection.
    for relative in ['examples/easyduino-rp2040/bom.csv','examples/easyduino-rp2040/LICENSE-CERN-OHL-P-2.0.txt',
                     'tests/fixtures/bom_kicad.csv','tests/fixtures/catalog.json']:
        dest=assets/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(root/relative,dest)
    for source in (root/'assets/brand').iterdir():
        if source.suffix.lower() in {'.png','.ico','.md'} and source.is_file() and not source.is_symlink():
            dest=assets/'assets/brand'/source.name;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,dest)
    for name in ['index.html','app.css','app.js']:
        source=root/'assets/desktop'/name;dest=assets/'assets/desktop'/name;dest.parent.mkdir(parents=True,exist_ok=True)
        if any(secret in source.read_bytes() for secret in secrets):raise SystemExit('Credential match in frontend; value omitted')
        shutil.copyfile(source,dest)
    entry=work/'desktop_entry.py';entry.write_text('from partlens.desktop import main\nraise SystemExit(main())\n',encoding='utf-8')
    command=[sys.executable,'-m','PyInstaller','--onefile','--name','PartLens','--noupx',
        '--console' if args.console else '--windowed','--distpath',str(work/'dist'),'--workpath',str(work/'build'),
        '--specpath',str(work),'--paths',str(root/'src'),'--exclude-module','anthropic','--exclude-module','pytest',
        '--exclude-module','pypdf','--exclude-module','tkinter','--exclude-module','PyQt5','--exclude-module','PyQt6',
        '--exclude-module','PySide2','--exclude-module','PySide6','--icon',str(root/'assets/brand/PartLens.ico'),'--add-data',str(assets)+';.',str(entry)]
    run('Build one-file Windows app',command)
    exe=work/'dist/PartLens.exe'
    # Test away from the source directory, without external Node/Python on PATH or any supplier credentials.
    scratch=work/'acceptance';scratch.mkdir()
    test_env={**env,'PATH':os.environ.get('SystemRoot','C:\\Windows')+'\\System32'}
    result=subprocess.run([str(exe),'--self-test','--data-dir',str(scratch/'state'),'--report',str(scratch/'report.json')],
        cwd=scratch,env=test_env,timeout=240,creationflags=subprocess.CREATE_NO_WINDOW)
    report=json.loads((scratch/'report.json').read_text(encoding='utf-8')) if (scratch/'report.json').exists() else {'success':False,'reason':'no acceptance report'}
    rec.log('packaged_acceptance',exit_code=result.returncode,report=report,external_node_python_on_path=False)
    if result.returncode or not report['success']:raise SystemExit('Packaged acceptance failed; see '+str(rec.path))
    dist=root/'dist';dist.mkdir(exist_ok=True)
    output=dist/'PartLens.exe'
    if output.exists():shutil.copyfile(output,work/'previous-PartLens.exe')
    try:shutil.copyfile(exe,output)
    except PermissionError:
        rec.log('release_install_blocked',reason='Running executable is locked. Accepted candidate and previous binary preserved.',candidate=str(exe))
        raise SystemExit('Close PartLens before replacing its executable. Accepted build preserved at '+str(exe)) from None
    summary={'executable':str(output),'size':output.stat().st_size,'sha256':hashlib.sha256(output.read_bytes()).hexdigest(),
             'build_record':str(rec.path),'acceptance':report,'credentials_bundled':False,'authenticode_signed':False,
             'external_services':['Ollama runtime/model','authorized Zetaris service'],'publication':False}
    (work/'release.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    rec.log('desktop_build_complete',summary=summary)
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
