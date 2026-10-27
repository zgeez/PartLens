"""Milestone 1 end-to-end run on real data, with a scripted planner in place of the LLM.

Design: Easyduino RP2040 BOM (examples/easyduino-rp2040/bom.csv). Supplier data: the local LCSC snapshot
(.partlens/cache/lcsc-easyduino.json, created by `python -m partlens.sources.lcsc_snapshot`-style code; not
committed). Memory: Meterless H-MEM under .partlens/hmem. Run record: .partlens/runs/<run>.jsonl.

The planner's question is answered from the command line (``--answer``), so the provenance of the answer is the
person running the script. Usage:

    python examples/easyduino-rp2040/milestone1_run.py --answer "initially 60 boards"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from partlens.agent import Agent, ScriptedProvider
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.records import RunRecorder
from partlens.replay import replay
from partlens.session import Session
from partlens.sources.catalog import LocalCatalog

HERE = Path(__file__).resolve().parent
STATE = Path(".partlens")


def plan(quote_for_quantity: str):
    def ask(results):
        gaps = results[1]["gaps"]
        g = next(g for g in gaps if g["id"] == "design.board_quantity")
        return [("ask_user", {"question": g["suggested_question"], "gap_id": g["id"]})]

    def record(results):
        return [("record_requirement", {"subject": "design", "parameter": "board_quantity", "op": "==",
                                        "value": "60", "user_quote": quote_for_quantity})]

    def research(results):
        return [("search_candidates", {"line_id": "L1", "text": "100nF"}),
                ("search_candidates", {"line_id": "L11", "text": "5.1k"}),
                ("search_candidates", {"line_id": "L18"})]

    def check(results):
        calls = []
        for r in results:
            for c in r["candidates"]:
                calls.append(("check_substitute", {"line_id": r["line"], "candidate_key": c["key"]}))
        return calls

    return [
        [("import_bom", {"path": str(HERE / "bom.csv"), "name": "easyduino-rp2040"})],
        [("match_parts", {}), ("find_missing_information", {})],
        ask,
        record,
        [("check_availability", {"part_key": "lcsc:C2843335", "line_id": "L18"}),
         ("check_availability", {"part_key": "lcsc:C1525", "line_id": "L1"})],
        research,
        check,
        "Scripted milestone run complete.",
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--answer", required=True, help="answer to the board-quantity question")
    ap.add_argument("--snapshot", default=str(STATE / "cache" / "lcsc-easyduino.json"))
    args = ap.parse_args()
    if not Path(args.snapshot).exists():
        sys.exit(f"missing supplier snapshot {args.snapshot}")

    catalog = LocalCatalog.from_json(args.snapshot, name="lcsc-snapshot")
    rec = RunRecorder.create(STATE / "runs")
    with HMemBridge(STATE / "hmem") as bridge:
        session = Session(rec, [catalog], memory=DecisionMemory(bridge, "easyduino-rp2040"))
        agent = Agent(session, ScriptedProvider(plan(args.answer)), ask=lambda q: args.answer)
        print(agent.send("Review the Easyduino RP2040 BOM for sourcing risk and cheaper verified alternatives."))

        summary = {}
        for d in session.decisions.values():
            summary.setdefault(d.subject, {}).setdefault(d.status.value, []).append(d.candidate)
        recalled = sum(1 for e in map(json.loads, rec.path.read_text(encoding="utf-8").splitlines())
                       if e["type"] == "tool_call" and e["name"] == "check_substitute"
                       and e["output"].get("prior_decisions_from_memory"))
        stats = bridge.call("stats")

    res = replay(rec.path, [catalog])
    print(json.dumps({
        "run": rec.run_id, "record": str(rec.path),
        "requirements": session.list_requirements()["requirements"],
        "decisions_by_line": summary,
        "checks_with_prior_memory": recalled,
        "hmem": stats,
        "replay": {"replayed": res.replayed, "matched": res.matched, "mismatches": list(res.mismatches)},
    }, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
