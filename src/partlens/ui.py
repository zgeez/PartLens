"""Small local desktop workflow over the same auditable agent tools; no web hosting or extra dependencies."""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path
from typing import Any

from .agent import Agent, ScriptedProvider, ToolCall, provider_from_env
from .cli import load_env_file
from .core.model import to_jsonable
from .demo import DEMO_BOM
from .memory.hmem import DecisionMemory, HMemBridge
from .records import RunRecorder, read_events
from .secrets import redact
from .session import Session, part_view
from .sources.catalog import Catalog
from .workflow import WorkflowRequest


def review_snapshot(session: Session) -> dict[str, Any]:
    """Read-only view; statuses and money always originate in deterministic session operations."""
    events = read_events(session.recorder.path) if session.recorder.path.exists() else []
    calls = [e for e in events if e["type"] == "tool_call"]
    memories = [m for e in calls if e["name"] == "recall_decisions"
                for m in e.get("output", {}).get("memories", [])]
    final = next((e for e in reversed(events) if e["type"] == "agent_result"), None)
    explanation = final["rendered"] if final and final.get("context_digest") == session.context_digest() else (
        "Previous result is historical; the BOM, requirements or supplier context changed. Run a new review."
        if final else "Analysis is not complete. Model drafts are retained only in the run record."
        if any(e["type"] == "assistant_turn" for e in events) else "")
    if memories:
        explanation += "\n\nRecalled memory context (requires current evidence rechecking):\n" + "\n\n".join(
            f"{m['id']} | {m['source']}\n{m['content']}" for m in memories)
    rechecks = [e["output"] for e in calls if e["name"] == "reverify_decision" and not e.get("error")]
    if rechecks:
        explanation += "\n\nCurrent deterministic memory comparisons:\n" + "\n".join(
            f"{r['memory_id']}: {r['outcome']} | {r['reason']}\n{r['source']}" for r in rechecks)
    qualifications = [e["output"] for e in calls if e["name"] == "check_substitute" and not e.get("error")]
    qualifications += [r["current_decision"] for r in rechecks if r.get("current_decision")]
    workflow = next((e["snapshot"] for e in reversed(events) if e["type"] == "workflow_state"), None)
    return {
        "Requirements": {**session.list_requirements(),
                         "gaps": session.find_missing_information()["gaps"] if session.bom else [], "workflow": workflow},
        "Parts": session.describe_design() if session.bom else {"note": "Load the demo BOM to begin."},
        "Evidence": {key: part_view(p) for key, p in session.observed_parts.items()},
        "Qualifications": [{**d, "current_context": d.get("decision_id") in session.decisions} for d in qualifications],
        "Sourcing": [e["output"] for e in calls if e["name"] == "check_availability"],
        "Cost": next((e["output"] if e.get("context_digest") == session.context_digest() else
                      {"note": "Historical cost context is not confirmed current; rerun cost comparison."}
                      for e in reversed(calls) if not e.get("error") and
                      e["name"] in {"estimate_cost", "compare_cost_scenarios", "optimise_cost"}),
                     {"note": "Record the build quantity, then estimate. Missing fees remain unknown."}),
        "Explanation": explanation,
        "Run record": {"path": str(session.recorder.path), "events": events},
    }


def nominal_price_summary(observations: list[dict]) -> str:
    lines = ["Official nominal price arithmetic (not a purchase quote or USD total):"]
    for p in observations:
        lines.append(f"  {p['line']} | {p['part']} | demand {p['needed']} x {p['unit_price']} = "
                     f"{p['nominal_amount']} | currency: {p['currency'] or 'UNKNOWN'}")
        lines.append(f"    {p['source']} | retrieved {p['retrieved_at']}")
    unknowns = sorted({v for p in observations for v in p["unknowns"]})
    lines.append("Unresolved terms: " + ", ".join(unknowns))
    return "\n".join(lines)


def format_view(name: str, content: Any) -> str:
    """Readable summaries retain sources and qualification scope; the run tab holds raw events."""
    if isinstance(content, str):
        return content or "No agent explanation has been generated for this session."
    if isinstance(content, dict) and set(content) == {"note"}:
        return content["note"]
    if name == "Requirements":
        rows = content["requirements"]
        recorded = "\n\n".join(f"{r['id']}: {r['op']} {r['value']}\n"
                           f"  {r['provenance']} | binding: {r['binding']}\n  {r['source']}" for r in rows) or \
            "No requirements recorded. Review the BOM to identify missing information."
        shown = recorded + "\n\nMissing information:\n" + "\n\n".join(
            f"{gap['id']}: {gap['missing']}\n  {gap['why']}\n  {gap['suggested_question']}"
            for gap in content.get("gaps", []))
        if content.get("workflow"):
            shown += "\n\nWorkflow operations:\n" + "\n".join(
                f"  {s['id']}: {s['status']} {s['failure_reason']}" for s in content["workflow"]["states"])
        return shown
    if name == "Evidence":
        blocks = []
        for key, part in content.items():
            blocks.append(f"{key} | {part['manufacturer']} {part['mpn']}\n"
                          f"{part['source']}\nRetrieved: {part['retrieved_at']}")
            blocks.append(f"  Package: {part['package']} | recorded stock: {part['stock']} | lifecycle: {part['lifecycle']}\n"
                          f"  MOQ: {part['moq']} | order multiple: {part['order_multiple']}\n"
                          f"  Price breaks (quantity, unit price, currency): {part['price_breaks']}\n"
                          f"  Datasheet: {part['datasheet_url'] or 'not supplied'}")
            if part.get("commercial_unknowns"):
                blocks.append("  Unknown supplier terms: " + ", ".join(part["commercial_unknowns"]))
                metadata = part.get("supplier_metadata", {})
                blocks.append(f"  Classification confidence: {metadata.get('assembly_class_mapping') or 'UNKNOWN'} "
                              f"(raw library type: {metadata.get('api_library_type')})\n"
                              "  Assembly eligibility: UNKNOWN; the API flag has no established eligibility meaning.\n"
                              f"  Supplier-reported joints/part: {metadata.get('solder_joint_count')} "
                              "(board billing applicability unknown)")
                ends = part.get("price_range_ends", [])
                blocks.append("  Official price intervals:")
                for i, (minimum, price, currency) in enumerate(part["price_breaks"]):
                    end = ends[i] if i < len(ends) else None
                    blocks.append(f"    {minimum}..{end if end is not None else 'unbounded'}: {price} "
                                  f"{currency or '(currency UNKNOWN)'}/unit")
            if evidence := part.get("assembly_class_evidence"):
                blocks.append(f"  Assembly classification: {part['assembly_class']} ({part['assembly_service']})\n"
                              f"    {evidence['locator']} | retrieved {evidence['retrieved_at']}")
            blocks.extend("  REVIEW: " + note for note in part.get("engineering_notes", []))
            for field, param in part["params"].items():
                blocks.append(f"  {field}: {param['value']} ({param.get('rating_kind') or 'rating domain unspecified'})\n"
                              f"    {param['evidence']['locator']}")
            blocks.append("")
        return "\n".join(blocks) or "Load and match the demo to inspect its evidence."
    if name == "Qualifications":
        blocks = []
        for decision in content:
            if "error" in decision:
                blocks.append("Check incomplete: " + decision["error"])
                continue
            if decision.get("current_context") is False:
                blocks.append("HISTORICAL DECISION: requirements or BOM changed; recheck before using this result.")
            comparison = decision.get("comparison", {})
            for label in ("original", "candidate"):
                part = comparison.get(label, {})
                blocks.append(f"{label.title()}: {part.get('manufacturer', 'unknown manufacturer')} | "
                              f"{part.get('mpn', decision[label])} | {part.get('package', 'unknown package')}\n"
                              f"  {part.get('source', '')}\n  Retrieved: {part.get('retrieved_at', 'unknown')}")
            blocks.append(f"{decision['line']} | {decision['original']} -> {decision['candidate']}\n"
                          f"Original-specification equivalence: {decision['status'].upper()}\n"
                          f"Application: {decision.get('application', {}).get('status', 'unverified').upper()}")
            for check in decision["checks"]:
                blocks.append(f"  {check['status'].upper()}: {check['message']}")
                if check.get("expected") is not None or check.get("observed") is not None:
                    blocks.append(f"    Required: {check.get('expected')} | observed: {check.get('observed')}")
                blocks.extend("    " + e for e in check["evidence"])
            blocks.append("  Application checks:")
            for check in decision.get("application", {}).get("checks", []):
                blocks.append(f"    {check['status'].upper()}: {check['message']}")
            blocks.append("  " + decision.get("application", {}).get("note", ""))
            blocks.append("")
        return "\n".join(blocks) or "No alternatives checked yet. Run a review."
    if name == "Cost" and "scenarios" in content:
        blocks = [content["note"], "Scenario overview (assembly totals and savings remain incomplete):"]
        for scenario in content["scenarios"]:
            blocks.append(f"  {scenario['boards']} boards | {scenario['scenario'].upper()} | "
                          f"assembled savings: {scenario['assembled_savings']} | "
                          f"complete: {scenario['comparison_complete']}")
        for scenario in content["scenarios"]:
            blocks.append(f"\n{scenario['boards']} boards — {scenario['scenario'].upper()}\n"
                          f"Quantity source: {scenario['quantity_source']}\n"
                          f"Proposed replacements: {scenario['proposed_replacements']}\n"
                          f"Covered component subtotal difference: {scenario['component_subtotal_difference']}\n"
                          f"Assembled savings: {scenario['assembled_savings']} | complete: {scenario['comparison_complete']}\n"
                          "Official manufacturer quotation: unavailable\n")
            if observations := scenario.get("official_nominal_price_observations"):
                blocks.append(nominal_price_summary(observations))
            for label in ("baseline", "proposed"):
                blocks.append(label.upper() + "\n" + format_view("Cost", scenario[label]))
            blocks.append("Excluded alternatives:\n" + "\n".join(scenario["excluded"]))
        return "\n".join(blocks)
    if name == "Sourcing":
        return "\n\n".join(
            f"{r.get('part', 'Unknown part')} | needed {r.get('needed', '?')}, order {r.get('ordered', '?')}\n" +
            "\n".join(f"  {c['status'].upper()}: {c['message']}" for c in r.get("checks", []))
            for r in content) or "Build quantity is needed for sourcing checks."
    if name == "Cost" and "parts_total" in content:
        observations = content.get("official_nominal_price_observations")
        return ((nominal_price_summary(observations) + "\n\n" if observations else "")
                + f"{content['boards']} boards | {content['currency']}\n\n"
                f"Component subtotal: {content['parts_total']}\n"
                f"Component sourcing complete: {content['component_complete']}\n"
                f"Estimated assembled total: {content['total']}\n"
                f"All costs complete: {content['complete']}\n"
                f"Known subtotal (conditional): {content['known_subtotal']}\n\n"
                "Missing inputs / sourcing risks:\n" + "\n".join("  - " + p for p in content["problems"]) +
                "\n\nDerivation:\n" + "\n".join(content["derivation"]) +
                "\n\n" + "\n".join(f"{line['line']}: {line['derivation']}" for line in content["lines"]))
    return json.dumps(to_jsonable(content), indent=2, ensure_ascii=False)


def failure_message(exc: Exception) -> str:
    """Keep detailed sanitized diagnostics in the audit, with a short actionable desktop status."""
    message = str(exc).lower()
    if "credit balance" in message or "insufficient_quota" in message:
        return "Live provider unavailable: insufficient API credit. Restore access locally, then retry; evidence is saved."
    if "authentication" in message or "unauthorized" in message or "invalid api" in message:
        return "Provider authentication failed. Check local configuration; evidence is saved."
    return redact(f"Incomplete: {exc}")[:300]


class ReviewApp:
    def __init__(self, catalogs: list[Catalog], state: Path, fees=None, *, quantity_record: str | None = None,
                 demo_bom: Path | None = None, design_name: str = 'easyduino-rp2040', root=None) -> None:
        import tkinter as tk
        from tkinter import ttk

        self.tk, self.ttk = tk, ttk
        self.root = root if root is not None else tk.Tk()
        self.root.title("PartLens | Evidence-backed BOM review")
        self.root.geometry("1120x780")
        self.root.minsize(900, 600)
        self.state, self.catalogs, self.fees = state, catalogs, fees
        self.demo_bom=demo_bom if demo_bom is not None else DEMO_BOM
        self.design_name=design_name
        self.quantity_record = quantity_record
        self.events: queue.Queue = queue.Queue()
        self.answer_ready = threading.Event()
        self.answer = ""
        self.busy = False
        self.closed = False
        self.bridge = None
        self.agent = None
        self.new_session()

        mode_controls = ttk.Frame(self.root)
        self.mode_controls=mode_controls
        mode_controls.pack(fill="x", padx=20, pady=(8, 0))
        ttk.Label(mode_controls, text="Existing BOM review").pack(side="left", padx=(0, 15))
        ttk.Button(mode_controls, text="New Design from an idea", command=self.open_new_design).pack(side="left")
        self.configuration_text=tk.StringVar(value='')
        ttk.Label(mode_controls,textvariable=self.configuration_text).pack(side='left',padx=12)

        ttk.Label(self.root, text="PartLens / BOM review", font=("Segoe UI", 19, "bold")).pack(
            anchor="w", padx=20, pady=(16, 4))
        ttk.Label(self.root, text="Review requirements, check replacements, and keep the evidence behind each decision.").pack(
            anchor="w", padx=20)
        controls = ttk.Frame(self.root)
        controls.pack(fill="x", padx=20, pady=12)
        self.buttons = []
        for label, action in [("Load demo", self.load_demo), ("Import BOM",self.import_bom), ("Deterministic review", self.manual_review),
                              ("Live agent review", self.live_review), ("New session + recall", self.recall),
                              ("Compare costs: owner / 60", self.compare_costs), ("Check services", self.check_services)]:
            button = ttk.Button(controls, text=label, command=action)
            button.pack(side="left", padx=(0, 8))
            self.buttons.append(button)
        self.status = tk.StringVar(value=f"Ready. Run {self.session.recorder.run_id}. Live review uses the configured model provider.")
        ttk.Label(self.root, textvariable=self.status, wraplength=1060).pack(anchor="w", padx=20, pady=(0, 8))
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        self.views = {}
        self.part_evidence = {}
        for name in ("Parts", "Requirements", "Qualifications", "Evidence", "Sourcing", "Cost", "Explanation", "Run record"):
            frame = ttk.Frame(self.notebook)
            if name == "Parts":
                columns = ("line", "refs", "value", "qty", "package", "part")
                table_frame = ttk.Frame(frame)
                table_frame.pack(fill="both", expand=True)
                self.part_table = ttk.Treeview(table_frame, columns=columns, show="headings")
                for col, width in zip(columns, (55, 210, 160, 65, 130, 260)):
                    self.part_table.heading(col, text={"qty": "Per board", "part": "Matched part"}.get(col, col.title()))
                    self.part_table.column(col, width=width, minwidth=width, stretch=True)
                self.part_table.grid(row=0, column=0, sticky="nsew")
                table_frame.rowconfigure(0, weight=1)
                table_frame.columnconfigure(0, weight=1)
                for orient in ("vertical", "horizontal"):
                    scroll = ttk.Scrollbar(table_frame, orient=orient,
                                           command=self.part_table.yview if orient == "vertical" else self.part_table.xview)
                    scroll.grid(row=0 if orient == "vertical" else 1,
                                column=1 if orient == "vertical" else 0,
                                sticky="ns" if orient == "vertical" else "ew")
                    self.part_table.configure(**{("yscrollcommand" if orient == "vertical" else "xscrollcommand"): scroll.set})
                self.part_table.bind("<<TreeviewSelect>>", self.show_part_evidence)
                ttk.Label(frame, text="Select a matched part to inspect its source evidence.").pack(anchor="w", pady=8)
                self.notebook.add(frame, text=name)
                continue
            if name == "Qualifications":
                bar = ttk.Frame(frame)
                bar.pack(fill="x", padx=8, pady=6)
                ttk.Label(bar, text="Original-specification status:").pack(side="left")
                self.qualification_filter = tk.StringVar(value="all")
                select = ttk.Combobox(bar, textvariable=self.qualification_filter, state="readonly",
                                      values=("all", "verified", "rejected", "unverified"), width=14)
                select.pack(side="left", padx=8)
                select.bind("<<ComboboxSelected>>", lambda e: self.render_qualifications())
                self.qualification_table = ttk.Treeview(frame, columns=("line", "original", "candidate", "status", "application"),
                                                        show="headings", height=5)
                for col in self.qualification_table["columns"]:
                    self.qualification_table.heading(col, text=col.title())
                    self.qualification_table.column(col, width=130, stretch=True)
                self.qualification_table.pack(fill="x", padx=8)
                self.qualification_table.bind("<<TreeviewSelect>>", self.show_qualification)
                self.qualification_outputs = []
            text = tk.Text(frame, wrap="word", font=("Consolas", 10), padx=12, pady=12)
            scroll = ttk.Scrollbar(frame, command=text.yview)
            text.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
            text.pack(fill="both", expand=True)
            self.notebook.add(frame, text=name)
            self.views[name] = text
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.refresh()
        self.root.after(100, self.pump)

    def new_session(self) -> None:
        self.agent = None
        self.session = Session(RunRecorder.create(self.state / "runs"), self.catalogs, fees=self.fees)
        self.session.recorder.log("ui_session", interface="local desktop", design=self.design_name)
        self.session.recorder.log("cost_configuration", fees=self.fees)
        if getattr(self, "quantity_record", None):
            self.session.restore_quantity(self.quantity_record)

    def tool(self, tool_name: str, **args) -> dict:
        if self.agent is None:
            self.agent = Agent(self.session, ScriptedProvider([]), self.ask)
        result = self.agent._execute(ToolCall(f"ui-{self.session.recorder.seq + 1}", tool_name, args))
        data = json.loads(result["content"])
        if result.get("is_error"):
            raise ValueError(data["error"])
        return data

    def load_demo(self) -> None:
        self.work(lambda: (self.tool("import_bom", path=str(self.demo_bom), name=self.design_name),
                           self.tool("match_parts"), self.tool("find_missing_information")))

    def import_bom(self) -> None:
        if self.busy:return
        from tkinter import filedialog
        path=filedialog.askopenfilename(parent=self.root,title='Import BOM (read-only)',filetypes=[('CSV BOM','*.csv')])
        if path:
            self.work(lambda:(self.tool('import_bom',path=path,name=self.design_name),self.tool('match_parts'),
                              self.tool('find_missing_information')))

    def add_settings(self, callback) -> None:
        self.ttk.Button(self.mode_controls,text='Settings',command=callback).pack(side='right')

    def ensure_memory(self) -> None:
        if self.bridge is None:
            self.bridge = HMemBridge(self.state / "hmem")
        self.session.memory = DecisionMemory(self.bridge, self.design_name)
        self.session.recorder.log("memory_engine", info=self.bridge.info)

    def manual_review(self) -> None:
        def run():
            self.ensure_memory()
            if not self.session.bom:
                self.tool("import_bom", path=str(self.demo_bom), name=self.design_name)
                self.tool("match_parts")
            self.tool("find_missing_information")
            if self.session._boards() is None:
                reply = self.tool("ask_user", question="How many boards will be assembled? Enter a whole number.",
                                  gap_id="design.board_quantity")["answer"]
                self.tool("record_requirement", subject="design", parameter="board_quantity", op="==",
                          value=reply.strip(), user_quote=reply)
            for line_id, original in list(self.session.baseline.items()):
                if not original:
                    continue
                self.tool("check_availability", part_key=original.key, line_id=line_id)
                for candidate in self.tool("search_candidates", line_id=line_id, limit=5)["candidates"]:
                    self.tool("check_substitute", line_id=line_id, candidate_key=candidate["key"])
            self.tool("estimate_cost")
            self.session.recorder.log("ui_review_complete", mode="deterministic; no LLM explanation generated")
        self.work(run)

    def live_review(self) -> None:
        def run():
            load_env_file()
            self.ensure_memory()
            self.agent = Agent(self.session, provider_from_env(), self.ask)
            self.agent.send(
                f"Review the current BOM, or import {self.demo_bom} as {self.design_name} if none is loaded. Match parts, identify missing requirements and ask "
                "for build quantity (gap_id design.board_quantity) if it is not confirmed. Record my exact answer. "
                "Use supplier evidence and deterministic tools to review qualified, unverified and invalid "
                "alternatives, sourcing and cost. Explain the results with sources. Other unknown conditions "
                "and fees should remain explicit gaps. Use compare_cost_scenarios for a hypothetical 60-board "
                "comparison without replacing the owner's confirmed quantity. Do not request other missing circuit "
                "or quote inputs for this bounded preliminary review; list them as unresolved.", origin="ui_task",
                workflow=WorkflowRequest(self.session.bom.source if self.session.bom else str(self.demo_bom),
                                         design=self.design_name, costs=True)
            )
        self.work(run)

    def recall(self) -> None:
        def run():
            load_env_file()
            prior = self.session.recorder.run_id
            bom_path=self.session.bom.source if self.session.bom else str(self.demo_bom)
            self.new_session()
            self.ensure_memory()
            self.tool("import_bom", path=bom_path, name=self.design_name)
            self.tool("match_parts")
            recalled = self.tool("recall_decisions", query=self.design_name+" replacement decisions", run_id=prior)
            rechecked = 0
            seen = set()
            for memory in recalled["memories"]:
                line = memory.get("line")
                identity = (line, memory.get("candidate"))
                if identity in seen:
                    continue
                seen.add(identity)
                original = self.session.baseline.get(line)
                if original and original.key == memory.get("original") and memory.get("candidate"):
                    self.tool("reverify_decision", memory_id=memory["id"])
                    rechecked += 1
                    if rechecked == 3:
                        break
            self.session.recorder.log("ui_recall_complete", mode="real H-MEM retrieval and deterministic recheck; no LLM",
                                      prior_run=prior, memories_returned=len(recalled["memories"]), rechecked=rechecked)
        self.work(run)

    def compare_costs(self) -> None:
        self.work(lambda: self.tool("compare_cost_scenarios", hypothetical_boards=60))

    def check_services(self) -> None:
        def run():
            from .preflight import run_preflight
            report = run_preflight(self.state)
            self.session.recorder.log('ui_preflight', report=report)
            summary = '\n'.join(name+': '+('AVAILABLE' if value['available'] else 'UNAVAILABLE — '+value['action'])
                                for name,value in report['checks'].items())
            self.events.put(('service_notice', summary+'\n\nRecord: '+report['record']))
        self.work(run)

    def ask(self, question: str) -> str:
        self.answer_ready.clear()
        self.events.put(("question", question))
        self.answer_ready.wait()
        if self.closed or not self.answer.strip():
            raise ValueError("user did not provide an answer; no requirement confirmed")
        return self.answer

    def work(self, operation) -> None:
        if self.busy:
            return
        self.busy = True
        for button in self.buttons:
            button.configure(state="disabled")
        self.status.set("Working. Tool outputs and failures are saved in the run record.")

        def run():
            try:
                operation()
                self.events.put(("done", f"Finished. Run {self.session.recorder.run_id}"))
            except Exception as exc:
                self.session.recorder.log("ui_error", error_type=type(exc).__name__, message=str(exc))
                self.events.put(("done", f"{failure_message(exc)} Record: {self.session.recorder.path}"))
            finally:
                if self.closed and self.bridge:
                    self.bridge.close()
        threading.Thread(target=run, daemon=True).start()

    def pump(self) -> None:
        from tkinter import simpledialog

        try:
            while True:
                kind, value = self.events.get_nowait()
                if kind == "question":
                    self.answer = simpledialog.askstring("PartLens needs a requirement", value, parent=self.root) or ""
                    self.answer_ready.set()
                elif kind == 'service_notice':
                    from tkinter import messagebox
                    messagebox.showinfo('Demo service checks', value, parent=self.root)
                else:
                    self.busy = False
                    for button in self.buttons:
                        button.configure(state="normal")
                    self.status.set(value)
                    self.refresh()
        except queue.Empty:
            pass
        if not self.closed:
            self.root.after(100, self.pump)

    def refresh(self) -> None:
        snapshot = review_snapshot(self.session)
        self.part_evidence = snapshot["Evidence"]
        self.part_table.delete(*self.part_table.get_children())
        for line in snapshot["Parts"].get("lines", []):
            self.part_table.insert("", "end", values=(line["line"], line["refs"], line["value"],
                line["qty_per_board"], line["package"], line["matched_part"] or
                ("Unmatched" if line.get("purchased", True) else "Not purchased")))
        for name, content in snapshot.items():
            if name == "Parts":
                continue
            text = self.views[name]
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", redact(format_view(name, content)))
            text.configure(state="disabled")
        self.qualification_outputs = snapshot["Qualifications"]
        self.render_qualifications()

    def render_qualifications(self) -> None:
        self.qualification_table.delete(*self.qualification_table.get_children())
        for i, output in enumerate(self.qualification_outputs):
            if self.qualification_filter.get() not in {"all", output.get("status")}:
                continue
            comparison = output.get("comparison", {})
            def identity(label):
                part = comparison.get(label, {})
                return f"{part.get('manufacturer', '')} {part.get('mpn', output.get(label, '?'))}".strip()
            self.qualification_table.insert("", "end", iid=str(i), values=(output.get("line"), identity("original"),
                identity("candidate"), output.get("status", "error") +
                (" (historical)" if output.get("current_context") is False else ""),
                output.get("application", {}).get("status", "unverified")))
        rows = self.qualification_table.get_children()
        if rows:
            self.qualification_table.selection_set(rows[0])
            self.show_qualification()
        else:
            text = self.views["Qualifications"]
            text.configure(state="normal")
            text.delete("1.0", "end")
            text.insert("1.0", "No decisions match this filter. Run a review or select another status.")
            text.configure(state="disabled")

    def show_qualification(self, event=None) -> None:
        selected = self.qualification_table.selection()
        if not selected:
            return
        output = self.qualification_outputs[int(selected[0])]
        text = self.views["Qualifications"]
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", redact(format_view("Qualifications", [output])))
        text.configure(state="disabled")

    def show_part_evidence(self, event=None) -> None:
        selected = self.part_table.selection()
        if not selected:
            return
        key = self.part_table.item(selected[0], "values")[-1]
        if key not in self.part_evidence:
            self.notebook.select(self.views["Requirements"].master)
            return
        text = self.views["Evidence"]
        text.configure(state="normal")
        text.delete("1.0", "end")
        text.insert("1.0", redact(format_view("Evidence", {key: self.part_evidence[key]})))
        text.configure(state="disabled")
        self.notebook.select(text.master)

    def open_new_design(self) -> None:
        from .design.ui import open_new_design
        open_new_design(self.root, self.catalogs, self.state, self.fees)

    def close(self) -> None:
        self.closed = True
        self.answer_ready.set()
        if self.bridge and not self.busy:
            self.bridge.close()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
