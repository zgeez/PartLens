"""PartLens session state and the deterministic operations the tools expose."""

from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

from .checks.compat import check_application, check_availability, check_substitute
from .core.bom import Bom, BomLine, import_bom_csv, normalise_mpn
from .core.model import Decision, Op, Provenance, ProvenanceStatus, Requirement, RequirementKind, to_jsonable
from .core.parts import PartRecord
from .core.units import UnitError, format_value, parse_value
from .memory.hmem import DecisionMemory
from .optimise.cost import AssemblyFees, CostInputs, estimate, money
from .optimise.search import Option, optimise
from .records import RunRecorder, read_events, output_digest
from .sources.catalog import PARAM_UNITS, Catalog

UNITS_BY_PARAMETER = {**PARAM_UNITS, "applied_voltage": "V", "derating_factor": None}


class ToolError(ValueError):
    """An error the agent should see and can correct (bad id, missing prerequisite)."""


@dataclass
class Session:
    recorder: RunRecorder
    catalogs: list[Catalog]
    memory: DecisionMemory | None = None
    now: datetime | None = None
    bom: Bom | None = None
    design_name: str = "design"
    requirements: dict[str, Requirement] = field(default_factory=dict)
    baseline: dict[str, PartRecord | None] = field(default_factory=dict)
    decisions: dict[str, Decision] = field(default_factory=dict)
    alternatives: dict[str, list[Option]] = field(default_factory=dict)
    fees: AssemblyFees | None = None
    pcb_fabrication: Decimal | None = None
    pcb_source: str = ""
    observed_parts: dict[str, PartRecord] = field(default_factory=dict)
    bom_fingerprint: str | None = None

    def __post_init__(self) -> None:
        # Optional source hook: remote query events belong to this session, including through review overlays.
        self.catalogs = [bind(self.recorder) if (bind := getattr(c, "with_recorder", None)) else c
                         for c in self.catalogs]

    # ------------------------------------------------------------------ helpers
    def _now(self) -> datetime:
        return self.now or datetime.now(UTC)

    def _need_bom(self) -> Bom:
        if self.bom is None:
            raise ToolError("no BOM loaded; call import_bom first")
        return self.bom

    def _line(self, line_id: str) -> BomLine:
        try:
            return self._need_bom().line(line_id)
        except KeyError:
            raise ToolError(f"unknown line {line_id!r}") from None

    def get_part(self, key: str) -> PartRecord:
        for c in self.catalogs:
            p = c.get(key)
            if p:
                self.observed_parts[p.key] = p
                return p
        raise ToolError(f"part {key!r} not found in {[c.name for c in self.catalogs]}")

    def line_requirements(self, line_id: str) -> list[Requirement]:
        return [r for r in self.requirements.values() if r.subject == line_id]

    def design_requirement(self, parameter: str) -> Requirement | None:
        return next((r for r in self.requirements.values()
                     if r.subject == "design" and r.parameter == parameter), None)

    # ------------------------------------------------------------------ BOM
    def import_bom(self, path: str, name: str | None = None) -> dict[str, Any]:
        if any(p.casefold() == "experiments" or "benchmark" in p.casefold() or "badge" in p.casefold()
               for p in Path(path).resolve().parts):
            raise ToolError("excluded private material cannot be imported")
        imported = import_bom_csv(path, name=name)
        fingerprint = hashlib.sha256(Path(path).read_bytes()).hexdigest()
        if self.bom and self.bom_fingerprint != fingerprint:
            self.requirements.clear()
        self.bom = imported
        self.bom_fingerprint = fingerprint
        self.design_name = self.bom.name
        self.baseline = {}
        self.decisions.clear()
        self.alternatives.clear()
        self.observed_parts.clear()
        return self.describe_design()

    def describe_design(self) -> dict[str, Any]:
        bom = self._need_bom()
        lines = []
        for ln in bom.lines:
            lines.append({
                "line": ln.id, "refs": ",".join(ln.refs), "qty_per_board": ln.qty_per_board, "value": ln.value,
                "category": ln.category, "package": ln.package or ln.footprint, "mpn": ln.mpn,
                "supplier_pn": ln.supplier_pn, "dnp": ln.dnp, "issues": list(ln.issues),
                "matched_part": self.baseline[ln.id].key if self.baseline.get(ln.id) else None,
                "purchased": ln in bom.placed_lines,
            })
        return {"design": self.design_name, "source": bom.source, "lines": lines, "warnings": bom.warnings,
                "placed_lines": len(bom.placed_lines),
                "placements_per_board": sum(ln.qty_per_board for ln in bom.placed_lines)}

    def match_parts(self) -> dict[str, Any]:
        """Resolve each BOM line to a catalogue record by supplier part number, then exact MPN."""
        bom = self._need_bom()
        for catalog in self.catalogs:
            prepare = getattr(catalog, "prepare", None)
            if prepare:
                prepare([ln.supplier_pn for ln in bom.placed_lines if ln.supplier_pn])
        out = []
        for ln in bom.placed_lines:
            part, how = None, "unmatched"
            if ln.supplier_pn:
                for c in self.catalogs:
                    part = c.get(f"{getattr(c, 'bom_supplier', 'lcsc')}:{ln.supplier_pn}")
                    if part:
                        if ((ln.mpn and normalise_mpn(ln.mpn) != normalise_mpn(part.mpn)) or
                                (ln.manufacturer and ln.manufacturer.strip().casefold() !=
                                 part.manufacturer.strip().casefold())):
                            part = None
                            how = "supplier listing conflicts with explicit BOM manufacturer/MPN"
                            continue
                        how = f"supplier part number via {c.name}"
                        break
            if part is None and ln.mpn:
                hits = [p for c in self.catalogs for p in c.find_mpn(ln.mpn)]
                if ln.manufacturer:
                    hits = [p for p in hits if p.manufacturer.strip().casefold() == ln.manufacturer.strip().casefold()]
                identities = {p.manufacturer.strip().casefold() for p in hits}
                if len(identities) > 1 or (hits and "" in identities):
                    hits = []
                    how = "ambiguous or unknown manufacturer; exact identity must be established"
                if len(hits) == 1:
                    part, how = hits[0], "exact MPN"
                elif len(hits) > 1:
                    part = sorted(hits, key=lambda p: p.key)[0]
                    how = f"exact MPN ({len(hits)} listings; chose {part.key} by key order)"
            self.baseline[ln.id] = part
            if part:
                self.observed_parts[part.key] = part
            out.append({"line": ln.id, "matched": part.key if part else None, "how": how,
                        "retrieved_at": part.retrieved_at if part else None})
        return {"matches": out, "unmatched": [m["line"] for m in out if not m["matched"]]}

    # ------------------------------------------------------------------ gaps and requirements
    def find_missing_information(self) -> dict[str, Any]:
        bom = self._need_bom()
        gaps: list[dict[str, Any]] = []

        def gap(gid: str, subject: str, what: str, why: str, question: str) -> None:
            gaps.append({"id": gid, "subject": subject, "missing": what, "why": why, "suggested_question": question})

        if self._boards() is None:
            gap("design.board_quantity", "design", "production quantity",
                "price breaks, attrition and per-board cost depend on it", "How many boards will be assembled?")
        if self.fees is None:
            gap("design.assembly_fees", "design", "assembly service fee schedule",
                "loading fees can outweigh unit-price savings", "Which assembly service and fee schedule should I use?")
        if self.pcb_fabrication is None:
            gap("design.pcb_cost", "design", "PCB fabrication cost",
                "the assembled-cost total is incomplete without it", "Do you have a PCB fabrication quote?")
        for ln in bom.placed_lines:
            if not ln.mpn and not ln.supplier_pn:
                gap(f"{ln.id}.identity", ln.id, "part identity (MPN or supplier part number)",
                    "the line cannot be priced or checked",
                    f"Provide the manufacturer and MPN for {','.join(ln.refs)} ({ln.value}; {ln.footprint}), "
                    "or confirm pin count/pitch, orientation, mating dimensions, contact finish and voltage/current ratings.")
            elif ln.id in self.baseline and self.baseline[ln.id] is None:
                gap(f"{ln.id}.catalogue", ln.id, "catalogue record",
                    "no source states this part's parameters, stock or price",
                    f"Is {ln.mpn or ln.supplier_pn} the exact part for {','.join(ln.refs)}?")
            reqs = {r.parameter for r in self.line_requirements(ln.id)}
            if ln.category == "capacitor" and "applied_voltage" not in reqs:
                gap(f"{ln.id}.applied_voltage", ln.id, "maximum DC voltage across the capacitors",
                    "without it substitutes are only checked against the original rating (no-downgrade)",
                    f"What is the highest DC voltage across {','.join(ln.refs)}?")
            if ln.category == "ic" and "supply_voltage_max" not in reqs:
                gap(f"{ln.id}.supply_voltage_max", ln.id, "maximum supply/input voltage the part must withstand",
                    "application qualification needs this condition; original-specification checks can still run",
                    f"What is the highest input voltage {','.join(ln.refs)} must tolerate?")
            for issue in ln.issues:
                gap(f"{ln.id}.import", ln.id, "BOM data issue", issue, f"{ln.id}: {issue} — how should I treat it?")
        return {"gaps": gaps, "count": len(gaps)}

    def record_requirement(self, subject: str, parameter: str, op: str, value: str, user_quote: str = "",
                           rationale: str = "", unit: str | None = None) -> dict[str, Any]:
        """Record a requirement. It is ``user_confirmed`` only if ``user_quote`` appears verbatim in a recorded
        user message; otherwise it is ``provisional`` (never binding)."""
        if subject != "design":
            self._line(subject)
        try:
            rop = Op(op)
        except ValueError:
            raise ToolError(f"op must be one of {[o.value for o in Op]}") from None
        unit = unit or UNITS_BY_PARAMETER.get(parameter)
        parsed: Any = value
        if unit:
            try:
                parsed, unit = parse_value(value, unit)
            except UnitError as e:
                raise ToolError(str(e)) from None
        elif re.fullmatch(r"-?[0-9]+(\.[0-9]+)?", value.strip()):
            parsed = Decimal(value.strip())

        source, status = self._find_user_quote(user_quote)
        if status is ProvenanceStatus.USER_CONFIRMED and isinstance(parsed, Decimal):
            # A real quote is insufficient when the model changes the number or unit it actually stated.
            quoted_values = []
            for number, suffix in re.findall(
                    r"(?<![\w.])(-?[0-9]+(?:\.[0-9]+)?)(?:\s*(mV|kV|V|uF|µF|nF|pF|F|mA|A|mW|W|kOhm|Ohm|ohm|Ω))?",
                    user_quote):
                try:
                    number_value, number_unit = parse_value(number + suffix, unit)
                    if number_unit == unit:
                        quoted_values.append((number_value, bool(suffix)))
                except UnitError:
                    continue
            explicit = [v for v, has_unit in quoted_values if has_unit]
            values = explicit or [v for v, _ in quoted_values]
            if parsed not in values:
                source, status = "agent:unconfirmed", ProvenanceStatus.PROVISIONAL
        elif status is ProvenanceStatus.USER_CONFIRMED and isinstance(parsed, str):
            if parsed.strip().casefold() not in user_quote.casefold():
                source, status = "agent:unconfirmed", ProvenanceStatus.PROVISIONAL
        if parameter == "board_quantity":
            if (subject != "design" or rop is not Op.EQ or not isinstance(parsed, Decimal)
                    or not parsed.is_finite() or parsed <= 0 or parsed != parsed.to_integral_value()):
                raise ToolError("board_quantity must be a positive whole number for design with op ==")
            # A real quote about another value cannot confirm the model's chosen quantity.
            numbers = re.findall(r"(?<![\w.])[0-9]+(?:\.[0-9]+)?(?![\w.])", user_quote)
            if not any(Decimal(n) == parsed for n in numbers):
                source, status = "agent:unconfirmed", ProvenanceStatus.PROVISIONAL
        rid = f"{subject}.{parameter}"
        req = Requirement(rid, subject, parameter, rop, parsed, RequirementKind.HARD,
                          Provenance(status, source, recorded_at=self._now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                                     note=user_quote[:200]), unit=unit, rationale=rationale)
        if rid in self.requirements and self.requirements[rid].binding and not req.binding:
            raise ToolError("an unconfirmed proposal cannot overwrite an existing binding requirement")
        self.requirements[rid] = req
        derived = self._derive(req)
        if parameter == "derating_factor":
            for condition in list(self.requirements.values()):
                if condition.parameter == "applied_voltage":
                    derived.extend(self._derive(condition))
        if parameter != "board_quantity":
            affected = set(self.alternatives) if subject == "design" else {subject}
            for line_id in affected:
                self.alternatives.pop(line_id, None)
            self.decisions = {key: d for key, d in self.decisions.items() if d.subject not in affected}
        return {"recorded": _req_view(req), "binding": req.binding, "derived": [_req_view(d) for d in derived],
                "note": None if req.binding else
                "provisional: user_quote not found verbatim in the user's messages; not binding until confirmed"}

    def _find_user_quote(self, quote: str) -> tuple[str, ProvenanceStatus]:
        if quote:
            for e in self.recorder.user_messages():
                if e.get("origin", "user") == "user" and quote in e["text"]:
                    return f"user:{self.recorder.run_id}#seq{e['seq']}", ProvenanceStatus.USER_CONFIRMED
        return "agent:unconfirmed", ProvenanceStatus.PROVISIONAL

    def _derive(self, req: Requirement) -> list[Requirement]:
        """Calculated requirements that follow from user-stated values."""
        out: list[Requirement] = []
        if req.parameter == "applied_voltage" and isinstance(req.value, Decimal):
            factor_req = self.design_requirement("derating_factor")
            factor = factor_req.value if factor_req and factor_req.binding and isinstance(factor_req.value, Decimal) \
                else Decimal(1)
            status = ProvenanceStatus.CALCULATED if req.binding else ProvenanceStatus.PROVISIONAL
            d = Requirement(
                f"{req.subject}.voltage_rating.applied", req.subject, "voltage_rating", Op.GE,
                (req.value * factor).normalize(), RequirementKind.HARD,
                Provenance(status, f"calc:{req.id} x derating {factor}",
                           recorded_at=self._now().strftime("%Y-%m-%dT%H:%M:%SZ"),
                           note=f"voltage_rating >= applied_voltage ({req.value} V) x {factor}"
                                + ("" if factor_req else " (no derating factor set)")),
                unit="V", rationale="rated voltage must cover the applied voltage",
            )
            self.requirements[d.id] = d
            out.append(d)
        return out

    def list_requirements(self) -> dict[str, Any]:
        return {"requirements": [_req_view(r) for r in self.requirements.values()]}

    def context_digest(self) -> str:
        return output_digest({"bom": self.bom_fingerprint, "requirements": self.list_requirements(),
                              "baseline": self.baseline})

    def decision_context(self, line_id: str, original: PartRecord, candidate: PartRecord) -> dict[str, Any]:
        reqs = [r for r in self.list_requirements()["requirements"] if r["subject"] in {"design", line_id}]
        semantic = [{k: v for k, v in r.items() if k != "source"} for r in reqs]
        return {"design": self.design_name, "bom_sha256": self.bom_fingerprint,
                "line_sha256": output_digest(self._line(line_id)),
                "requirements": reqs, "requirements_sha256": output_digest(semantic),
                "original": {"key": original.key, "manufacturer": original.manufacturer, "mpn": original.mpn},
                "candidate": {"key": candidate.key, "manufacturer": candidate.manufacturer, "mpn": candidate.mpn}}

    def restore_quantity(self, path: str | Path) -> dict[str, Any]:
        """Operator-only reuse of a recorded owner answer; retain its original user-message provenance."""
        source_path = Path(path)
        if any(p.casefold() == "experiments" or "benchmark" in p.casefold() or "badge" in p.casefold()
               for p in source_path.resolve().parts):
            raise ToolError("excluded private material cannot be imported")
        events = read_events(source_path)
        for event in reversed(events):
            if event["type"] != "tool_call" or event.get("name") != "record_requirement" or event.get("error"):
                continue
            args, output = event["input"], event["output"]
            if args.get("parameter") != "board_quantity" or not output.get("binding"):
                continue
            quote = args.get("user_quote", "")
            view = output["recorded"]
            source = view.get("source")
            matching = [m for m in events if m["type"] == "user_message" and m.get("origin", "user") == "user"
                        and quote and quote in m["text"] and source == f"user:{m['run']}#seq{m['seq']}"]
            value = Decimal(args["value"])
            if (not matching or view.get("provenance") != "user_confirmed" or args.get("subject") != "design"
                    or args.get("op") != "==" or not value.is_finite() or value <= 0
                    or value != value.to_integral_value()
                    or not any(Decimal(n) == value for n in re.findall(r"\b[0-9]+(?:\.[0-9]+)?\b", quote))):
                raise ToolError("prior quantity lacks valid original user provenance")
            self.requirements["design.board_quantity"] = Requirement(
                "design.board_quantity", "design", "board_quantity", Op.EQ, value, RequirementKind.HARD,
                Provenance(ProvenanceStatus.USER_CONFIRMED, source, recorded_at=matching[0]["at"], note=quote),
                rationale=args.get("rationale", ""))
            result = _req_view(self.requirements["design.board_quantity"])
            self.recorder.log("quantity_restored", source_record=str(source_path), source_sha256=hashlib.sha256(
                source_path.read_bytes()).hexdigest(), requirement=result, new_owner_confirmation=False)
            return result
        raise ToolError("no confirmed quantity found in prior run")

    # ------------------------------------------------------------------ research and checks
    def search_candidates(self, line_id: str, text: str | None = None, limit: int = 10) -> dict[str, Any]:
        ln = self._line(line_id)
        base = self.baseline.get(line_id)
        category = base.category if base else ln.category
        package = base.package if base else ln.package
        seen: dict[str, PartRecord] = {}
        if base:
            for key in base.suggested_alternates:
                for catalog in self.catalogs:
                    part = catalog.get(key)
                    if part:
                        seen.setdefault(part.key, part)
                        break
        for c in self.catalogs:
            discover = getattr(c, "discover_for", None)
            parts = discover(base, category, package, text, limit) if base and discover else c.search(category, package, text, limit)
            for p in parts:
                seen.setdefault(p.key, p)
        cands = [p for p in seen.values() if not base or p.key != base.key]
        return {"line": line_id, "category": category, "package": package,
                "searched": [c.name for c in self.catalogs],
                "note": "supplier suggested alternates are research leads; every candidate needs deterministic checks",
                "candidates": [_part_brief(p) for p in cands[:limit]]}

    def part_details(self, key: str) -> dict[str, Any]:
        p = self.get_part(key)
        return part_view(p)

    def check_substitute(self, line_id: str, candidate_key: str) -> dict[str, Any]:
        ln = self._line(line_id)
        original = self.baseline.get(line_id)
        if original is None:
            raise ToolError(f"{line_id} has no matched original part; call match_parts or resolve the identity first")
        cand = self.get_part(candidate_key)
        context = self.decision_context(line_id, original, cand)

        recalled = self.memory.recall(original.key, cand.key, line_id=ln.id) if self.memory else []
        decision = check_substitute(ln, original, cand, self.line_requirements(line_id))
        application = check_application(ln, original, cand, self.line_requirements(line_id))
        self.decisions[decision.id] = decision
        opts = self.alternatives.setdefault(line_id, [])
        opts[:] = [o for o in opts if o.part.key != cand.key] + [Option(cand, decision)]

        mem_id = None
        if self.memory:
            same = next((r for r in recalled if r.decision_id == decision.id and r.details.get("context") == context), None)
            if same:
                # Identical decision on identical evidence: reinforce the existing memory (ledgered), no duplicate.
                self.memory.bridge.call("feedback", id=same.memory_id, kind="helpful")
                mem_id = same.memory_id
            else:
                mem_id = self.memory.remember(decision, run_id=self.recorder.run_id, context=context)["id"]
        prior = [{"memory_id": r.memory_id, "status": r.status, "decision_id": r.decision_id, "source": r.source,
                  "summary": r.content,
                  "agrees_with_current": r.status == decision.status.value} for r in recalled]
        return {
            "decision_id": decision.id, "line": line_id, "original": original.key, "candidate": cand.key,
            "status": decision.status.value,
            "qualification_scope": "original_specification_equivalence",
            "comparison": {"original": part_view(original), "candidate": part_view(cand)},
            "application": {"status": application.status.value, "checks": to_jsonable(application.checks),
                            "note": "equivalence rejection alone does not establish an unsafe application"},
            "checks": [{"check": c.check, "status": c.status.value, "message": c.message,
                        "expected": c.expected, "observed": c.observed,
                        "evidence": [f"{e.kind.value}: {e.locator} ({e.field}={e.value})" for e in c.evidence]}
                       for c in decision.checks],
            "prior_decisions_from_memory": prior,
            "stored_in_memory": mem_id,
            "context": context,
        }

    def reverify_decision(self, memory_id: str) -> dict[str, Any]:
        """Read actual memory, bind its identity/context, refresh supplier evidence, and run checks again."""
        if not self.memory:
            raise ToolError("decision memory not configured")
        memory = self.memory.read_decision(memory_id)
        if not memory:
            raise ToolError("memory not found in this design's engineering decisions")
        tags = memory["tags"]
        def tag(prefix):
            return next((t[len(prefix):] for t in tags if t.startswith(prefix)), None)
        refs = (memory.get("provenance") or {}).get("refs") or []
        details = json.loads(refs[1]) if len(refs) > 1 else {}
        result = {"memory_id": memory_id, "source": memory["source"], "stored_status": details.get("status"),
                  "outcome": "cannot_reverify", "current_decision": None, "context_matches": False}
        line_id, original_key, candidate_key = tag("line:"), tag("original:"), tag("candidate:")
        if not self.bom or line_id not in {ln.id for ln in self.bom.placed_lines}:
            return {**result, "reason": "historical BOM line is not present in the current design"}
        original = self.baseline.get(line_id)
        if not original or original.key != original_key:
            return {**result, "reason": "current original part does not match the remembered pair"}
        # These are actual source reads now, not the remembered or previous-session parameter values.
        fresh_original, fresh_candidate = self.get_part(original_key), self.get_part(candidate_key)
        line = self._line(line_id)
        if ((line.mpn and normalise_mpn(line.mpn) != normalise_mpn(fresh_original.mpn)) or
                (line.manufacturer and line.manufacturer.casefold() != fresh_original.manufacturer.casefold())):
            return {**result, "reason": "fresh supplier identity conflicts with the explicit BOM identity"}
        current_context = self.decision_context(line_id, fresh_original, fresh_candidate)
        stored_context = details.get("context")
        context_matches = bool(stored_context and all(stored_context.get(k) == current_context.get(k)
            for k in ("design", "bom_sha256", "line_sha256", "requirements_sha256", "original", "candidate")))
        self.baseline[line_id] = fresh_original
        self.alternatives.pop(line_id, None)
        self.decisions = {key: d for key, d in self.decisions.items() if d.subject != line_id}
        current = self.check_substitute(line_id, candidate_key)
        if not context_matches:
            outcome = "changed_context" if stored_context else "cannot_reverify"
            reason = "historical context differs" if stored_context else "legacy memory lacks identity/requirements context"
        elif current["status"] == "unverified":
            outcome, reason = "cannot_reverify", "fresh checks still lack required engineering evidence"
        else:
            outcome = "unchanged" if current["status"] == details.get("status") else "changed"
            reason = "fresh deterministic checks compared with the original recorded result"
        return {**result, "outcome": outcome, "reason": reason, "context_matches": context_matches,
                "current_decision": current, "current_context": current_context,
                "stored_context": stored_context, "source_reads_executed_now": True,
                "note": "Source reads do not refresh retained fixture timestamps or establish live inventory."}

    def check_availability(self, part_key: str, line_id: str) -> dict[str, Any]:
        ln = self._line(line_id)
        boards = self._boards()
        if boards is None:
            raise ToolError("board quantity not recorded; ask the user and record design.board_quantity")
        p = self.get_part(part_key)
        needed = ln.qty_per_board * boards
        res = check_availability(p, needed, now=self._now())
        return {"part": p.key, "needed": needed, "boards": boards,
                "ordered": None if any(x in p.commercial_unknowns for x in
                                       ("minimum order quantity", "order multiple")) else p.order_quantity(needed),
                "checks": [to_jsonable(c) for c in res]}

    def recall_decisions(self, query: str, run_id: str | None = None) -> dict[str, Any]:
        if not self.memory:
            return {"memories": [], "note": "decision memory not configured"}
        return {"memories": self.memory.search(query, run_id=run_id),
                "retrieval": "exact_design_and_run_source" if run_id is not None else "hybrid_text_query",
                "note": "With run_id, exact stored sources select the decisions; query is not used for ranking. "
                        "Recall supplies context only; rerun checks for current qualification."}

    # ------------------------------------------------------------------ cost
    def _boards(self) -> int | None:
        r = self.design_requirement("board_quantity")
        if (r and r.binding and isinstance(r.value, Decimal) and r.value.is_finite()
                and r.value > 0 and r.value == r.value.to_integral_value()):
            return int(r.value)
        return None

    def estimate_cost(self) -> dict[str, Any]:
        bom = self._need_bom()
        boards = self._boards()
        if boards is None:
            raise ToolError("board quantity not recorded (or not user-confirmed)")
        rep = estimate(bom, self.baseline, CostInputs(boards, self.fees or AssemblyFees(), self.pcb_fabrication,
                                                    self.pcb_source, now=self._now()))
        view = _cost_view(rep)
        observations = self._official_price_observations(boards)
        if observations:
            view["official_nominal_price_observations"] = observations
        return view

    def _official_price_observations(self, boards: int) -> list[dict[str, Any]]:
        from .sources.jlcpcb import quantity_price_observation

        return [{"line": ln.id, **quantity_price_observation(part, ln.qty_per_board * boards)}
                for ln in self._need_bom().placed_lines
                if (part := self.baseline.get(ln.id)) and part.supplier == "jlcpcb"]

    def optimise_cost(self) -> dict[str, Any]:
        bom = self._need_bom()
        boards = self._boards()
        if boards is None or self.fees is None:
            raise ToolError("board quantity and fee schedule are required")
        res = optimise(bom, self.baseline, self.alternatives,
                       CostInputs(boards, self.fees, self.pcb_fabrication, self.pcb_source, now=self._now()))
        return {"method": res.method, "savings_vs_baseline": money(res.savings),
                "comparison_complete": res.comparison_complete,
                "baseline": _cost_view(res.baseline), "optimised": _cost_view(res.best),
                "choices": [{"line": c.line_id, "chosen": c.chosen, "explanation": c.explanation} for c in res.choices],
                "excluded": list(res.excluded),
                "rule": "only substitutes with a verified decision are eligible"}

    def compare_cost_scenarios(self, hypothetical_boards: int = 60) -> dict[str, Any]:
        """Compare costs without changing any owner requirement or applying proposed parts to the design."""
        boards = self._boards()
        if boards is None:
            raise ToolError("restore or record the owner's quantity before comparing scenarios")
        results = []
        for quantity, label in ((boards, "owner_confirmed"), (hypothetical_boards, "hypothetical")):
            res = optimise(self._need_bom(), self.baseline, self.alternatives, CostInputs(
                quantity, self.fees or AssemblyFees(), self.pcb_fabrication, self.pcb_source, now=self._now()))
            results.append({"scenario": label, "boards": quantity,
                            "quantity_source": self.design_requirement("board_quantity").provenance.source
                            if label == "owner_confirmed" else "scenario:hypothetical; not an owner requirement",
                            "baseline": _cost_view(res.baseline), "proposed": _cost_view(res.best),
                            "proposed_replacements": [{"line": c.line_id, "original": c.baseline, "candidate": c.chosen,
                                                       "reason": c.explanation} for c in res.choices
                                                      if c.baseline and c.chosen != c.baseline],
                            "component_subtotal_difference": money(res.baseline.parts_total - res.best.parts_total),
                            "assembled_savings": money(res.savings), "comparison_complete": res.comparison_complete,
                            "excluded": list(res.excluded), "method": res.method,
                            "official_manufacturer_quotation": None,
                            "qualification_scope": "recorded original specification; application compatibility remains separate"})
            observations = self._official_price_observations(quantity)
            if observations:
                results[-1]["official_nominal_price_observations"] = observations
        return {"scenarios": results, "owner_requirement_unchanged": True,
                "note": "Partial component differences are not complete assembled savings or an official quote."}


def _fmt(v: Any, unit: str | None) -> str:
    return format_value(v, unit) if isinstance(v, Decimal) and unit and unit != "%" else \
        (f"{v}%" if unit == "%" else str(v))


def _req_view(r: Requirement) -> dict[str, Any]:
    v = r.value
    shown = _fmt(v, r.unit) if isinstance(v, Decimal) else (list(v) if isinstance(v, tuple) else v)
    return {"id": r.id, "subject": r.subject, "parameter": r.parameter, "op": r.op.value, "value": shown,
            "kind": r.kind.value, "provenance": r.provenance.status.value, "source": r.provenance.source,
            "binding": r.binding}


def _part_brief(p: PartRecord) -> dict[str, Any]:
    return {"key": p.key, "mpn": p.mpn, "manufacturer": p.manufacturer, "category": p.category,
            "package": p.package, "description": p.description, "assembly_class": p.assembly_class,
            "stock": p.stock, "lifecycle": p.lifecycle, "retrieved_at": p.retrieved_at,
            "params": {k: _fmt(v.value, v.unit) for k, v in p.params.items()}}


def part_view(p: PartRecord) -> dict[str, Any]:
    """Display an already-observed record without making a new supplier request."""
    view = {**_part_brief(p), "source": p.source, "datasheet_url": p.datasheet_url, "moq": p.moq,
            "order_multiple": p.order_multiple, "suggested_alternates": list(p.suggested_alternates),
            "assembly_service": p.assembly_service, "assembly_class_evidence": to_jsonable(p.assembly_class_evidence),
            "price_breaks": [[b.min_qty, str(b.unit_price), b.currency] for b in p.price_breaks],
            "engineering_notes": list(p.engineering_notes),
            "params": {k: {"value": _fmt(v.value, v.unit), "evidence": to_jsonable(v.evidence),
                           "rating_kind": v.rating_kind} for k, v in p.params.items()}}
    if p.commercial_unknowns or p.supplier_metadata:
        view.update(commercial_unknowns=list(p.commercial_unknowns), supplier_metadata=p.supplier_metadata,
                    moq=None if "minimum order quantity" in p.commercial_unknowns else p.moq,
                    order_multiple=None if "order multiple" in p.commercial_unknowns else p.order_multiple)
    if any(b.max_qty is not None for b in p.price_breaks):
        view["price_range_ends"] = [b.max_qty for b in p.price_breaks]
    return view


def _cost_view(rep) -> dict[str, Any]:
    return {"boards": rep.boards, "currency": rep.currency, "parts_total": money(rep.parts_total),
            "component_complete": rep.component_complete, "known_subtotal": money(rep.known_subtotal),
            "stencil_fee": money(rep.stencil_fee), "joint_fees": money(rep.joint_fees),
            "fee_source": rep.fee_source, "fee_retrieved_at": rep.fee_retrieved_at,
            "process_fees": {k: money(v) for k, v in rep.process_fees.items()},
            "loading_fees": money(rep.loading_fees), "loading_detail": list(rep.loading_detail),
            "setup_fee": money(rep.setup_fee), "placement_fees": money(rep.placement_fees),
            "pcb_fabrication": money(rep.pcb_fabrication), "total": money(rep.total),
            "per_board": money(rep.per_board), "complete": rep.complete, "problems": list(rep.problems),
            "lines": [{"line": lc.line_id, "part": lc.part_key, "derivation": lc.derivation,
                       "needed": lc.needed, "ordered": lc.ordered,
                       "unit_price": str(lc.unit_price) if lc.unit_price is not None else None,
                       "extended": str(lc.extended) if lc.extended is not None else None,
                       "problem": lc.problem, "sourcing": list(lc.sourcing),
                       "source": lc.source, "retrieved_at": lc.retrieved_at} for lc in rep.lines],
            "derivation": list(rep.derivation)}
