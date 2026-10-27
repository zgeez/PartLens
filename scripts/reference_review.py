"""Engineering-only scripted reference on existing fixtures; does not supply a new owner's build quantity."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from partlens.agent import Agent, ScriptedProvider
from partlens.cli import catalogs_from_args
from partlens.demo import DEMO_BOM
from partlens.evaluation import evaluate_run
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.records import RunRecorder, new_run_id
from partlens.session import Session


def no_answer(question: str) -> str:
    raise RuntimeError("reference review must not invent an owner's answer")


def explanation(results):
    rejected = next(r for r in results if r.get("status") == "rejected")
    failures = [c for c in rejected["checks"] if c["status"] == "fail"]
    return ("Scripted engineering reference: original-specification equivalence rejected for "
            + rejected["candidate"] + ": " + "; ".join(
                c["message"] + " [" + "; ".join(c["evidence"]) + "]" for c in failures)
            + ". Actual application conditions remain unverified.")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", action="append", required=True)
    parser.add_argument("--evidence", action="append")
    args = parser.parse_args()
    catalogs = catalogs_from_args(args)
    state = Path(".partlens")
    memory_dir = state / "reference-memory" / new_run_id()
    records = []
    for phase in ("engineering", "recall"):
        rec = RunRecorder.create(state / "runs")
        records.append(rec.path)
        rec.log("reference_scope", phase=phase, mode="scripted; no live LLM", quantity="not supplied",
                memory_store=str(memory_dir))
        with HMemBridge(memory_dir) as bridge:
            rec.log("memory_engine", info=bridge.info)
            session = Session(rec, catalogs, memory=DecisionMemory(bridge, "easyduino-rp2040"))
            script = [
                [("import_bom", {"path": str(DEMO_BOM), "name": "easyduino-rp2040"})],
                [("match_parts", {}), ("find_missing_information", {})],
            ]
            if phase == "engineering":
                script += [
                    [("get_part", {"key": "lcsc:C25905"}), ("get_part", {"key": "lcsc:C53109434"}),
                     ("get_part", {"key": "lcsc:C347376"})],
                    [("check_substitute", {"line_id": "L1", "candidate_key": "lcsc:C105883"}),
                     ("check_substitute", {"line_id": "L11", "candidate_key": "lcsc:C53109434"}),
                     ("check_substitute", {"line_id": "L18", "candidate_key": "lcsc:C1857757"})],
                    explanation,
                ]
            else:
                script += [[("check_substitute", {"line_id": "L11", "candidate_key": "lcsc:C53109434"})],
                           "Scripted second-session recheck complete; inspect prior_decisions_from_memory."]
            print(Agent(session, ScriptedProvider(script), no_answer).send(
                "Engineering-only reference over the approved demo; no owner quantity provided.", origin="reference_task"))
        rec.log("evaluation", report=evaluate_run(rec.path, prior_path=records[0] if phase == "recall" else None))
    print(json.dumps({"records": [str(p) for p in records], "mode": "scripted engineering reference"}))


if __name__ == "__main__":
    main()
