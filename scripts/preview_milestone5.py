"""Display actual model-selected pairs in the existing UI after new deterministic supplier checks.

No model call is made by this preview. It uses current official JLCPCB/Zetaris reads and real H-MEM,
labels the original live run, and keeps all observations internal. Visual inspection is a separate step.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from partlens.cli import catalogs_from_args, load_env_file
from partlens.demo import DEMO_BOM
from partlens.optimise.cost import load_fees
from partlens.records import new_run_id, read_events
from partlens.sources.audit import AuditedCatalog
from partlens.ui import ReviewApp


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--quantity-record", required=True)
    parser.add_argument("--fees")
    args = parser.parse_args()
    load_env_file()
    args.jlc, args.zetaris, args.catalog, args.evidence, args.jlc_leads = True, True, [], [], None
    state = Path(".partlens/milestone5-ui") / new_run_id()
    source = catalogs_from_args(args)[0]
    source.base.client.cache_dir = state / "cache"
    app = ReviewApp([AuditedCatalog(source)], state, load_fees(args.fees), quantity_record=args.quantity_record)
    app.root.withdraw()
    try:
        selected = list(dict.fromkeys((e["input"]["line_id"], e["input"]["candidate_key"])
                        for e in read_events(args.run) if e["type"] == "tool_call" and e["name"] == "check_substitute"
                        and not e.get("error") and e.get("actor") == "model"))
        app.session.recorder.log("milestone5_ui_preview", source_live_run=str(args.run), model_called=False,
                                 mode="new deterministic checks of pairs selected by the recorded live agent")
        app.ensure_memory()
        app.tool("import_bom", path=str(DEMO_BOM), name="easyduino-rp2040")
        app.tool("match_parts")
        # Batch exactly the actual selected codes, not an operator-supplied candidate list.
        # This prefetch is outside a tool boundary. HTTP requests are still audited; subsequent tool
        # reads journal the complete returned records for replay, rather than inventing a prepare call.
        app.session.catalogs[0].base.prepare(sorted({key.split(":", 1)[1] for _, key in selected}))
        for line, key in selected:
            app.tool("check_substitute", line_id=line, candidate_key=key)
        for line in ("L1", "L11", "L18"):
            app.tool("check_availability", line_id=line, part_key=app.session.baseline[line].key)
        app.tool("compare_cost_scenarios", hypothetical_boards=60)
        app.refresh()
        app.status.set("Fresh official reads + deterministic rechecks of live-agent selections; no new LLM call. "
                       "Quantity 1; hypothetical 60. Costs incomplete.")
        app.session.recorder.log("milestone5_ui_ready", rows=len(app.part_table.get_children()),
                                 tabs=len(app.notebook.tabs()), source_live_run=str(args.run), visual_acceptance=False)
        print(json.dumps({"state": str(state), "record": str(app.session.recorder.path), "ready": True}), flush=True)
        app.root.deiconify()
        app.root.mainloop()
    finally:
        if app.bridge:
            app.bridge.close()


if __name__ == "__main__":
    main()
