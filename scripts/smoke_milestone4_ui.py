"""Programmatic desktop acceptance with actual tools and cold memory. No visual-verification claim."""

import argparse
import json
import time
from pathlib import Path

from partlens.cli import catalogs_from_args, load_env_file
from partlens.demo import DEMO_BOM
from partlens.optimise.cost import load_fees
from partlens.records import new_run_id, read_events
from partlens.ui import ReviewApp, review_snapshot


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", action="append")
    parser.add_argument("--zetaris", action="store_true")
    parser.add_argument("--evidence", action="append")
    parser.add_argument("--fees")
    parser.add_argument("--quantity-record", required=True)
    args = parser.parse_args()
    load_env_file()
    state = Path(".partlens/ui-validation") / new_run_id()
    app = ReviewApp(catalogs_from_args(args), state, load_fees(args.fees), quantity_record=args.quantity_record)
    app.root.withdraw()
    records = [str(app.session.recorder.path)]
    try:
        app.ensure_memory()
        app.tool("import_bom", path=str(DEMO_BOM), name="easyduino-rp2040")
        app.tool("match_parts")
        for line, key in [("L1", "lcsc:C105883"), ("L11", "lcsc:C53109434"), ("L18", "lcsc:C1857757")]:
            app.tool("check_substitute", line_id=line, candidate_key=key)
        app.tool("check_availability", line_id="L18", part_key="lcsc:C2843335")
        costs = app.tool("compare_cost_scenarios", hypothetical_boards=60)
        assert costs["scenarios"][0]["boards"] == 1 and costs["scenarios"][1]["scenario"] == "hypothetical"
        assert all(not s["comparison_complete"] for s in costs["scenarios"])
        app.refresh()
        assert len(app.part_table.get_children()) == 19 and len(app.notebook.tabs()) == 8
        assert "HYPOTHETICAL" in app.views["Cost"].get("1.0", "end")
        assert "complete: False" in app.views["Cost"].get("1.0", "end")
        app.session.recorder.log("ui_acceptance_write", programmatic=True, rows=19, tabs=8,
                                 cost_unknowns_and_hypothetical_labels=True, owner_quantity=app.session._boards())
        app.bridge.close()
        app.bridge = None
        app.recall()  # The real button handler, worker and queue; a new bridge process opens the saved store.
        deadline = time.monotonic() + 90
        while app.busy and time.monotonic() < deadline:
            app.root.update()
            time.sleep(0.02)
        assert not app.busy, "recall worker timed out"
        records.append(str(app.session.recorder.path))
        events = read_events(app.session.recorder.path)
        completion = next(e for e in events if e["type"] == "ui_recall_complete")
        assert completion["rechecked"] == 3
        assert len(review_snapshot(app.session)["Qualifications"]) == 3
        for status in ("verified", "rejected", "unverified"):
            app.qualification_filter.set(status)
            app.render_qualifications()
            assert len(app.qualification_table.get_children()) == 1
            assert "equivalence: " + status.upper() in app.views["Qualifications"].get("1.0", "end")
        assert "Current deterministic memory comparisons" in app.views["Explanation"].get("1.0", "end")
        assert app.session._boards() == 1
        app.session.recorder.log("ui_acceptance_passed", programmatic=True, independent_memory_processes=True,
                                 recall_rechecked=3, three_status_filters=True, owner_quantity=1,
                                 visual_verification=False, records=records)
        print(json.dumps({"status": "passed", "records": records, "visual_verification": False}))
    except Exception as exc:
        app.session.recorder.log("ui_acceptance_failed", error_type=type(exc).__name__, message=str(exc))
        raise
    finally:
        app.close()


if __name__ == "__main__":
    main()
