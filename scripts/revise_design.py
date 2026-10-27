"""Apply an actual operator-relayed owner answer to a recorded design and independently revalidate.

The answer must be the owner's verbatim words, never a fabricated evaluation answer. This is a
controller operation, not another autonomous model trial. Runtime source data remains ignored.
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
    p.add_argument('--run',type=Path,required=True);p.add_argument('--answer',required=True)
    p.add_argument('--parameter',required=True);p.add_argument('--value',required=True)
    p.add_argument('--jlc',action='store_true');p.add_argument('--zetaris',action='store_true')
    p.add_argument('--catalog',action='append');p.add_argument('--evidence',action='append')
    args=p.parse_args();load_env_file()
    if any(x.casefold()=='experiments' or 'benchmark' in x.casefold() or 'badge' in x.casefold() for x in args.run.resolve().parts):
        raise SystemExit('excluded design source')
    events=read_events(args.run);old=next(e['report'] for e in events[::-1] if e['type']=='design_agent_result')
    spec=restore_requirements(old['requirements'],events)
    rec=RunRecorder.create('.partlens/runs');root=Path('.partlens/owner-revisions')/rec.run_id
    catalogs=catalogs_from_args(args)
    if args.jlc:(catalogs[0].base if args.zetaris else catalogs[0]).client.cache_dir=root/'cache'
    with HMemBridge(root/'hmem') as bridge:
        s=DesignSession(rec,[AuditedCatalog(c) for c in catalogs],description=spec.description,design_id=spec.design_id,
            _record_description=False,engineering_mode=True,memory=DecisionMemory(bridge,spec.design_id))
        s.spec=spec
        rec.log('new_design_start',description=spec.description,design_id=spec.design_id,description_source=spec.description_source)
        rec.log('design_context_restored',source_record=str(args.run),requirements=spec.view(),
            source_sha256=hashlib.sha256(args.run.read_bytes()).hexdigest(),inherited_verification=False,new_owner_answer=False)
        a=Agent(s,ScriptedProvider([]),lambda q:None)
        def call(name,**kwargs):
            out=a._execute(ToolCall('revision-'+str(rec.seq),name,kwargs),actor='controller')
            if out.get('is_error'):raise RuntimeError(out['content'])
            return json.loads(out['content'])
        selections=json.dumps(old['architecture']['selections'])
        call('propose_design_architecture',selections_json=selections);call('generate_design_bom')
        call('source_design_roles');call('qualify_design');export(s,root/'before')
        rec.log('user_message',text=args.answer,origin='user',input_kind='actual_owner_reply_relayed_by_operator')
        entry=call('record_design_requirement',parameter=args.parameter,value=args.value,user_quote=args.answer,action='replace')
        if not entry['entry']['binding']:raise SystemExit('Answer did not establish the claimed typed requirement; remains provisional')
        invalidated=s.bom is None and not s.qualifications and not s.decisions
        call('propose_design_architecture',selections_json=selections);call('generate_design_bom')
        call('source_design_roles');call('qualify_design');call('design_cost_scenarios');call('remember_design')
        artifacts=export(s,root/'after')
        result={'record':str(rec.path),'actual_answer':args.answer,'confirmed_parameter':args.parameter,
            'previous_results_invalidated':invalidated,'failed':s.design_report()['acceptance']['failed'],
            'accepted':s.design_report()['acceptance']['accepted'],'model_called':False,'artifacts':artifacts}
        rec.log('owner_revision_result',summary=result,report=s.design_report());print(json.dumps(result))


if __name__=='__main__':main()
