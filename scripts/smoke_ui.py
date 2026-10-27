"""Programmatic desktop smoke check on the approved demo; does not invent a quantity or call an LLM."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from partlens.cli import catalogs_from_args
from partlens.demo import DEMO_BOM
from partlens.optimise.cost import load_fees
from partlens.ui import ReviewApp


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--catalog", action="append", required=True)
    parser.add_argument("--evidence", action="append")
    parser.add_argument("--fees")
    args = parser.parse_args()
    app = ReviewApp(catalogs_from_args(args), Path(".partlens"), load_fees(args.fees))
    app.root.withdraw()
    try:
        app.tool("import_bom", path=str(DEMO_BOM), name="easyduino-rp2040")
        app.tool("match_parts")
        app.tool("find_missing_information")
        app.refresh()
        app.root.update_idletasks()
        rows = app.part_table.get_children()
        assert len(rows) == len(app.session.bom.lines)
        assert len(app.notebook.tabs()) == 8
        assert app.session._boards() is None
        assert "No requirements recorded" in app.views["Requirements"].get("1.0", "end")
        selected = next(i for i in rows if app.part_table.item(i, "values")[-1] != "Unmatched")
        key = app.part_table.item(selected, "values")[-1]
        app.part_table.selection_set(selected)
        app.show_part_evidence()
        assert key in app.views["Evidence"].get("1.0", "end")
        for line_id, candidate in (("L1", "lcsc:C105883"), ("L11", "lcsc:C53109434"), ("L18", "lcsc:C1857757")):
            app.tool("check_substitute", line_id=line_id, candidate_key=candidate)
        app.refresh()
        assert len(app.qualification_table.get_children()) == 3
        app.qualification_filter.set("rejected")
        app.render_qualifications()
        checked = app.qualification_table.get_children()
        assert len(checked) == 1
        assert "equivalence: REJECTED" in app.views["Qualifications"].get("1.0", "end")
        app.qualification_table.selection_set(checked[0])
        app.show_qualification()
        text = app.views["Qualifications"].get("1.0", "end")
        assert "Original:" in text and "Candidate:" in text and "Required:" in text and "Application:" in text
        assert app.session._boards() is None
        app.session.recorder.log("ui_programmatic_smoke", bom_rows=len(rows), tabs=8,
                                 evidence_selection=True, quantity_not_invented=True,
                                 qualification_filter_and_comparison=True,
                                 visual_review="separate manual UI evidence; this record is programmatic only")
        print(json.dumps({"record": str(app.session.recorder.path), "rows": len(rows), "tabs": 8,
                          "status": "programmatic smoke passed"}))
    except Exception as exc:
        app.session.recorder.log("ui_smoke_failure", error_type=type(exc).__name__, message=str(exc))
        raise
    finally:
        app.close()


if __name__ == "__main__":
    main()
