"""Engineering decision memory on Meterless H-MEM.

PartLens writes each substitution decision (verified, rejected or unverified) to H-MEM with its provenance:
the run record, the decision id, and the checks that produced it. Before evaluating a candidate again, PartLens
recalls earlier decisions for the same (original, candidate) pair and shows them with their provenance.

A recalled decision is context, not a verdict: the deterministic checks are re-run on current data, and a
recalled rejection is reported next to the new result (and flagged if the two disagree).

H-MEM runs in a Node process (``integrations/hmem-bridge``) spoken to over JSON lines.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from ..core.model import Decision, to_jsonable
from ..paths import resource_root

REPO_ROOT = Path(__file__).resolve().parents[3]
BRIDGE_DIR = REPO_ROOT / "integrations" / "hmem-bridge"


class HMemError(RuntimeError):
    pass


class HMemBridge:
    def __init__(self, persist_dir: str | Path, *, actor: str = "partlens", clock_ms: int | None = None,
                 bridge_dir: Path = BRIDGE_DIR) -> None:
        tsx = bridge_dir / "node_modules" / ".bin" / ("tsx.cmd" if os.name == "nt" else "tsx")
        bundled = getattr(sys,'frozen',False)
        if not bundled and not tsx.exists():
            raise HMemError(f"H-MEM bridge not installed: run `npm install && npm run setup` in {bridge_dir}")
        if not bundled and not (bridge_dir / "vendor" / "hmem" / "src" / "index.ts").exists():
            raise HMemError(f"H-MEM engine not vendored: run `npm run setup` in {bridge_dir}")
        node = str(resource_root()/'memory/node.exe') if bundled else shutil.which("node")
        if not node:
            raise HMemError("node not found on PATH")
        cli = bridge_dir / "node_modules" / "tsx" / "dist" / "cli.mjs"
        persist = Path(persist_dir).resolve()  # the bridge runs with its own working directory
        args = [node, str(cli), str(bridge_dir / "bridge.ts"), "--persist-dir", str(persist), "--actor", actor]
        cwd=bridge_dir
        if bundled:
            entry=resource_root()/'memory/bridge.mjs'
            if not Path(node).is_file() or not entry.is_file():raise HMemError('Bundled memory runtime missing; rebuild PartLens.exe')
            args=[node,str(entry),'--bundled','--persist-dir',str(persist),'--actor',actor]
            cwd=entry.parent
        if clock_ms is not None:
            args += ["--clock-ms", str(clock_ms)]
        self._proc = subprocess.Popen(args, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                      text=True, encoding="utf-8", cwd=cwd,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        self._lock = threading.Lock()
        self._seq = 0
        self.info = self.call("hello")

    def call(self, op: str, **args: Any) -> Any:
        with self._lock:
            self._seq += 1
            req = {"id": self._seq, "op": op, "args": args}
            assert self._proc.stdin and self._proc.stdout
            try:
                self._proc.stdin.write(json.dumps(req) + "\n")
                self._proc.stdin.flush()
                line = self._proc.stdout.readline()
            except OSError as e:
                raise HMemError(f"H-MEM bridge died: {self._stderr()}") from e
            if not line:
                raise HMemError(f"H-MEM bridge exited: {self._stderr()}")
            resp = json.loads(line)
            if resp.get("id") != self._seq:
                raise HMemError(f"out-of-order response {resp.get('id')} for {self._seq}")
            if not resp.get("ok"):
                raise HMemError(resp.get("error", "unknown H-MEM error"))
            return resp.get("result")

    def _stderr(self) -> str:
        try:
            self._proc.wait(timeout=2)
            return (self._proc.stderr.read() if self._proc.stderr else "")[-500:]
        except subprocess.TimeoutExpired:
            return "(no exit)"

    def close(self) -> None:
        if self._proc.poll() is None:
            if self._proc.stdin:
                self._proc.stdin.close()
            try:
                self._proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._proc.kill()

    def __enter__(self) -> HMemBridge:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()


def _tag(s: str) -> str:
    return s.replace(" ", "_")


def _epoch_ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


@dataclass(frozen=True)
class RecalledDecision:
    memory_id: str
    content: str
    status: str
    decision_id: str
    original: str | None
    candidate: str
    source: str
    recorded_at_ms: int
    confidence: float
    details: dict[str, Any]


class DecisionMemory:
    def __init__(self, bridge: HMemBridge, design: str) -> None:
        self.bridge = bridge
        self.design = design

    def remember(self, decision: Decision, *, run_id: str, reason: str | None = None,
                 context: dict[str, Any] | None = None) -> dict[str, Any]:
        summary = reason or "; ".join(c.message for c in (decision.failures or decision.gaps)) or "all checks passed"
        content = (f"PartLens {decision.status.value} {decision.candidate} as substitute for {decision.original} "
                   f"on {self.design} {decision.subject}: {summary}")
        details = {
            "decision_id": decision.id,
            "status": decision.status.value,
            "checks": [to_jsonable(c) for c in decision.checks],
            "context": context,
        }
        tags = ["partlens", "decision", f"decision:{decision.status.value}", f"design:{_tag(self.design)}",
                f"line:{decision.subject}", f"candidate:{decision.candidate}"]
        if decision.original:
            tags.append(f"original:{decision.original}")
        rec = self.bridge.call(
            "add", content=content, type="factual", layer="long_term", tags=tags, confidence=1.0,
            source=f"partlens:run:{run_id}:decision:{decision.id}",
            provenance={"origin": "plan_completion", "learnedAt": _epoch_ms(decision.decided_at),
                        "label": f"partlens check run {run_id}",
                        "refs": [f"decision:{decision.id}", json.dumps(details, sort_keys=True)]},
        )
        return rec

    def read_decision(self, memory_id: str) -> dict[str, Any] | None:
        """Ledgered exact read restricted to this design; model text cannot supply historical facts."""
        matches = self.bridge.call("find_by_tags", tags=["partlens", "decision", f"design:{_tag(self.design)}"])
        return next((m for m in matches if m["id"] == memory_id), None)

    def recall(self, original: str | None, candidate: str, line_id: str | None = None) -> list[RecalledDecision]:
        tags = ["partlens", "decision", f"design:{_tag(self.design)}", f"candidate:{candidate}"]
        if original:
            tags.append(f"original:{original}")
        if line_id:
            tags.append(f"line:{line_id}")
        out = []
        for m in self.bridge.call("find_by_tags", tags=tags):
            status = next((t.split(":", 1)[1] for t in m["tags"] if t.startswith("decision:")), "unknown")
            refs = (m.get("provenance") or {}).get("refs") or []
            details = json.loads(refs[1]) if len(refs) > 1 else {}
            out.append(RecalledDecision(
                memory_id=m["id"], content=m["content"], status=status,
                decision_id=details.get("decision_id", ""), original=original, candidate=candidate,
                source=m["source"], recorded_at_ms=m["timestamp"], confidence=m["confidence"], details=details,
            ))
        return out

    def search(self, text: str, top_n: int = 5, *, run_id: str | None = None) -> list[dict[str, Any]]:
        """Hybrid text retrieval, or explicit exact run-source lookup through the real H-MEM store."""
        if run_id is not None:
            matches = self.bridge.call("find_by_tags", tags=["partlens", "decision", f"design:{_tag(self.design)}"])
            memories = [{"memory": m, "relevance": None} for m in matches
                        if m.get("source", "").startswith(f"partlens:run:{run_id}:decision:")]
        else:
            memories = self.bridge.call("query", query=text, topN=max(top_n, 50))["memories"]
        return [{"id": r["memory"]["id"], "content": r["memory"]["content"], "relevance": r["relevance"],
                 "source": r["memory"]["source"],
                 "retrieval": "exact_design_and_run_source" if run_id is not None else "hybrid_text_query",
                 **{field: next((tag[len(prefix):] for tag in r["memory"].get("tags", []) if tag.startswith(prefix)), None)
                    for field, prefix in (("original", "original:"), ("candidate", "candidate:"), ("line", "line:"))}}
                for r in memories
                if {"partlens", "decision", f"design:{_tag(self.design)}"} <= set(r["memory"].get("tags", []))][:top_n]

    def history(self, memory_id: str) -> list[dict[str, Any]]:
        return self.bridge.call("history", id=memory_id)
