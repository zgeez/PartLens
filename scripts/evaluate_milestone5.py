"""Real bounded Qwen -> official component API -> Zetaris -> H-MEM evaluation, with cold recall.

Candidate pairs are never supplied. Optional retained records supply code-discovery hints only;
all checked parts come from the official source. Every run, source observation and failure is retained.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from partlens.agent import Agent
from partlens.cli import catalogs_from_args, load_env_file
from partlens.core.model import to_jsonable
from partlens.demo import DEMO_BOM
from partlens.local_provider import OllamaProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.optimise.cost import load_fees
from partlens.records import RunRecorder, new_run_id, read_events
from partlens.replay import replay
from partlens.secrets import redact
from partlens.session import Session
from partlens.sources.audit import AuditedCatalog
from partlens.workflow import WorkflowRequest


def applications_supported(decisions: list[dict]) -> bool:
    """Unknown application conditions forbid a pass; evidenced nominal/function failures may reject."""
    return all(d["application"]["status"] != "verified" and (
        d["application"]["status"] != "rejected" or any(c["status"] == "fail" and c.get("evidence")
                                                     for c in d["application"]["checks"])) for d in decisions)


def reassess_bundle(root: Path) -> int:
    from partlens.core.model import digest

    rec = RunRecorder.create(".partlens/runs")
    reports = []
    for stage in ("A", "C"):
        raw = (root / f"{stage}.json").read_text(encoding="utf-8")
        original = json.loads(raw)
        criteria = dict(original["criteria"])
        criteria.pop("all_applications_retained_unverified", None)
        criteria["no_unearned_application_pass"] = applications_supported(original["result"]["decisions"])
        report = {"scenario": stage, "source_record": original["record"], "original_report_passed": original["passed"],
                  "source_report_digest": digest(json.loads(raw)), "criteria": criteria, "passed": all(criteria.values()),
                  "correction": "Evaluator permits an evidenced application rejection; no engineering result changed.",
                  "new_model_or_supplier_call": False}
        rec.log("milestone5_acceptance_reassessment", **report)
        reports.append(report)
    out = root / f"reassessment-{rec.run_id}.json"
    with out.open("x", encoding="utf-8") as f:
        json.dump({"record": str(rec.path), "reports": reports}, f, ensure_ascii=False, indent=2)
    print(json.dumps({"record": str(rec.path), "report": str(out), "passed": all(r["passed"] for r in reports)}))
    return 0 if all(r["passed"] for r in reports) else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jlc-leads", help="existing approved internal catalogue for code discovery only")
    parser.add_argument("--quantity-record")
    parser.add_argument("--fees")
    parser.add_argument("--assess-bundle", type=Path, help="append a corrected assessment without rerunning the model or rewriting evidence")
    args = parser.parse_args()
    if args.assess_bundle:
        return reassess_bundle(args.assess_bundle)
    if not args.quantity_record:
        parser.error("--quantity-record is required for live evaluation")
    load_env_file()
    args.jlc, args.zetaris, args.catalog, args.evidence = True, True, [], []
    root = Path(".partlens/milestone5") / new_run_id()
    root.mkdir(parents=True, exist_ok=False)
    reports, first = [], None
    for stage in ("A", "C"):
        rec = RunRecorder.create(".partlens/runs")
        print(f"{stage}: {rec.path}", flush=True)
        rec.log("milestone5_evaluation", scenario=stage, live_llm=True, scripted=False,
                source_mode="official_jlcpcb_via_actual_zetaris", candidate_pairs_supplied=False,
                research_leads_configured=bool(args.jlc_leads), research_leads_are_engineering_evidence=False,
                budgets={"turns": 32, "tool_attempts": 60, "tokens": 300000,
                         "api_http_attempts": 12, "api_distinct_codes": 40})
        try:
            if stage == "C" and first is None:
                raise ValueError("no preceding live session is available for recall")
            source = catalogs_from_args(args)[0]
            # Each session has a fresh cache namespace: a cold recall cannot relabel an old cache hit as live stock.
            source.base.client.cache_dir = root / "cache" / stage
            with HMemBridge(root / "memory") as bridge:
                rec.log("memory_engine", info=bridge.info, process_id=bridge._proc.pid,
                        persistent_store=str(root / "memory"), independent_session=stage)
                session = Session(rec, [AuditedCatalog(source)], fees=load_fees(args.fees),
                                  memory=DecisionMemory(bridge, "easyduino-rp2040"))
                session.restore_quantity(args.quantity_record)
                rec.log("cost_configuration", fees=session.fees)
                request = WorkflowRequest(str(DEMO_BOM), lines=("L1", "L11", "L18"),
                                          research=stage == "A", costs=stage == "A",
                                          recall_run=first.stem if stage == "C" else None)
                task = (f"Review the approved Easyduino RP2040 BOM at {DEMO_BOM}. The owner's one-board requirement "
                        "has been restored from the original message; do not change it. ")
                if stage == "A":
                    task += ("Independently discover replacements for L1, L11 and L18 through the configured source. "
                             "Use fresh official supplier evidence through Zetaris and deterministic checks. Find verified, "
                             "rejected and unverified alternatives if evidence supports them. Show sourcing risks and "
                             "compare the owner quantity and explicitly hypothetical 60 boards. Currency, MOQ, order "
                             "multiples, eligibility and quote inputs must remain unknown when undocumented. "
                             "Retained fixture entries are research leads only; never use their specifications as fresh official data.")
                else:
                    task += (f"Recall decisions from run {first.stem}. Retrieve applicable current official evidence and "
                             "reverify every retrieved item. Explain any changed context, unchanged result, or remaining "
                             "uncertainty without inheriting historical verified status.")
                agent = Agent(session, OllamaProvider(model="qwen3.5:9b"), lambda _: None,
                              max_steps=32, max_tool_calls=60, max_total_tokens=300000)
                agent.send(task, origin="milestone5_evaluation_task", workflow=request)
                result = agent.last_result
                events = read_events(rec.path)
                calls = [e for e in events if e["type"] == "tool_call"]
                turns = [e for e in events if e["type"] == "assistant_turn"]
                checks = [e["output"] for e in calls if e["name"] == "check_substitute" and not e.get("error")]
                api = [e["lookup"] for e in events if e["type"] == "jlcpcb_response"]
                sql = [e["query"] for e in events if e["type"] == "zetaris_query"]
                criteria = {
                    "actual_local_qwen": bool(turns) and all(e["usage"].get("model") == "qwen3.5:9b" for e in turns),
                    "operations_complete": result.workflow["operations_complete"],
                    "genuine_authenticated_supplier_success": bool(api) and all(e["http_status"] == 200 for e in api),
                    "genuine_zetaris_success": bool(sql) and all(q["status"] == "succeeded" for q in sql),
                    "owner_quantity_preserved": session._boards() == 1,
                    "all_decisions_official": all(d["original"].startswith("jlcpcb:") and d["candidate"].startswith("jlcpcb:")
                                                  for d in checks),
                    "no_unearned_application_pass": applications_supported(checks),
                }
                if stage == "A":
                    criteria.update(
                        model_discovered_candidates=any(e.get("actor") == "model" and e["name"] == "search_candidates"
                                                        and not e.get("error") for e in calls),
                        supported_three_outcomes={d["status"] for d in checks} >= {"verified", "rejected", "unverified"},
                        actual_memory_persistence=bool(checks) and all(d["stored_in_memory"] for d in checks),
                        separate_quantity_scenarios=bool(result.costs) and [(s["boards"], s["scenario"]) for s in
                            result.costs.get("scenarios", [])] == [(1, "owner_confirmed"), (60, "hypothetical")],
                        no_complete_quote=bool(result.costs) and all(not s["baseline"]["complete"] and
                            s["baseline"]["total"] == "n/a" for s in result.costs.get("scenarios", [])))
                    first = rec.path
                else:
                    criteria.update(
                        actual_independent_recall=bool(result.reverifications),
                        all_recalled_reverified=bool(result.reverifications) and not agent.controller.pending_rechecks(),
                        actual_current_checks=bool(result.reverifications) and all(r.get("current_decision")
                                                                                  for r in result.reverifications))
                rows = session.catalogs[0].base.base.rows
                with (root / f"{stage}-parts.json").open("x", encoding="utf-8") as f:
                    json.dump(list(rows.values()), f, ensure_ascii=False, indent=2)
                verification = replay(rec.path)
                criteria["deterministic_replay_matched"] = verification.ok
                report = {"scenario": stage, "record": str(rec.path), "passed": all(criteria.values()),
                          "criteria": criteria, "result": result.as_dict(), "replay": to_jsonable(verification),
                          "model_turns": len(turns), "tool_attempts": len(calls),
                          "blocked_model_proposals": sum(bool(c.get("controller_blocked")) for c in calls),
                          "executed_tool_failures": sum(bool(c.get("error")) and not c.get("controller_blocked") for c in calls),
                          "model_tool_calls": sum(c.get("actor", "model") == "model" for c in calls),
                          "controller_tool_calls": sum(c.get("actor") == "controller" for c in calls),
                          "api_http_attempts": sum(e["type"] == "jlcpcb_request" for e in events),
                          "api_returned_codes": sorted({r["componentCode"] for e in api for r in e["data"]}),
                          "api_server_traces": [e["trace_id"] for e in api],
                          "successful_zetaris_queries": sum(q["status"] == "succeeded" for q in sql),
                          "memory_process_id": bridge._proc.pid}
                rec.log("milestone5_evaluation_result", report=report)
        except Exception as exc:
            rec.log("milestone5_evaluation_failure", error_type=type(exc).__name__, message=str(exc))
            report = {"scenario": stage, "record": str(rec.path), "passed": False,
                      "error_type": type(exc).__name__, "message": redact(str(exc))}
        reports.append(report)
        with (root / f"{stage}.json").open("x", encoding="utf-8") as f:
            json.dump(redact(report), f, ensure_ascii=False, indent=2)
        print(json.dumps({k: report[k] for k in ("scenario", "record", "passed")}), flush=True)
    with (root / "summary.json").open("x", encoding="utf-8") as f:
        json.dump(redact(reports), f, ensure_ascii=False, indent=2)
    print(f"Preserved evaluation bundle: {root}", flush=True)
    return 0 if all(r["passed"] for r in reports) else 1


if __name__ == "__main__":
    raise SystemExit(main())
