"""Prepare an audited source-only PartLens checkout under ignored local state. No Git or publication.

--verify additionally creates a clean venv, installs declared test dependencies, bootstraps the pinned
public H-MEM bridge, and runs both original examples and tests. It never copies credentials/runtime data.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

from partlens.cli import load_env_file
from partlens.records import RunRecorder
from partlens.secrets import redact

ROOT_FILES=['README.md','DEVELOPMENT.md','THIRD_PARTY.md','LICENSE','NOTICE','pyproject.toml',
    '.gitignore','.env.example','.gitattributes']
DIRECTORIES=['src','tests','scripts','docs','examples/easyduino-rp2040','integrations/hmem-bridge','assets/brand','assets/desktop']
EXCLUDED_NAMES={'ai_state.md','decisions.md','ai_handoff.py','test_ai_handoff.py','commit_all.ps1'}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--verify',action='store_true');args=p.parse_args()
    load_env_file();root=Path.cwd().resolve();rec=RunRecorder.create(root/'.partlens/source-preparation')
    out=root/'.partlens/partlens-source'/rec.run_id;out.mkdir(parents=True,exist_ok=False)
    files=[root/n for n in ROOT_FILES]
    for name in DIRECTORIES:
        for directory,dirs,names in os.walk(root/name,followlinks=False):
            dirs[:]=[d for d in dirs if not d.startswith('.') and not d.endswith('.egg-info') and d not in {'vendor','node_modules','__pycache__','build','dist'}
                and not any(x in d.casefold() for x in ('benchmark','badge','experiments'))
                and not (Path(directory)/d).is_symlink() and not (Path(directory)/d).is_junction()]
            for name in names:
                path=Path(directory)/name
                images=path.is_relative_to(root/'assets/brand') and path.suffix.casefold() in {'.png','.ico'}
                if path.is_symlink() or (not images and path.suffix.casefold() not in {'.py','.ts','.md','.json','.toml','.csv','.txt','.ps1','.lock','.yml','.yaml','.svg','.html','.css','.js'}):continue
                if any(x in name.casefold() for x in ('benchmark','badge')) or name.casefold() in EXCLUDED_NAMES:continue
                files.append(path)
    secrets=[v.encode() for k,v in os.environ.items() if len(v)>=8 and any(x in k.upper() for x in ('API_KEY','SECRET_KEY','ACCESS_KEY','APP_ID','PASSWORD','TOKEN'))]
    manifest=[]
    for path in files:
        relative=path.relative_to(root);data=path.read_bytes()
        if any(s in data for s in secrets):
            rec.log('source_audit_failed',file=relative.as_posix(),reason='configured credential value found; value omitted')
            raise SystemExit('Configured credential match; no publication or repository operation attempted')
        dest=out/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        dest.write_bytes(data)
        manifest.append({'path':relative.as_posix(),'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)})
    rec.log('source_tree_prepared',path=str(out),manifest=manifest,credentials_copied=False,git_created=False)
    (out/'SOURCE-MANIFEST.json').write_text(json.dumps({'files':manifest,'publication':False},indent=2),encoding='utf-8')
    print(json.dumps({'source':str(out),'record':str(rec.path),'files':len(files),'published':False}),flush=True)
    if not args.verify:return
    env={k:v for k,v in os.environ.items() if not k.startswith(('JLC_','ZETARIS_','ANTHROPIC_','PARTLENS_','DIGIKEY_','NVIDIA_'))}
    scratch=out/'.partlens/tmp';scratch.mkdir(parents=True)
    env.update({'TEMP':str(scratch),'TMP':str(scratch),'PYTHONIOENCODING':'utf-8'})
    def run(label,command,cwd=out):
        result=subprocess.run(command,cwd=cwd,env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
        rec.log('source_verification_command',label=label,exit_code=result.returncode,output=redact(result.stdout+result.stderr))
        print(label+': '+str(result.returncode),flush=True)
        if result.returncode:raise SystemExit(result.returncode)
    run('create clean Python environment',[sys.executable,'-m','venv',str(out/'.venv')])
    python=out/'.venv/Scripts/python.exe' if os.name=='nt' else out/'.venv/bin/python'
    run('editable PartLens/test installation',[str(python),'-m','pip','install','--index-url','https://pypi.org/simple','-e','.[dev,llm,desktop]'])
    npm=shutil.which('npm.cmd' if os.name=='nt' else 'npm')
    if not npm:raise SystemExit('Node/npm required for complete bridge verification')
    run('locked bridge dependencies',[npm,'ci'],out/'integrations/hmem-bridge')
    run('pinned public H-MEM setup',[npm,'run','setup'],out/'integrations/hmem-bridge')
    run('real H-MEM bridge smoke',[str(python),'-m','partlens.cli','smoke-hmem'])
    run('new original deterministic example',[str(python),'scripts/new_design_demo.py'])
    run('existing synthetic example',[str(python),'scripts/sample_demo.py'])
    run('complete independent suite',[str(python),'scripts/validate.py'])
    rec.log('source_verification_complete',source=str(out),public_source_only=True,paid_inference=False)


if __name__=='__main__':main()
