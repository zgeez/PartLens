"""Genuine bounded local Qwen evaluations; no supplied candidate pairs, paid inference or hidden success."""

import argparse
import json
from pathlib import Path

from partlens.agent import Agent
from partlens.cli import catalogs_from_args, load_env_file
from partlens.demo import DEMO_BOM
from partlens.local_provider import OllamaProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.optimise.cost import load_fees
from partlens.records import RunRecorder, new_run_id, read_events
from partlens.session import Session
from partlens.workflow import WorkflowRequest


class FaultCatalog:
    """Explicit injected source faults; successful operations still use the configured real catalogue."""
    def __init__(self, base, fault, recorder):
        self.base, self.fault, self.recorder = base, fault, recorder
        self.name = f"injected-{fault}:{base.name}"
        self.failed = False

    def with_recorder(self, recorder):
        base = self.base.with_recorder(recorder) if hasattr(self.base, "with_recorder") else self.base
        return FaultCatalog(base, self.fault, recorder)

    def get(self, key):
        if self.fault == "unavailable" or not self.failed:
            self.failed = True
            self.recorder.log("fault_injection", fault=self.fault, operation="catalogue.get", key=key,
                              note="Injected test failure, not a real sponsor outage")
            raise TimeoutError("Explicit injected supplier timeout/unavailability")
        return self.base.get(key)

    def find_mpn(self, mpn):
        return self.base.find_mpn(mpn)

    def search(self, *args):
        return self.base.search(*args)


class ArgumentFaultProvider(OllamaProvider):
    def __init__(self, recorder):
        super().__init__()
        self.recorder, self.injected = recorder, False

    def next_turn(self, *args):
        turn = super().next_turn(*args)
        if turn.tool_calls and not self.injected:
            call = turn.tool_calls[0]
            self.recorder.log("fault_injection", fault="malformed_arguments", source="evaluation injector, not model",
                              original_model_call={"name": call.name, "input": dict(call.input)},
                              injected_field="TEST_unexpected_argument")
            call.input["TEST_unexpected_argument"] = "injected"
            for block in turn.assistant_content:
                if block.get("type") == "tool_use" and block["id"] == call.id:
                    block["input"] = call.input
            turn.usage["injected_test_fault"] = "malformed_arguments; original model call preserved separately"
            self.injected = True
        return turn


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--catalog", action="append")
    ap.add_argument("--zetaris", action="store_true")
    ap.add_argument("--evidence", action="append")
    ap.add_argument("--fees")
    ap.add_argument("--quantity-record", required=True)
    ap.add_argument("--scenarios", default="A,C,B,E_timeout,E_unavailable,E_budget")
    args = ap.parse_args()
    load_env_file()
    catalogs = catalogs_from_args(args)
    root = Path(".partlens/milestone4") / new_run_id()
    root.mkdir(parents=True)
    memory_path = root / "memory"
    reports, first = [], None
    for scenario in args.scenarios.split(","):
        rec = RunRecorder.create(Path(".partlens/runs"))
        print(f"{scenario}: {rec.path}", flush=True)
        rec.log("milestone4_evaluation", scenario=scenario, live_llm=True,
                source_mode="real_zetaris_over_retained_fixture" if args.zetaris else "retained_local_fixture",
                candidate_pairs_supplied=False, source_data_is_live_inventory=False)
        try:
            provider = ArgumentFaultProvider(rec) if scenario == "E_arguments" else OllamaProvider()
            selected = catalogs
            if scenario in {"E_timeout", "E_unavailable"}:
                selected = [FaultCatalog(c, "timeout_once" if scenario == "E_timeout" else "unavailable", rec) for c in catalogs]
            with HMemBridge(memory_path) as bridge:
                rec.log("memory_engine", info=bridge.info)
                s = Session(rec, selected, memory=DecisionMemory(bridge, "easyduino-rp2040"), fees=load_fees(args.fees))
                s.restore_quantity(args.quantity_record)
                rec.log("cost_configuration", fees=s.fees)
                research = scenario not in {"B", "C", "E_stale", "E_arguments"}
                req = WorkflowRequest(str(DEMO_BOM), lines=("L1", "L11", "L18"), research=research,
                                      costs=scenario not in {"B", "C", "E_stale", "E_arguments"}, clarify_electrical=scenario == "B",
                                      recall_run=first.stem if scenario in {"C", "E_stale"} and first else None)
                if scenario in {"C", "E_stale"} and not first:
                    raise RuntimeError("Run A first to create actual decisions for independent-session recall")
                prompt = (f"Review the approved Easyduino RP2040 BOM at {DEMO_BOM}. The owner's one-board "
                          "requirement has been restored from its original answer; do not replace it. ")
                if scenario == "E_arguments":
                    prompt += "Import the design, identify missing requirements and match its supplier records."
                elif scenario == "B":
                    prompt += "Ask necessary electrical questions for L1, L11 and L18; unanswered questions stay unresolved."
                elif scenario in {"C", "E_stale"}:
                    prompt += f"Recall decisions from run {first.stem}, reverify each and explain what changed or remains unknown."
                else:
                    prompt += ("Independently discover replacements for L1, L11 and L18. Use supplier evidence and "
                               "deterministic checks. Find qualified, rejected and unverified alternatives if supported. "
                               "Check sourcing risks and compare costs for one board and a hypothetical 60-board scenario. "
                               "Do not invent missing conditions, fees or a quotation.")
                if scenario == "E_stale":
                    # Explicit context-version fault only: no design file, owner requirement, or part value is changed.
                    original_import = s.import_bom
                    def changed_context_import(*import_args, **import_kwargs):
                        output = original_import(*import_args, **import_kwargs)
                        s.bom_fingerprint = "TEST-injected-context-version-mismatch"
                        rec.log("fault_injection", fault="stale_memory_context", design_file_modified=False,
                                owner_requirement_modified=False)
                        return output
                    s.import_bom = changed_context_import
                agent = Agent(s, provider, lambda question: None, max_steps=40,
                              max_tool_calls=2 if scenario == "E_budget" else 70)
                text = agent.send(prompt, origin="milestone4_evaluation_task", workflow=req)
                result = agent.last_result
                events = read_events(rec.path)
                turns = [e for e in events if e["type"] == "assistant_turn"]
                calls = [e for e in events if e["type"] == "tool_call"]
                criteria = {
                    "actual_requested_local_model": bool(turns) and all(t["usage"].get("model") == "qwen3.5:9b" for t in turns),
                    "mandatory_operations_complete": result.workflow["operations_complete"],
                    "model_selected_candidates": any(c["name"] == "search_candidates" and c.get("actor") == "model" and not c.get("error") for c in calls),
                    "no_fabricated_owner_answer": not any(e["type"] == "user_message" and e.get("in_reply_to") for e in events),
                    "original_owner_quantity_preserved": s._boards() == 1,
                    "authoritative_final_rendering": text == result.render(),
                    "unknown_costs_not_a_quote": all(sc["official_manufacturer_quotation"] is None and
                            (sc["baseline"]["complete"] or sc["baseline"]["total"] == "n/a")
                            for sc in (result.costs or {}).get("scenarios", [])),
                }
                if scenario in {"A", "E_timeout"}:
                    criteria["cost_comparison_executed"] = bool(result.costs)
                    criteria["one_board_and_hypothetical_sixty"] = bool(result.costs and
                        [(sc["boards"], sc["scenario"]) for sc in result.costs["scenarios"]] ==
                        [(1, "owner_confirmed"), (60, "hypothetical")])
                if scenario == "E_arguments":
                    criteria["malformed_argument_recovered"] = result.workflow["operations_complete"] and any(
                        c.get("error") and "unsupported keys" in c["error"] for c in calls)
                if scenario == "B":
                    criteria["actual_questions_unanswered"] = bool(result.workflow["unanswered_questions"])
                if scenario in {"C", "E_stale"}:
                    criteria["all_recalled_memories_rechecked"] = bool(result.reverifications) and not agent.controller.pending_rechecks()
                    criteria["actual_current_checks"] = all(r.get("current_decision") for r in result.reverifications)
                if scenario == "E_stale":
                    criteria["context_mismatch_not_inherited"] = bool(result.reverifications) and all(
                        r["outcome"] == "changed_context" and not r["context_matches"] for r in result.reverifications)
                if scenario in {"E_unavailable", "E_budget"}:
                    criteria["honest_partial_result"] = result.status == "partial" and bool(result.workflow["missing_actions"])
                acceptance = [v for k, v in criteria.items() if k not in {"model_selected_candidates", "mandatory_operations_complete"}]
                if scenario in {"A", "E_timeout", "C", "E_stale"}:
                    acceptance.append(criteria["mandatory_operations_complete"])
                if scenario == "A":
                    acceptance.append(criteria["model_selected_candidates"])
                report = {"scenario": scenario, "record": str(rec.path), "criteria": criteria,
                          "passed": all(acceptance), "result": result.as_dict(), "model_turns": len(turns),
                          "tool_calls": len(calls), "model_tool_calls": sum(c.get("actor", "model") == "model" for c in calls),
                          "controller_tool_calls": sum(c.get("actor") == "controller" for c in calls),
                          "failed_tool_calls": sum(bool(c.get("error")) for c in calls),
                          "blocked_model_proposals": sum(bool(c.get("controller_blocked")) for c in calls),
                          "executed_failed_tool_calls": sum(bool(c.get("error")) and not c.get("controller_blocked") for c in calls),
                          "latency_ms": sum(t.get("latency_ms", 0) for t in turns),
                          "usage": [t["usage"] for t in turns],
                          "successful_zetaris_queries": sum(e["type"] == "zetaris_query" and e["query"]["status"] == "succeeded" for e in events),
                          "narrative_policy": "Only validated references accepted; raw factual prose replaced deterministically"}
                report["injected_faults"] = [e for e in events if e["type"] == "fault_injection"]
                rec.log("milestone4_evaluation_result", report=report)
                if scenario == "A":
                    first = rec.path
        except Exception as exc:
            rec.log("milestone4_evaluation_failure", error_type=type(exc).__name__, message=str(exc))
            report = {"scenario": scenario, "record": str(rec.path), "passed": False, "error_type": type(exc).__name__}
        reports.append(report)
        print(json.dumps({k: report[k] for k in ("scenario", "record", "passed")}, ensure_ascii=False), flush=True)
        with (root / f"{scenario}.json").open("x", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
    with (root / "summary.json").open("x", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"Preserved evaluation bundle: {root}", flush=True)


if __name__ == "__main__":
    main()
