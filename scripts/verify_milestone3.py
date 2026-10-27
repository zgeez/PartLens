"""Real Zetaris + independent H-MEM process checks; explicitly deterministic, with no LLM calls."""

import argparse
import json
from pathlib import Path

from partlens.agent import Agent, ScriptedProvider, ToolCall
from partlens.cli import catalogs_from_args, load_env_file
from partlens.demo import DEMO_BOM
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.records import RunRecorder, new_run_id, read_events
from partlens.session import Session
from partlens.ui import review_snapshot


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--zetaris", action="store_true")
    ap.add_argument("--catalog", action="append")
    ap.add_argument("--evidence", action="append")
    ap.add_argument("--quantity-record", required=True)
    args = ap.parse_args()
    load_env_file()
    catalogs = catalogs_from_args(args)
    store = Path(".partlens/milestone3-memory") / new_run_id()
    first = None
    records = []
    for phase in ("write", "cold_recall"):
        rec = RunRecorder.create(Path(".partlens/runs"))
        records.append(str(rec.path))
        print(f"{phase}: {rec.path}", flush=True)
        rec.log("milestone3_integration_validation", phase=phase, mode="deterministic; no live LLM",
                memory_store=str(store), prior_record=records[0] if phase == "cold_recall" else None)
        try:
            with HMemBridge(store) as bridge:
                rec.log("memory_engine", info=bridge.info)
                session = Session(rec, catalogs, memory=DecisionMemory(bridge, "easyduino-rp2040"))
                agent = Agent(session, ScriptedProvider([]), lambda q: "")
                def call(tool_name, **kwargs):
                    result = agent._execute(ToolCall(f"validate-{rec.seq + 1}", tool_name, kwargs))
                    output = json.loads(result["content"])
                    if result.get("is_error"):
                        raise RuntimeError(output["error"])
                    return output
                call("import_bom", path=str(DEMO_BOM), name="easyduino-rp2040")
                matches = call("match_parts")
                assert len(matches["matches"]) == 17 and len(matches["unmatched"]) == 2
                session.restore_quantity(args.quantity_record)
                assert session._boards() == 1
                if phase == "write":
                    outcomes = [call("check_substitute", line_id=lid, candidate_key=key)
                                for lid, key in [("L1", "lcsc:C105883"), ("L11", "lcsc:C53109434"),
                                                 ("L18", "lcsc:C1857757")]]
                    assert [o["status"] for o in outcomes] == ["verified", "rejected", "unverified"]
                    first = f"partlens:run:{rec.run_id}:decision:{outcomes[1]['decision_id']}"
                    rec.log("qualification_outcomes", statuses=[o["status"] for o in outcomes],
                            memory_ids=[o["stored_in_memory"] for o in outcomes], source_for_recall=first)
                else:
                    call("recall_decisions", query="easyduino-rp2040 rejected 25V 50V resistor")
                    result = call("check_substitute", line_id="L11", candidate_key="lcsc:C53109434")
                    recalled = result["prior_decisions_from_memory"]
                    assert result["status"] == "rejected" and any(m["source"] == first for m in recalled)
                    assert not DecisionMemory(bridge, "TEST-unrelated-design").recall(
                        "lcsc:C25905", "lcsc:C53109434", line_id="L11")
                    assert not session.memory.recall("lcsc:C25905", "lcsc:C53109434", line_id="TEST-other-line")
                    rec.log("cold_recall_verified", source=first, rechecked_status=result["status"],
                            design_and_line_scope_verified=True, new_memory_id=result["stored_in_memory"])
                before = len(read_events(rec.path))
                review_snapshot(session)
                assert len(read_events(rec.path)) == before  # rendering must not issue SQL or mutate audit
                queries = [e["query"] for e in read_events(rec.path) if e["type"] == "zetaris_query"]
                if args.zetaris:
                    assert queries and all(q["status"] == "succeeded" and q["http_status"] == 200 for q in queries)
                rec.log("integration_validation_passed", phase=phase, successful_queries=len(queries),
                        rendering_read_only=True, owner_quantity=1,
                        quantity_source=session.design_requirement("board_quantity").provenance.source)
        except Exception as exc:
            rec.log("integration_validation_failed", error_type=type(exc).__name__, message=str(exc))
            raise
    print(json.dumps({"records": records, "status": "passed", "live_llm": False}))


if __name__ == "__main__":
    main()
