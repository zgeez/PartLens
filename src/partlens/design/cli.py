"""Operator-owned New Design entry point and append-only artifacts; no remote publication."""

import csv
import io
import json
from pathlib import Path

from ..cli import catalogs_from_args
from ..core.model import to_jsonable
from ..local_provider import OllamaProvider
from ..memory.hmem import HMemBridge, DecisionMemory
from ..optimise.cost import load_fees
from ..records import RunRecorder
from ..sources.audit import AuditedCatalog
from .agent import DesignAgent
from .session import DesignSession


def export(session,root):
    root=Path(root)
    root.mkdir(parents=True,exist_ok=False)
    report=session.design_report()
    report.update({"record":str(session.recorder.path),"export_scope":"preliminary; no schematic/netlist/ERC"})
    for name,value in (("report.json",report),("requirements.json",session.spec.view()),
                       ("circuit.json",session.circuit.view() if session.circuit else None)):
        with (root/name).open('x',encoding='utf-8') as f:json.dump(to_jsonable(value),f,indent=2,ensure_ascii=False)
    if session.interaction_mode:
        from .views import readable_presentation
        with (root/'design-review.md').open('x',encoding='utf-8') as f:
            for name,content in readable_presentation(report).items():
                f.write('## '+name+'\n\n'+content+'\n\n')
    with (root/'bom.csv').open('x',encoding='utf-8',newline='') as f:
        fields=['line','block','role','references','quantity','manufacturer','mpn','supplier_key','package',
                'role_equivalence','application','source','retrieved_at','risks']
        writer=csv.DictWriter(f,fieldnames=fields);writer.writeheader()
        for item in report['bom']:
            p=item.get('component') or {};q=item.get('qualification') or {};r=item['role']
            writer.writerow(dict(zip(fields,[item['line_id'],item['block'],r['name'],','.join(item['refs']),r['quantity'],
                p.get('manufacturer',r['manufacturer']),p.get('mpn',r['mpn']),p.get('key',''),p.get('package',r['package']),
                q.get('status','unverified'),q.get('application_status','unverified'),p.get('source',''),
                p.get('retrieved_at',''),'; '.join(r['omissions'])])))
    return str(root)


def run_new_design(args):
    if getattr(args,'quantity_record',None):
        raise SystemExit('New Design does not import Easyduino quantity provenance')
    rec=RunRecorder.create('.partlens/runs')
    catalogs=catalogs_from_args(args) if args.jlc or args.zetaris or args.catalog else []
    catalogs=[AuditedCatalog(c) for c in catalogs]
    design_id=args.design_id or 'new-'+rec.run_id
    root=Path('.partlens/new-design')/rec.run_id
    if args.allow_proposals:
        rec.log('design_choice_authorization',source='operator --allow-proposals',meaning='defaults remain provisional, not user confirmations')
    with HMemBridge(root/'hmem') as bridge:
        session=DesignSession(rec,catalogs,description=args.idea,design_id=design_id,
            memory=DecisionMemory(bridge,design_id),fees=load_fees(args.fees),engineering_mode=True,interaction_mode=True)
        rec.log('memory_engine',info=bridge.info,process_id=bridge._proc.pid)
        rec.log('cost_configuration',fees=session.fees)
        agent=DesignAgent(session,OllamaProvider(),lambda question:None if args.unattended else (input(question+'\n> ') or None),
                          allow_proposals=args.allow_proposals,max_steps=40,max_tool_calls=80,max_total_tokens=300000)
        result=agent.send('Develop a preliminary electronic design from this product description: '+args.idea,
                          origin='new_design_task')
        print(result)
        artifacts=export(session,root/'artifacts')
        print(json.dumps({'record':str(rec.path),'artifacts':artifacts,'manufacturing_ready':False}))
        if not agent.last_report['controller']['operational_pipeline_complete']:
            raise SystemExit(1)
