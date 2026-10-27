"""Official JLCPCB public-component lookup only; no ordering or private-library operations.

Contract: https://api.jlcpcb.com/docs/api-request-signature and the approved
Query Component Detail Data Interface PDF. Response data stays internal pending usage review.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from ..core.model import digest, to_jsonable, utc_now
from ..records import RunRecorder
from ..secrets import redact
from ..core.bom import normalise_mpn
from ..core.parts import PartRecord
from .catalog import LocalCatalog, record_from_row

ORIGIN = "https://open.jlcpcb.com"
DETAIL_PATH = "/overseas/openapi/component/getComponentDetailByCode"
CODE = re.compile(r"C[1-9][0-9]*\Z")
MAX_CODES = 25  # narrower than the documented 1000; explicit research, never catalogue mirroring


class JLCError(RuntimeError):
    pass


@dataclass(frozen=True)
class JLCConfig:
    app_id: str = field(repr=False)
    access_key: str = field(repr=False)
    secret_key: str = field(repr=False)
    app_name: str = field(default="", repr=False)

    def __post_init__(self) -> None:
        if not all(re.fullmatch(r"[A-Za-z0-9_-]+", v) for v in (self.app_id, self.access_key)):
            raise JLCError("JLC_APP_ID and JLC_ACCESS_KEY must be safe header identifiers")
        if not self.secret_key:
            raise JLCError("JLC_SECRET_KEY is required")

    @classmethod
    def from_env(cls) -> JLCConfig | None:
        values = [os.getenv(n, "") for n in ("JLC_APP_ID", "JLC_ACCESS_KEY", "JLC_SECRET_KEY")]
        return cls(*values, os.getenv("JLC_APP_NAME", "")) if all(values) else None


def authorization(cfg: JLCConfig, body: bytes, timestamp: int, nonce: str) -> str:
    """Sign the exact UTF-8 request bytes, including the fifth terminating newline."""
    if not re.fullmatch(r"[A-Za-z0-9]{32}", nonce) or type(timestamp) is not int or timestamp < 0:
        raise JLCError("invalid signing timestamp or nonce")
    message = f"POST\n{DETAIL_PATH}\n{timestamp}\n{nonce}\n".encode() + body + b"\n"
    signature = base64.b64encode(hmac.new(cfg.secret_key.encode(), message, hashlib.sha256).digest()).decode()
    return (f'JOP appid="{cfg.app_id}",accesskey="{cfg.access_key}",nonce="{nonce}",'
            f'timestamp="{timestamp}",signature="{signature}"')


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None  # authenticated requests must never forward credentials to another destination


@dataclass(frozen=True)
class Lookup:
    data: tuple[dict[str, Any], ...]
    retrieved_at: str
    request_id: str  # client identifier, never presented as a server trace
    trace_id: str | None
    http_status: int
    response_digest: str
    cached: bool = False

    @property
    def source(self) -> str:
        return f"{ORIGIN}{DETAIL_PATH}#client-request={self.request_id}"


class JLCClient:
    def __init__(self, cfg: JLCConfig, *, cache_dir: str | Path = ".partlens/jlcpcb/cache",
                 recorder: RunRecorder | None = None, timeout: float = 20, ttl: int = 300,
                 attempts: int = 3, transport: Callable | None = None,
                 sleep: Callable[[float], None] = time.sleep, max_requests: int = 12,
                 max_distinct_codes: int = 40) -> None:
        if not 0 < timeout <= 60 or not 0 <= ttl <= 3600 or not 1 <= attempts <= 3:
            raise JLCError("invalid bounded timeout, cache TTL or retry count")
        self.cfg, self.cache_dir, self.recorder = cfg, Path(cache_dir), recorder
        self.timeout, self.ttl, self.attempts = timeout, ttl, attempts
        self.transport = transport or build_opener(_NoRedirect()).open
        self.sleep = sleep
        if type(max_requests) is not int or not 1 <= max_requests <= 30 or type(max_distinct_codes) is not int or not 1 <= max_distinct_codes <= 100:
            raise JLCError("invalid session API budget")
        self.max_requests, self.max_distinct_codes = max_requests, max_distinct_codes
        self.requests_used = 0
        self.requested_codes: set[str] = set()

    def _log(self, event: str, **data: Any) -> None:
        if self.recorder:
            self.recorder.log(event, **data)

    def lookup(self, codes: list[str], *, refresh: bool = False) -> Lookup:
        if not isinstance(codes, list) or not 1 <= len(codes) <= MAX_CODES or any(
                not isinstance(c, str) or not CODE.fullmatch(c) for c in codes):
            raise JLCError(f"lookup requires 1..{MAX_CODES} explicit C codes")
        codes = sorted(set(codes))
        cache_key = digest([self.cfg.app_id, self.cfg.access_key, codes])
        if not refresh and self.ttl:
            for path in sorted(self.cache_dir.glob(cache_key + "-*.json"), reverse=True):
                try:
                    entry = json.loads(path.read_text(encoding="utf-8"))
                    age = (datetime.now(UTC) - datetime.fromisoformat(entry["retrieved_at"])).total_seconds()
                    if not 0 <= age <= self.ttl:
                        continue
                    data = self._data(entry["payload"], codes)
                    if digest(entry["payload"]) != entry["response_digest"]:
                        continue
                    result = Lookup(tuple(data), entry["retrieved_at"], entry["request_id"],
                                    entry["trace_id"], 200, entry["response_digest"], True)
                    self._log("jlcpcb_cache_hit", codes=codes, lookup=result)
                    return result
                except (ValueError, KeyError, TypeError, OSError, JLCError):
                    continue
        body = json.dumps({"componentCodes": codes}, separators=(",", ":")).encode()
        for attempt in range(self.attempts):
            if self.requests_used >= self.max_requests or len(self.requested_codes | set(codes)) > self.max_distinct_codes:
                self._log("jlcpcb_budget_exhausted", requests_used=self.requests_used,
                          distinct_codes=len(self.requested_codes), requested_codes=codes)
                raise JLCError("session API request/code budget exhausted; no further request sent")
            self.requests_used += 1
            self.requested_codes.update(codes)
            rid, at = secrets.token_hex(16), utc_now()
            req = Request(ORIGIN + DETAIL_PATH, data=body, method="POST", headers={
                "Content-Type": "application/json", "Accept": "application/json",
                "Authorization": authorization(self.cfg, body, int(time.time()), secrets.token_hex(16))})
            self._log("jlcpcb_request", request_id=rid, endpoint=ORIGIN + DETAIL_PATH,
                      codes=codes, queried_at=at, attempt=attempt + 1, method="POST",
                      session_requests_used=self.requests_used, session_request_limit=self.max_requests,
                      session_distinct_codes=len(self.requested_codes), session_code_limit=self.max_distinct_codes)
            status, trace = None, None
            try:
                with self.transport(req, timeout=self.timeout) as response:
                    status = response.status
                    trace = response.headers.get("J-Trace-ID")
                    # Inspect only non-secret response metadata; never persist cookies or arbitrary headers.
                    public_headers = ("Content-Type", "Content-Language", "Date", "Currency", "Content-Currency",
                                      "X-Currency", "X-Locale", "Retry-After", "RateLimit-Limit",
                                      "RateLimit-Remaining", "X-RateLimit-Limit", "X-RateLimit-Remaining")
                    self._log("jlcpcb_response_metadata", request_id=rid, http_status=status,
                              headers={k: response.headers.get(k) for k in public_headers if response.headers.get(k)})
                    raw = response.read(4_000_001)
                    if len(raw) > 4_000_000:
                        raise JLCError("response exceeds bounded lookup size")
                    payload = json.loads(raw.decode("utf-8"), parse_float=Decimal)
                if status != 200:
                    raise JLCError("unexpected HTTP status")
                # Convert decimal JSON numbers to exact strings for persistent round trips.
                payload = redact(to_jsonable(payload))
                data = self._data(payload, codes)
                result = Lookup(tuple(data), at, rid, trace, status, digest(payload))
                self._log("jlcpcb_response", lookup=result, successful=True,
                          observed_fields=sorted({k for row in data for k in row}))
                self.cache_dir.mkdir(parents=True, exist_ok=True)
                entry = {"payload": payload, "retrieved_at": at, "request_id": rid,
                         "trace_id": trace, "response_digest": result.response_digest}
                # Append snapshots; old successes and failures are never overwritten.
                with (self.cache_dir / f"{cache_key}-{time.time_ns()}-{rid}.json").open("x", encoding="utf-8") as f:
                    json.dump(entry, f, ensure_ascii=False, sort_keys=True)
                return result
            except Exception as exc:
                status = exc.code if isinstance(exc, HTTPError) else status
                trace = exc.headers.get("J-Trace-ID") if isinstance(exc, HTTPError) else trace
                self._log("jlcpcb_failure", request_id=rid, http_status=status, trace_id=trace,
                          error_type=type(exc).__name__, attempt=attempt + 1,
                          reason=str(exc) if isinstance(exc, JLCError) else "transport or response failure")
                transient = isinstance(exc, (TimeoutError, ConnectionError)) or (
                    isinstance(exc, HTTPError) and status in {429, 500, 502, 503, 504})
                # URLError may contain a timeout/connection error; messages are not logged.
                from urllib.error import URLError
                transient = transient or isinstance(exc, URLError) and not isinstance(exc, HTTPError)
                if not transient or attempt + 1 == self.attempts:
                    raise JLCError(f"official JLCPCB lookup failed ({type(exc).__name__}, HTTP {status})") from None
                delay = 2 ** attempt + secrets.randbelow(100) / 100
                if isinstance(exc, HTTPError) and (after := exc.headers.get("Retry-After")):
                    try:
                        delay = float(after) if after.isdigit() else (
                            parsedate_to_datetime(after) - datetime.now(UTC)).total_seconds()
                    except (ValueError, TypeError, OverflowError):
                        delay = 2 ** attempt
                if delay > 60:
                    raise JLCError("rate-limit wait exceeds bounded retry window; retry later") from None
                self._log("jlcpcb_retry", request_id=rid, after_seconds=max(0, delay))
                self.sleep(max(0, delay))
        raise AssertionError("unreachable")

    @staticmethod
    def _data(payload: Any, codes: list[str]) -> list[dict[str, Any]]:
        # Approved PDF uses `successful`; the real overseas service uses `success`.
        if (not isinstance(payload, dict) or payload.get("code") != 200
                or not any(payload.get(k) is True for k in ("successful", "success"))
                or any(k in payload and payload[k] is not True for k in ("successful", "success"))):
            raise JLCError("JLCPCB did not confirm business success")
        data = payload.get("data")
        if not isinstance(data, list) or any(not isinstance(r, dict) for r in data):
            raise JLCError("unrecognised component detail schema")
        ids = [r.get("componentCode") for r in data]
        if len(set(ids)) != len(ids) or any(c not in codes for c in ids):
            raise JLCError("response component identity differs from requested codes")
        return data  # missing requested codes remain missing, never an invented record


PARAMETERS = {
    "capacitance": "capacitance", "resistance": "resistance", "inductance": "inductance",
    "voltage rating": "voltage_rating", "tolerance": "tolerance_pct", "power(watts)": "power_w",
    "current rating": "current_rating", "output current": "output_current", "output voltage": "output_voltage",
    "frequency": "frequency", "illumination color": "color",
}
CATEGORIES = {"Capacitors": "capacitor", "Resistors": "resistor", "Inductors": "inductor",
              "Diodes": "diode", "Connectors": "connector", "Switches": "switch",
              "Crystals, Oscillators, Resonators": "crystal"}


def row_from_detail(raw: dict[str, Any], lookup: Lookup) -> dict[str, Any]:
    """Separate distributor attributes, opaque API fields and assembly classifications.

    No description mining. An unqualified `Voltage - Supply` is never a recommended
    operating limit. The service does not document currency/MOQ/multiples in this endpoint.
    """
    code = raw.get("componentCode")
    if not isinstance(code, str) or not CODE.fullmatch(code):
        raise JLCError("invalid component identity")
    category = CATEGORIES.get(raw.get("firstTypeName"), "ic")
    if raw.get("secondTypeName") == "LED Indication - Discrete":
        category = "led"
    source = lookup.source + f"&component={code}"
    params: dict[str, Any] = {}
    conflicts: set[str] = set()
    values = raw.get("parameters")
    if values is not None and not isinstance(values, list):
        raise JLCError("unrecognised parameters schema")
    for item in values or []:
        if not isinstance(item, dict) or not isinstance(item.get("parameterName"), str):
            raise JLCError("unrecognised parameter entry")
        name, value = item["parameterName"], item.get("parameterValue")
        key = PARAMETERS.get(name.strip().lower())
        if name.strip().lower() == "temperature coefficient" and category == "capacitor":
            key = "dielectric"
        if name.strip().lower() == "operating temperature":
            key = "temp_range"
            # Preserve conditional ambient/junction notation as opaque; don't erase qualifiers.
            if isinstance(value, str) and re.fullmatch(r"[+-]?\d+(?:℃|°C)~[+-]?\d+(?:℃|°C)", value):
                value = "~".join(str(int(n)) for n in re.findall(r"[+-]?\d+", value))
            else:
                key = None
        if not key or value in (None, "", "-"):
            continue
        if key in params and params[key]["value"] != value:
            conflicts.add(key)
        params[key] = {"value": value, "evidence": {
            "kind": "supplier_record", "locator": source + f"&parameter={name}",
            "retrieved_at": lookup.retrieved_at, "excerpt": f"{name}: {item['parameterValue']}"}}
    for key in conflicts:
        params.pop(key, None)  # contradictory duplicates cannot verify anything
    prices = []
    intervals = []
    for item in raw.get("priceRanges") or []:
        if not isinstance(item, dict):
            raise JLCError("unrecognised price range schema")
        start, end, price = item.get("startQuantity"), item.get("endQuantity"), item.get("unitPrice")
        if (type(start) is not int or start < 1 or type(end) is not int
                or end != -1 and end < start):
            raise JLCError("invalid price range bounds")
        amount = Decimal(str(price))
        if not amount.is_finite() or amount < 0:
            raise JLCError("invalid unit price")
        prices.append([start, str(amount), None if end == -1 else end])
        intervals.append((start, None if end == -1 else end))
    intervals.sort()
    if any(a[1] is None or a[1] >= b[0] for a, b in zip(intervals, intervals[1:])):
        raise JLCError("overlapping price ranges")
    library = raw.get("libraryType")
    # Corroborated by official product pages C1525 (Basic/base) and C347376 (Extended/expand).
    # This mapping is an explicit inference; unknown/new enums never imply eligibility or a zero fee.
    classification = {"base": "basic", "expand": "extended"}.get(library)
    class_ev = {"kind": "supplier_record", "locator": source + "&field=libraryType",
                "field": "assembly_class", "value": classification, "retrieved_at": lookup.retrieved_at,
                "excerpt": f"libraryType={library}; enum mapping corroborated with official product pages "
                           "https://jlcpcb.com/partdetail/C1525 and https://jlcpcb.com/partdetail/C347376"}
    sheet = raw.get("datasheetUrl") or raw.get("dataManualUrl")
    if not isinstance(sheet, str) or not sheet.startswith("https://"):
        sheet = None  # the published PDF calls this a file ID; never fabricate a download endpoint
    return {
        "supplier": "jlcpcb", "supplier_pn": code, "mpn": raw.get("componentModel") or "",
        "manufacturer": raw.get("componentBrandEn") or "", "category": category,
        "package": raw.get("componentSpecification") or "", "description": raw.get("description") or "",
        "params": params, "price_breaks": prices, "stock": raw.get("stockCount"),
        "currency": "", "moq": None, "order_multiple": None,
        "commercial_unknowns": ["price currency", "minimum order quantity", "order multiple", "assembly eligibility"],
        "assembly_class": classification, "assembly_service": "jlcpcb" if classification else None,
        "assembly_class_evidence": class_ev if classification else None,
        "datasheet_url": sheet, "retrieved_at": lookup.retrieved_at, "source": source,
        "supplier_metadata": {
            "api_library_type": library, "assembly_class_mapping": "corroborated inference" if classification else None,
            "assembly_component_flag": raw.get("assemblyComponentFlag"), "assembly_eligible": None,
            "solder_joint_count": raw.get("solderJointCount"), "raw_parameters": values,
            "conflicting_parameters": sorted(conflicts), "price_ranges": raw.get("priceRanges"),
            "manufacturer_reference": raw.get("dataManualOfficialLink") or None,
            "datasheet_reference": raw.get("datasheetUrl"), "server_trace_id": lookup.trace_id,
            "http_status": lookup.http_status, "client_request_id": lookup.request_id,
            "response_digest": lookup.response_digest, "scope": "JLCPCB PCBA component supply; not a retail shipment quote",
        },
    }


def quantity_price_observation(part: PartRecord, needed: int) -> dict[str, Any]:
    """Exact nominal demand arithmetic, explicitly conditional on unknown procurement terms.

    This is deliberately separate from the USD BOM/assembly total. It cannot enter optimisation.
    """
    price = part.price_at(needed)
    return {"part": part.key, "needed": needed, "unit_price": str(price.unit_price) if price else None,
            "nominal_amount": str(price.unit_price * needed) if price else None,
            "currency": price.currency or None if price else None, "complete": False,
            "quantity_is_purchase_quote": False, "unknowns": list(part.commercial_unknowns),
            "stock": part.stock, "stock_covers_nominal_demand": part.stock >= needed if part.stock is not None else None,
            "source": part.source, "retrieved_at": part.retrieved_at}


class JLCCatalog:
    """Explicit-code network reads; parametric/MPN search covers only already retrieved records."""
    name = "jlcpcb-official"
    bom_supplier = "jlcpcb"

    def __init__(self, client: JLCClient, leads: LocalCatalog | None = None) -> None:
        self.client = client
        self.leads = leads
        self.rows: dict[str, dict[str, Any]] = {}
        self.provenance = {"name": self.name, "research_leads": getattr(leads, "provenance", None),
                           "lead_specs_used_for_qualification": False,
                           "max_requests": client.max_requests, "max_distinct_codes": client.max_distinct_codes}

    def with_recorder(self, recorder: RunRecorder) -> JLCCatalog:
        client = JLCClient(self.client.cfg, cache_dir=self.client.cache_dir, recorder=recorder,
                           timeout=self.client.timeout, ttl=self.client.ttl, attempts=self.client.attempts,
                           transport=self.client.transport, sleep=self.client.sleep,
                           max_requests=self.client.max_requests, max_distinct_codes=self.client.max_distinct_codes)
        return JLCCatalog(client, self.leads)

    def prepare(self, codes: list[str]) -> None:
        now = datetime.now(UTC)
        codes = sorted({code for code in codes if code not in self.rows or not 0 <= (now - datetime.fromisoformat(
            self.rows[code]["retrieved_at"].replace("Z", "+00:00"))).total_seconds() <= self.client.ttl})
        for start in range(0, len(codes), MAX_CODES):
            result = self.client.lookup(codes[start:start + MAX_CODES])
            for raw in result.data:
                row = row_from_detail(raw, result)
                record_from_row(row)  # reject malformed commercial values before retaining a row
                self.rows[row["supplier_pn"]] = row

    def get(self, key: str) -> PartRecord | None:
        supplier, _, code = key.partition(":")
        if supplier != "jlcpcb" or not CODE.fullmatch(code):
            return None
        row = self.rows.get(code)
        age = (datetime.now(UTC) - datetime.fromisoformat(row["retrieved_at"].replace("Z", "+00:00"))).total_seconds() if row else None
        if age is None or not 0 <= age <= self.client.ttl:
            self.prepare([code])
        return record_from_row(self.rows[code]) if code in self.rows else None

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        return [record_from_row(r) for r in self.rows.values() if normalise_mpn(r["mpn"]) == normalise_mpn(mpn)]

    def search(self, category: str, package: str | None = None, text: str | None = None,
               limit: int = 20) -> list[PartRecord]:
        return LocalCatalog([record_from_row(r) for r in self.rows.values()]).search(category, package, text, limit)

    def discover_for(self, original: PartRecord, category: str, package: str | None,
                     text: str | None, limit: int) -> list[PartRecord]:
        """Use retained catalogue hints to choose codes; return only official evidence for qualification."""
        if self.leads is None:
            return self.search(category, package, text, limit)
        candidates: dict[str, PartRecord] = {}
        prior = self.leads.get("lcsc:" + original.supplier_pn)
        if prior and normalise_mpn(prior.mpn) == normalise_mpn(original.mpn):
            for key in prior.suggested_alternates:
                lead = self.leads.get(key)
                if lead and (not text or text.lower() in f"{lead.mpn} {lead.description}".lower()):
                    candidates.setdefault(lead.supplier_pn, lead)
        for lead in self.leads.search(category, package, text, min(limit, 6)):
            candidates.setdefault(lead.supplier_pn, lead)
        candidates = {pn: lead for pn, lead in candidates.items()
                      if pn != original.supplier_pn and lead.supplier == "lcsc" and CODE.fullmatch(pn)}
        selected = dict(list(candidates.items())[:min(limit, 6)])
        self.client._log("jlcpcb_discovery_leads", original=original.key, category=category, package=package,
                         text=text, limit=limit, lead_source=self.provenance["research_leads"],
                         leads=[{"code": pn, "source": p.source, "retrieved_at": p.retrieved_at}
                                for pn, p in selected.items()], engineering_fields_transferred=False)
        if selected:
            self.prepare(list(selected))
        results = []
        for pn, lead in selected.items():
            if pn not in self.rows:
                continue
            self.rows[pn]["supplier_metadata"]["research_lead"] = {
                "source": lead.source, "retrieved_at": lead.retrieved_at,
                "scope": "code discovery only; no engineering, price, stock or classification transfer"}
            results.append(record_from_row(self.rows[pn]))
        return results


class JLCZetarisCatalog:
    """Official lookups followed by real read-only Zetaris SELECTs; no fallback if either service fails."""
    name = "jlcpcb-official-via-zetaris"
    bom_supplier = "jlcpcb"

    def __init__(self, base: JLCCatalog, client) -> None:
        self.base, self.client = base, client
        self.provenance = {**base.provenance, "name": self.name, "zetaris_mode": "read-only relation"}

    def with_recorder(self, recorder: RunRecorder) -> JLCZetarisCatalog:
        from .zetaris import ZetarisClient

        return JLCZetarisCatalog(self.base.with_recorder(recorder), ZetarisClient(
            self.client.cfg, self.client.timeout, recorder=recorder))

    def prepare(self, codes: list[str]) -> None:
        self.base.prepare(codes)

    def _relation(self):
        from .zetaris import ZetarisInlineCatalog

        # Each query is bounded even after many explicit lookups in a long-lived session.
        return ZetarisInlineCatalog(self.client, list(self.base.rows.values())[-MAX_CODES:])

    def get(self, key: str) -> PartRecord | None:
        part = self.base.get(key)
        if part is None:
            return None
        # Ensure an explicitly requested older row remains in this bounded relation.
        rows = [r for r in self.base.rows.values() if r["supplier_pn"] != part.supplier_pn][-(MAX_CODES - 1):]
        from .zetaris import ZetarisInlineCatalog
        return ZetarisInlineCatalog(self.client, rows + [self.base.rows[part.supplier_pn]]).get(key)

    def find_mpn(self, mpn: str) -> list[PartRecord]:
        return self._relation().find_mpn(mpn) if self.base.rows else []

    def search(self, category: str, package: str | None = None, text: str | None = None,
               limit: int = 20) -> list[PartRecord]:
        return self._relation().search(category, package, text, limit) if self.base.rows else []

    def discover_for(self, original: PartRecord, category: str, package: str | None,
                     text: str | None, limit: int) -> list[PartRecord]:
        return [part for candidate in self.base.discover_for(original, category, package, text, limit)
                if (part := self.get(candidate.key)) is not None]
