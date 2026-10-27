"""Re-evaluate a recorded failed architecture and investigate a checked improvement, without model calls.

No existing BOM or supplier snapshot is imported. Original typed requirements and pattern choices are
restored with provenance; generated roles, sourcing and qualification are recomputed for each trial.
"""
import argparse
import hashlib
import json
from pathlib import Path

from partlens.agent import Agent,ScriptedProvider,ToolCall
from partlens.cli import load_env_file,catalogs_from_args
from partlens.design.session import DesignSession
from partlens.design.restore import restore_requirements
from partlens.design.cli import export
from partlens.memory.hmem import HMemBridge,DecisionMemory
from partlens.records import RunRecorder,read_events
from partlens.sources.audit import AuditedCatalog


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--run',type=Path,required=True)
    p.add_argument('--jlc',action='store_true');p.add_argument('--zetaris',action='store_true')
    p.add_argument('--catalog',action='append');p.add_argument('--evidence',action='append')
    args=p.parse_args();load_env_file()
    if any(x.casefold()=='experiments' or 'benchmark' in x.casefold() or 'badge' in x.casefold() for x in args.run.resolve().parts):
        raise SystemExit('excluded design context source')
    events=read_events(args.run)
    report=next(e['report'] for e in events[::-1] if e['type']=='design_agent_result')
    spec=restore_requirements(report['requirements'],events)
    rec=RunRecorder.create('.partlens/runs');root=Path('.partlens/architecture-correction')/rec.run_id
    catalogs=catalogs_from_args(args)
    if args.jlc:
        official=catalogs[0].base if args.zetaris else catalogs[0]
        official.client.cache_dir=root/'cache'
    with HMemBridge(root/'hmem') as bridge:
        s=DesignSession(rec,[AuditedCatalog(c) for c in catalogs],description=spec.description,design_id=spec.design_id,
            _record_description=False,engineering_mode=True,memory=DecisionMemory(bridge,spec.design_id))
        s.spec=spec
        rec.log('new_design_start',description=spec.description,design_id=spec.design_id,description_source=spec.description_source)
        rec.log('design_context_restored',source_record=str(args.run),requirements=spec.view(),
            source_sha256=hashlib.sha256(args.run.read_bytes()).hexdigest(),inherited_verification=False,new_owner_answer=False)
        rec.log('correction_evaluation',model_called=False,actor='controller',memory_process_id=bridge._proc.pid)
        a=Agent(s,ScriptedProvider([]),lambda q:None)
        def call(name,**kwargs):
            out=a._execute(ToolCall('correction-'+str(rec.seq),name,kwargs),actor='controller')
            if out.get('is_error'):raise RuntimeError(out['content'])
            return json.loads(out['content'])
        call('start_new_design');call('propose_design_architecture',selections_json=json.dumps(report['architecture']['selections']))
        call('generate_design_bom');call('source_design_roles');call('qualify_design');call('design_cost_scenarios')
        export(s,root/'before')
        compared=call('compare_design_alternatives')
        options=[r for r in compared['alternatives'] if r['resolved_failures'] and not r['new_failures']]
        if not options:raise SystemExit('No evidenced improving alternative; original failures retained')
        trial=min(options,key=lambda r:len(r['failed_constraints']))
        fingerprint=s.spec.fingerprint
        call('investigate_design_alternative',alternative_id=trial['id'])
        call('generate_design_bom');call('source_design_roles');call('qualify_design');call('design_cost_scenarios');call('remember_design')
        artifacts=export(s,root/'after')
        final=s.design_report()
        summary={'record':str(rec.path),'model_called':False,'requirements_unchanged':s.spec.fingerprint==fingerprint,
            'resolved_failures':trial['resolved_failures'],'remaining_failures':final['acceptance']['failed'],
            'accepted':final['acceptance']['accepted'],'sourced_roles':sum(bool(x) for x in s.baseline.values()),'artifacts':artifacts}
        rec.log('architecture_correction_result',summary=summary,report=final)
        print(json.dumps(summary))


if __name__=='__main__':main()
