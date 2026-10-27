"""Distributable synthetic fallback. Explicitly deterministic; no live LLM/supplier/sponsor claim."""

import json
from pathlib import Path

from partlens.agent import Agent, ScriptedProvider, ToolCall
from partlens.records import RunRecorder
from partlens.session import Session
from partlens.sources.catalog import LocalCatalog
from partlens.workflow import WorkflowController, WorkflowRequest
from partlens.results import FinalResult


def main():
    rec = RunRecorder.create(Path(".partlens/sample-runs"))
    rec.log("synthetic_sample", live_llm=False, live_supplier=False, zetaris=False,
            licence="Apache-2.0 original synthetic fixtures", owner_requirement_modified=False)
    session = Session(rec, [LocalCatalog.from_json("tests/fixtures/catalog.json")])
    request = WorkflowRequest("tests/fixtures/bom_kicad.csv", design="bom_kicad", lines=("L1",), require_memory=False)
    controller = WorkflowController(request)
    agent = Agent(session, ScriptedProvider([]), lambda question: None)
    calls = [("import_bom", {"path": request.bom_path}), ("find_missing_information", {}), ("match_parts", {}),
             ("search_candidates", {"line_id": "L1"})]
    calls += [("check_substitute", {"line_id": "L1", "candidate_key": key}) for key in (
        "fixture:TEST-C100N-X7R-50V-EXT", "fixture:TEST-C100N-X7R-6V3", "fixture:TEST-C100N-NODIEL")]
    for name, args in calls:
        block = agent._execute(ToolCall(f"sample-{rec.seq+1}", name, args), actor="deterministic_sample")
        controller.observe(name, args, json.loads(block["content"]), bool(block.get("is_error")), actor="deterministic_sample")
    result = FinalResult.build(controller, session, "")
    rec.log("sample_result", result=result.as_dict(), rendered=result.render())
    print("SYNTHETIC DETERMINISTIC SAMPLE — no live LLM, supplier, Zetaris or H-MEM operation.\n")
    print(result.render())


if __name__ == "__main__":
    main()
