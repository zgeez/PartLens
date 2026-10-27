"""Outcome-based evaluation; never requires a particular planner tool-call sequence."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .records import read_events


def evaluate_run(path: str | Path, *, prior_path: str | Path | None = None) -> dict[str, Any]:
    events = read_events(path)
    calls = [e for e in events if e["type"] == "tool_call"]
    successful = [c for c in calls if not c.get("error")]
    decisions = [c["output"] for c in successful if c["name"] == "check_substitute"]
    rechecks = [c["output"] for c in successful if c["name"] == "reverify_decision"]
    decisions += [r["current_decision"] for r in rechecks if r.get("current_decision")]
    turns = [e for e in events if e["type"] == "assistant_turn"]
    start = next((e for e in events if e["type"] == "agent_start"),
                 next((e for e in events if e["type"] == "baseline_setup"), {}))
    confirmed = [c["output"].get("recorded", {}) for c in successful if c["name"] == "record_requirement"]
    quantity_sources = {r.get("source") for r in confirmed if r.get("id") == "design.board_quantity"
                        and r.get("binding") and r.get("provenance") == "user_confirmed"}
    quantity_questions = {e.get("in_reply_to") for e in events if e["type"] == "user_message"
                          and f"user:{e['run']}#seq{e['seq']}" in quantity_sources and e.get("in_reply_to")}
    sources = sorted({ev for d in decisions for check in d.get("checks", []) for ev in check.get("evidence", [])})
    prior_memories = set()
    if prior_path:
        prior_memories = {c["output"].get("stored_in_memory") for c in read_events(prior_path)
                          if c["type"] == "tool_call" and c["name"] == "check_substitute"}
        prior_memories.discard(None)
    recalled = [r for d in decisions for r in d.get("prior_decisions_from_memory", [])]
    recalled += [r for c in successful if c["name"] == "recall_decisions"
                 for r in c["output"].get("memories", [])]
    final = next((e["result"] for e in reversed(events) if e["type"] == "agent_result"), None)
    criteria = {
        "bom_imported": any(c["name"] == "import_bom" for c in successful),
        "missing_requirements_identified": any(c["name"] == "find_missing_information"
                                              and c["output"].get("count", 0) > 0 for c in successful),
        "quantity_question_asked": any(e["type"] == "question" and
                                       (e.get("gap_id") == "design.board_quantity" or e.get("question") in quantity_questions)
                                       for e in events),
        "quantity_user_confirmed": any(r.get("id") == "design.board_quantity" and r.get("binding")
                                       and r.get("provenance") == "user_confirmed" for r in confirmed),
        "supplier_evidence": any("supplier_record: https://" in s and "fixture" not in s
                                  and "TEST-" not in s for s in sources),
        "qualified_alternative": any(d.get("status") == "verified" and d.get("candidate") != d.get("original")
                                     and d.get("checks") and all(c.get("status") == "pass" and c.get("evidence")
                                                                for c in d["checks"]) for d in decisions),
        "unverified_alternative": any(d.get("status") == "unverified" for d in decisions),
        "invalid_with_evidence": any(d.get("status") == "rejected" and
                                      any(c.get("status") == "fail" and c.get("evidence")
                                          for c in d.get("checks", [])) for d in decisions),
        "meterless_persisted": any(d.get("stored_in_memory") for d in decisions),
        "explanation_present": bool(final) or bool(turns and turns[-1].get("text") and not turns[-1].get("tool_calls")
                                    and turns[-1].get("stop_reason") in {"end_turn", "stop_sequence"}),
    }
    if prior_path:
        criteria["recalled_first_session_decision"] = any(r.get("memory_id", r.get("id")) in prior_memories
                                                         and r.get("source") for r in recalled)
        criteria["recalled_pair_rechecked"] = any(
            r.get("memory_id", r.get("id")) in prior_memories and r.get("source")
            for d in decisions for r in d.get("prior_decisions_from_memory", []))
    live = str(start.get("provider", "")).startswith(("anthropic:", "ollama:"))
    requested = start.get("requested_model")
    model_confirmed = bool(requested and turns) and all(
        t.get("usage", {}).get("model") == requested for t in turns)
    return {
        "run": events[0]["run"] if events else None, "record": str(path),
        "provider": start.get("provider"), "requested_model": start.get("requested_model"),
        "observed_models": sorted({t["usage"]["model"] for t in turns if t.get("usage", {}).get("model")}),
        "baseline_model_confirmed": live and model_confirmed and start.get("fallback_enabled") is False,
        "criteria": criteria, "tool_calls": len(calls), "sources": sources,
        "controlled_workflow_complete": bool(final and final["status"] == "completed_preliminary"),
        "failures": [e for e in events if e["type"] in {"provider_error", "setup_error", "run_failed", "agent_stopped", "agent_incomplete"}
                     or (e["type"] == "tool_call" and e.get("error"))
                     or (e["type"] == "agent_result" and e["result"]["status"] == "partial")],
        "automated_outcomes_met": all(criteria.values()),
        "explanation_review": "manual review required for engineering accuracy and citation coverage",
    }


def compare_runs(reference: str | Path, live: str | Path, recall: str | Path | None = None) -> dict[str, Any]:
    expected = evaluate_run(reference)
    observed = evaluate_run(live)
    second = evaluate_run(recall, prior_path=live) if recall else None
    return {
        "reference": expected, "live": observed, "recall": second,
        "outcomes": {name: {"scripted": value, "live": observed["criteria"].get(name, False)}
                     for name, value in expected["criteria"].items()},
        "method": "compare demonstrated outcomes and provenance; tool-call order/count need not match",
        "automated_live_baseline_criteria_met": observed["baseline_model_confirmed"] and observed["automated_outcomes_met"]
                                  and not observed["failures"],
        "automated_live_recall_criteria_met": bool(second and second["baseline_model_confirmed"]
                                     and second["criteria"].get("recalled_first_session_decision")
                                     and second["criteria"].get("recalled_pair_rechecked")
                                     and not second["failures"]),
        "manual_review_required": "explanation correctness, citations and relevance of recalled decisions",
    }
