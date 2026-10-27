"""New Design state reuses existing source, compatibility, cost and decision-memory implementations."""

from __future__ import annotations

from collections import Counter
from dataclasses import replace
from decimal import Decimal
import json

from ..checks.compat import check_substitute, check_application, check_availability
from ..core.bom import Bom, BomLine, normalise_mpn
from ..core.model import Evidence, EvidenceKind, digest, to_jsonable
from ..core.parts import PartRecord
from ..optimise.cost import AssemblyFees, CostInputs, estimate
from ..records import output_digest
from ..session import Session, ToolError, _cost_view, part_view
from ..sources.catalog import record_from_row
from .architecture import Circuit, propose, check_circuit
from .patterns import PATTERNS, library, all_patterns, get_pattern
from .requirements import Requirements, State, parse, FIELDS


class DesignSession(Session):
    def __init__(self, recorder, catalogs, *, description: str, design_id: str | None = None, memory=None, fees=None,
                 _record_description: bool = True, engineering_mode: bool = False, interaction_mode: bool = False):
        super().__init__(recorder,catalogs,memory=memory,fees=fees)
        if not description.strip() or len(description)>5000:
            raise ValueError("product description must be 1..5000 characters")
        self.design_name=design_id or "new-"+recorder.run_id
        if _record_description:
            recorder.log("user_message",text=description,origin="user",input_kind="new_design_description")
        self.spec=Requirements(self.design_name,description,f"user:{recorder.run_id}#seq{recorder.seq}")
        self.circuit: Circuit | None=None
        self.qualifications={}
        self.source_attempted=False
        self.qualification_attempted=False
        self.costs=None
        self.memory_records=[]
        self.started=False
        self.source_failures=[]
        self.engineering_mode=engineering_mode
        self.interaction_mode=interaction_mode
        self.workflow_status=None
        self.design_history=[]
        self.architecture_alternatives=None
        self.correction_attempts=0
        self.sourcing_history=[]
        if memory is not None and memory.design!=self.design_name:
            raise ValueError("New Design memory must be scoped to this design ID")
        if _record_description:
            recorder.log("new_design_start",description=description,design_id=self.design_name,
                         description_source=self.spec.description_source,schema="partlens.requirements/1")
        if engineering_mode:recorder.log('design_engineering_mode',version=2)
        if interaction_mode:recorder.log('design_interaction_mode',version=1)

    def _preserve_revision(self,reason):
        if self.engineering_mode and self.circuit:
            snapshot={'reason':reason,'circuit':self.circuit.view(),'qualification':to_jsonable(self.qualifications),
                      'requirements_fingerprint':self.circuit.requirements_fingerprint}
            self.design_history.append(snapshot)
            self.recorder.log('design_revision_preserved',snapshot=snapshot)

    def compare_design_alternatives(self):
        if not self.circuit:raise ToolError('propose a current architecture first')
        from .iteration import alternatives
        self.architecture_alternatives=alternatives(self.spec,self.circuit)
        if self.interaction_mode:
            from .interaction import runtime_options
            self.architecture_alternatives['runtime_options']=runtime_options(self.spec,self.circuit)
        return self.architecture_alternatives

    def investigate_design_alternative(self,alternative_id: str):
        if not self.architecture_alternatives or self.architecture_alternatives['requirements_fingerprint']!=self.spec.fingerprint:
            raise ToolError('compare alternatives for the current requirements first')
        if self.correction_attempts>=2:raise ToolError('bounded correction budget exhausted')
        row=next((a for a in self.architecture_alternatives['alternatives'] if a['id']==alternative_id),None)
        if not row:raise ToolError('unknown alternative identifier')
        if row['selections']==self.circuit.selections:raise ToolError('alternative must change an architecture block')
        if row['new_failures'] or not row['resolved_failures']:
            raise ToolError('alternative does not resolve a recorded failure without adding a new failure')
        self.correction_attempts+=1
        self.propose_design_architecture(json.dumps(row['selections']),justification='Bounded research trial: '+', '.join(row['resolved_failures']))
        return {'trial':self._architecture_summary(),'accepted_design':False,'requirements_changed':False,
                'reason':'Research only; all acceptance gaps are retained'}

    def _invalidate_design(self):
        self.workflow_status=None
        self._preserve_revision('requirements changed; all dependent current results invalidated')
        self.architecture_alternatives=None
        old={"bom":self.bom_fingerprint,"decisions":list(self.decisions)}
        self.circuit=None
        self.bom=None
        self.bom_fingerprint=None
        self.baseline.clear()
        self.decisions.clear()
        self.alternatives.clear()
        self.observed_parts.clear()
        self.qualifications.clear()
        self.source_attempted=False
        self.qualification_attempted=False
        self.costs=None
        self.memory_records=[]
        self.source_failures=[]
        self.recorder.log("design_invalidated",new_revision=self.spec.revision,previous=old)

    def start_new_design(self):
        self.started=True
        return self.design_requirements()

    def design_requirements(self):
        result={**self.spec.view(),"gaps":self.spec.gaps(interview=self.interaction_mode),
                "parameter_contracts":{k:{"domain":domain,"unit_or_allowed_values":kind} for k,(domain,kind) in FIELDS.items()},
                "rule":"Agent defaults are proposed scenario values, never user-confirmed requirements."}
        if self.interaction_mode:
            from .interaction import clarification_plan
            result['clarification_plan']=clarification_plan(self.spec,self.circuit)
        return result

    def record_design_requirements(self,requirements_json: str):
        try:
            rows=json.loads(requirements_json)
            if not isinstance(rows,list) or not 1<=len(rows)<=24:
                raise ValueError("requirements_json must contain 1..24 objects")
            allowed={'parameter','value','user_quote','intent','action','rationale'}
            for row in rows:
                if (not isinstance(row,dict) or set(row)-allowed or not {'parameter','value'}<=set(row)
                        or any(not isinstance(v,str) for v in row.values())):
                    raise ValueError("each requirement needs string parameter/value and only supported optional fields")
                parse(row['parameter'],row['value'])
                if row.get('intent','proposal') not in {'proposal','optional'} or row.get('action','append') not in {'append','replace'}:
                    raise ValueError("invalid intent/action")
        except (ValueError,TypeError) as exc:
            raise ToolError(str(exc)) from None
        return {'recorded':[self.record_design_requirement(**row) for row in rows],
                'revision':self.spec.revision,'note':'All agent-proposed defaults remain provisional.'}

    def propose_design_requirements(self,requirements: list[dict]):
        if not isinstance(requirements,list) or any(not isinstance(r,dict) for r in requirements):
            raise ToolError('requirements must be a native array of objects')
        if len({r.get('parameter') for r in requirements})!=len(requirements):
            raise ToolError('propose each parameter at most once per batch')
        if any(set(r)-{'parameter','value','rationale'} for r in requirements):
            raise ToolError('only provisional parameter/value/rationale fields are allowed')
        return self.record_design_requirements(json.dumps(requirements))

    def record_design_requirement(self,parameter: str,value: str,user_quote: str="",intent: str="proposal",action: str="append",rationale: str=""):
        if intent not in {"proposal","optional"} or action not in {"append","replace"}:
            raise ToolError("invalid requirement intent/action")
        source,status=self._find_user_quote(user_quote)
        try:
            parse(parameter,value)
            old=self.spec.current.get(parameter)
            if self.interaction_mode and old and old.binding and parse(parameter,value)[0]==old.value:
                from copy import deepcopy
                preview=deepcopy(self.spec).record(parameter,value,source=source,quote=user_quote,
                    confirmed=status.value=='user_confirmed',replace=True)
                if not preview.binding:
                    return {'entry':{**to_jsonable(old),'binding':True},'revision':self.spec.revision,
                            'retained':'Existing owner confirmation preserved; a model restatement does not replace provenance'}
            if self.engineering_mode and old and parse(parameter,value)[0]!=old.value and (old.binding or self.circuit or self.design_history):
                from copy import deepcopy
                preview=deepcopy(self.spec).record(parameter,value,source=source,quote=user_quote,
                    confirmed=status.value=='user_confirmed',replace=True)
                if not preview.binding:
                    raise ToolError('Changing an established design target requires a new actual user answer; do not weaken constraints to clear a failure')
            confirmed=status.value=="user_confirmed"
            if confirmed:
                # Preserve the existing binding-requirement gate as well as the new typed-unit gate.
                confirmed=Session.record_requirement(self,"design",parameter,"==",value,user_quote=user_quote)['binding']
            entry=self.spec.record(parameter,value,source=source,quote=user_quote,
                confirmed=confirmed,optional=intent=="optional",replace=action=="replace",rationale=rationale)
        except ValueError as exc:
            raise ToolError(str(exc)) from None
        self._invalidate_design()
        return {"entry":{**to_jsonable(entry),"binding":entry.binding},"revision":self.spec.revision,
                "invalidated":"previous circuit/BOM/qualification/cost state; audit and memory history retained"}

    def design_patterns(self):
        # Compact model view; full reviewed role definitions remain in library() and exported circuit records.
        return {"schema":"partlens.patterns/1","patterns":[{
            "id":p.id,"block":p.block,"function":p.function,"reference":p.reference,
            "reviewed_reference":p.reviewed,"hardware_validated":False,"supply":p.supply,
            "support_roles":[r.name for r in p.roles],"omissions":p.omissions}
            for p in (all_patterns() if self.engineering_mode else PATTERNS).values()]}

    def propose_design_architecture(self,selections_json: str,justification: str=""):
        try:
            choices=json.loads(selections_json)
            if not isinstance(choices,dict) or any(not isinstance(k,str) or not isinstance(v,str) for k,v in choices.items()):
                raise ValueError("selections_json must be an object mapping required block names to pattern IDs")
            self._preserve_revision('architecture replaced; dependent verification invalidated')
            self.circuit=propose(self.spec,choices,{k:justification for k in choices})
            if self.engineering_mode:
                from .completion import reviewed_roles
                reviewed_roles(self.circuit)
                self._check_circuit()
        except (ValueError,TypeError) as exc:
            raise ToolError(str(exc)) from None
        self.bom=None
        self.bom_fingerprint=None
        self.qualifications.clear()
        self.decisions.clear()
        self.baseline.clear()
        self.alternatives.clear()
        self.source_attempted=False
        self.qualification_attempted=False
        self.costs=None
        self.memory_records=[]
        self.observed_parts.clear()
        return self._architecture_summary()

    def select_design_patterns(self,selections: dict,justification: str=''):
        from .patterns import required_blocks
        if self.engineering_mode and set(selections)!=required_blocks(self.spec.features):
            raise ToolError('Include all required blocks using exact IDs: '+', '.join(sorted(required_blocks(self.spec.features))))
        return self.propose_design_architecture(json.dumps(selections),justification)

    def _check_circuit(self):
        check_circuit(self.spec,self.circuit)
        if self.engineering_mode:
            from .validation import validate
            validate(self.spec,self.circuit)

    def _architecture_summary(self):
        if not self.circuit:
            raise ToolError("propose an architecture first")
        return {"schema":"partlens.circuit/1","fingerprint":self.circuit.fingerprint,
                "requirements_revision":self.spec.revision,"selected_patterns":self.circuit.selections,
                "rails":self.circuit.rails,"buses":self.circuit.buses,"assignments":self.circuit.assignments,
                "checks":to_jsonable(self.circuit.checks),"estimates":self.circuit.estimates,
                "roles":len(self.circuit.roles),"unresolved":self.circuit.unresolved,
                "status":"preliminary","manufacturing_ready":False}

    def generate_design_bom(self):
        if not self.circuit or self.circuit.requirements_fingerprint!=self.spec.fingerprint:
            raise ToolError("a current architecture is required before BOM generation")
        self._check_circuit()
        if any(c.check.startswith('support.') and c.status.value=='fail' for c in self.circuit.checks):
            raise ToolError("required circuit support roles are missing; regenerate the architecture")
        lines=[]
        for row in self.circuit.roles:
            source=f"generated://{self.design_name}/{self.spec.revision}/{row.block}/{row.role.name}"
            ev=Evidence(EvidenceKind.CALCULATION,source,"component_role",row.role.value,
                        excerpt="Expanded from selected reviewed pattern roles; not an imported BOM")
            lines.append(BomLine(row.line_id,row.refs,row.role.quantity,row.role.value,row.role.package,
                row.role.mpn or None,row.role.manufacturer or None,row.role.codes[0] if row.role.codes else None,
                row.block+": "+row.role.name,False,len(lines)+1,ev,
                tuple(g for g in ("identity unresolved" if not row.role.mpn else "",
                                 "land pattern unresolved" if not row.role.package else "") if g)))
        self.bom=Bom(self.design_name,"generated://"+self.circuit.fingerprint,lines,
                     ["Preliminary generated role BOM; not manufacturing-ready or a validated circuit"])
        self.bom_fingerprint=self.circuit.fingerprint
        self.baseline.clear()
        self.qualifications.clear()
        self.decisions.clear()
        self.alternatives.clear()
        self.source_attempted=False
        self.qualification_attempted=False
        self.costs=None
        return {"schema":"partlens.design-bom/1",**self.describe_design(),"origin":"generated_from_patterns",
                "imported_bom":False,"manufacturing_ready":False,"requirements_revision":self.spec.revision}

    def source_design_roles(self):
        self._need_bom()
        from .completion import ROLE_LEADS
        def leads(row):return ROLE_LEADS.get((row.block,row.role.name),()) if self.engineering_mode else ()
        codes=sorted({code for row in self.circuit.roles for code in (*row.role.codes,*(c for c,_ in leads(row)))})
        if len(codes)>25:
            raise ToolError("design research exceeds bounded explicit-code limit")
        self.source_attempted=True
        failures=[]
        for catalog in self.catalogs:
            try:
                if prepare:=getattr(catalog,"prepare",None):prepare(codes)
            except Exception as exc:
                failures.append({"catalogue":catalog.name,"error_type":type(exc).__name__})
        rows=[]
        for row in self.circuit.roles:
            chosen=None
            attempted=[]
            candidates=[]
            for code in (*row.role.codes,*(c for c,_ in leads(row))):
                for catalog in self.catalogs:
                    key=f"{getattr(catalog,'bom_supplier','lcsc')}:{code}"
                    try:
                        part=catalog.get(key)
                    except Exception as exc:
                        failures.append({"line":row.line_id,"catalogue":catalog.name,"error_type":type(exc).__name__})
                        continue
                    if part:
                        self.observed_parts[part.key]=part
                        attempted.append(part_view(part))
                        exact=(row.role.mpn and normalise_mpn(part.mpn)==normalise_mpn(row.role.mpn)
                                and part.manufacturer.casefold().strip()==row.role.manufacturer.casefold().strip())
                        lead=any(c==code and normalise_mpn(mpn)==normalise_mpn(part.mpn) for c,mpn in leads(row))
                        if self.engineering_mode:
                            decision=check_substitute(self._line(row.line_id),self._reference(row),part)
                            candidates.append({'candidate':part.key,'identity_matches':bool(exact or lead),
                                'status':decision.status.value,'checks':to_jsonable(decision.checks),
                                'source':part.source,'note':'Supplier lead identity is not independent manufacturer qualification'})
                            if decision.status.value=='rejected':continue
                        if exact or lead:
                            chosen=part
                            break
                if chosen:break
            self.baseline[row.line_id]=chosen
            rows.append({"line":row.line_id,"role":row.block+"."+row.role.name,
                         "selected":chosen.key if chosen else None,"observations":attempted,
                         "status":"source_found" if chosen else "unresolved",
                         "note":"Exact identity required; catalogue availability is not engineering qualification."})
            if self.engineering_mode:rows[-1]['candidate_evaluations']=candidates
        self.source_failures=failures
        if self.engineering_mode:self.sourcing_history.append({'circuit_fingerprint':self.circuit.fingerprint,'rows':rows,'failures':failures})
        return {"explicit_codes":codes,"rows":rows,"failures":failures,
                "supplier_calls_attempted":bool(codes and self.catalogs)}

    def _reference(self,row):
        role=row.role
        source=role.reference or (row.evidence.locator if row.evidence else "unknown")
        reviewed_at=('2026-10-24' if role.reference and any(name in role.reference for name in ('CL10A475KO8NNN','CL05A105KA5NQN'))
                     else '2026-10-23' if role.reference else row.evidence.retrieved_at if row.evidence else None)
        return record_from_row({"supplier":"reference","supplier_pn":row.line_id,
            "manufacturer":role.manufacturer,"mpn":role.mpn,"category":role.category,"package":role.package,
            "source":source,"retrieved_at":reviewed_at,"params":{
                k:{"value":v,"evidence":{"kind":"datasheet","locator":source,"retrieved_at":reviewed_at}}
                for k,v in role.parameters}})

    def qualify_design(self):
        self._need_bom()
        if not self.source_attempted:
            raise ToolError("attempt current sourcing before qualification")
        self.qualification_attempted=True
        self.qualifications.clear()
        self.decisions.clear()
        boards=self.spec.get("board_quantity")
        for row in self.circuit.roles:
            part=self.baseline.get(row.line_id)
            if not part:
                self.qualifications[row.line_id]={"line":row.line_id,"status":"unverified",
                    "checks":[],"application_status":"unverified","reason":"no exact sourced component identity",
                    "support_roles_complete":False}
                continue
            reference=self._reference(row)
            line=self._line(row.line_id)
            decision=check_substitute(line,reference,part)
            app=check_application(line,reference,part,[])
            self.decisions[decision.id]=decision
            self.qualifications[row.line_id]={"line":row.line_id,"status":decision.status.value,
                "decision_id":decision.id,"checks":to_jsonable(decision.checks),
                "application_status":app.status.value,"application_checks":to_jsonable(app.checks),
                "scope":"equivalence to the selected role/reference; does not qualify the complete circuit",
                "sourcing":to_jsonable(check_availability(part,row.role.quantity*boards,now=self._now())) if boards else [],
                "quantity_scenario":"user_confirmed" if self.spec.current.get('board_quantity') and
                    self.spec.current['board_quantity'].binding else "provisional_hypothetical"}
        return {"qualifications":list(self.qualifications.values()),"architecture":self._architecture_summary(),
                "manufacturing_ready":False,"note":"Even verified role equivalence does not establish application/board qualification."}

    def design_cost_scenarios(self):
        self._need_bom()
        boards=self.spec.get("board_quantity")
        if not boards:
            self.costs={"complete":False,"reason":"quantity unresolved; no cost invented"}
            return self.costs
        entry=self.spec.current["board_quantity"]
        scenarios=[]
        for quantity,label in ((boards,"user_confirmed" if entry.binding else "provisional_hypothetical"),(60,"hypothetical")):
            report=estimate(self.bom,self.baseline,CostInputs(quantity,self.fees or AssemblyFees(),now=self._now()))
            scenarios.append({"boards":quantity,"scenario":label,"quantity_source":entry.source,
                              "cost":_cost_view(report),"official_nominal_price_observations":self._official_price_observations(quantity)})
        self.costs={"scenarios":scenarios,"complete":False,
                    "note":"Not a manufacturing quotation. Proposed quantities never become confirmed owner requirements."}
        return self.costs

    def _memory_context(self):
        semantics={k:{"value":to_jsonable(e.value),"unit":e.unit,"state":e.state.value} for k,e in self.spec.current.items()}
        return {"schema":"partlens.design-memory/1","design":self.design_name,
                "requirements_sha256":digest(semantics),"circuit":self.circuit.fingerprint if self.circuit else None,
                "pattern_versions":{b:get_pattern(p).version for b,p in self.circuit.selections.items()} if self.circuit else {}}

    def remember_design(self):
        if not self.memory:
            return {"stored":[],"reason":"actual H-MEM unavailable"}
        if not self.qualification_attempted:
            raise ToolError("qualify current roles before remembering decisions")
        stored=[]
        for decision in self.decisions.values():
            row=self.memory.remember(decision,run_id=self.recorder.run_id,context=self._memory_context(),
                reason="Generated role/reference check only; entire circuit remains preliminary")
            stored.append({"memory_id":row['id'],"decision_id":decision.id,"source":row['source']})
        self.memory_records=stored
        return {"stored":stored,"design_id":self.design_name,"context":self._memory_context()}

    def recall_design(self,run_id: str):
        if not self.memory:
            return {"memories":[],"reason":"actual H-MEM unavailable"}
        return {"memories":self.memory.search("generated design decisions",run_id=run_id),
                "note":"Historical context only. The controller must call reverify_design for this run."}

    def reverify_design(self,run_id: str):
        if not self.memory:
            raise ToolError("actual H-MEM unavailable")
        memories=self.memory.search("generated design decisions",run_id=run_id)
        if not self.bom:
            raise ToolError("generate the current design BOM before recalling qualification")
        # Actual supplier reads again; the existing catalogue controls cache age and provenance.
        sourcing=self.source_design_roles()
        self.qualify_design()
        comparisons=[]
        for memory in memories:
            actual=self.memory.read_decision(memory["id"])
            refs=(actual.get("provenance") or {}).get("refs") or []
            details=json.loads(refs[1]) if len(refs)>1 else {}
            old=details.get("context")
            current=self.qualifications.get(memory.get("line"))
            context_matches=bool(old and old==self._memory_context())
            # A changed candidate must never inherit the old result, even if requirements match.
            matching=next((d for d in self.decisions.values() if d.subject==memory.get("line") and
                           d.candidate==memory.get("candidate") and d.original==memory.get("original")),None)
            outcome=("changed_context" if not context_matches else "cannot_reverify" if not matching or
                     matching.status.value=="unverified" else "unchanged" if matching.status.value==details.get("status") else "changed")
            comparisons.append({"memory_id":memory["id"],"source":memory["source"],"outcome":outcome,
                "context_matches":context_matches,"current_status":current.get("status") if current else "unverified",
                "fresh_checks_executed":True})
        return {"comparisons":comparisons,"source_failures":sourcing['failures'],"manufacturing_ready":False}

    def design_report(self):
        rows=[]
        if self.circuit:
            for row in self.circuit.roles:
                part=self.baseline.get(row.line_id)
                rows.append({**to_jsonable(row),"component":part_view(part) if part else None,
                             "qualification":self.qualifications.get(row.line_id),
                             "source_status":"source_found" if part else "required_role_unresolved"})
        result={"schema":"partlens.design-report/1","mode":"new_design","requirements":self.design_requirements(),
                "architecture":self.circuit.view() if self.circuit else None,"bom_origin":"generated_from_patterns" if self.bom else None,
                "bom":rows,"qualifications_current":self.qualification_attempted,"costs":self.costs,
                "source_failures":self.source_failures,
                "memory":self.memory_records,"manufacturing_ready":False,"hardware_validated":False,
                "explanation":("Generated preliminary component roles from the recorded product requirements and selected reference patterns. "
                    if self.bom else "No component BOM has been generated in the current context. ")+
                    "Verified role equivalence is separate from application safety. Missing support parts, evidence, operating "
                    "conditions, commercial terms and pin-level connections prevent a manufacturing-ready design.",
                "connectivity_output":"tool-independent named port/net intent only; no schematic, netlist or ERC output"}
        if self.engineering_mode:
            from .validation import acceptance
            from .completion import role_inventory
            result.update({'engineering_version':2,'architecture_history':self.design_history,
                'alternatives':self.architecture_alternatives,'role_inventory':role_inventory(self.circuit) if self.circuit else [],
                'sourcing_history':self.sourcing_history,
                'acceptance':acceptance(self.spec,self.circuit,self.qualifications) if self.circuit else {'accepted':False,'status':'no_architecture'}})
            result['sourcing_counts']={'supplier_identified_roles':sum(bool(p) for p in self.baseline.values()),
                'exact_role_matches':sum(bool(p and r.role.mpn and normalise_mpn(p.mpn)==normalise_mpn(r.role.mpn)
                    and p.manufacturer.strip().casefold()==r.role.manufacturer.strip().casefold())
                    for r in self.circuit.roles if (p:=self.baseline.get(r.line_id))) if self.circuit else 0}
        if self.interaction_mode:
            from .interaction import sourcing_triage
            result['interaction_version']=1
            result['sourcing_triage']=sourcing_triage(result)
            if self.workflow_status:result['controller']=self.workflow_status
        return result

    def context_digest(self):
        if not hasattr(self,"spec"):
            return super().context_digest()
        return output_digest({"design":self.spec.fingerprint,"circuit":self.circuit.fingerprint if self.circuit else None,
                              "baseline":self.baseline})

    def restore_quantity(self,path):
        raise ToolError("New Design never restores the Easyduino quantity; use design-specific user provenance")

    def _boards(self):
        if not hasattr(self,'spec'):return None
        entry=self.spec.current.get('board_quantity')
        return entry.value if entry and entry.binding else None
