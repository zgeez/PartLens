"""Command line: interactive agent session, replay, and the Zetaris / H-MEM smoke tests."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from .records import RunRecorder
from .sources.catalog import Catalog, LocalCatalog
from .optimise.cost import load_fees

STATE = Path(os.environ.get("PARTLENS_STATE", ".partlens"))


def load_env_file(path: Path = Path(".env.local")) -> None:
    """Minimal KEY=VALUE loader; existing environment variables win."""
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def catalogs_from_args(args: argparse.Namespace, *, state: Path | None = None) -> list[Catalog]:
    state = state if state is not None else STATE
    cats: list[Catalog] = []
    if getattr(args, "jlc", False):
        from .sources.jlcpcb import JLCCatalog, JLCClient, JLCConfig

        cfg = JLCConfig.from_env()
        if cfg is None:
            sys.exit("JLCPCB not configured: set JLC_APP_ID, JLC_ACCESS_KEY and JLC_SECRET_KEY in .env.local")
        lead_path = getattr(args, "jlc_leads", None)
        if lead_path and any(p.casefold() == "experiments" or "benchmark" in p.casefold() or "badge" in p.casefold()
                             for p in Path(lead_path).resolve().parts):
            sys.exit("excluded material cannot supply research leads")
        leads = LocalCatalog.from_json(lead_path) if lead_path else None
        cats.append(JLCCatalog(JLCClient(cfg, cache_dir=state / "jlcpcb/cache"), leads))
    if getattr(args, "zetaris", False):
        from .sources.zetaris import ZetarisCatalog, ZetarisClient, ZetarisConfig

        cfg = ZetarisConfig.from_env()
        if cfg is None or not cfg.parts_table:
            sys.exit("Zetaris not configured: set ZETARIS_BASE_URL, ZETARIS_ORG_ID, ZETARIS_API_KEY and "
                     "PARTLENS_ZETARIS_PARTS_TABLE")
        if getattr(args, "jlc", False):
            from .sources.jlcpcb import JLCZetarisCatalog

            cats[0] = JLCZetarisCatalog(cats[0], ZetarisClient(cfg))
        else:
            cats.append(ZetarisCatalog(ZetarisClient(cfg), cfg.parts_table))
    for c in getattr(args, "catalog", None) or []:
        cats.append(LocalCatalog.from_json(c))
    if not cats:
        sys.exit("no catalogue: pass --catalog FILE, --zetaris and/or --jlc")
    for review in getattr(args, "evidence", None) or []:
        from .sources.review import ReviewedCatalog
        cats = [ReviewedCatalog(c, review) for c in cats]
    return cats


def cmd_chat(args: argparse.Namespace) -> None:
    from .agent import Agent, provider_from_env
    from .memory.hmem import DecisionMemory, HMemBridge
    from .session import Session
    from .workflow import WorkflowRequest
    from .demo import DEMO_BOM

    rec = RunRecorder.create(STATE / "runs")
    bridge = HMemBridge(STATE / "hmem")
    session = Session(rec, catalogs_from_args(args), memory=DecisionMemory(bridge, args.design or "easyduino-rp2040"),
                      fees=load_fees(args.fees))
    if args.quantity_record:
        session.restore_quantity(args.quantity_record)
    rec.log("cost_configuration", fees=session.fees)
    agent = Agent(session, provider_from_env(), ask=lambda q: input(f"\nPartLens asks: {q}\n> "))
    print(f"run {rec.run_id} -> {rec.path}")
    try:
        first = args.message or input("> ")
        print(agent.send(first, workflow=WorkflowRequest(str(DEMO_BOM), design=args.design or "easyduino-rp2040",
                                                        lines=("L1", "L11", "L18"), costs=True)))
        while True:
            msg = input("\n> ").strip()
            if msg in {"", "exit", "quit"}:
                break
            print(agent.send(msg, workflow=WorkflowRequest(str(DEMO_BOM), design=args.design or "easyduino-rp2040",
                                                          lines=("L1", "L11", "L18"), costs=True)))
    except (EOFError, KeyboardInterrupt):
        pass
    finally:
        bridge.close()


def cmd_replay(args: argparse.Namespace) -> None:
    from .replay import replay

    res = replay(args.run, None if args.recorded_sources else catalogs_from_args(args))
    print(json.dumps({"run": res.run_id, "replayed": res.replayed, "matched": res.matched,
                      "skipped": res.skipped, "mismatches": list(res.mismatches),
                      "audit_record": res.audit_record}, indent=2))
    sys.exit(0 if res.ok else 1)


def cmd_smoke_zetaris(args: argparse.Namespace) -> None:
    from .sources.zetaris import ZetarisClient, ZetarisConfig, ZetarisError

    rec = RunRecorder.create(STATE / "runs")
    cfg = ZetarisConfig.from_env()
    if cfg is None:
        rec.log("integration_blocked", integration="zetaris", reason="authorized credentials not configured")
        sys.exit(f"Zetaris not configured; record {rec.path}")
    try:
        client = ZetarisClient(cfg, recorder=rec)
    except ZetarisError as exc:
        rec.log("integration_blocked", integration="zetaris", reason=str(exc))
        sys.exit(f"Invalid Zetaris configuration; see {rec.path}")
    sql = args.sql
    if not sql:
        from .sources.zetaris import IDENT
        if not cfg.parts_table or not IDENT.fullmatch(cfg.parts_table):
            rec.log("integration_blocked", integration="zetaris", reason="demo supplier table not configured")
            sys.exit(f"Set PARTLENS_ZETARIS_PARTS_TABLE to the demo dataset table; record {rec.path}")
        from .core.bom import import_bom_csv
        from .demo import DEMO_BOM
        demo_parts = sorted({line.supplier_pn for line in import_bom_csv(DEMO_BOM).placed_lines if line.supplier_pn})
        values = ", ".join("'" + pn + "'" for pn in demo_parts)
        sql = (f"SELECT supplier, supplier_pn, mpn FROM {cfg.parts_table} "
               f"WHERE lower(supplier) = 'lcsc' AND supplier_pn IN ({values}) LIMIT 5")
    try:
        rows, q = client.query(sql, limit=5)
    except Exception:
        sys.exit(f"Zetaris query failed; see {rec.path}")
    matched_ids = [r.get("supplier_pn") for row in rows for r in [{str(k).lower(): v for k, v in row.items()}]
                   if r.get("supplier_pn") in (demo_parts if not args.sql else [])]
    rec.log("zetaris_dataset_evidence", query_request_id=q.request_id, demo_supplier_ids=matched_ids,
            demo_dataset_verified=bool(matched_ids), explicit_query=bool(args.sql))
    print(json.dumps({"record": str(rec.path), "query": q.__dict__, "rows": rows[:5]}, indent=2, default=str))
    if not args.sql and not matched_ids:
        sys.exit("Query returned no matching demo records; demo dataset integration remains unverified")


def cmd_live_demo(args: argparse.Namespace) -> None:
    from .demo import run_live_demo

    reports = run_live_demo(catalogs_from_args(args), STATE, ask=lambda q: input(f"\nPartLens asks: {q}\n> "),
                            fees=load_fees(args.fees))
    print(json.dumps(reports, indent=2, ensure_ascii=False))
    if (len(reports) < 2 or not reports[0]["automated_outcomes_met"]
            or any(not report["baseline_model_confirmed"] or report["failures"] for report in reports)
            or not reports[1]["criteria"].get("recalled_first_session_decision")
            or not reports[1]["criteria"].get("recalled_pair_rechecked")):
        sys.exit(1)


def cmd_evaluate(args: argparse.Namespace) -> None:
    from .evaluation import evaluate_run

    print(json.dumps(evaluate_run(args.run, prior_path=args.prior), indent=2, ensure_ascii=False))


def cmd_ui(args: argparse.Namespace) -> None:
    from .ui import ReviewApp

    ReviewApp(catalogs_from_args(args), STATE, load_fees(args.fees), quantity_record=args.quantity_record).run()


def cmd_cost_scenarios(args: argparse.Namespace) -> None:
    from .agent import Agent, ScriptedProvider, ToolCall
    from .demo import DEMO_BOM
    from .session import Session

    rec = RunRecorder.create(STATE / "runs")
    rec.log("scenario_setup", mode="deterministic; no live LLM", hypothetical_boards=60)
    session = Session(rec, catalogs_from_args(args), fees=load_fees(args.fees))
    rec.log("cost_configuration", fees=session.fees)
    agent = Agent(session, ScriptedProvider([]), lambda q: "")
    def call(tool_name, **kwargs):
        result = agent._execute(ToolCall(f"scenario-{rec.seq + 1}", tool_name, kwargs))
        output = json.loads(result["content"])
        if result.get("is_error"):
            raise ValueError(output["error"])
        return output
    call("import_bom", path=str(DEMO_BOM), name="easyduino-rp2040")
    call("match_parts")
    session.restore_quantity(args.quantity_record)
    for line_id, part in session.baseline.items():
        if part:
            for candidate in call("search_candidates", line_id=line_id)["candidates"]:
                call("check_substitute", line_id=line_id, candidate_key=candidate["key"])
    report = call("compare_cost_scenarios", hypothetical_boards=60)
    print(json.dumps({"record": str(rec.path), "report": report}, indent=2, ensure_ascii=False))


def cmd_compare(args: argparse.Namespace) -> None:
    from .evaluation import compare_runs

    report = compare_runs(args.reference, args.live, args.recall)
    rec = RunRecorder.create(STATE / "evaluations")
    rec.log("run_comparison", report=report)
    print(json.dumps({"record": str(rec.path), "outcomes": report["outcomes"],
                      "automated_live_baseline_criteria_met": report["automated_live_baseline_criteria_met"],
                      "automated_live_recall_criteria_met": report["automated_live_recall_criteria_met"]}, indent=2))


def cmd_smoke_hmem(args: argparse.Namespace) -> None:
    from .memory.hmem import HMemBridge

    with HMemBridge(STATE / "hmem-smoke") as b:
        print(json.dumps({"hello": b.info, "stats": b.call("stats")}, indent=2))


def cmd_smoke_jlc(args: argparse.Namespace) -> None:
    from .sources.jlcpcb import JLCClient, JLCConfig, JLCError, row_from_detail

    rec = RunRecorder.create(STATE / "runs")
    cfg = JLCConfig.from_env()
    if cfg is None:
        rec.log("integration_blocked", integration="jlcpcb", reason="authorized credentials not configured")
        sys.exit(f"Set JLC_APP_ID, JLC_ACCESS_KEY and JLC_SECRET_KEY locally; record {rec.path}")
    try:
        lookup = JLCClient(cfg, cache_dir=STATE / "jlcpcb/cache", recorder=rec).lookup(
            [args.code], refresh=args.refresh)
        for raw in lookup.data:
            row_from_detail(raw, lookup)
        print(json.dumps({"record": str(rec.path), "endpoint": lookup.source,
                          "queried_at": lookup.retrieved_at, "http_status": lookup.http_status,
                          "server_trace_id": lookup.trace_id, "cache_hit": lookup.cached,
                          "returned_codes": [r["componentCode"] for r in lookup.data],
                          "commercial_terms": "currency, MOQ, order multiple and assembly eligibility remain unknown"},
                         indent=2))
    except JLCError:
        sys.exit(f"Official component lookup incomplete; see {rec.path}")


def cmd_preflight(args: argparse.Namespace) -> None:
    from .preflight import run_preflight
    report = run_preflight(STATE)
    print(json.dumps(report, indent=2))
    if not report['services_available']:raise SystemExit(1)


def main(argv: list[str] | None = None) -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    load_env_file()
    p = argparse.ArgumentParser(prog="partlens")
    sub = p.add_subparsers(dest="cmd", required=True)
    preflight = sub.add_parser('preflight', help='check Ollama/model, fresh official JLC read, demo Zetaris SELECT and H-MEM')
    preflight.set_defaults(fn=cmd_preflight)

    def add_sources(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("--catalog", action="append", help="local catalogue JSON (repeatable)")
        sp.add_argument("--zetaris", action="store_true", help="query the parts table through Zetaris")
        sp.add_argument("--jlc", action="store_true", help="official read-only JLCPCB public-component API")
        sp.add_argument("--jlc-leads", help="existing internal fixture for code discovery only; never used as official evidence")
        sp.add_argument("--evidence", action="append", help="operator-reviewed manufacturer evidence JSON")
        sp.add_argument("--fees", help="operator-selected assembly fee schedule JSON; missing fees stay unknown")
        sp.add_argument("--quantity-record", help="restore the original confirmed quantity from an existing run")

    c = sub.add_parser("chat", help="interactive agent session")
    add_sources(c)
    c.add_argument("--design")
    c.add_argument("-m", "--message")
    c.set_defaults(fn=cmd_chat)

    r = sub.add_parser("replay", help="re-execute a run record and compare outputs")
    add_sources(r)
    r.add_argument("run")
    r.add_argument("--recorded-sources", action="store_true", help="offline deterministic replay using lossless supplier observations in the run")
    r.set_defaults(fn=cmd_replay)

    z = sub.add_parser("smoke-zetaris", help="run one SQL statement through Zetaris")
    z.add_argument("--sql", help="defaults to querying the configured demo supplier table")
    z.set_defaults(fn=cmd_smoke_zetaris)

    h = sub.add_parser("smoke-hmem", help="start the H-MEM bridge and print its status")
    h.set_defaults(fn=cmd_smoke_hmem)

    jlc = sub.add_parser("smoke-jlc", help="one official read-only public-component lookup")
    jlc.add_argument("--code", default="C1525", help="explicit C code; defaults to approved demo capacitor")
    jlc.add_argument("--refresh", action="store_true", help="bypass the five-minute request cache")
    jlc.set_defaults(fn=cmd_smoke_jlc)

    live = sub.add_parser("live-demo", help="two controlled live model sessions; baseline fallback disabled")
    add_sources(live)
    live.set_defaults(fn=cmd_live_demo)

    ev = sub.add_parser("evaluate", help="evaluate a preserved run by outcomes, not tool-call sequence")
    ev.add_argument("run")
    ev.add_argument("--prior", help="first session record for recall verification")
    ev.set_defaults(fn=cmd_evaluate)

    ui = sub.add_parser("ui", help="local desktop BOM review with live agent and evidence tabs")
    add_sources(ui)
    ui.set_defaults(fn=cmd_ui)

    new = sub.add_parser("new-design", help="local requirements-to-patterns-to-new-BOM proposal; never imports a prior design")
    add_sources(new)
    new.add_argument("--idea", required=True, help="original product description; no private design files")
    new.add_argument("--design-id", help="operator-chosen independent design identifier")
    new.add_argument("--allow-proposals", action="store_true", help="delegate defaults, kept provisional rather than user-confirmed")
    new.add_argument("--unattended", action="store_true", help="questions remain unanswered, never fabricated")
    from .design.cli import run_new_design
    new.set_defaults(fn=run_new_design)

    scenarios = sub.add_parser("cost-scenarios", help="owner quantity versus hypothetical 60-board cost review")
    add_sources(scenarios)
    scenarios.set_defaults(fn=cmd_cost_scenarios)

    compare = sub.add_parser("compare", help="compare live and scripted runs by outcomes; preserve the comparison")
    compare.add_argument("--reference", required=True)
    compare.add_argument("--live", required=True)
    compare.add_argument("--recall")
    compare.set_defaults(fn=cmd_compare)

    args = p.parse_args(argv)
    if args.cmd == "cost-scenarios" and not args.quantity_record:
        p.error("cost-scenarios requires --quantity-record; an owner's answer is never invented")
    args.fn(args)


if __name__ == "__main__":
    main()
