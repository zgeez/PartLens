"""Real official component reads, deterministic decisions/costs and optional read-only Zetaris queries.

Only the approved public demo and an existing research lead are used. No LLM, orders, uploads, DDL,
private libraries, fabricated owner answers or supplier refresh outside the official API.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from partlens.agent import Agent, ScriptedProvider, ToolCall
from partlens.cli import load_env_file
from partlens.core.model import to_jsonable
from partlens.demo import DEMO_BOM
from partlens.optimise.cost import load_fees
from partlens.records import RunRecorder
from partlens.session import Session
from partlens.sources.catalog import LocalCatalog
from partlens.sources.jlcpcb import JLCCatalog, JLCClient, JLCConfig, JLCZetarisCatalog
from partlens.sources.zetaris import IDENT, ZetarisClient, ZetarisConfig, ZetarisInlineCatalog


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, default=Path(".partlens/cache/lcsc-easyduino.json"))
    parser.add_argument("--quantity-record", type=Path, required=True)
    parser.add_argument("--fees", type=Path)
    parser.add_argument("--zetaris", action="store_true")
    args = parser.parse_args()
    load_env_file()
    rec = RunRecorder.create(".partlens/runs")
    print(f"Record: {rec.path}", flush=True)
    try:
        cfg = JLCConfig.from_env()
        if cfg is None:
            raise ValueError("set JLC_APP_ID, JLC_ACCESS_KEY and JLC_SECRET_KEY locally")
        if any(p.casefold() == "experiments" or "benchmark" in p.casefold() or "badge" in p.casefold()
               for p in args.fixture.resolve().parts):
            raise ValueError("excluded material cannot be imported")
        fixture_hash = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
        old = LocalCatalog.from_json(args.fixture)
        # The alternative must already be in the retained internal research fixture.
        if old.get("lcsc:C105883") is None:
            raise ValueError("approved retained alternative is unavailable")
        official = JLCCatalog(JLCClient(cfg, recorder=rec))
        source = official
        zetaris = None
        if args.zetaris:
            zcfg = ZetarisConfig.from_env()
            if zcfg is None or not zcfg.parts_table or not IDENT.fullmatch(zcfg.parts_table):
                raise ValueError("authorized Zetaris demo table is not configured")
            zetaris = ZetarisClient(zcfg, recorder=rec)
            source = JLCZetarisCatalog(official, zetaris)
        rec.log("integration_validation", mode="deterministic tool execution; no live LLM", read_only=True,
                fixture_sha256=fixture_hash, approved_design=str(DEMO_BOM))
        session = Session(rec, [source], fees=load_fees(args.fees))
        agent = Agent(session, ScriptedProvider([]), lambda _: "")

        def call(tool_name: str, **kwargs):
            result = agent._execute(ToolCall(f"jlc-{rec.seq + 1}", tool_name, kwargs))
            value = json.loads(result["content"])
            if result.get("is_error"):
                raise ValueError(value["error"])
            return value

        call("import_bom", path=str(DEMO_BOM), name="easyduino-rp2040")
        matched = call("match_parts")
        session.restore_quantity(args.quantity_record)
        decision = call("check_substitute", line_id="L1", candidate_key="jlcpcb:C105883")
        sourcing = call("check_availability", part_key="jlcpcb:C105883", line_id="L1")
        scenarios = call("compare_cost_scenarios", hypothetical_boards=60)
        bound = session.catalogs[0]
        official = bound.base if isinstance(bound, JLCZetarisCatalog) else bound
        rows = list(official.rows.values())
        target = Path(".partlens/jlcpcb/datasets") / rec.run_id
        target.mkdir(parents=True, exist_ok=False)
        with (target / "parts.json").open("x", encoding="utf-8") as f:
            json.dump(rows, f, ensure_ascii=False, indent=2)
        differences = []
        for row in rows:
            before = old.get("lcsc:" + row["supplier_pn"])
            after = official.get("jlcpcb:" + row["supplier_pn"])
            if before is None:
                continue
            for name in ("mpn", "manufacturer", "package", "stock"):
                if getattr(before, name) != getattr(after, name):
                    differences.append({"part": after.key, "field": name,
                                        "retained": getattr(before, name), "official": getattr(after, name)})
            for name in set(before.params) | set(after.params):
                left, right = before.params.get(name), after.params.get(name)
                if (left.value if left else None) != (right.value if right else None):
                    differences.append({"part": after.key, "field": "params." + name,
                                        "comparison": "value_difference" if left and right else "adapter_coverage_difference",
                                        "retained": str(left.value) if left else None,
                                        "official": str(right.value) if right else None})
            differences.append({"part": after.key, "field": "price_breaks", "retained_currency": "USD",
                                "official_currency": None, "direct_currency_comparison_valid": False,
                                "retained": to_jsonable(before.price_breaks), "official": to_jsonable(after.price_breaks),
                                "retained_source": before.source, "official_source": after.source,
                                "retained_at": before.retrieved_at, "official_at": after.retrieved_at})
        rec.log("supplier_comparison", differences=differences, record_count=len(rows),
                note="Manufacturer label differences are discrepancies, not proof of different manufacturers; "
                     "no aliases or datasheet review transfers were invented.")
        join_evidence = None
        if zetaris:
            relation = ZetarisInlineCatalog(zetaris, rows)
            namespace = zetaris.cfg.parts_table.rsplit(".", 1)[0]
            sql = relation.prefix + (f"SELECT b.line_id, b.supplier_pn, p.mpn, p.stock, p.retrieved_at, p.source "
                  f"FROM {namespace}.bom b LEFT JOIN {relation.table} p ON b.supplier_pn = p.supplier_pn "
                  "WHERE b.placed = true ORDER BY b.line_id")
            returned, query = zetaris.query(sql)
            expected = {l.id for l in session.bom.placed_lines if l.supplier_pn}
            observed = {r["line_id"] for r in returned if r.get("mpn")}
            if observed != expected or len(returned) != len(session.bom.placed_lines):
                raise ValueError("Zetaris official supplier/BOM join did not match the approved demo")
            join_evidence = {"query": to_jsonable(query), "rows": returned}
            rec.log("jlcpcb_zetaris_bom_join", **join_evidence)
        if hashlib.sha256(args.fixture.read_bytes()).hexdigest() != fixture_hash:
            raise ValueError("retained fixture changed")
        report = {"record": str(rec.path), "parts_file": str(target / "parts.json"), "official_records": len(rows),
                  "decision": decision, "sourcing": sourcing, "scenarios": scenarios,
                  "differences": differences, "zetaris": join_evidence, "matching": matched,
                  "fixture_unchanged": True, "full_dollar_cost_available": False,
                  "qualification_succeeded": decision["status"] == "verified"}
        with (target / "report.json").open("x", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        rec.log("jlcpcb_validation_completed", report=str(target / "report.json"),
                decision_status=decision["status"], application_status=decision["application"]["status"],
                full_dollar_cost_available=False, fixture_unchanged=True,
                zetaris_join_succeeded=join_evidence is not None)
        print(json.dumps({"report": str(target / "report.json"), "records": len(rows),
                          "decision": decision["status"], "application": decision["application"]["status"],
                          "zetaris_join_succeeded": join_evidence is not None,
                          "full_dollar_cost_available": False}, indent=2))
        return 0
    except Exception as exc:
        rec.log("jlcpcb_validation_failed", error_type=type(exc).__name__, error=str(exc))
        print(f"Validation failed ({type(exc).__name__}); see {rec.path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
