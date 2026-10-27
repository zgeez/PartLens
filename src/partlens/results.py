"""Authoritative final facts and deterministic prose. Model drafts never supply factual fields."""

from __future__ import annotations

import json
from dataclasses import dataclass

from .core.model import to_jsonable


@dataclass(frozen=True)
class FinalResult:
    status: str
    workflow: dict
    requirements: list[dict]
    decisions: list[dict]
    sourcing: list[dict]
    costs: dict | None
    reverifications: list[dict]
    gaps: list[dict]
    narrative_validation: dict
    record: str
    stopped_reason: str | None = None

    @classmethod
    def build(cls, controller, session, draft: str, *, stopped_reason: str | None = None):
        snap = controller.snapshot(session)
        decisions = [c["output"] for c in controller.successful("check_substitute")]
        rechecks = [c["output"] for c in controller.successful("reverify_decision")]
        decisions += [r["current_decision"] for r in rechecks if r.get("current_decision")]
        decisions = list({d["decision_id"]: d for d in decisions
                          if d["decision_id"] in session.decisions and
                          session.decisions[d["decision_id"]].status.value == d["status"]}.values())
        gaps = session.find_missing_information()["gaps"] if session.bom else []
        costs = controller.successful("compare_cost_scenarios")
        facts = {"decision_refs": {d["decision_id"] for d in decisions}, "gap_refs": {g["id"] for g in gaps}}
        validation = {"accepted": False, "action": "deterministic_replacement",
                      "reason": "Free-form factual claims are excluded from the authoritative final answer"}
        try:
            selected = json.loads(draft)
            if (isinstance(selected, dict) and set(selected) <= set(facts) and selected and
                    all(isinstance(v, list) and all(isinstance(x, str) and x in facts[k] for x in v)
                        for k, v in selected.items())):
                validation = {"accepted": True, "action": "validated_reference_selection", "references": selected}
        except (TypeError, ValueError):
            pass
        status = "completed_preliminary" if snap["operations_complete"] and not stopped_reason else "partial"
        if snap["unanswered_questions"]:
            status = "partial"
        snap["states"] += [
            {"id": "completion_check", "status": "complete" if snap["operations_complete"] else "blocked",
             "prerequisites": [s["id"] for s in snap["states"] if s["status"] != "not_required"],
             "evidence": {"missing_actions": snap["missing_actions"]}, "permitted_tools": [],
             "failure_reason": stopped_reason or "" if snap["operations_complete"] else "Mandatory operations remain",
             "permitted_transitions": ["final_result"]},
            {"id": "final_result", "status": "complete" if status == "completed_preliminary" else "partial",
             "prerequisites": ["completion_check"], "evidence": validation, "permitted_tools": [],
             "failure_reason": stopped_reason or "" if status == "completed_preliminary" else "Partial result explicitly labelled",
             "permitted_transitions": []}]
        return cls(status, snap, session.list_requirements()["requirements"], decisions,
                   [c["output"] for c in controller.successful("check_availability")],
                   costs[-1]["output"] if costs else None, rechecks, gaps, validation,
                   str(session.recorder.path), stopped_reason)

    def as_dict(self) -> dict:
        return to_jsonable(self)

    def render(self) -> str:
        lines = [f"PartLens: {self.status.replace('_', ' ')}.",
                 "Scope: original-specification equivalence. Application safety needs separate circuit evidence."]
        if self.stopped_reason:
            lines.append("Stopped: " + self.stopped_reason)
        if self.workflow["missing_actions"]:
            lines.append("Missing operations: " + ", ".join(self.workflow["missing_actions"]))
        for r in self.requirements:
            if r["id"] == "design.board_quantity":
                lines.append(f"User-confirmed requirement: {r['value']} board(s). Source: {r['source']}"
                             if r["binding"] and r["provenance"] == "user_confirmed" else
                             "Build quantity remains unconfirmed.")
        for d in self.decisions:
            original, candidate = d["comparison"]["original"], d["comparison"]["candidate"]
            lines.extend(["", f"{d['line']}: {original['manufacturer']} {original['mpn']} -> "
                          f"{candidate['manufacturer']} {candidate['mpn']}",
                          f"Equivalence: {d['status']}. Application: {d['application']['status']}.",
                          f"Source: {candidate['source']} | retrieved {candidate['retrieved_at']}"])
            for c in d["checks"]:
                lines.append(f"  {c['status']}: {c['message']}")
                lines.extend("    " + e for e in c["evidence"])
            for c in d["application"]["checks"]:
                if c["status"] != "pass":
                    lines.append("  Application gap: " + c["message"])
        for sourcing in self.sourcing:
            lines.append(f"\nSourcing: {sourcing['part']} at {sourcing['boards']} confirmed board(s)")
            lines.extend(f"  {c['status']}: {c['message']}" for c in sourcing["checks"])
        for r in self.reverifications:
            lines.extend([f"\nMemory {r['memory_id']}: {r['outcome']} ({r['reason']}).",
                          "Original recorded source: " + r["source"]])
        if self.costs:
            for s in self.costs["scenarios"]:
                b = s["baseline"]
                label = "User-confirmed requirement" if s["scenario"] == "owner_confirmed" else "Hypothetical scenario"
                priced = sum(line.get("extended") is not None for line in b["lines"])
                lines.extend([f"\n{label}: {s['boards']} board(s). Source: {s['quantity_source']}",
                              f"Component purchasing subtotal: {b['currency']} {b['parts_total']} "
                              f"({priced} priced lines; complete: {b['component_complete']}).",
                              f"Conditional manufacturing subtotal including covered components: "
                              f"{b['currency']} {b['known_subtotal']}.",
                              f"Estimated assembled cost: {b['total']} (complete: {b['complete']}).",
                              f"Assembled savings: {s['assembled_savings']}.",
                              "Official manufacturer quotation: unavailable. No parts have been ordered."])
                lines.append(f"Fee evidence: {b['fee_source']} | retrieved {b['fee_retrieved_at']}")
                lines.extend("  Component evidence: " + source + " | retrieved " + str(retrieved)
                             for source, retrieved in sorted({(line["source"], str(line["retrieved_at"]))
                                                             for line in b["lines"] if line.get("source")}))
                lines.extend("  Missing/conditional: " + p for p in b["problems"])
                lines.extend("  Excluded: " + p for p in s["excluded"])
        lines.append("\nUnresolved information:")
        lines.extend(f"  {g['id']}: {g['missing']} — {g['why']}" for g in self.gaps)
        if self.workflow["unanswered_questions"]:
            lines.append("Unanswered owner questions: " + ", ".join(self.workflow["unanswered_questions"]))
        lines.append("\nRun record: " + self.record)
        return "\n".join(lines)
