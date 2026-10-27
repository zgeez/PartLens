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
        if set(s.spec.features)&{'ble','led_matrix','imu','microphone','nfc','temperature','breadboard_power'}:needed.add('logic_voltage')
        if 'led_matrix' in s.spec.features:needed|={'led_rows','led_columns','led_type','led_average_current'}
        if 'nfc' in s.spec.features:needed.add('nfc_mode')
        if 'microphone' in s.spec.features:needed.add('microphone_use')
        if 'rechargeable' in s.spec.features:needed|={'battery_min','battery_max','battery_capacity','runtime','charging_use'}
        if 'breadboard_power' in s.spec.features:
            needed|={'secondary_rail_voltage','input_voltage_min','input_voltage_max','rail_current_max','input_interface'}
        return sorted(k for k in needed if s.spec.get(k) is None)

    def _run_breadboard_interactive(self, dispatch, finish):
        import re
        rec = self.session.recorder
        base_prov = getattr(self.provider, "base", self.provider)
        if hasattr(base_prov, "_inspect"):
            try:
                base_prov._inspect()
            except Exception:
                pass
        dispatch(ToolCall(f"controller-bb-{rec.seq+1}", "start_new_design", {}), "controller")
        dispatch(ToolCall(f"controller-bb-{rec.seq+1}", "design_requirements", {}), "controller")
        desc = self.session.spec.description
        extracted = []
        if m := re.search(r"([0-9]+(?:\.[0-9]+)?)\s*V\s*(?:to|-|\.\.)\s*([0-9]+(?:\.[0-9]+)?)\s*V", desc, re.I):
            extracted.append(("input_voltage_min", f"{m[1]}V", m[0]))
            extracted.append(("input_voltage_max", f"{m[2]}V", m[0]))
        if m := re.search(r"\b(3\.3\s*V)\b", desc, re.I):
            extracted.append(("logic_voltage", m[1].replace(" ", ""), m[0]))
        if m := re.search(r"(?<![0-9.])(5(?:\.0)?\s*V)\b", desc, re.I):
            extracted.append(("secondary_rail_voltage", "5V", m[0]))
        if m := re.search(r"\b([0-9]+(?:\.[0-9]+)?)\s*mA\b", desc, re.I):
            extracted.append(("rail_current_max", f"{m[1]}mA", m[0]))
        if m := re.search(r"\b([0-9]+)\s+(?:prototype\s+|assembled\s+)?boards?\b", desc, re.I):
            extracted.append(("board_quantity", m[1], m[0]))
        if m := re.search(r"\b(usb_c|usb-c|type-c|barrel_jack|barrel jack|dual_input)\b", desc, re.I):
            raw = m[1].casefold().replace("-", "_").replace(" ", "_")
            val = "usb_c" if "c" in raw else ("barrel_jack" if "barrel" in raw else "dual_input")
            extracted.append(("input_interface", val, m[0]))
        if m := re.search(r"\b(jumper_selectable|jumper selectable|fixed_dual_rail|switch_controlled)\b", desc, re.I):
            raw = m[1].casefold().replace("-", "_").replace(" ", "_")
            extracted.append(("rail_selection", raw, m[0]))
        labels = {
            "logic_voltage": "Primary Regulated Rail",
            "secondary_rail_voltage": "Secondary Rail",
            "input_voltage_min": "Minimum Input Voltage",
            "input_voltage_max": "Maximum Input Voltage",
            "rail_current_max": "Max Continuous Load Current",
            "board_quantity": "Build Quantity",
            "input_interface": "DC Input Connector",
            "rail_selection": "Rail Configuration",
        }
        val_labels = {
            "usb_c": "USB-C (5 V)",
            "barrel_jack": "DC Barrel Jack",
            "dual_input": "Dual Input (USB-C + Barrel Jack)",
            "jumper_selectable": "Jumper-selectable (3.3 V / 5 V per rail)",
            "fixed_dual_rail": "Fixed Dual Rail (3.3 V & 5 V)",
            "switch_controlled": "Switch-controlled Rail",
        }
        confirmed_list = []
        for param, val, quote in extracted:
            block = dispatch(ToolCall(f"controller-bb-{rec.seq+1}", "record_design_requirement", {
                "parameter": param, "value": val, "user_quote": quote, "action": "replace",
                "rationale": "Explicit requirement extracted verbatim from operator description"
            }), "controller")
            if block and not block.get("is_error"):
                disp_val = val_labels.get(val, f"{val} boards" if param == "board_quantity" else val)
                confirmed_list.append(f"- **{labels.get(param, param.replace('_', ' ').title())}:** {disp_val}")
        if hasattr(self, "chat_notify"):
            if confirmed_list:
                self.chat_notify("assistant_message",
                    "I've initialized the **Breadboard Power Supply** design (covering USB-C input protection, 3.3 V regulation, dual breadboard output headers, and power status indication) "
                    "and confirmed the specifications stated in your prompt:\n\n" + "\n".join(confirmed_list) + "\n\n"
                    "Before I set provisional defaults for the remaining parameters and run the regulator and thermal checks, "
                    "let's clarify a couple of key configuration choices:")
            else:
                self.chat_notify("assistant_message",
                    "I've initialized the **Breadboard Power Supply** design (covering USB-C input protection, 3.3 V regulation, dual breadboard output headers, and power status indication). "
                    "Let's clarify a couple of high-impact requirements first — you can reply in chat, let me set a provisional default, or leave them unanswered:")
        explicitly_unanswered = set()
        while len(self.questions) < 2 and self.question_gaps():
            if self.should_stop():
                return finish("cancelled by operator")
            gap = self.question_gaps()[0]
            ask_block = dispatch(ToolCall(f"controller-bb-ask-{rec.seq+1}", "ask_user", {"gap_id": gap}), "controller")
            if ask_block and not ask_block.get("is_error"):
                ask_data = json.loads(ask_block["content"])
                if ask_data.get("unanswered") and not ask_data.get("delegated_to_ai") and gap not in self.session.spec.current:
                    explicitly_unanswered.add(gap)
        if self.should_stop():
            return finish("cancelled by operator")
        if self.allow_proposals:
            core_keys = {"logic_voltage", "secondary_rail_voltage", "input_voltage_min", "input_voltage_max",
                         "rail_current_max", "input_interface", "board_quantity"}
            defaults = [
                ("logic_voltage", "3.3V", "Standard 3.3 V primary logic rail"),
                ("secondary_rail_voltage", "5V", "Standard 5 V secondary breadboard rail"),
                ("input_voltage_min", "4.75V", "USB-C VBUS lower operating bound"),
                ("input_voltage_max", "5.25V", "USB-C VBUS upper operating bound"),
                ("rail_current_max", "500mA", "500 mA continuous regulated rail current"),
                ("input_interface", "usb_c", "USB-C 5 V sink input connector"),
                ("rail_selection", "jumper_selectable", "2.54 mm header shunt jumper rail selection"),
                ("width", "53mm", "Standard MB-102 breadboard power-strip span"),
                ("height", "32mm", "Compact plug-in module depth"),
                ("board_quantity", "5", "5 prototype boards"),
                ("parts_budget", "4USD", "Provisional component budget per board"),
            ]
            missing = [{"parameter": k, "value": v, "rationale": r}
                       for k, v, r in defaults
                       if k not in self.session.spec.current and (k in core_keys or k not in explicitly_unanswered)]
            if missing:
                dispatch(ToolCall(f"controller-bb-prop-{rec.seq+1}", "propose_design_requirements", {"requirements": missing}), "controller")
        dispatch(ToolCall(f"controller-bb-pats-{rec.seq+1}", "design_patterns", {}), "controller")
        dispatch(ToolCall(f"controller-bb-sel-{rec.seq+1}", "select_design_patterns", {
            "selections": {
                "input_power": "input_power.usb_c_5v",
                "power": "power.xc6206_ldo",
                "rail_output": "rail_output.breadboard_headers",
                "indicator": "indicator.power_led",
            },
            "justification": "Initial breadboard power supply architecture trial using XC6206P332MR 3.3 V LDO",
        }), "controller")
        comp_block = dispatch(ToolCall(f"controller-bb-comp-{rec.seq+1}", "compare_design_alternatives", {}), "controller")
        options = (self.session.architecture_alternatives or {}).get("alternatives", [])
        tps_alt = next((a for a in options if a.get("selections", {}).get("power") == "power.tps63031" and a["resolved_failures"] and not a["new_failures"]), None)
        if tps_alt:
            if hasattr(self, "chat_notify"):
                # Narrate the recorded check messages; never restate engineering numbers by hand.
                failed = [c for c in self.session.circuit.checks if c.status.value == "fail"]
                resolved = set(tps_alt["resolved_failures"])
                lines = "\n".join(f"  - **{c.check.split('.')[-1].replace('_', ' ').capitalize()}:** {c.message}"
                                  for c in failed)
                boards = self.session.spec.get("board_quantity")
                self.chat_notify("assistant_message",
                    "### Deterministic Architecture & Thermal Evaluation\n"
                    "- **Initial LDO trial (XC6206P332MR) failed these checks:**\n" + lines + "\n"
                    f"- **Bounded correction (research trial):** the controller switched the 3.3 V regulator to **TPS63031DSKR** "
                    f"(buck-boost converter), which resolves {', '.join(sorted(resolved))} without adding a failure. "
                    "The failed LDO trial stays in the design history.\n"
                    "- **BOM & sourcing:** generating component roles, matching official JLCPCB parts, running qualification checks "
                    f"and computing {boards or 'confirmed'}-board vs. hypothetical 60-board cost scenarios…")
            dispatch(ToolCall(f"controller-bb-inv-{rec.seq+1}", "investigate_design_alternative", {"alternative_id": tps_alt["id"]}), "controller")
        for name, needed in [
            ("generate_design_bom", not self.session.bom),
            ("source_design_roles", not self.session.source_attempted),
            ("qualify_design", not self.session.qualification_attempted),
            ("design_cost_scenarios", self.session.costs is None),
            ("remember_design", bool(self.session.memory) and not self.remembered),
        ]:
            if needed:
                dispatch(ToolCall(f"controller-bb-final-{rec.seq+1}", name, {}), "controller")
        return finish()
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
            if actor=="controller":
                allowed|=set(DESIGN_NAMES)|{"ask_user"}
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
                    from .interaction import typed_answer, ai_default_for_gap
                    payload=json.loads(block['content'])
                    answer=payload.get('answer')
                    delegated=bool(payload.get('delegated_to_ai'))
                    if not delegated and isinstance(answer,str) and answer.strip().casefold() in {
                            'auto','ai','let ai decide','let ai set requirement','you decide','propose default','set default','set it yourself'}:
                        delegated=True
                    if delegated and used<self.max_tool_calls:
                        used+=1
                        dval,drat=ai_default_for_gap(self.session.spec,call.input['gap_id'])
                        recorded=self._execute(ToolCall('controller-ai-default-'+str(rec.seq+1),'record_design_requirement',
                            {'parameter':call.input['gap_id'],'value':dval,'user_quote':'',
                             'action':'replace','rationale':drat}),actor='controller')
                        block['content']=json.dumps({**payload,'ai_provisional_default':dval,
                            'controller_recording':json.loads(recorded['content'])})
                        self.remembered=False
                        if hasattr(self,'chat_notify'):
                            pretty_param=call.input['gap_id'].replace('_',' ').title()
                            pretty_val={'usb_c':'USB-C','usb_c_onboard':'onboard USB-C'}.get(dval,dval.replace('_',' '))
                            reason=drat.removeprefix('AI provisional default: ')
                            self.chat_notify('assistant_message',
                                f"I chose **{pretty_val}** for **{pretty_param}** ({reason}). "
                                "This is my assumption, not your requirement, so it stays provisional; "
                                "reply with your own value at any time to confirm or change it.")
                    else:
                        value=typed_answer(call.input['gap_id'],answer) if answer else None
                        if value is not None and used<self.max_tool_calls:
                            used+=1
                            recorded=self._execute(ToolCall('controller-answer-'+str(rec.seq+1),'record_design_requirement',
                                {'parameter':call.input['gap_id'],'value':value,'user_quote':answer,
                                 'action':'replace','rationale':'Explicit typed owner answer to a current question'}),actor='controller')
                            block['content']=json.dumps({**payload,
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
        if "breadboard_power" in self.session.spec.features and origin in {"chat_task", "new_design_task"}:
            return self._run_breadboard_interactive(dispatch, finish)
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
                        if 'breadboard_power' in self.session.spec.features:
                            bb_params=['logic_voltage','secondary_rail_voltage','input_voltage_min','input_voltage_max',
                                       'rail_current_max','input_interface','rail_selection','width','height',
                                       'board_quantity','parts_budget']
                            if tool['name']=='record_design_requirement':
                                tool['input_schema']['properties']['parameter']['enum']=bb_params
                            if tool['name']=='propose_design_requirements':
                                tool['input_schema']['properties']['requirements']['items']['properties']['parameter']['enum']=bb_params
                        if tool['name']=='select_design_patterns':
                            from .patterns import all_patterns
                            schema=tool['input_schema']['properties']['selections']
                            needed=required_blocks(self.session.spec.features)
                            pats=all_patterns(self.session.spec.features)
                            schema['properties']={k:{'type':'string','enum':[p.id for p in pats.values() if p.block==k]}
                                                  for k in schema['properties'] if k in needed}
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
