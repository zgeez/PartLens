"""Replay a run record: re-execute its tool calls against the same sources and compare outputs.

Memory-dependent fields and tools (H-MEM recall) are excluded; ``ask_user`` answers come from the record. The
clock of each call is restored so freshness checks see the same time.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .agent import stable_view
from .core.model import to_jsonable
from .optimise.cost import AssemblyFees
from decimal import Decimal
from .records import RunRecorder, output_digest, read_events
from .session import Session, ToolError
from .sources.catalog import Catalog
from .tools import BY_NAME, run_tool

SKIP = {"recall_decisions", "ask_user", "reverify_decision", "remember_design", "recall_design", "reverify_design", "design_report"}


@dataclass(frozen=True)
class ReplayResult:
    run_id: str
    replayed: int
    matched: int
    skipped: int
    mismatches: tuple[str, ...]
    audit_record: str | None = None

    @property
    def ok(self) -> bool:
        return not self.mismatches


def replay(path: str | Path, catalogs: list[Catalog] | None = None) -> ReplayResult:
    events = read_events(path)
    run_id = events[0]["run"] if events else "?"
    audit_root = Path(path).parent / "replays"
    audit_root.mkdir(parents=True, exist_ok=True)
    audit = RunRecorder.create(audit_root)
    audit.log("replay_started", source=str(path), source_run=run_id, source_digest=output_digest(events))
    if catalogs is None:
        from .sources.audit import observations_from_events
        catalogs = observations_from_events(events)
        audit.log("replay_source_mode", mode="recorded supplier observations; no live supplier, Zetaris or memory operation")
    with tempfile.TemporaryDirectory(dir=audit_root) as tmp:
        rec = RunRecorder.create(tmp, f"replay-{run_id}")
        rec.run_id = run_id  # provenance written during replay must cite the original run's messages
        design_start = next((e for e in events if e["type"] == "new_design_start"), None)
        if design_start:
            from .design.session import DesignSession
            session = DesignSession(rec, catalogs, description=design_start["description"], design_id=design_start["design_id"],
                                    _record_description=False,engineering_mode=any(e['type']=='design_engineering_mode' for e in events),
                                    interaction_mode=any(e['type']=='design_interaction_mode' for e in events))
            session.spec.description_source = design_start["description_source"]
        else:
            session = Session(rec, catalogs)
        replayed = matched = skipped = 0
        mismatches: list[str] = []
        for e in events:
            if e['type']=='design_context_restored':
                from .design.restore import restore_requirements
                import hashlib
                source=Path(e['source_record'])
                if any(p.casefold()=='experiments' or 'benchmark' in p.casefold() or 'badge' in p.casefold() for p in source.resolve().parts):
                    raise ToolError('excluded design context source')
                if hashlib.sha256(source.read_bytes()).hexdigest()!=e['source_sha256']:
                    raise ToolError('original design context fingerprint changed')
                session.spec=restore_requirements(e['requirements'],read_events(source))
                continue
            if e["type"] == "cost_configuration" and e.get("fees"):
                data = dict(e["fees"])
                for key in ("setup_fee", "per_placement_fee", "stencil_fee", "per_joint_fee", "attrition_pct"):
                    if data.get(key) is not None:
                        data[key] = Decimal(str(data[key]))
                data["loading_fee_by_class"] = {k: Decimal(str(v)) for k, v in data["loading_fee_by_class"].items()}
                data["additional_unknowns"] = tuple(data.get("additional_unknowns", []))
                data["process_fees"] = {k: Decimal(str(v)) if v is not None else None
                                        for k, v in data.get("process_fees", {}).items()}
                session.fees = AssemblyFees(**data)
                continue
            if e["type"] == "quantity_restored":
                try:
                    import hashlib
                    source = Path(e["source_record"])
                    # restore_quantity checks excluded paths before file access.
                    session.restore_quantity(source)
                    if hashlib.sha256(source.read_bytes()).hexdigest() != e["source_sha256"]:
                        session.requirements.pop("design.board_quantity", None)
                        raise ToolError("original quantity record fingerprint changed")
                except Exception as err:
                    mismatches.append(f"seq {e['seq']} quantity restoration: {type(err).__name__}")
                    audit.log("quantity_restore_failed", error_type=type(err).__name__, message=str(err))
                continue
            if e["type"] == "user_message":
                rec.seq = e["seq"] - 1
                rec.log("user_message", text=e["text"], origin=e.get("origin", "user"))
                continue
            if e["type"] != "tool_call":
                continue
            name = e["name"]
            if name in SKIP or name not in BY_NAME or e.get("controller_blocked"):
                skipped += 1
                continue
            session.now = datetime.fromisoformat(e["clock"].replace("Z", "+00:00"))
            try:
                for catalog in catalogs:
                    begin = getattr(catalog, "begin", None)
                    if begin:
                        begin(e["seq"])
                out = to_jsonable(run_tool(session, name, e["input"]))
                for catalog in catalogs:
                    finish = getattr(catalog, "finish", None)
                    if finish:
                        finish()
            except ToolError as err:
                out = {"error": str(err)}
            except Exception as err:
                out = {"error": f"internal error {type(err).__name__}: {err}"}
                audit.log("replay_tool_failure", tool=name, error_type=type(err).__name__, message=str(err))
            replayed += 1
            if output_digest(stable_view(name, out)) == e["stable_digest"]:
                matched += 1
            else:
                mismatches.append(f"seq {e['seq']} {name}({e['input']})")
    result = ReplayResult(run_id, replayed, matched, skipped, tuple(mismatches), str(audit.path))
    audit.log("replay_finished", result=result, memory_verification="excluded; requires actual memory operations")
    return result
