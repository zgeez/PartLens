"""Actual cold H-MEM recall and fresh source checks, then an explicit hypothetical requirement revision.

This is a controller-operated verification session, not another autonomous model-design trial. It restores
the original requirements/provenance and model-selected patterns, never a supplier/BOM snapshot.
"""

import argparse
import hashlib
import json
from pathlib import Path

from partlens.agent import Agent,ScriptedProvider,ToolCall
from partlens.cli import catalogs_from_args,load_env_file
from partlens.design.cli import export
from partlens.design.restore import restore_requirements
from partlens.design.session import DesignSession
from partlens.memory.hmem import HMemBridge,DecisionMemory
from partlens.records import RunRecorder,read_events
from partlens.sources.audit import AuditedCatalog


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',type=Path,required=True)
    parser.add_argument('--jlc',action='store_true');parser.add_argument('--zetaris',action='store_true')
    parser.add_argument('--catalog',action='append');parser.add_argument('--evidence',action='append')
    parser.add_argument('--revise-parameter',default='led_columns');parser.add_argument('--revise-value',default='32')
    parser.add_argument('--memory-store',type=Path,help='Existing ignored H-MEM store for a desktop/custom-state run')
    parser.add_argument('--no-revision',action='store_true',help='Cold recall/recheck only, retaining the source engineering/interaction mode')
    args=parser.parse_args();load_env_file()
    if any(p.casefold()=='experiments' or 'benchmark' in p.casefold() or 'badge' in p.casefold() for p in args.run.resolve().parts):
        raise SystemExit('excluded material cannot be read')
    events=read_events(args.run)
    result=next(e['report'] for e in reversed(events) if e['type']=='design_agent_result')
    if not result['bom_origin'] or not result['memory']:
        raise SystemExit('source run lacks a generated BOM or genuine persisted decisions')
    spec=restore_requirements(result['requirements'],events)
    rec=RunRecorder.create('.partlens/runs')
    root=Path('.partlens/design-rechecks')/rec.run_id
    catalogs=catalogs_from_args(args)
    if args.jlc:
        official=catalogs[0].base if args.zetaris else catalogs[0]
        official.client.cache_dir=root/'cache'
    store=args.memory_store or Path('.partlens/new-design')/args.run.stem/'hmem'
    if args.memory_store and (not store.resolve().is_relative_to(Path('.partlens').resolve())
            or not store.is_dir() or any(x in str(store).casefold() for x in ('experiments','benchmark'))):
        raise SystemExit('memory store must already exist inside ignored PartLens state')
    with HMemBridge(store) as bridge:
        rec.log('design_cold_recheck',source_record=str(args.run),source_sha256=hashlib.sha256(args.run.read_bytes()).hexdigest(),
                original_requirements=spec.view(),model_called=False,actor='controller',process_id=bridge._proc.pid,
                persistent_store=str(store))
        session=DesignSession(rec,[AuditedCatalog(c) for c in catalogs],description=spec.description,design_id=spec.design_id,
                              memory=DecisionMemory(bridge,spec.design_id),_record_description=False,
                              engineering_mode=args.no_revision and any(e['type']=='design_engineering_mode' for e in events),
                              interaction_mode=args.no_revision and any(e['type']=='design_interaction_mode' for e in events))
        session.spec=spec
        rec.log('new_design_start',description=spec.description,design_id=spec.design_id,
                description_source=spec.description_source,schema='partlens.requirements/1')
        rec.log('design_context_restored',source_record=str(args.run),requirements=spec.view(),
                source_sha256=hashlib.sha256(args.run.read_bytes()).hexdigest(),
                inherited_verification=False,new_owner_answer=False)
        runner=Agent(session,ScriptedProvider([]),lambda q:None)
        def call(name,**args):
            out=runner._execute(ToolCall('controller-'+str(rec.seq),name,args),actor='controller')
            if out.get('is_error'):raise RuntimeError(out['content'])
            return json.loads(out['content'])
        choices=json.dumps(result['architecture']['selections'])
        call('start_new_design');call('propose_design_architecture',selections_json=choices)
        call('generate_design_bom');recalled=call('recall_design',run_id=args.run.stem)
        current=call('reverify_design',run_id=args.run.stem)
        if args.no_revision:
            call('compare_design_alternatives')
            call('design_cost_scenarios')
            artifacts=export(session,root/'current')
            summary={'record':str(rec.path),'recalled':len(recalled['memories']),
                     'current_outcomes':[c['outcome'] for c in current['comparisons']],
                     'model_called':False,'owner_requirements_changed':False,'artifacts':artifacts}
            rec.log('design_cold_recheck_result',summary=summary,report=session.design_report())
            print(json.dumps(summary))
            return 0 if recalled['memories'] and not current['source_failures'] else 1
        export(session,root/'current')
        call('record_design_requirement',parameter=args.revise_parameter,value=args.revise_value,action='replace',
             rationale='Explicit hypothetical revision for changed-context verification, not a new owner requirement')
        invalidated=session.bom is None and not session.qualifications and not session.decisions
        call('propose_design_architecture',selections_json=choices);call('generate_design_bom')
        changed=call('reverify_design',run_id=args.run.stem)
        export(session,root/'revised')
        rec.log('design_cold_recheck_result',recalled=len(recalled['memories']),current=current,
                hypothetical_revision={'parameter':args.revise_parameter,'value':args.revise_value},
                earlier_verification_invalidated=invalidated,revised=changed,model_called=False)
        summary={'record':str(rec.path),'recalled':len(recalled['memories']),
                 'current_outcomes':[c['outcome'] for c in current['comparisons']],
                 'revised_outcomes':[c['outcome'] for c in changed['comparisons']],
                 'earlier_verification_invalidated':invalidated,'model_called':False,'artifacts':str(root)}
        print(json.dumps(summary))
        if not recalled['memories'] or not invalidated or not all(c['outcome']=='changed_context' for c in changed['comparisons']):
            raise SystemExit(1)


if __name__=='__main__':raise SystemExit(main())
