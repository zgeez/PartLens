"""Small evidence-driven workflow gate around the existing single-model tool loop."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from dataclasses import dataclass, field
from typing import Any

from .records import output_digest


@dataclass(frozen=True)
class WorkflowRequest:
    bom_path: str
    design: str = "easyduino-rp2040"
    lines: tuple[str, ...] = ()
    research: bool = True
    costs: bool = False
    recall_run: str | None = None
    clarify_electrical: bool = False
    require_memory: bool = True
    desired_outcomes: tuple[str, ...] = ("verified", "rejected", "unverified")
    max_recoveries: int = 5


@dataclass
class WorkflowController:
    request: WorkflowRequest
    calls: list[dict] = field(default_factory=list)
    recoveries: int = 0

    def observe(self, name: str, args: dict, output: Any, error: bool, *, actor: str = "model") -> None:
        self.calls.append({"name": name, "input": args, "output": output, "error": error, "actor": actor})
        # A reimport or changed requirement invalidates completion as well as the session's decisions.
        if not error and name == "import_bom":
            self.calls = [self.calls[-1]]
        elif not error and name == "record_requirement" and args.get("parameter") != "board_quantity":
            self.calls = [c for c in self.calls if c["name"] not in {
                "check_substitute", "reverify_decision", "estimate_cost", "optimise_cost", "compare_cost_scenarios"}]

    def successful(self, name: str) -> list[dict]:
        return [c for c in self.calls if c["name"] == name and not c["error"]]

    def memories(self) -> list[dict]:
        return [m for c in self.successful("recall_decisions") for m in c["output"].get("memories", [])]

    def pending_rechecks(self) -> list[dict]:
        done = {c["input"]["memory_id"] for c in self.successful("reverify_decision")}
        return [m for m in self.memories() if m["id"] not in done]

    def snapshot(self, session) -> dict:
        req = self.request
        lines = req.lines or tuple(p.id for p in session.bom.placed_lines) if session.bom else req.lines
        matched = [line for line in lines if session.baseline.get(line)]
        gaps = [g for c in self.successful("find_missing_information") for g in c["output"].get("gaps", [])]
        needed = [g for g in gaps if req.costs and g["id"] == "design.board_quantity" and session._boards() is None or
                  req.clarify_electrical and g["subject"] in lines and
                  g["id"].endswith((".applied_voltage", ".supply_voltage_max")) and
                  not (session.requirements.get(g["id"]) and session.requirements[g["id"]].binding)]
        asked = {c["input"].get("gap_id") for c in self.calls if c["name"] == "ask_user" and
                 (not c["error"] or c["output"].get("unanswered"))}
        unasked = [g for g in needed if g["id"] not in asked]
        unanswered = [c["input"].get("gap_id") or "unmapped_question" for c in self.calls if c["name"] == "ask_user"
                      and c["output"].get("unanswered")]
        unrecorded = [g["id"] for g in needed if g["id"] in asked and g["id"] not in unanswered]
        searches = {c["input"]["line_id"] for c in self.successful("search_candidates")}
        checks = [c["output"] for c in self.successful("check_substitute")
                  if c["output"].get("decision_id") in session.decisions]
        checked = {d["line"] for d in checks}
        statuses = {d["status"] for d in checks if d["candidate"] != d["original"]}
        investigate = [c for c in self.successful("check_substitute") if c["output"].get("status") in {
            "rejected", "unverified"}]
        rechecks = [c["output"] for c in self.successful("reverify_decision")]
        unavailable_rechecks = [r for r in rechecks if not r.get("current_decision")]
        states = []
        def state(name, ready, complete, prerequisites, permitted, evidence, reason="", required=True):
            states.append({"id": name, "status": "not_required" if not required else "complete" if complete else
                           "pending" if ready else "blocked", "prerequisites": prerequisites,
                           "permitted_tools": permitted if ready and not complete and required else [], "evidence": evidence,
                           "failure_reason": reason if not complete else ""})
        imported = bool(self.successful("import_bom")) and bool(session.bom)
        requirements = bool(self.successful("find_missing_information"))
        supplier = bool(self.successful("match_parts"))
        state("import", True, imported, [], ["import_bom"], [session.bom_fingerprint] if imported else [],
              "Import the requested BOM", True)
        state("requirements", imported, requirements, ["import"], ["find_missing_information", "list_requirements"],
              [g["id"] for g in gaps], "Identify missing requirements")
        state("clarification", requirements, not unasked and not unrecorded and requirements, ["requirements"],
              ["ask_user", "record_requirement", "list_requirements"], {"unanswered": unanswered, "unrecorded": unrecorded},
              "Ask required questions; do not invent answers")
        state("supplier", imported and requirements, supplier, ["import", "requirements"], ["match_parts", "get_part"],
              {"matched": matched, "unmatched": [l for l in lines if l not in matched]}, "Retrieve supplier evidence")
        state("discovery", supplier, all(l in searches for l in lines), ["supplier"], ["search_candidates", "get_part"],
              sorted(searches), f"Search independently for alternatives on {sorted(set(lines)-searches)}", req.research)
        state("checks", supplier, bool(lines) and all(l in checked for l in lines), ["supplier", "discovery"],
              ["check_substitute", "get_part", "search_candidates", "check_availability"],
              [d["decision_id"] for d in checks],
              f"Run check_substitute NOW on {sorted(set(lines)-checked)}. Missing application voltages are NOT "
              "a prerequisite for original-specification equivalence checks. Choose a candidate from each line's "
              "actual search results and call the tool; it returns unverified when required evidence is absent. "
              "Do not infer or refuse its verdict. Keep full application qualification unknown.", req.research)
        missing_outcomes = set(req.desired_outcomes) - statuses
        state("investigation", bool(checks), not missing_outcomes, ["checks"],
              ["search_candidates", "check_substitute"],
              {"observed": sorted(statuses), "missing": sorted(missing_outcomes)},
              f"Investigate other retrieved candidates for {sorted(missing_outcomes)} outcomes if supported. "
              "Never force a verdict. Search limit 10 without a text filter; inspect contrasting ratings.", req.research)
        sourced = {c["input"]["line_id"] for c in self.successful("check_availability")}
        state("sourcing", supplier and session._boards() is not None, all(l in sourced for l in matched) and bool(matched),
              ["supplier", "clarification"], ["check_availability"], sorted(sourced),
              f"Check sourcing for original parts on {sorted(set(matched)-sourced)} at the confirmed quantity", req.costs)
        compared = any([(s.get("boards"), s.get("scenario")) for s in c["output"].get("scenarios", [])] ==
                       [(session._boards(), "owner_confirmed"), (60, "hypothetical")]
                       for c in self.successful("compare_cost_scenarios"))
        state("costs", supplier and session._boards() is not None,
              compared, ["supplier", "clarification"],
              ["check_availability", "compare_cost_scenarios", "estimate_cost", "optimise_cost"],
              [c["name"] for c in self.calls if c["name"] in {"compare_cost_scenarios", "estimate_cost"}],
              "Compare the confirmed quantity and explicitly hypothetical 60 boards; unknown fees stay unknown", req.costs)
        state("persistence", bool(checks), bool(checks) and all(d.get("stored_in_memory") for d in checks),
              ["checks"], ["check_substitute"], [d.get("stored_in_memory") for d in checks],
              "Persist decisions in the configured real memory engine", req.research and req.require_memory)
        recalled = self.successful("recall_decisions")
        state("recall", supplier, bool(recalled and self.memories()), ["supplier"], ["recall_decisions"],
              [m["source"] for m in self.memories()], "Recall actual decisions from the requested preceding run", bool(req.recall_run))
        state("reverification", bool(self.memories()), bool(self.memories()) and not self.pending_rechecks()
              and not unavailable_rechecks, ["recall"], ["reverify_decision"],
              [{k: r.get(k) for k in ("memory_id", "source", "outcome", "context_matches")} for r in rechecks],
              "Every retrieved decision requires an actual current check, context comparison and an explicit outcome",
              bool(req.recall_run) or bool(self.memories()))
        missing = [s["id"] for s in states if s["status"] in {"pending", "blocked"}]
        for current in states:
            current["permitted_transitions"] = ([s["id"] for s in states if current["id"] in s["prerequisites"]]
                                                if current["status"] in {"complete", "not_required"} else
                                                [current["id"], "partial_result"])
        return {"states": states, "missing_actions": missing, "operations_complete": not missing,
                "unanswered_questions": unanswered, "unasked_questions": unasked,
                "unrecorded_answers": unrecorded,
                "unmatched_requested_lines": [line for line in lines if line not in matched],
                "scope": "preliminary original-specification research; application and complete costs may remain unknown",
                "recoveries": self.recoveries, "call_evidence_digest": output_digest(self.calls)}

    def guidance(self, session) -> str:
        snap = self.snapshot(session)
        next_state = next((s for s in snap["states"] if s["status"] == "pending"), None)
        focus = next_state or next((s for s in snap["states"] if s["status"] == "blocked"), None)
        if focus:
            unchecked = []
            choices = self.line_choices(session, "check_substitute")
            checked = {(c["input"].get("line_id"), c["input"].get("candidate_key"))
                       for c in self.successful("check_substitute")}
            for call in self.successful("search_candidates"):
                for candidate in call["output"].get("candidates", []):
                    if ((call["input"]["line_id"], candidate["key"]) not in checked and
                            (choices is None or call["input"]["line_id"] in choices)):
                        unchecked.append({"line": call["input"]["line_id"], "key": candidate["key"],
                                          "parameters": candidate["params"]})
            return ("WORKFLOW CONTROLLER: " + focus["id"] + ": " + focus["failure_reason"] + "\n" +
                    (f"check_substitute is restricted to line_id in {choices}; other lines will not execute.\n"
                     if choices is not None else "") +
                    json.dumps({"missing_actions": snap["missing_actions"], "focus_evidence": focus["evidence"],
                                "unasked_questions": snap["unasked_questions"],
                                "bom_path": self.request.bom_path, "design": self.request.design,
                                "recall_run": self.request.recall_run,
                                "unchecked_retrieved_candidates": unchecked if focus["id"] == "investigation" else []}, ensure_ascii=False) +
                    "\nContinue with actual tool calls. Do not claim missing steps succeeded. "
                    "A question without an owner answer remains unresolved. Do not choose an outcome yourself.")
        return ('Operations addressed. Finish with JSON references only: {"decision_refs": ["actual decision_id"], '
                '"gap_refs": ["actual gap id"]}. Do not supply quantities, prices, statuses or factual prose; '
                'the authoritative renderer explains the tool results. No supplier transaction has occurred.')

    def permitted(self, session) -> set[str]:
        snap = self.snapshot(session)
        if snap["states"][0]["status"] != "complete":
            return {"import_bom"}
        if snap["states"][1]["status"] != "complete":
            return {"find_missing_information", "list_requirements"}
        if snap["unasked_questions"] or snap["unrecorded_answers"]:
            return {"ask_user", "record_requirement", "list_requirements"}
        if not self.successful("match_parts"):
            return {"match_parts", "get_part"}
        focus = next((s for s in snap["states"] if s["status"] == "pending"), None)
        if focus:
            tools = set(focus["permitted_tools"])
            if focus["id"] in {"checks", "persistence"}:
                return {"check_substitute"}
            if focus["id"] == "discovery":
                return {"search_candidates"}
            if focus["id"] == "costs":
                return {"compare_cost_scenarios"}
            return tools
        return set()

    def line_choices(self, session, tool_name: str) -> list[str] | None:
        snapshot = self.snapshot(session)
        focus = next((s for s in snapshot["states"] if s["status"] == "pending"), None)
        stages = {"check_substitute": "checks", "search_candidates": "discovery", "check_availability": "sourcing"}
        if focus and focus["id"] == "investigation" and tool_name == "check_substitute":
            # Bounded breadth: repeatedly checking one uncertain IC cannot crowd out other researched lines.
            lines = self.request.lines or tuple(p.id for p in session.bom.placed_lines)
            tried = {(c["input"]["line_id"], c["input"]["candidate_key"]) for c in self.successful("check_substitute")}
            available = {c["input"]["line_id"] for c in self.successful("search_candidates")
                         if any((c["input"]["line_id"], p["key"]) not in tried for p in c["output"]["candidates"])}
            counts = {line: sum(c["input"].get("line_id") == line for c in self.successful("check_substitute"))
                      for line in lines if line in available}
            return [line for line, count in counts.items() if count == min(counts.values())] if counts else []
        if not focus or stages.get(tool_name) != focus["id"]:
            return None
        lines = self.request.lines or tuple(p.id for p in session.bom.placed_lines)
        done = {c["input"].get("line_id") for c in self.successful(tool_name)}
        return [line for line in lines if session.baseline.get(line) and line not in done]

    def tool_schemas(self, tools, session):
        allowed = self.permitted(session)
        exposed = deepcopy([t for t in tools if t["name"] in allowed])
        for tool in exposed:
            if tool["name"] == "compare_cost_scenarios":
                tool["input_schema"]["properties"]["hypothetical_boards"]["enum"] = [60]
            if tool["name"] == "ask_user":
                tool["input_schema"]["required"] = ["question", "gap_id"]
                tool["input_schema"]["properties"]["gap_id"]["enum"] = [
                    g["id"] for g in self.snapshot(session)["unasked_questions"]]
            choices = self.line_choices(session, tool["name"])
            if choices is not None:
                tool["input_schema"]["properties"]["line_id"]["enum"] = choices
        return exposed

    def model_context(self, session) -> dict:
        """Rebase at stage boundaries on recorded facts, removing stale model plans without losing the audit."""
        decisions = [c["output"] for c in self.successful("check_substitute")]
        return {
            "notice": "Controller summary of actual tool state, not a new owner statement. Full outputs remain in the run record.",
            "design": {"name": session.design_name, "bom_sha256": session.bom_fingerprint},
            "requirements": session.list_requirements(),
            "application_and_cost_gaps_not_prerequisites_for_equivalence": session.find_missing_information() if session.bom else None,
            "original_parts": {line: {"key": p.key, "manufacturer": p.manufacturer, "mpn": p.mpn,
                "parameters": {k: str(v.value) + (" " + v.unit if v.unit else "") for k, v in p.params.items()}}
                for line, p in session.baseline.items() if p and (not self.request.lines or line in self.request.lines)},
            "discovered_candidates": [c["output"] for c in self.successful("search_candidates")],
            "checked_candidates": [{"decision_id": d["decision_id"], "line": d["line"], "candidate": d["candidate"],
                "status": d["status"], "application": d["application"]["status"],
                "nonpassing_checks": [c for c in d["checks"] if c["status"] != "pass"]} for d in decisions],
            "sourcing": [c["output"] for c in self.successful("check_availability")],
            "recorded_answers": [{"question": c["input"], "result": c["output"]} for c in self.calls if c["name"] == "ask_user"],
            "memories": self.memories(),
            "reverifications": [compact_output("reverify_decision", c["output"]) for c in self.successful("reverify_decision")],
            "costs": [compact_output("compare_cost_scenarios", c["output"]) for c in self.successful("compare_cost_scenarios")],
            "last_error": {"name": self.calls[-1]["name"], "input": self.calls[-1]["input"],
                           "message": str(self.calls[-1]["output"].get("error", ""))[:300]}
                          if self.calls and self.calls[-1]["error"] else None,
        }


def compact_output(name: str, value: dict) -> dict:
    """Keep full output in the audit; avoid repeating entire records in a small model's context."""
    if "error" in value:
        return value
    if name == "check_substitute":
        source_urls = sorted({url.split("#", 1)[0] for c in value["checks"] for e in c["evidence"]
                              for url in re.findall(r"https?://[^\s)]+", e)})
        shown = {k: v for k, v in value.items() if k not in {"comparison", "context", "checks", "application"}} | {
            "comparison": {role: {k: p[k] for k in ("key", "manufacturer", "mpn", "package", "source", "retrieved_at")}
                           for role, p in value["comparison"].items()},
            "checks": [{k: v for k, v in c.items() if k != "evidence"} | {"evidence_present": bool(c["evidence"])}
                       for c in value["checks"]],
            "sources": source_urls, "full_evidence": "preserved in the original tool event",
            "application": {"status": value["application"]["status"], "checks": [
                {k: v for k, v in c.items() if k in {"check", "status", "message", "expected", "observed"}}
                for c in value["application"]["checks"]]}}
        return shown
    if name == "compare_cost_scenarios":
        return {k: v for k, v in value.items() if k != "scenarios"} | {"scenarios": [
            {k: v for k, v in s.items() if k not in {"baseline", "proposed", "excluded"}} |
            {"baseline": {k: v for k, v in s["baseline"].items() if k not in {"lines", "derivation"}},
             "proposed": {k: v for k, v in s["proposed"].items() if k not in {"lines", "derivation"}},
             "excluded": s["excluded"]} for s in value["scenarios"]]}
    if name == "reverify_decision":
        return {k: v for k, v in value.items() if k not in {"stored_context", "current_context", "current_decision"}} | {
            "current_decision": compact_output("check_substitute", value["current_decision"])
            if value.get("current_decision") else None}
    return value
