"""New operations use the shared registry and argument validation, not model-authored verdicts."""

from .requirements import ALL_FIELDS


def tools(Tool, obj):
    from .patterns import all_patterns
    patterns=all_patterns(('breadboard_power',))
    selection_schema=obj({block:{'type':'string','enum':[p.id for p in patterns.values() if p.block==block]}
        for block in {p.block for p in patterns.values()}},[])
    empty=lambda:obj({},[])
    return [
        Tool('propose_design_requirements','Propose a bounded batch of explicit-unit requirements as a native array of objects. All values remain provisional; never overwrite owner-confirmed choices or invent user quotations.',
             obj({'requirements':{'type':'array','minItems':1,'maxItems':24,'items':obj({
                 'parameter':{'type':'string','enum':list(ALL_FIELDS)},'value':{'type':'string'},
                 'rationale':{'type':'string'}},['parameter','value'])}},['requirements']),
             lambda s,requirements:s.propose_design_requirements(requirements)),
        Tool('select_design_patterns','Select the architecture using exact enumerated pattern IDs. Supply selections as an object, including all required blocks. Independent checks expose unsupported requirements; never change a target merely to clear a failure.',
             obj({'selections':selection_schema,'justification':{'type':'string'}},['selections']),lambda s,**a:s.select_design_patterns(**a)),
        Tool('compare_design_alternatives','Compare bounded reviewed architecture alternatives with unchanged requirements. Returns independent checks and unresolved acceptance gates; never invent a battery or relax a target.',
             empty(),lambda s:s.compare_design_alternatives()),
        Tool('investigate_design_alternative','Start a new research trial from a compared alternative ID that resolves a recorded failure without introducing a new one. Invalidates prior BOM/checks. This does not accept a final design.',
             obj({'alternative_id':{'type':'string'}},['alternative_id']),lambda s,alternative_id:s.investigate_design_alternative(alternative_id)),
        Tool("start_new_design","Initialize the operator-supplied product description, never import a prior BOM.",
             empty(),lambda s:s.start_new_design()),
        Tool("design_requirements","Read versioned requirements, binding provenance and missing questions.",
             empty(),lambda s:s.design_requirements()),
        Tool("record_design_requirement","Record one value with explicit units. Exact user_quote is checked against actual "
             "user messages; invented/default values remain inferred. Revision invalidates previous circuit/BOM/checks.",
             obj({"parameter":{"type":"string","enum":list(ALL_FIELDS)},"value":{"type":"string"},
                  "user_quote":{"type":"string"},"intent":{"type":"string","enum":["proposal","optional"]},
                  "action":{"type":"string","enum":["append","replace"]},"rationale":{"type":"string"}},
                 ["parameter","value"]),lambda s,**a:s.record_design_requirement(**a)),
        Tool("design_patterns","List the limited reviewed pattern options, required supporting roles and omissions. "
             "A reviewed reference is not a validated implementation.",empty(),lambda s:s.design_patterns()),
        Tool("record_design_requirements","Record a batch of proposed or genuinely quoted requirements efficiently. "
             "requirements_json is a JSON ARRAY STRING of objects with parameter and value strings; optional user_quote, "
             "intent, action, rationale. Use parameter_contracts from design_requirements for exact units/enums. "
             "Defaults remain inferred. Do not fill every gap before preliminary architecture generation.",
             obj({"requirements_json":{"type":"string"}},["requirements_json"]),
             lambda s,requirements_json:s.record_design_requirements(requirements_json)),
        Tool("propose_design_architecture","Choose pattern IDs by required block using a JSON object string. "
             "Example shape only: selections_json maps block names to IDs returned by design_patterns. "
             "Deterministic feasibility checks expose failures and uncertainty; no model status is accepted.",
             obj({"selections_json":{"type":"string"},"justification":{"type":"string"}},["selections_json"]),
             lambda s,**a:s.propose_design_architecture(**a)),
        Tool("generate_design_bom","Expand the current selected patterns into a new component-role BOM, including "
             "support parts and unresolved roles. This does not import or optimize an existing BOM.",
             empty(),lambda s:s.generate_design_bom()),
        Tool("source_design_roles","Bounded explicit-code supplier research for the generated roles through configured "
             "catalogues. Keep missing identities, stock and prices unknown. Does not qualify engineering.",
             empty(),lambda s:s.source_design_roles()),
        Tool("qualify_design","Run the existing independent compatibility/application/sourcing checks for current roles "
             "and show architecture constraints. No manufacturing-ready verdict is possible from incomplete evidence.",
             empty(),lambda s:s.qualify_design()),
        Tool("design_cost_scenarios","Use existing Decimal cost engine for the recorded quantity and hypothetical 60. "
             "Agent-proposed quantities are labeled provisional hypothetical; unknown prices/fees stay unknown.",
             empty(),lambda s:s.design_cost_scenarios()),
        Tool("remember_design","Persist current generated-role decisions through actual Meterless H-MEM with design context.",
             empty(),lambda s:s.remember_design(),deterministic=False),
        Tool("recall_design","Retrieve actual historical H-MEM decisions by run in the current design; reverification required.",
             obj({"run_id":{"type":"string"}},["run_id"]),lambda s,run_id:s.recall_design(run_id),deterministic=False),
        Tool("reverify_design","Read actual memories, retrieve current applicable supplier evidence, rerun independent "
             "checks and compare requirements/identity context. Changed requirements never inherit verification.",
             obj({"run_id":{"type":"string"}},["run_id"]),lambda s,run_id:s.reverify_design(run_id),deterministic=False),
        Tool("design_report","Return the authoritative current generated-design report. Model narrative does not set facts.",
             empty(),lambda s:s.design_report(),deterministic=False),
    ]
