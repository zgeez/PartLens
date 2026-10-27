"""Zetaris data access: run Lightning SQL through the Zetaris REST (UI proxy) API.

Configuration (environment or ``.env.local``), names as in the Zetaris getting-started guide:

    ZETARIS_BASE_URL   web UI origin, e.g. http://localhost:3000
    ZETARIS_ORG_ID     numeric organisation id
    ZETARIS_API_KEY    bearer API key
    ZETARIS_ENGINE_ID  optional compute engine id
    PARTLENS_ZETARIS_PARTS_TABLE   fully qualified table holding catalogue rows (see catalog.py)

Every query is recorded (SQL, request id, time, row count) so evidence can point at the query that
produced a value.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from ..core.model import digest, utc_now
from ..core.parts import PartRecord
from ..records import RunRecorder
from ..secrets import redact
from .catalog import record_from_row

RUN_QUERY_PATH = "/api/proxy/sql-editor/sqls/run-query"
IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*){0,3}$")


class ZetarisError(RuntimeError):
    pass


@dataclass(frozen=True)
class QueryRecord:
    request_id: str
    sql: str
    executed_at: str
    rows: int
    locator: str  # what evidence cites: zetaris://<base>/query/<request_id>
    status: str = "succeeded"
    http_status: int | None = None
    server_query_id: str | None = None
    server_request_id: str | None = None
    response_digest: str | None = None
    result_identifiers: tuple[str, ...] = ()
    error: str | None = None
    server_elapsed_ms: int | None = None


@dataclass
class ZetarisConfig:
    base_url: str
    org_id: str
    api_key: str = field(repr=False)
    engine_id: str | None = None
    parts_table: str | None = None
    bom_supplier: str = "lcsc"

    @classmethod
    def from_env(cls) -> ZetarisConfig | None:
        base, org, key = (os.environ.get(k) for k in ("ZETARIS_BASE_URL", "ZETARIS_ORG_ID", "ZETARIS_API_KEY"))
        if not (base and org and key):
            return None
        return cls(base.rstrip("/"), org, key, os.environ.get("ZETARIS_ENGINE_ID") or None,
                   os.environ.get("PARTLENS_ZETARIS_PARTS_TABLE") or None,
                   os.environ.get("PARTLENS_ZETARIS_BOM_SUPPLIER") or "lcsc")


class ZetarisClient:
    def __init__(self, cfg: ZetarisConfig, timeout: float = 30, *, recorder: RunRecorder | None = None) -> None:
        if not re.fullmatch(r"https?://[^/?#@]+", cfg.base_url):
            raise ZetarisError("ZETARIS_BASE_URL must be an http(s) origin without a path")
        if not cfg.org_id.isdigit():
            raise ZetarisError("ZETARIS_ORG_ID must be numeric")
        self.cfg = cfg
        self.timeout = timeout
        self.log: list[QueryRecord] = []
        self.recorder = recorder

    def query(self, sql: str, limit: int = 1000) -> tuple[list[dict[str, Any]], QueryRecord]:
        if not sql.strip() or not isinstance(limit, int) or limit < 1:
            raise ZetarisError("SQL must not be empty and limit must be positive")
        rid = str(uuid.uuid4())
        at = utc_now()
        body: dict[str, Any] = {"sql": sql, "limit": limit}
        if self.cfg.engine_id:
            body["engineId"] = self.cfg.engine_id
        req = Request(
            self.cfg.base_url + RUN_QUERY_PATH, method="POST", data=json.dumps(body).encode(),
            headers={"Authorization": f"Bearer {self.cfg.api_key}", "X-Org-ID": self.cfg.org_id,
                     "X-Request-ID": rid, "Content-Type": "application/json"},
        )
        http_status = None
        server_request_id = server_query_id = response_digest = None
        if self.recorder:
            self.recorder.log("zetaris_query_started", request_id=rid, sql=sql, executed_at=at,
                              endpoint=self.cfg.base_url + RUN_QUERY_PATH)
        try:
            with urlopen(req, timeout=self.timeout) as resp:
                http_status = resp.status
                server_request_id = resp.headers.get("X-Request-ID")
                payload = json.loads(resp.read().decode("utf-8"))
            response_digest = digest(payload)
            if isinstance(payload, dict):
                server_query_id = next((str(payload[k]) for k in ("queryId", "query_id", "executionId", "id")
                                        if payload.get(k) is not None), None)
            rows = rows_from_payload(payload)
        except Exception as exc:
            if isinstance(exc, HTTPError):
                http_status = exc.code
                message = f"HTTP {exc.code} from Zetaris"  # response bodies may echo credentials
            else:
                message = redact(f"Zetaris query failed ({type(exc).__name__}): {exc}")
            rec = QueryRecord(rid, sql, at, 0, f"zetaris:{rid}", "failed", http_status,
                              server_query_id, server_request_id, response_digest, error=message)
            self._record(rec)
            raise ZetarisError(message) from exc
        identifiers = tuple(str(r.get("supplier", "")) + ":" + str(r["supplier_pn"])
                            if r.get("supplier_pn") else "row-sha256:" + digest(r) for r in rows)
        elapsed = payload.get("timeUsed") if isinstance(payload, dict) else None
        elapsed = elapsed if type(elapsed) is int and elapsed >= 0 else None
        rec = QueryRecord(rid, sql, at, len(rows), f"zetaris:{rid}", "succeeded", http_status,
                          server_query_id, server_request_id, response_digest, identifiers,
                          server_elapsed_ms=elapsed)
        self._record(rec)
        return rows, rec

    def _record(self, rec: QueryRecord) -> None:
        self.log.append(rec)
        if self.recorder:
            self.recorder.log("zetaris_query", query=rec)


def rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    """Normalise the run-query response to a list of dicts.

    Accepts a list of objects, or an object with column names plus row arrays under common keys. Raises when
    the shape is not recognised, rather than guessing.
    """
    if isinstance(payload, list):
        if all(isinstance(r, dict) for r in payload):
            return payload
    if isinstance(payload, dict):
        if (payload.get("error") or payload.get("errors") or payload.get("success") is False
                or str(payload.get("status", "")).lower() in {"failed", "error", "cancelled", "pending", "queued", "running"}):
            raise ZetarisError("Zetaris returned an execution error")
        for k in ("data", "result", "results", "rows", "records"):
            if k in payload:
                inner = payload[k]
                if isinstance(inner, list) and all(isinstance(r, dict) for r in inner):
                    return inner
                if isinstance(inner, dict):
                    try:
                        return rows_from_payload(inner)
                    except ZetarisError:
                        pass
        # The hackathon 2.4.3 gateway returns {headers: [...], data: [[...]], total, timeUsed}.
        cols = next((payload[k] for k in ("columns", "columnNames", "schema", "headers")
                     if isinstance(payload.get(k), list)), None)
        data = next((payload[k] for k in ("data", "rows", "values") if isinstance(payload.get(k), list)), None)
        if isinstance(cols, list) and isinstance(data, list):
            names = [c.get("name") if isinstance(c, dict) else str(c) for c in cols]
            if any(not isinstance(n, str) or not n for n in names) or len(set(names)) != len(names):
                raise ZetarisError("Zetaris columns must have unique nonempty names")
            if any(not isinstance(r, list) or len(r) != len(names) for r in data):
                raise ZetarisError("Zetaris row width does not match its columns")
            return [dict(zip(names, r)) for r in data]
    raise ZetarisError("unrecognised run-query response shape")


def _quote(s: str) -> str:
    # Spark SQL treats backslashes specially. Hex literals cannot terminate the SQL expression,
    # even when an untrusted part description/search string contains quotes and backslashes.
    return "decode(unhex('" + s.encode("utf-8").hex() + "'), 'UTF-8')"


class ZetarisCatalog:
    """Catalogue rows (see catalog.py) queried in place through Zetaris."""

    def __init__(self, client: ZetarisClient, table: str) -> None:
        if not IDENT.match(table):
            raise ZetarisError(f"invalid table identifier {table!r}")
        self.client = client
        self.table = table
        if client.cfg.bom_supplier not in {"lcsc", "jlcpcb"}:
            raise ZetarisError("unsupported BOM supplier namespace")
        self.bom_supplier = client.cfg.bom_supplier
        self.name = f"zetaris:{table}"

    def with_recorder(self, recorder: RunRecorder) -> ZetarisCatalog:
        """Bind query evidence to one session without redirecting another session's audit events."""
        if self.client.recorder is recorder:
            return self
        return ZetarisCatalog(ZetarisClient(self.client.cfg, self.client.timeout, recorder=recorder), self.table)

    def _records(self, where: str, limit: int) -> list[PartRecord]:
        rows, q = self.client.query(self._select(where, limit), limit)
        out = []
        for row in rows:
            row = {str(k).lower(): v for k, v in row.items()}
            # Evidence cites the query that returned the row, plus the snapshot source the row came from.
            row["source"] = f"{q.locator}#{row.get('supplier')}:{row.get('supplier_pn')}" + (
                f" (from {row['source']})" if row.get("source") else "")
            out.append(record_from_row(row))
        return out

    def _select(self, where: str, limit: int) -> str:
        return f"SELECT * FROM {self.table} WHERE {where} LIMIT {int(limit)}"

    def get(self, key: str) -> PartRecord | None:
        supplier, _, pn = key.partition(":")
        hits = self._records(f"lower(supplier) = {_quote(supplier.lower())} AND supplier_pn = {_quote(pn)}", 2)
        return hits[0] if hits else None

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        norm = re.sub(r"\s+", "", mpn).upper()
        return self._records(f"upper(mpn) = {_quote(norm)}", 50)

    def search(self, category: str, package: str | None = None, text: str | None = None,
               limit: int = 20) -> list[PartRecord]:
        conds = [f"category = {_quote(category)}"]
        if package:
            conds.append(f"lower(package) = {_quote(package.lower())}")
        if text:
            conds.append(f"(lower(mpn) LIKE {_quote('%' + text.lower() + '%')} OR "
                         f"lower(description) LIKE {_quote('%' + text.lower() + '%')})")
        return self._records(" AND ".join(conds), limit)


class ZetarisInlineCatalog(ZetarisCatalog):
    """Read-only query relation for a small official snapshot; no DDL, files or persistent table writes.

    Literal values are UTF-8 hex encoded to preserve JSON/backslashes without SQL interpolation.
    Zetaris executes the SELECT over the supplied supplier rows; this is not a local query fallback.
    """
    def __init__(self, client: ZetarisClient, rows: list[dict[str, Any]]) -> None:
        from .catalog import FLAT_COLUMNS

        if not 1 <= len(rows) <= 25 or any(r.get("supplier") != "jlcpcb" for r in rows):
            raise ZetarisError("inline official dataset requires 1..25 JLCPCB component rows")
        super().__init__(client, "partlens_official_components")
        self.bom_supplier = "jlcpcb"
        self.rows = rows
        encoded = []
        for row in rows:
            values = []
            for column in FLAT_COLUMNS:
                value = row.get(column)
                if value is None:
                    values.append("CAST(NULL AS STRING)")
                else:
                    if isinstance(value, (dict, list, tuple)):
                        value = json.dumps(value, ensure_ascii=False, sort_keys=True)
                    value = str(value).encode("utf-8").hex()
                    values.append(f"decode(unhex('{value}'), 'UTF-8')")
            encoded.append("(" + ",".join(values) + ")")
        self.prefix = (f"WITH {self.table} (" + ",".join(FLAT_COLUMNS) + ") AS (VALUES "
                       + ",".join(encoded) + ") ")
        self.name = "zetaris:official-jlcpcb-read-only-relation"

    def _select(self, where: str, limit: int) -> str:
        return self.prefix + super()._select(where, limit)

    def with_recorder(self, recorder: RunRecorder) -> ZetarisInlineCatalog:
        return ZetarisInlineCatalog(ZetarisClient(self.client.cfg, self.client.timeout, recorder=recorder), self.rows)
