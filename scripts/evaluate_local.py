"""Bounded, genuine local agent evaluation with real catalogue tools and cold H-MEM recall."""

import argparse
import json
from pathlib import Path

from partlens.agent import Agent, provider_from_env
from partlens.cli import catalogs_from_args, load_env_file
from partlens.demo import DEMO_BOM
from partlens.evaluation import evaluate_run
from partlens.local_provider import OllamaProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.optimise.cost import load_fees
from partlens.records import RunRecorder, new_run_id
from partlens.session import Session
from partlens.workflow import WorkflowRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="append")
    parser.add_argument("--zetaris", action="store_true")
    parser.add_argument("--evidence", action="append")
    parser.add_argument("--fees")
    parser.add_argument("--quantity-record", required=True)
    parser.add_argument("--focused", action="store_true", help="Guided review of three known engineering pairs; not autonomous discovery")
    args = parser.parse_args()
    load_env_file()
    provider = provider_from_env()
    if not isinstance(provider, OllamaProvider):
        raise ValueError("This evaluation requires PARTLENS_LLM_PROVIDER=ollama; no cloud calls allowed")
    catalogs = catalogs_from_args(args)
    store = Path(".partlens/local-agent-memory") / new_run_id()
    reports, prior = [], None

    def no_new_answer(question):
        # Do not fabricate an owner reply for an unattended run.
        raise RuntimeError("No new owner answer is available; retain the missing requirement")

    for phase in ("review", "cold_recall"):
        rec = RunRecorder.create(Path(".partlens/runs"))
        print(f"{phase}: {rec.path}", flush=True)
        rec.log("local_agent_evaluation", phase=phase, prior_record=str(prior) if prior else None,
                mode="live local LLM; not scripted", memory_store=str(store),
                research_scope="operator-specified candidate pairs" if args.focused else "model candidate discovery")
        try:
            with HMemBridge(store) as bridge:
                rec.log("memory_engine", info=bridge.info)
                session = Session(rec, catalogs, memory=DecisionMemory(bridge, "easyduino-rp2040"),
                                  fees=load_fees(args.fees))
                session.restore_quantity(args.quantity_record)
                rec.log("cost_configuration", fees=session.fees)
                agent = Agent(session, provider, no_new_answer, max_steps=28, max_tool_calls=50)
                task = (
                    f"Import the approved BOM at {DEMO_BOM} as easyduino-rp2040. Match parts, list requirements "
                    "and find missing information. The owner's one-board quantity has already been restored "
                    "from its original recorded answer; inspect its provenance instead of recording a new answer. "
                    "Do not ask new questions in this unattended preliminary review: report missing inputs. "
                )
                if phase == "review":
                    task += (
                        "Review these operator-specified replacement pairs using check_substitute: "
                        "L1 with lcsc:C105883, L11 with lcsc:C53109434, L18 with lcsc:C1857757. "
                        "Run all three checks, then compare_cost_scenarios for hypothetical_boards 60. "
                        "Explain the actual check results with sources and keep application safety separate "
                        "from equivalence. These candidate identities are research inputs, never verified evidence. "
                        "Keep missing fees unknown and the owner's original one-board requirement unchanged."
                    ) if args.focused else (
                        "Investigate replacement candidates for L1 (capacitor), L11 (resistor) and L18 (flash). "
                        "Use search limit 10 without a text filter to avoid hiding different ratings. Spend at "
                        "most two checks per line; cover all three lines rather than repeatedly checking capacitors. "
                        "Investigate whether a listed 25V resistor can replace the original 50V resistor on L11, "
                        "using actual catalogue evidence. A failed equivalence check alone does not prove circuit danger. "
                        "Use searches and deterministic checks to demonstrate a qualified alternative, a rejected "
                        "replacement and an unverified alternative if the evidence supports them. Check flash "
                        "availability. Compare costs for the confirmed one board and a hypothetical 60 boards "
                        "without changing requirements. Finish with a concise explanation citing source URLs, "
                        "qualification scopes, sourcing risks and missing manufacturing fees."
                    )
                else:
                    task += (
                        f"Recall a relevant replacement decision stored in the preceding live run {prior.stem}; "
                        "prefer a rejection if one exists, otherwise a verified or unverified decision. "
                        f"Call recall_decisions with run_id {prior.stem} for exact stored-source lookup "
                        "and query easyduino-rp2040 replacement decisions; verify the returned source belongs to that run. "
                        "Cite that run's memory source and recheck that same pair against "
                        "the current catalogue. Finish with a concise sourced explanation."
                    )
                explanation = agent.send(task, origin="local_evaluation_task", workflow=WorkflowRequest(
                    str(DEMO_BOM), lines=("L1", "L11", "L18"), research=phase == "review", costs=phase == "review",
                    recall_run=prior.stem if phase == "cold_recall" and prior else None))
                rec.log("local_evaluation_finished", phase=phase, explanation=explanation,
                        owner_quantity=session._boards(),
                        quantity_source=session.design_requirement("board_quantity").provenance.source)
        except Exception as exc:
            rec.log("run_failed", error_type=type(exc).__name__, message=str(exc))
        report = evaluate_run(rec.path, prior_path=prior)
        rec.log("evaluation", report=report)
        reports.append(report)
        print(json.dumps({k: report[k] for k in ("record", "observed_models", "tool_calls", "criteria")}), flush=True)
        prior = rec.path
        if not report["baseline_model_confirmed"]:
            break
    target = Path(".partlens/evaluations") / f"local-agent-{new_run_id()}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as f:
        json.dump(reports, f, indent=2, ensure_ascii=False)
    print(f"Evaluation: {target}", flush=True)


if __name__ == "__main__":
    main()
