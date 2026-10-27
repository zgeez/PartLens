"""Bounded New Design controller over the existing provider, strict tool registry and dispatch journal."""

from __future__ import annotations

from collections import Counter
import json
import time

from ..agent import Agent, ToolCall
from ..core.model import to_jsonable
from ..records import output_digest
from ..secrets import redact
from ..tools import DESIGN_NAMES
from .requirements import QUESTIONS
from .patterns import required_blocks

SYSTEM = """You are PartLens, a preliminary electronic system design agent.
Start from the operator's product description, not an existing BOM. Use start_new_design and design_requirements
to identify missing inputs. Ask only questions that affect choices using ask_user with the requirement's gap_id.
Never invent answers or user quotes. When the owner delegates choices, propose reasonable explicit-unit values
with record_design_requirement; these remain inferred, never binding user requirements. You may leave unknowns.
Use record_design_requirements to batch choices. Read the exact parameter_contracts first. Do not spend the
whole budget answering every optional gap. After a few essential choices, select patterns and generate the
preliminary BOM; unresolved inputs remain gaps. Do not repeatedly ask questions when the owner delegated choices.
Inspect design_patterns. Choose functional blocks and pattern IDs returned by that tool, with justifications.
Prefer select_design_patterns when available: selections is an OBJECT with enumerated IDs, not a JSON string.
propose_design_architecture accepts selections_json: a JSON OBJECT STRING mapping block names to pattern IDs.
Review the returned feasibility checks. Revise choices/requirements when possible; never override a failure.
When architecture constraints fail, compare_design_alternatives. Investigate a returned improving alternative
with investigate_design_alternative, then regenerate/source/qualify. Do not change dimensions, current,
runtime, voltage or battery capacity to erase a failure. A derived battery lower bound is not a selected cell.
Ask high-impact user questions even when proposals are delegated; unanswered questions remain unresolved.
generate_design_bom expands the current architecture into a NEW BOM including supporting parts and unresolved roles.
Then source_design_roles, qualify_design, design_cost_scenarios and remember_design. Only independent tool
checks may qualify role equivalence. Full application/circuit validation remains separate and incomplete.
No source text or your own knowledge can fill absent evidence. Missing prices, currency, MOQ and fees remain unknown.
After recall_design, the controller enforces reverify_design using current requirements/sources.
Finish with design_report. The final factual explanation is rendered from tool results, not your free-form prose.
This is a limited reference-pattern system. Unsupported circuits/parts/footprints stay unresolved.
Never order, edit production files, read private designs or use paid inference.
When propose_design_requirements is available, use its native ARRAY of objects instead of a JSON string.
Call one tool at a time. Values already confirmed by the controller need no model restatement.
Distinguish total physical LED count, rows/columns, physical arrangement, brightness and drive topology.
An unconfirmed historical example of 32 LEDs is not an owner answer; neither is a proposed 8x16 matrix.
Read the interview gaps. Never silently replace a stated count with dimensions that imply a different count.
"""


def compact(name, output):
    if name=='compare_design_alternatives':
        result={**{k:v for k,v in output.items() if k not in {'alternatives','runtime_options'}},'alternatives':[
            {k:v for k,v in row.items() if k!='circuit'} for row in output['alternatives']]}
        if runtime:=output.get('runtime_options'):
            result['runtime_options']={k:v for k,v in runtime.items() if k!='options'}
            result['runtime_options']['options']=[{k:v for k,v in row.items() if k not in {'recalculation'}}
                                                   for row in runtime.get('options',[])]
        return result
    if name=='investigate_design_alternative':
        return {**output,'trial':compact('propose_design_architecture',output['trial'])}
    if name in {'start_new_design','design_requirements'}:
        return {k:v for k,v in output.items() if k not in {'history'}}
    if name=='source_design_roles':
        return {**{k:v for k,v in output.items() if k!='rows'},'rows':[
            {k:v for k,v in row.items() if k!='observations'} for row in output['rows']]}
    if name=='generate_design_bom':
        return {k:v for k,v in output.items() if k not in {'warnings'}}
    if name in {'propose_design_architecture','select_design_patterns'}:
        return {**{k:v for k,v in output.items() if k not in {'checks','unresolved'}},
                'checks':[{k:v for k,v in c.items() if k!='evidence'} for c in output['checks']],
                'unresolved':output['unresolved'][:12]}
    if name=='qualify_design':
        return {'qualifications':[{'line':q['line'],'status':q['status'],'application_status':q['application_status'],
                'gaps':[c['message'] for c in q.get('checks',[]) if c['status']!='pass'][:3]} for q in output['qualifications']],
                'architecture':compact('propose_design_architecture',output['architecture']),
                'manufacturing_ready':False}
    if name=='design_cost_scenarios':
        return {'complete':False,'note':output.get('note',output.get('reason')),
                'scenarios':[{'boards':s['boards'],'scenario':s['scenario'],'component_subtotal':s['cost']['parts_total'],
                    'total':s['cost']['total'],'problems':s['cost']['problems'][:8]} for s in output.get('scenarios',[])]}
    return output


def render(report: dict) -> str:
    req=report['requirements']
    arch=report.get('architecture') or {}
    lines=["PartLens / New Design — PRELIMINARY",f"Design: {req['design_id']} | requirements revision {req['revision']}",
           "Generated from requirements and selected patterns; no existing BOM imported." if report.get('bom_origin') else
           "Design generation incomplete: no BOM generated; no existing BOM imported.",
           "Not manufacturing-ready. No validated schematic, electrical netlist or ERC output.",
           "\nRequirements:"]
    for key,item in req['requirements'].items():
        lines.append(f"  {key}: {item['value']} {item['unit'] or ''} | {item['state']} | {item['source']}")
    lines.append("\nArchitecture:")
    for block,pid in arch.get('selections',{}).items():lines.append(f"  {block}: {pid}")
    if report.get('acceptance'):
        lines.append('Final acceptance: '+report['acceptance']['status']+' | accepted: '+str(report['acceptance']['accepted']))
    if report.get('alternatives'):
        lines.append('\nArchitecture alternatives (research trials, not accepted designs):')
        for a in report['alternatives']['alternatives']:
            lines.append(f"  {a['name']}: remaining failures {a['failed_constraints']}; resolved {a['resolved_failures']}; accepted {a['acceptance']['accepted']}")
        for remedy in report['alternatives']['energy_remedies']:lines.append('  Energy remedy: '+json.dumps(remedy))
    lines.append("\nFeasibility checks (conditional on proposed values):")
    for c in arch.get('checks',[]):
        lines.append(f"  {c['status'].upper()}: {c['check']} — {c['message']}")
        for e in c['evidence']:lines.append("    "+e['locator'])
    lines.append("\nGenerated BOM:")
    for row in report.get('bom',[]):
        role=row['role']; part=row.get('component')
        q=row.get('qualification') or {}
        identity=f"{part['manufacturer']} {part['mpn']} | {part['key']}" if part else "UNRESOLVED component identity"
        lines.append(f"  {row['line_id']} {','.join(row['refs'])} x{role['quantity']} | {row['block']}.{role['name']} | {identity}")
        lines.append(f"    role equivalence: {q.get('status','unverified')} | application: {q.get('application_status','unverified')}")
        if part:lines.append(f"    {part['source']} | retrieved {part['retrieved_at']}")
    lines.append("\nCost scenarios:")
    for scenario in (report.get('costs') or {}).get('scenarios',[]):
        cost=scenario['cost']
        lines.append(f"  {scenario['boards']} boards | {scenario['scenario']} | component subtotal: {cost['parts_total']} "
                     f"| assembled: {cost['total']} | complete: {cost['complete']}")
        lines.extend("    "+p for p in cost['problems'])
    lines.append("\nUnresolved requirements / provisional assumptions:")
    lines.extend(f"  {g['id']}: {g['state']} — {g['question']}" for g in req['gaps'])
    lines.append("\nImplementation omissions:")
    lines.extend("  "+s for s in arch.get('unresolved',[]))
    lines.extend(["\n"+report['explanation'],"Memory persistence is reported separately from current qualification."])
    if controller:=report.get('controller'):
        lines.append("Controller stop: "+str(controller['stop_reason'])+" | operations complete: "+str(controller['operational_pipeline_complete']))
    return "\n".join(lines)


class DesignAgent(Agent):
    def __init__(self,session,provider,ask,*,allow_proposals=False,should_stop=None,**budgets):
        super().__init__(session,provider,ask,system=SYSTEM,tool_names=DESIGN_NAMES|{"ask_user"},**budgets)
        self.allow_proposals=allow_proposals
        self.questions=set()
        self.requirements_seen=False
        self.patterns_seen=False
        self.remembered=False
        self.pending_recall=None
        self.requested_recall=None
        self.recall_done=False
        self.last_report=None
        self.should_stop=should_stop or (lambda:False)
        self.design_cycles=0
        self.compared=False
        self.investigated=False

    def permitted(self):
        s=self.session
        proposal='select_design_patterns' if s.engineering_mode else 'propose_design_architecture'
        if not s.started:return {"start_new_design"}
        batch='propose_design_requirements' if s.interaction_mode else 'record_design_requirements'
        base={"design_requirements","record_design_requirement",batch,"design_patterns"}
        if not self.allow_proposals:base.add('ask_user')
        if not self.requirements_seen:return {"design_requirements"}
        if s.engineering_mode:
            if len(self.questions)<2 and self.question_gaps():
                # Requirements were already returned; repeating that read can strand the interview.
                return {'ask_user'} if s.interaction_mode else {'design_requirements','ask_user'}
            if s.circuit and not self.compared:return {'compare_design_alternatives'}
            if s.circuit and self.compared and not self.investigated:
                rows=(s.architecture_alternatives or {}).get('alternatives',[])
                if any(a['resolved_failures'] and not a['new_failures'] and a['selections']!=s.circuit.selections for a in rows):
                    return {'investigate_design_alternative'}
        # Bounded revision is not a requirement that all constraints pass. Preserve failed checks and
        # generate the honest preliminary role BOM instead of silently weakening evidence to finish.
        if self.design_cycles>=2 and s.circuit:
            if not s.bom:return {'generate_design_bom','design_requirements'}
            if not s.source_attempted:return {'source_design_roles'}
            if not s.qualification_attempted:return {'qualify_design'}
            if s.costs is None:return {'design_cost_scenarios'}
            if s.memory and not self.remembered:return {'remember_design'}
            return {'design_report','recall_design'}
        if not self.allow_proposals and len(self.questions)<min(3,len(s.spec.gaps())):
            return {"design_requirements","ask_user"}
        if self.patterns_seen and not s.circuit:
            if self.allow_proposals and self.core_missing():
                return {'design_requirements','record_design_requirement',batch}
            return {proposal,'design_requirements'}
        if self.patterns_seen:base.add(proposal)
        if s.circuit:base.add("generate_design_bom")
        if s.bom:base|={"source_design_roles","recall_design"}
        if s.source_attempted:base.add("qualify_design")
        if s.qualification_attempted:
            base|={"design_cost_scenarios","remember_design","reverify_design"}
            if s.costs is not None and (self.remembered or not s.memory):base.add("design_report")
        return base

    def question_gaps(self):
        if self.session.interaction_mode:
            from .interaction import clarification_plan
            return [g['id'] for g in clarification_plan(self.session.spec,self.session.circuit)
                    if g['id'] not in self.questions][:3]
        gaps={g['id'] for g in self.session.spec.gaps()}-self.questions
        priority=['runtime','led_type','nfc_mode','microphone_use','battery_capacity','board_quantity','width','parts_budget']
        return [key for key in priority if key in gaps][:3] or sorted(gaps)[:3]

    def core_missing(self):
        s=self.session
        needed={'board_quantity'}
        if set(s.spec.features)&{'ble','led_matrix','imu','microphone','nfc','temperature'}:needed.add('logic_voltage')
        if 'led_matrix' in s.spec.features:needed|={'led_rows','led_columns','led_type','led_average_current'}
        if 'nfc' in s.spec.features:needed.add('nfc_mode')
        if 'microphone' in s.spec.features:needed.add('microphone_use')
        if 'rechargeable' in s.spec.features:needed|={'battery_min','battery_max','battery_capacity','runtime','charging_use'}
        return sorted(k for k in needed if s.spec.get(k) is None)

    def send(self,text: str,*,origin="user",recall_run: str | None=None):
        rec=self.session.recorder
        self.requested_recall=recall_run
        rec.log("design_task",text=text,origin=origin,allow_proposals=self.allow_proposals,
                recall_run=recall_run,model_supplied_architecture=False,model_supplied_bom=False)
        self.messages.append({"role":"user","content":text+
            (" Owner delegated design choices: propose values, but never mark defaults user-confirmed." if self.allow_proposals else "")})
        used,tokens=0,0
        repeated=Counter()
        def finish(reason=None):
            report=self.session.design_report()
            steps_complete=bool(
                    self.session.bom and self.session.source_attempted and self.session.qualification_attempted
                    and self.session.costs is not None and (self.remembered or not self.session.memory))
            report['controller']={"stop_reason":reason,"tools_executed":used,"total_tokens":tokens,
                "questions_attempted":sorted(self.questions),"workflow_steps_complete":steps_complete,
                "operational_pipeline_complete":bool(steps_complete and self.session.observed_parts and self.session.memory_records),
                "exact_sourced_roles":report.get('sourcing_counts',{}).get('exact_role_matches',sum(bool(p) for p in self.session.baseline.values())),
                "supplier_identified_roles":sum(bool(p) for p in self.session.baseline.values()),
                "persisted_decisions":len(self.session.memory_records)}
            if self.session.interaction_mode:self.session.workflow_status=report['controller']
            self.last_report=to_jsonable(report)
            rendered=render(self.last_report)
            rec.log("design_agent_result",report=self.last_report,rendered=rendered,
                    context_digest=self.session.context_digest())
            return rendered
        def dispatch(call,actor="model"):
            nonlocal used
            signature=output_digest({"name":call.name,"input":call.input})
            repeated[signature]+=1
            if used>=self.max_tool_calls or repeated[signature]>self.max_repeated_calls:return None
            used+=1
            allowed=self.permitted()
            if actor=="controller" and self.session.bom and call.name in {"recall_design","reverify_design"}:
                allowed.add(call.name)
            if call.name not in allowed:
                output={"error":"Design prerequisite missing", "permitted":sorted(allowed)}
                rec.log("tool_call",name=call.name,call_id=call.id,input=call.input,output=output,
                        error=output['error'],controller_blocked=True,actor=actor,deterministic=False)
                return {"type":"tool_result","tool_use_id":call.id,"content":json.dumps(output),"is_error":True}
            if call.name=="ask_user":
                gap=call.input.get('gap_id')
                if gap not in {g['id'] for g in self.session.spec.gaps(interview=self.session.interaction_mode)} or gap in self.questions:
                    output={'error':'ask a current, unasked requirement gap','available':self.question_gaps()}
                    rec.log('tool_call',name=call.name,call_id=call.id,input=call.input,output=output,
                        error=output['error'],controller_blocked=True,actor=actor,deterministic=False)
                    return {"type":"tool_result","tool_use_id":call.id,"content":json.dumps(output),"is_error":True}
                self.questions.add(gap)
                # The controller asks the requirement's own question, not an arbitrary model-proposed premise.
                call=ToolCall(call.id,call.name,{"gap_id":gap,"question":QUESTIONS[gap]})
            try:
                block=self._execute(call,actor=actor)
            except Exception as exc:
                if call.name!='ask_user':raise
                block={"type":"tool_result","tool_use_id":call.id,"content":json.dumps({"unanswered":True,"error_type":type(exc).__name__}),"is_error":True}
            if not block.get('is_error'):
                if call.name=='ask_user' and self.session.interaction_mode:
                    from .interaction import typed_answer
                    answer=json.loads(block['content']).get('answer')
                    value=typed_answer(call.input['gap_id'],answer) if answer else None
                    if value is not None and used<self.max_tool_calls:
                        used+=1
                        recorded=self._execute(ToolCall('controller-answer-'+str(rec.seq+1),'record_design_requirement',
                            {'parameter':call.input['gap_id'],'value':value,'user_quote':answer,
                             'action':'replace','rationale':'Explicit typed owner answer to a current question'}),actor='controller')
                        block['content']=json.dumps({**json.loads(block['content']),
                            'controller_recording':json.loads(recorded['content'])})
                        self.remembered=False
                if call.name=='design_requirements':self.requirements_seen=True
                if call.name=='design_patterns':self.patterns_seen=True
                if call.name in {'propose_design_architecture','select_design_patterns'}:self.design_cycles+=1;self.compared=False
                if call.name=='compare_design_alternatives':self.compared=True
                if call.name=='investigate_design_alternative':self.investigated=True;self.design_cycles+=1
                if call.name in {'record_design_requirement','record_design_requirements','propose_design_requirements','propose_design_architecture','select_design_patterns','generate_design_bom','investigate_design_alternative'}:self.remembered=False
                if call.name=='remember_design':self.remembered=True
                if call.name=='recall_design':self.pending_recall=call.input['run_id']
                view=compact(call.name,json.loads(block['content']))
                rec.log('model_tool_view',call_id=call.id,actor=actor,content=view)
                block['content']=json.dumps(view,ensure_ascii=False)
            return block
        for step in range(self.max_steps):
            if self.should_stop():return finish('cancelled by operator')
            if self.requested_recall and self.session.bom and not self.recall_done:
                block=dispatch(ToolCall('controller-recall-'+str(rec.seq+1),'recall_design',{'run_id':self.requested_recall}),'controller')
                self.recall_done=True
                if block is None:return finish('budget during requested recall')
                self.messages.append({'role':'user','content':'Controller performed requested actual recall: '+block['content']})
            if self.pending_recall:
                block=dispatch(ToolCall('controller-'+str(rec.seq+1),'reverify_design',{'run_id':self.pending_recall}),'controller')
                self.pending_recall=None
                if block is None:return finish('tool budget during mandatory recall recheck')
                self.messages.append({'role':'user','content':'Controller executed mandatory current recheck (not a model call): '+block['content']})
            if self.session.engineering_mode and self.session.circuit and self.compared:
                options=(self.session.architecture_alternatives or {}).get('alternatives',[])
                improving=any(a['resolved_failures'] and not a['new_failures'] and a['selections']!=self.session.circuit.selections for a in options)
                if self.investigated or not improving:
                    rec.log('controller_terminal_pipeline',reason='bounded architecture proposal/comparison completed; execute mandatory evidence/check/cost operations without more inference',actor='controller')
                    for name,needed in [('generate_design_bom',not self.session.bom),('source_design_roles',not self.session.source_attempted),
                            ('qualify_design',not self.session.qualification_attempted),('design_cost_scenarios',self.session.costs is None),
                            ('remember_design',bool(self.session.memory) and not self.remembered)]:
                        if needed:
                            block=dispatch(ToolCall('controller-final-'+str(rec.seq+1),name,{}),'controller')
                            if block is None or block.get('is_error'):return finish('mandatory terminal operation failed or budget exhausted')
                    return finish()
            if self.session.qualification_attempted and self.session.costs is not None and (self.remembered or not self.session.memory):
                rec.log('controller_finalize',reason='all preliminary workflow steps attempted; retain failed checks and missing evidence',actor='controller')
                return finish()
            if tokens>=self.max_total_tokens:return finish('token budget')
            allowed=self.permitted()
            state={"permitted":sorted(allowed),"revision":self.session.spec.revision,
                   "required_blocks":sorted(required_blocks(self.session.spec.features)),
                   "core_missing_for_delegated_scenario":self.core_missing() if self.allow_proposals else [],
                   "question_gaps_available":self.question_gaps(),"questions_already_attempted":sorted(self.questions),
                   "next":"Inspect gaps, propose requirements with units, inspect patterns, select blocks, generate, source, qualify, cost, remember, report."}
            if self.session.interaction_mode:
                from .interaction import clarification_plan
                state['question_priorities']=clarification_plan(self.session.spec,self.session.circuit)[:6]
            self.messages.append({'role':'user','content':'Controller state: '+json.dumps(state)})
            try:
                started=time.perf_counter()
                available_tools=[t for t in self.tools if t['name'] in allowed]
                if self.session.engineering_mode:
                    from copy import deepcopy
                    available_tools=deepcopy(available_tools)
                    for tool in available_tools:
                        if tool['name']=='ask_user':tool['input_schema']['properties']['gap_id']['enum']=self.question_gaps()
                        if tool['name']=='select_design_patterns':
                            schema=tool['input_schema']['properties']['selections']
                            needed=required_blocks(self.session.spec.features)
                            schema['properties']={k:v for k,v in schema['properties'].items() if k in needed}
                            schema['required']=sorted(schema['properties'])
                turn=self.provider.next_turn(self.system,self.messages,available_tools)
            except Exception as exc:
                rec.log('provider_error',error_type=type(exc).__name__,message=redact(str(exc)))
                return finish('provider failure: '+type(exc).__name__)
            tokens+=sum(v for k in ('input','output') if type(v:=turn.usage.get(k)) is int and v>=0)
            rec.log('assistant_turn',text=turn.text,usage=turn.usage,stop_reason=turn.stop_reason,
                    latency_ms=round((time.perf_counter()-started)*1000),
                    tool_calls=[{'id':c.id,'name':c.name,'input':c.input} for c in turn.tool_calls])
            self.messages.append({'role':'assistant','content':turn.assistant_content})
            if not turn.tool_calls:
                if 'design_report' in allowed:return finish()
                self.messages.append({'role':'user','content':'Workflow incomplete; continue required tools or leave explicit unresolved results. Do not invent completion.'})
                continue
            blocks=[]
            final_requested=False
            for call in turn.tool_calls:
                block=dispatch(call)
                if block is None:return finish('tool/repetition budget')
                blocks.append(block)
                if call.name=='design_report' and not block.get('is_error'):final_requested=True
            self.messages.append({'role':'user','content':blocks})
            if final_requested:return finish()
        return finish('model-turn budget')
