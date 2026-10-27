"""Run records: an append-only JSON-lines log of everything a PartLens session did.

Each event has a sequence number, UTC time, type and payload. Tool calls record their inputs and a digest of
their outputs, so a run can be replayed: deterministic tools are re-executed from the recorded inputs and their
output digests compared.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .core.model import digest, to_jsonable, utc_now
from .secrets import redact


def new_run_id() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + secrets.token_hex(3)


@dataclass
class RunRecorder:
    path: Path
    run_id: str
    seq: int = 0

    @classmethod
    def create(cls, root: str | Path, run_id: str | None = None) -> RunRecorder:
        run_id = run_id or new_run_id()
        p = Path(root) / f"{run_id}.jsonl"
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            raise FileExistsError(p)
        return cls(p, run_id)

    def log(self, type_: str, **payload: Any) -> dict[str, Any]:
        self.seq += 1
        event = {"seq": self.seq, "at": utc_now(), "run": self.run_id, "type": type_, "format_version": 2,
                 **redact(to_jsonable(payload))}
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n")
        return event

    def user_messages(self) -> list[dict[str, Any]]:
        return [e for e in read_events(self.path) if e["type"] == "user_message"]


def read_events(path: str | Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line.strip()]


def output_digest(result: Any) -> str:
    return digest(result)
