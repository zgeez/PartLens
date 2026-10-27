"""The PartLens tool registry: one definition per tool, shared by the agent and (later) the Cirquill MCP server.

Tools marked ``deterministic`` compute their result only from their inputs and the session's sources; they are
re-executed on replay. ``ask_user`` is special: the agent loop routes it to the user interface.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from .session import Session, ToolError

S = "string"


def _obj(props: dict[str, Any], required: list[str]) -> dict[str, Any]:
    return {"type": "object", "properties": props, "required": required, "additionalProperties": False}


@dataclass(frozen=True)
class Tool:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Any] | None   # (session, **input) -> JSON-able; None for ask_user
    deterministic: bool = True


TOOLS: list[Tool] = [
    Tool("import_bom", "Import a BOM CSV (KiCad or JLCPCB style export) and describe it.",
         _obj({"path": {"type": S}, "name": {"type": S}}, ["path"]),
         lambda s, path, name=None: s.import_bom(path, name)),
    Tool("describe_design", "Describe the loaded design: BOM lines, categories, packages, identities, issues.",
         _obj({}, []), lambda s: s.describe_design()),
    Tool("match_parts", "Resolve every placed BOM line to a catalogue record (supplier part number, then exact MPN).",
         _obj({}, []), lambda s: s.match_parts()),
    Tool("find_missing_information",
         "List information that is missing for verification or costing, with why it matters and a suggested "
         "question. Deterministic; use it to decide what to ask.",
         _obj({}, []), lambda s: s.find_missing_information()),
    Tool("ask_user", "Ask the user one targeted question and wait for the answer.",
         _obj({"question": {"type": S}, "gap_id": {"type": S}}, ["question"]), None, deterministic=False),
    Tool("record_requirement",
         "Record a requirement. Put the user's exact words that state it in user_quote; it becomes user_confirmed "
         "only if that text appears verbatim in the user's messages, otherwise it is provisional and not binding. "
         "subject is 'design' or a BOM line id. Parameters: board_quantity, applied_voltage, supply_voltage_max, "
         "voltage_rating, derating_factor, or a part parameter name.",
         _obj({"subject": {"type": S}, "parameter": {"type": S},
               "op": {"type": S, "enum": [">=", "<=", "==", "one_of", "covers"]},
               "value": {"type": S}, "user_quote": {"type": S}, "rationale": {"type": S}},
              ["subject", "parameter", "op", "value", "user_quote"]),
         lambda s, **kw: s.record_requirement(**kw), deterministic=False),
    Tool("list_requirements", "List recorded requirements with provenance and whether each is binding.",
         _obj({}, []), lambda s: s.list_requirements()),
    Tool("search_candidates", "Search the catalogues for alternatives in the same category and package as a line.",
         _obj({"line_id": {"type": S}, "text": {"type": S}, "limit": {"type": "integer"}}, ["line_id"]),
         lambda s, line_id, text=None, limit=10: s.search_candidates(line_id, text, limit)),
    Tool("get_part", "Full catalogue record of a part: parameters with evidence, price breaks, stock, source.",
         _obj({"key": {"type": S}}, ["key"]), lambda s, key: s.part_details(key)),
    Tool("check_substitute",
         "Run the deterministic compatibility checks for replacing a line's original part with a candidate. "
         "Returns verified / rejected / unverified with per-check evidence, plus earlier decisions recalled from "
         "memory. Status qualifies original-specification equivalence; application qualification is separate. "
         "Run this even when application voltages are unknown; missing evidence returns unverified rather than "
         "preventing the tool call. "
         "Only this tool can verify a substitute.",
         _obj({"line_id": {"type": S}, "candidate_key": {"type": S}}, ["line_id", "candidate_key"]),
         lambda s, line_id, candidate_key: s.check_substitute(line_id, candidate_key)),
    Tool("check_availability", "Sourcing checks for a part on a line at the recorded board quantity: data freshness, "
         "stock, lifecycle, price.",
         _obj({"part_key": {"type": S}, "line_id": {"type": S}}, ["part_key", "line_id"]),
         lambda s, part_key, line_id: s.check_availability(part_key, line_id)),
    Tool("recall_decisions", "Search engineering decision memory (Meterless H-MEM). Supply run_id for exact "
         "design-scoped lookup by stored source when recalling a known run; otherwise query is approximate text search.",
         _obj({"query": {"type": S}, "run_id": {"type": S}}, ["query"]),
         lambda s, query, run_id=None: s.recall_decisions(query, run_id), deterministic=False),
    Tool("reverify_decision", "Read an actual H-MEM decision by memory_id, validate design/BOM/identity/requirements, "
         "retrieve current applicable supplier evidence and rerun deterministic checks. Returns unchanged, changed, "
         "changed_context or cannot_reverify. Required after recall; memory alone never qualifies a replacement.",
         _obj({"memory_id": {"type": S}}, ["memory_id"]),
         lambda s, memory_id: s.reverify_decision(memory_id), deterministic=False),
    Tool("estimate_cost", "Assembled cost of the current selection at the recorded board quantity, with derivations.",
         _obj({}, []), lambda s: s.estimate_cost()),
    Tool("optimise_cost", "Choose among verified substitutes to minimise assembled cost; explains each line.",
         _obj({}, []), lambda s: s.optimise_cost()),
    Tool("compare_cost_scenarios", "Compare the confirmed owner quantity with an explicitly hypothetical build; "
         "preserves requirements and reports incomplete manufacturing totals and excluded candidates.",
         _obj({"hypothetical_boards": {"type": "integer", "minimum": 1}}, []),
         lambda s, hypothetical_boards=60: s.compare_cost_scenarios(hypothetical_boards)),
]

from .design.registry import tools as _design_tools

TOOLS += _design_tools(Tool, _obj)
BY_NAME = {t.name: t for t in TOOLS}


DESIGN_NAMES = {t.name for t in _design_tools(Tool, _obj)}


def anthropic_tools(names: set[str] | None = None) -> list[dict[str, Any]]:
    selected = names if names is not None else set(BY_NAME) - DESIGN_NAMES
    return [{"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in TOOLS if t.name in selected]


def run_tool(session: Session, name: str, args: dict[str, Any]) -> Any:
    tool = BY_NAME.get(name)
    if tool is None or tool.handler is None:
        raise KeyError(name)
    validate_arguments(tool, args)
    return tool.handler(session, **args)


def validate_arguments(tool: Tool, args: dict[str, Any]) -> None:
    """Enforce the small registry schema before dispatch; invalid model arguments never execute."""
    schema = tool.input_schema
    props = schema["properties"]
    error = None
    if not isinstance(args, dict):
        error = "arguments must be an object"
    elif unknown := set(args) - set(props):
        error = f"unsupported keys {sorted(unknown)}"
    elif missing := set(schema["required"]) - set(args):
        error = f"missing required keys {sorted(missing)}"
    else:
        for key, value in args.items():
            rule = props[key]
            if ((rule["type"] == "string" and not isinstance(value, str))
                    or (rule["type"] == "integer" and type(value) is not int)
                    or ("enum" in rule and value not in rule["enum"])
                    or ("minimum" in rule and type(value) is int and value < rule["minimum"])):
                error = f"invalid value for {key}"
                break
    if error:
        expected = ", ".join(f"{key}: {value['type']}" for key, value in props.items()) or "no keys; use {}"
        raise ToolError(f"{tool.name}: {error}. Allowed arguments: {expected}. Retry using the tool schema.")
