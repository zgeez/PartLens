"""One bounded genuine local New Design evaluation. No supplied BOM or final pattern selections."""
import argparse
import json
import os
from pathlib import Path

from partlens.agent import Agent, ScriptedProvider, ToolCall
from partlens.cli import catalogs_from_args, load_env_file
from partlens.design.agent import DesignAgent
from partlens.design.cli import export
from partlens.design.session import DesignSession
from partlens.local_provider import OllamaProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.records import RunRecorder, read_events
from partlens.sources.audit import AuditedCatalog


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--protocol', required=True, choices=['native','json-schema'])
    p.add_argument('--owner-led-record', type=Path, help='Existing local run containing the actual Monochrome reply; historical relay, never fresh')
    p.add_argument('--jlc', action='store_true');p.add_argument('--zetaris', action='store_true')
    args = p.parse_args()
    load_env_file()
    os.environ['PARTLENS_LOCAL_PROTOCOL'] = args.protocol
    rec = RunRecorder.create('.partlens/finalization-runs')
    root = Path('.partlens/finalization')/rec.run_id
    print(json.dumps({'record':str(rec.path),'protocol':args.protocol}), flush=True)
    idea = 'Design a rechargeable smart LED badge with Bluetooth phone control, an LED matrix, NFC, microphone and IMU.'
    cats = [AuditedCatalog(c) for c in catalogs_from_args(args)] if args.jlc or args.zetaris else []
    with HMemBridge(root/'hmem') as bridge:
        s = DesignSession(rec,cats,description=idea,design_id='finalization-'+rec.run_id,
            memory=DecisionMemory(bridge,'finalization-'+rec.run_id),engineering_mode=True,interaction_mode=True)
        rec.log('memory_engine',info=bridge.info,process_id=bridge._proc.pid)
        rec.log('finalization_evaluation',protocol=args.protocol,live_model=True,
            limits={'model_turns':20,'tool_calls':55,'total_tokens':220000},
            owner_delegation_quote='make your own decisions for the design',
            historical_count_context='32 LEDs discussed; not a confirmed target',supplied_bom=False,supplied_selections=False)
        if args.owner_led_record:
            path = args.owner_led_record.resolve()
            if (not path.is_relative_to(Path('.partlens').resolve()) or path.suffix!='.jsonl'
                    or any(x in str(path).casefold() for x in ('experiments','benchmark'))):
                raise ValueError('Only an existing internal run record is allowed')
            event = next(e for e in read_events(path) if e['type']=='user_message' and e.get('text')=='Monochrome'
                         and e.get('origin','user')=='user')
            rec.log('user_message',text='Monochrome',origin='user',input_kind='historical_owner_relay',
                original_record=str(args.owner_led_record),original_seq=event['seq'],fresh_owner_answer=False)
            runner = Agent(s,ScriptedProvider([]),lambda _:None)
            result = runner._execute(ToolCall('historical-owner-led','record_design_requirement',{
                'parameter':'led_type','value':'mono','user_quote':'Monochrome'}),actor='controller')
            if result.get('is_error') or not json.loads(result['content'])['entry']['binding']:
                raise RuntimeError('Historical confirmation could not be restored')
        a = DesignAgent(s,OllamaProvider(),lambda _:None,allow_proposals=True,
            max_steps=20,max_tool_calls=55,max_total_tokens=220000)
        a.send('Develop the preliminary design. The earlier concept discussed 32 LEDs, but the owner has not confirmed '
            'a numeric count or arrangement. The owner says: make your own decisions for the design. '
            'Ask essential questions; absent answers remain unanswered. Proposed choices remain provisional.',origin='operator_evaluation')
        artifacts = export(s,root/'artifacts')
        events = read_events(rec.path)
        turns = [e for e in events if e['type']=='assistant_turn']
        report = a.last_report
        summary = {'record':str(rec.path),'artifacts':artifacts,'protocol':args.protocol,'model_turns':len(turns),
            'provider_errors':[{'type':e.get('error_type'),'message':e.get('message')} for e in events if e['type']=='provider_error'],
            'controller':report['controller'],'acceptance':report['acceptance'],
            'jlc_fresh_successes':sum(e['type']=='jlcpcb_response' and e.get('lookup',{}).get('http_status')==200
                and not e.get('lookup',{}).get('cached') for e in events),
            'zetaris_queries':sum(e['type']=='zetaris_query' for e in events)}
        rec.log('finalization_evaluation_result',summary=summary)
        print(json.dumps(summary),flush=True)
    return 0 if report['controller']['operational_pipeline_complete'] else 1


if __name__=='__main__':raise SystemExit(main())
