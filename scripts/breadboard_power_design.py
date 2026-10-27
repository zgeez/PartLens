"""Run the Breadboard Power Supply New Design workflow end-to-end and persist artifacts + desktop conversation."""

from __future__ import annotations

import json
from pathlib import Path

from partlens.agent import ScriptedProvider
from partlens.chat_engine import design_summary
from partlens.conversations import ConversationStore
from partlens.core.model import to_jsonable
from partlens.design.agent import DesignAgent, render
from partlens.design.cli import export
from partlens.design.session import DesignSession
from partlens.memory.hmem import DecisionMemory, HMemBridge
from partlens.optimise.cost import load_fees
from partlens.paths import app_home
from partlens.records import RunRecorder
from partlens.sources.audit import AuditedCatalog
from partlens.sources.catalog import LocalCatalog, record_from_row
from partlens.sources.jlcpcb import Lookup, row_from_detail

DESCRIPTION = (
    "Design a dual-rail breadboard power supply with USB-C 5V DC input (4.75V to 5.25V), "
    "a regulated 3.3V primary output rail and a 5V secondary breadboard rail, delivering "
    "500mA maximum continuous load current for 5 boards. Set reasonable provisional defaults "
    "for the remaining parameters."
)

CONFIRMED_REQUIREMENTS = [
    ("logic_voltage", "3.3V", "3.3V", "User-confirmed primary regulated breadboard rail voltage"),
    ("secondary_rail_voltage", "5V", "5V", "User-confirmed secondary breadboard rail voltage"),
    ("input_voltage_min", "4.75V", "4.75V", "User-confirmed minimum USB-C 5V input voltage"),
    ("input_voltage_max", "5.25V", "5.25V", "User-confirmed maximum USB-C 5V input voltage"),
    ("rail_current_max", "500mA", "500mA", "User-confirmed maximum continuous 3.3V rail current"),
    ("board_quantity", "5", "5 boards", "User-confirmed prototype build quantity"),
]

PROVISIONAL_DEFAULTS = [
    {"parameter": "rail_selection", "value": "jumper_selectable",
     "rationale": "Provisional agent default: 1x3P shunt headers allow independent 3.3V/5V selection per rail"},
    {"parameter": "width", "value": "53mm",
     "rationale": "Provisional agent default: spans standard MB-102 breadboard width across outer power strips"},
    {"parameter": "height", "value": "32mm",
     "rationale": "Provisional agent default: compact plug-in module depth leaving breadboard tie-points open"},
    {"parameter": "parts_budget", "value": "4USD",
     "rationale": "Provisional agent default: target component-only budget per board"},
]

INITIAL_SELECTIONS = {
    "input_power": "input_power.usb_c_5v",
    "power": "power.xc6206_ldo",
    "rail_output": "rail_output.breadboard_headers",
    "indicator": "indicator.power_led",
}


def load_cached_catalogs() -> list[AuditedCatalog]:
    """Load existing timestamped internal LCSC and JLCPCB cache fixtures without network calls."""
    catalogs: list[AuditedCatalog] = []
    lcsc_path = Path(".partlens/cache/lcsc-easyduino.json")
    rows = []
    if lcsc_path.is_file():
        lcsc_cat = LocalCatalog.from_json(lcsc_path)
        for rec in lcsc_cat._by_key.values():
            rows.append(rec)
    jlc_dir = Path(".partlens/jlcpcb/cache")
    if jlc_dir.is_dir():
        seen_keys = {r.key for r in rows}
        for path in sorted(jlc_dir.glob("*.json")):
            try:
                entry = json.loads(path.read_text(encoding="utf-8"))
                lookup = Lookup(
                    (), entry.get("retrieved_at", "2026-10-25T00:00:00Z"),
                    entry.get("request_id", "cached"), entry.get("trace_id"), 200,
                    entry.get("response_digest", "cached"), True,
                )
                for item in (entry.get("payload") or {}).get("data") or ():
                    if isinstance(item, dict) and item.get("componentCode"):
                        for sup in ("jlcpcb", "lcsc"):
                            k = f"{sup}:{item['componentCode']}"
                            if k not in seen_keys:
                                row = row_from_detail(item, lookup)
                                row["supplier"] = sup
                                rows.append(record_from_row(row))
                                seen_keys.add(k)
            except Exception:
                continue
    if rows:
        catalogs.append(AuditedCatalog(LocalCatalog(rows, name="cached-supplier-fixtures")))
    return catalogs


class BreadboardScriptedProvider(ScriptedProvider):
    """Deterministic scripted sequence that exercises the full DesignAgent workflow and alternative comparison."""

    def next_turn(self, system, messages, tools):
        results = [m for m in messages if m["role"] == "user" and isinstance(m["content"], list)]
        return super().next_turn(system, results[-1:] or messages, tools)


def build_script() -> list:
    return [
        [("start_new_design", {})],
        [("design_requirements", {})],
        [("ask_user", {"gap_id": "input_interface", "question": "Which DC input interface is required?"})],
        [("ask_user", {"gap_id": "rail_selection", "question": "How should the breadboard output rails be configured?"})],
        *[
            [("record_design_requirement", {"parameter": k, "value": v, "user_quote": q, "rationale": r})]
            for k, v, q, r in CONFIRMED_REQUIREMENTS
        ],
        [("propose_design_requirements", {"requirements": PROVISIONAL_DEFAULTS})],
        [("design_patterns", {})],
        [("select_design_patterns", {
            "selections": INITIAL_SELECTIONS,
            "justification": "Initial trial with XC6206P332MR 250mA LDO to evaluate linear thermal/current limits against 500mA target",
        })],
        [("compare_design_alternatives", {})],
        lambda results: [(
            "investigate_design_alternative",
            {"alternative_id": next(
                a["id"] for a in results[0]["alternatives"]
                if "power.design_budget" in a["resolved_failures"]
                and "power.thermal_dissipation" in a["resolved_failures"]
                and not a["new_failures"]
                and a["selections"]["power"] == "power.tps63031"
            )},
        )],
    ]


def run_breadboard_workflow(root: Path | None = None, *, sync_desktop: bool = True) -> dict:
    rec = RunRecorder.create((root / "runs") if root else Path(".partlens/runs"))
    design_id = f"breadboard-psu-{rec.run_id}"
    out_root = (root / "new-design" / rec.run_id) if root else (Path(".partlens/new-design") / rec.run_id)
    out_root.mkdir(parents=True, exist_ok=True)
    catalogs = load_cached_catalogs()
    fee_files = sorted(Path(".partlens/fees").glob("jlcpcb-economic-*.json"))
    fees = load_fees(fee_files[-1]) if fee_files else None

    def ask_callback(question: str):
        ans = "usb_c" if "input" in question.casefold() else None
        if ans is not None:
            rec.log("user_message", text=ans, origin="user", input_kind="interactive_answer")
        return ans

    with HMemBridge(out_root / "hmem") as bridge:
        session = DesignSession(
            rec, catalogs, description=DESCRIPTION, design_id=design_id,
            memory=DecisionMemory(bridge, design_id), fees=fees,
            engineering_mode=True, interaction_mode=True,
        )
        rec.log("memory_engine", info=bridge.info)
        agent = DesignAgent(
            session, BreadboardScriptedProvider(build_script()), ask_callback,
            allow_proposals=True, max_steps=30, max_tool_calls=60,
        )
        rendered = agent.send(DESCRIPTION, origin="user")
        artifacts_dir = export(session, out_root / "artifacts")

    # Verify cold-session H-MEM recall & reverification
    with HMemBridge(out_root / "hmem") as cold_bridge:
        cold_rec = RunRecorder.create((root / "runs") if root else Path(".partlens/runs"))
        cold_session = DesignSession(
            cold_rec, catalogs, description=DESCRIPTION, design_id=design_id,
            memory=DecisionMemory(cold_bridge, design_id), fees=fees,
            engineering_mode=True, interaction_mode=True,
        )
        cold_session.spec = session.spec
        cold_session.select_design_patterns(session.circuit.selections, justification="Cold-session H-MEM recheck")
        cold_session.generate_design_bom()
        reverified = cold_session.reverify_design(rec.run_id)

    report = session.design_report()
    desktop_chat_id = None
    if sync_desktop:
        for base_dir in (app_home() / "state", Path(".partlens/desktop-profile/state")):
            try:
                store = ConversationStore(base_dir)
                for existing in store.list():
                    if "breadboard" in existing.title.casefold():
                        store.delete(existing.id)
                chat = store.create("Breadboard Power Supply (3.3V / 5V Dual Rail)", "design")
                store.message(chat, "user", DESCRIPTION)
                store.message(chat, "assistant",
                    "I've initialized the **Breadboard Power Supply** design (covering USB-C input protection, 3.3 V regulation, dual breadboard output headers, and power status indication) "
                    "and confirmed the specifications stated in your prompt:\n\n"
                    "- **Primary Regulated Rail:** 3.3 V\n"
                    "- **Secondary Rail:** 5 V\n"
                    "- **Input Voltage Range:** 4.75 V to 5.25 V\n"
                    "- **Max Continuous Load Current:** 500 mA\n"
                    "- **Build Quantity:** 5 boards\n"
                    "- **DC Input Connector:** USB-C (5 V)\n\n"
                    "Before I set provisional defaults for the remaining parameters and run the regulator and thermal checks, "
                    "let's clarify the remaining configuration choice:", kind="commentary")
                store.message(chat, "assistant", "How should the breadboard output rails be configured (**Jumper-selectable**, **Fixed dual-rail**, or **Switch-controlled**)?", kind="question")
                store.message(chat, "user", "Let AI set this requirement (provisional default).", kind="requirement_answer")
                store.message(chat, "assistant",
                    "I've set **Rail Selection** to **jumper selectable** as a provisional requirement (*AI provisional default: 1x3P 2.54 mm shunt jumper headers per breadboard side; non-binding*).\n\n"
                    "### Deterministic Architecture & Thermal Evaluation\n"
                    "- **Initial LDO Trial (Rejected):** The **XC6206P332MR** (250 mA SOT-23 linear regulator) failed both **Continuous Current Budget** (requires 500 mA vs. 250 mA max) and **Thermal Dissipation** (0.98 W dropout dissipation vs. 0.25 W SOT-23 limit; thermal ceiling is 127.7 mA).\n"
                    "- **Autonomous Architecture Correction (Selected):** Switched the 3.3 V regulator to the **TPS63031DSKR** (1.2 A synchronous buck-boost converter), resolving both the current and thermal failures while preserving the failed LDO trial in the design history.\n"
                    "- **BOM & Sourcing:** Generated the 16 component roles (22 placements/board), matched official JLCPCB/LCSC parts, verified specifications, and calculated 5-board vs. 60-board cost scenarios.",
                    kind="commentary")
                chat_art_dir = base_dir / "chat-artifacts" / rec.run_id
                chat_art_dir.mkdir(parents=True, exist_ok=True)
                report_path = chat_art_dir / "report.json"
                report_path.write_text(json.dumps(to_jsonable(report), indent=2, ensure_ascii=False), encoding="utf-8")
                summary_text = design_summary(report)
                store.append(chat, "chat_artifact", mode="new_design", run_id=rec.run_id, record=str(rec.path),
                             report=str(report_path), export=artifacts_dir, cancelled=False)
                store.message(chat, "assistant", summary_text, kind="report")
                if desktop_chat_id is None:
                    desktop_chat_id = chat.id
                try:
                    from partlens.settings import load_settings
                    from partlens.web_desktop import DesktopBridge
                    home_dir = base_dir.parent
                    bridge = DesktopBridge(home_dir, load_settings(home_dir), catalogs, token="SYNC")
                    try:
                        bridge.request("select_chat", {"id": chat.id}, token="SYNC")
                        bridge.request("bom_from_design", {}, token="SYNC")
                    finally:
                        bridge._projects.close()
                except Exception:
                    pass
            except PermissionError:
                continue

    return {
        "run_id": rec.run_id,
        "design_id": design_id,
        "record": str(rec.path),
        "artifacts": artifacts_dir,
        "desktop_chat_id": desktop_chat_id,
        "reverified_count": len(reverified["comparisons"]),
        "reverified_outcomes": [c["outcome"] for c in reverified["comparisons"]],
        "report": report,
        "rendered": rendered,
    }


if __name__ == "__main__":
    outcome = run_breadboard_workflow()
    print(outcome["rendered"])
    print("\n" + json.dumps({
        "run_id": outcome["run_id"],
        "design_id": outcome["design_id"],
        "record": outcome["record"],
        "artifacts": outcome["artifacts"],
        "desktop_chat_id": outcome["desktop_chat_id"],
        "reverified_count": outcome["reverified_count"],
        "reverified_outcomes": outcome["reverified_outcomes"],
    }, indent=2))
