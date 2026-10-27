"""Synthetic protocol responses only. C900000001 is a fictitious API identifier; MPNs are TEST-prefixed.

These tests prove adapter behaviour, never operational supplier success.
"""

import base64
import hashlib
import hmac
import json
from dataclasses import replace
from io import BytesIO
from decimal import Decimal
from urllib.error import HTTPError, URLError

import pytest

from partlens.checks.compat import check_availability, check_substitute
from partlens.core.model import DecisionStatus, utc_now
from partlens.optimise.cost import AssemblyFees, line_cost
from partlens.records import RunRecorder, read_events
from partlens.session import Session, part_view
from partlens.sources.catalog import LocalCatalog, record_from_row
from partlens.sources.jlcpcb import (
    DETAIL_PATH, ORIGIN, JLCCatalog, JLCClient, JLCConfig, JLCError, JLCZetarisCatalog, Lookup,
    _NoRedirect, authorization, quantity_price_observation, row_from_detail,
)
from partlens.sources.zetaris import ZetarisClient, ZetarisConfig, ZetarisInlineCatalog

CODE = "C900000001"
CFG = JLCConfig("TEST-app", "TEST-access", "TEST-secret", "TEST-name")


def component():
    return {"componentCode": CODE, "componentModel": "TEST-CAP-100N", "componentBrandEn": "TEST-Mfr",
            "componentSpecification": "0402", "firstTypeName": "Capacitors", "libraryType": "base",
            "stockCount": 100, "solderJointCount": 2, "assemblyComponentFlag": False,
            "datasheetUrl": "TEST-file-id", "priceRanges": [
                {"startQuantity": 1, "endQuantity": 9, "unitPrice": "0.1234"},
                {"startQuantity": 10, "endQuantity": -1, "unitPrice": "0.1000"}],
            "parameters": [{"parameterName": k, "parameterValue": v} for k, v in (
                ("Capacitance", "100nF"), ("Voltage Rating", "25V"),
                ("Temperature Coefficient", "X7R"), ("Tolerance", "10%"))]}


def observation(raw=None):
    return Lookup((raw or component(),), utc_now(), "TEST-client", "TEST-trace", 200, "TEST-digest")


def part(raw=None):
    raw = raw or component()
    return record_from_row(row_from_detail(raw, observation(raw)))


class Response:
    status = 200
    headers = {"J-Trace-ID": "TEST-trace"}

    def __init__(self, payload=None):
        self.raw = json.dumps(payload if payload is not None else {
            "code": 200, "success": True, "data": [component()]}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self, n):
        return self.raw[:n]


def test_signature_exact_bytes_trailing_newline_and_optional_app_name():
    body = b'{"componentCodes":["C900000001"]}'
    nonce = "N" * 32
    expected_message = b'POST\n/overseas/openapi/component/getComponentDetailByCode\n1234\n' + nonce.encode() + b'\n' + body + b'\n'
    expected = base64.b64encode(hmac.new(b"TEST-secret", expected_message, hashlib.sha256).digest()).decode()
    header = authorization(CFG, body, 1234, nonce)
    assert f'signature="{expected}"' in header
    assert header == authorization(replace(CFG, app_name="TEST-other"), body, 1234, nonce)
    assert "TEST-name" not in header and "TEST-secret" not in repr(CFG)


def test_exact_endpoint_headers_timeout_and_no_auth_in_audit(tmp_path):
    seen = []
    rec = RunRecorder.create(tmp_path / "runs")
    def transport(req, **kwargs):
        seen.append((req, kwargs))
        return Response()
    client = JLCClient(CFG, cache_dir=tmp_path / "cache", recorder=rec, transport=transport)
    result = client.lookup([CODE])
    req, opts = seen[0]
    assert req.full_url == ORIGIN + DETAIL_PATH and req.method == "POST"
    assert req.data == b'{"componentCodes":["C900000001"]}' and opts["timeout"] == 20
    assert req.get_header("Authorization").startswith('JOP appid="TEST-app"')
    assert result.http_status == 200 and result.trace_id == "TEST-trace" and not result.cached
    text = rec.path.read_text()
    assert "TEST-access" not in text and "TEST-secret" not in text and "signature=" not in text


@pytest.mark.parametrize("payload", [
    {"code": 200, "data": []}, {"code": 1001, "success": True, "data": []},
    {"code": 200, "success": False, "data": []},
    {"code": 200, "success": True, "successful": False, "data": []},
    {"code": 200, "success": "true", "data": []},
    {"code": 200, "success": True, "data": {}},
    {"code": 200, "success": True, "data": [component(), component()]},
    {"code": 200, "success": True, "data": [{"componentCode": "C900000002"}]},
])
def test_business_or_schema_failure_is_not_success(payload, tmp_path):
    client = JLCClient(CFG, cache_dir=tmp_path, transport=lambda *a, **k: Response(payload))
    with pytest.raises(JLCError):
        client.lookup([CODE])
    assert not list(tmp_path.glob("*.json"))


@pytest.mark.parametrize("field", ["success", "successful"])
def test_documented_and_observed_envelopes_and_missing_components(field, tmp_path):
    result = JLCClient(CFG, cache_dir=tmp_path, transport=lambda *a, **k: Response({
        "code": 200, field: True, "data": []})).lookup([CODE])
    assert result.data == ()


@pytest.mark.parametrize("codes", [[], ["https://TEST"], ["C1?x=2"], ["lcsc:C1"], [1], ["C1"] * 26])
def test_rejects_invalid_or_bulk_requests_before_network(codes, tmp_path):
    def forbidden(*args, **kwargs):
        pytest.fail("network must not be called")
    with pytest.raises(JLCError):
        JLCClient(CFG, cache_dir=tmp_path, transport=forbidden).lookup(codes)


def test_cache_reuses_original_timestamp_trace_and_validates_digest(tmp_path):
    calls = []
    def transport(*args, **kwargs):
        calls.append(1)
        return Response()
    rec = RunRecorder.create(tmp_path / "runs")
    client = JLCClient(CFG, cache_dir=tmp_path / "cache", recorder=rec, transport=transport)
    first = client.lookup([CODE])
    cached = client.lookup([CODE, CODE])
    assert len(calls) == 1 and cached.cached and cached.retrieved_at == first.retrieved_at
    file = next((tmp_path / "cache").glob("*.json"))
    entry = json.loads(file.read_text()); entry["response_digest"] = "TEST-corrupt"
    file.write_text(json.dumps(entry))
    assert not client.lookup([CODE]).cached and len(calls) == 2
    assert len(list((tmp_path / "cache").glob("*.json"))) == 2  # append, never replace
    assert any(e["type"] == "jlcpcb_cache_hit" for e in read_events(rec.path))


def test_cache_bypass_and_expiration(tmp_path):
    calls = []
    def transport(*a, **k):
        calls.append(1); return Response()
    client = JLCClient(CFG, cache_dir=tmp_path, transport=transport)
    client.lookup([CODE]); client.lookup([CODE], refresh=True)
    assert len(calls) == 2
    for file in tmp_path.glob("*.json"):
        entry = json.loads(file.read_text()); entry["retrieved_at"] = "2000-01-01T00:00:00+00:00"
        file.write_text(json.dumps(entry))
    client.lookup([CODE])
    assert len(calls) == 3


@pytest.mark.parametrize("status", [429, 500, 502, 503, 504])
def test_retry_transient_status_and_retry_after(status, tmp_path):
    calls, sleeps = [], []
    def transport(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise HTTPError(ORIGIN, status, "TEST", {"Retry-After": "0"}, BytesIO(b"TEST-SECRET"))
        return Response()
    assert JLCClient(CFG, cache_dir=tmp_path, transport=transport, sleep=sleeps.append).lookup([CODE]).data
    assert len(calls) == 2 and sleeps == [0]


@pytest.mark.parametrize("status", [301, 302, 400, 401, 403, 404])
def test_no_retry_auth_redirect_or_parameter_error(status, tmp_path):
    calls = []
    def transport(*a, **k):
        calls.append(1); raise HTTPError(ORIGIN, status, "TEST-SECRET", {}, BytesIO(b"TEST-SECRET"))
    rec = RunRecorder.create(tmp_path / "runs")
    with pytest.raises(JLCError):
        JLCClient(CFG, cache_dir=tmp_path / "cache", recorder=rec, transport=transport).lookup([CODE])
    assert len(calls) == 1 and "TEST-SECRET" not in rec.path.read_text()
    assert _NoRedirect().redirect_request(None, None, 302, None, None, "https://TEST.example") is None


def test_retry_budget_and_long_rate_limit_stop(tmp_path):
    calls, sleeps = [], []
    def transport(*a, **k):
        calls.append(1); raise URLError("TEST-network")
    with pytest.raises(JLCError):
        JLCClient(CFG, cache_dir=tmp_path, transport=transport, sleep=sleeps.append).lookup([CODE])
    assert len(calls) == 3 and len(sleeps) == 2
    def limited(*a, **k):
        raise HTTPError(ORIGIN, 429, "TEST", {"Retry-After": "120"}, BytesIO())
    with pytest.raises(JLCError, match="retry later"):
        JLCClient(CFG, cache_dir=tmp_path, transport=limited, sleep=lambda _: pytest.fail("must not sleep")).lookup([CODE])


def test_exact_prices_bounds_and_unknown_currency_procurement_not_assumed(bom):
    p = part()
    assert p.params["capacitance"].value == Decimal("100e-9")
    assert p.price_at(9).unit_price == Decimal("0.1234") and p.price_at(10).unit_price == Decimal("0.1000")
    assert not p.price_at(9).currency
    obs = quantity_price_observation(p, 11)
    assert obs["nominal_amount"] == "1.1000" and obs["currency"] is None and not obs["complete"]
    cost = line_cost(bom.placed_lines[0], p, 1, AssemblyFees())
    assert cost.extended is None and cost.ordered is None and "unknown supplier terms" in cost.problem
    view = part_view(p)
    assert view["moq"] is None and view["order_multiple"] is None
    checks = {c.check: c.status.value for c in check_availability(p, 11)}
    assert checks["supply.price"] == checks["supply.stock"] == "unverified"
    assert next(c.status.value for c in check_availability(replace(p, stock=0), 11) if c.check == "supply.stock") == "fail"


def test_price_gap_and_overlap_never_extrapolated():
    raw = component(); raw["priceRanges"][1]["startQuantity"] = 20
    assert part(raw).price_at(10) is None
    raw["priceRanges"][1]["startQuantity"] = 9
    with pytest.raises(JLCError, match="overlapping"):
        row_from_detail(raw, observation(raw))


def test_temperature_formatting_preserves_semantics_and_actual_source_words():
    raw = component()
    raw["parameters"].append({"parameterName": "Operating Temperature", "parameterValue": "-55\u2103~+125\u2103"})
    p = part(raw)
    assert p.params["temp_range"].value == "-55~125"
    assert p.params["temp_range"].evidence.excerpt == "Operating Temperature: -55\u2103~+125\u2103"


@pytest.mark.parametrize("field,value", [("startQuantity", 0), ("startQuantity", 1.5),
                                        ("endQuantity", 0), ("unitPrice", "NaN"), ("unitPrice", "-1")])
def test_bad_price_ranges_fail_closed(field, value):
    raw = component(); raw["priceRanges"][0][field] = value
    with pytest.raises((JLCError, ValueError)):
        row_from_detail(raw, observation(raw))


def test_opaque_voltage_missing_specs_and_conflicts_never_qualify(bom):
    raw = component()
    raw["parameters"] += [{"parameterName": "Voltage - Supply", "parameterValue": "8V"},
                          {"parameterName": "Absolute Maximum Input Voltage", "parameterValue": "9V"},
                          {"parameterName": "Voltage Rating", "parameterValue": "6.3V"}]
    p = part(raw)
    assert not {"voltage_rating", "supply_voltage_max", "input_voltage_absolute_max"} & p.params.keys()
    assert p.supplier_metadata["conflicting_parameters"] == ["voltage_rating"]
    assert check_substitute(bom.placed_lines[0], part(), p).status is DecisionStatus.UNVERIFIED
    assert check_substitute(bom.placed_lines[0], part(), replace(part(), manufacturer="")).status is DecisionStatus.UNVERIFIED
    assert check_substitute(bom.placed_lines[0], part(), replace(part(), params={})).status is DecisionStatus.UNVERIFIED


def test_engineering_pass_fail_and_application_scope(bom):
    original, candidate = part(), part()
    assert check_substitute(bom.placed_lines[0], original, candidate).status is DecisionStatus.VERIFIED
    raw = component(); raw["parameters"][1]["parameterValue"] = "6.3V"
    assert check_substitute(bom.placed_lines[0], original, part(raw)).status is DecisionStatus.REJECTED
    assert all(p.evidence.kind.value == "supplier_record" for p in candidate.params.values())
    assert candidate.datasheet_url is None  # file ID cannot become an invented URL or manufacturer evidence


@pytest.mark.parametrize("library,classification", [("base", "basic"), ("expand", "extended"), ("TEST-new", None)])
def test_assembly_classification_does_not_imply_eligibility(library, classification):
    raw = component(); raw["libraryType"] = library
    p = part(raw)
    assert p.assembly_class == classification
    assert p.supplier_metadata["assembly_eligible"] is None
    assert p.supplier_metadata["assembly_component_flag"] is False
    assert "assembly eligibility" in p.commercial_unknowns


def test_flat_snapshot_round_trip_preserves_params_classification_bounds(tmp_path):
    row = row_from_detail(component(), observation())
    path = tmp_path / "TEST-snapshot.json"; path.write_text(json.dumps([row]))
    cat = LocalCatalog.from_json(path)
    p = cat.get("jlcpcb:" + CODE)
    assert cat.bom_supplier == "jlcpcb" and p.assembly_class_evidence.locator.startswith(ORIGIN)
    assert p.price_breaks[0].max_qty == 9 and p.supplier_metadata["server_trace_id"] == "TEST-trace"
    assert p.commercial_unknowns


def test_catalog_prepares_once_search_is_local_and_recorders_are_isolated(tmp_path):
    calls = []
    def transport(*a, **k):
        calls.append(1); return Response()
    catalog = JLCCatalog(JLCClient(CFG, cache_dir=tmp_path / "cache", transport=transport))
    one, two = RunRecorder.create(tmp_path / "runs"), RunRecorder.create(tmp_path / "runs")
    a, b = catalog.with_recorder(one), catalog.with_recorder(two)
    a.prepare([CODE]); a.get("jlcpcb:" + CODE); a.search("capacitor"); a.find_mpn("TEST-CAP-100N")
    assert len(calls) == 1 and not b.rows
    b.prepare([CODE]); assert len(calls) == 1
    assert all(e["run"] == one.run_id for e in read_events(one.path))
    assert all(e["run"] == two.run_id for e in read_events(two.path))
    assert a.get("lcsc:" + CODE) is None


def test_zetaris_relation_is_read_only_and_preserves_official_provenance(tmp_path, monkeypatch):
    row = row_from_detail(component(), observation())
    row["description"] = "TEST ' quote \\ backslash ; DROP TABLE TEST"
    captured = []
    cfg = ZetarisConfig("http://localhost:3000", "1", "TEST-KEY")
    client = ZetarisClient(cfg)
    def query(sql, limit=1000):
        captured.append(sql)
        flat = {k: json.dumps(v) if isinstance(v, (dict, list)) else v for k, v in row.items()}
        from partlens.sources.zetaris import QueryRecord
        return [flat], QueryRecord("TEST-query", sql, utc_now(), 1, "zetaris:TEST-query")
    monkeypatch.setattr(client, "query", query)
    cat = ZetarisInlineCatalog(client, [row])
    p = cat.get("jlcpcb:" + CODE)
    assert captured[0].startswith("WITH partlens_official_components")
    assert "SELECT *" in captured[0] and "DROP TABLE" not in captured[0]
    assert p.source.startswith("zetaris:TEST-query") and ORIGIN in p.source
    assert p.params["voltage_rating"].evidence.locator.startswith(ORIGIN)
    assert p.assembly_class_evidence.locator.startswith(ORIGIN) and p.commercial_unknowns
    assert p.supplier_metadata["server_trace_id"] == "TEST-trace"
    assert p.price_breaks[0].max_qty == 9 and not p.price_breaks[0].currency
    cat.search("capacitor", text="TEST\\'; DROP TABLE TEST; --")
    assert "DROP TABLE" not in captured[-1]


def test_redaction_handles_jop_and_signed_documentation_urls(monkeypatch):
    from partlens.secrets import redact
    monkeypatch.setenv("JLC_ACCESS_KEY", "TEST-access")
    monkeypatch.setenv("JLC_APP_ID", "TEST-app")
    assert "TEST-app" not in redact("identifier TEST-app")
    assert "TEST-access" not in redact(authorization(CFG, b"{}", 1234, "N" * 32))
    safe = redact("https://TEST.example/doc?OSSAccessKeyId=TEST-one&Signature=TEST-two&security-token=TEST-three")
    assert not any(x in safe for x in ("TEST-one", "TEST-two", "TEST-three"))
    assert redact({"accessKey": "TEST-one", "signature": "TEST-two"}) == {
        "accessKey": "[REDACTED]", "signature": "[REDACTED]"}


def test_session_registry_quantity_provenance_and_ui_cost_display(tmp_path):
    from partlens.ui import format_view

    file = tmp_path / "TEST-bom.csv"
    file.write_text('Refs,Value,Footprint,Qty,LCSC\nC1,100nF,C_0402,1,' + CODE + '\n')
    rec = RunRecorder.create(tmp_path / "runs")
    cat = JLCCatalog(JLCClient(CFG, cache_dir=tmp_path / "cache", transport=lambda *a, **k: Response()))
    session = Session(rec, [cat])
    session.import_bom(str(file))
    session.match_parts()
    assert session.baseline["L1"].key == "jlcpcb:" + CODE
    rec.log("user_message", text="1", origin="user", synthetic_test=True)
    session.record_requirement("design", "board_quantity", "==", "1", user_quote="1")
    source = session.design_requirement("board_quantity").provenance.source
    report = session.compare_cost_scenarios(60)
    assert [s["boards"] for s in report["scenarios"]] == [1, 60]
    assert session._boards() == 1 and session.design_requirement("board_quantity").provenance.source == source
    assert not report["scenarios"][0]["baseline"]["component_complete"]
    assert not report["scenarios"][0]["proposed_replacements"]
    assert report["scenarios"][1]["official_nominal_price_observations"][0]["nominal_amount"] == "6.0000"
    shown = format_view("Cost", report)
    assert "not a purchase quote or USD total" in shown and "HYPOTHETICAL" in shown
    current = session.estimate_cost()
    assert current["official_nominal_price_observations"][0]["currency"] is None
    assert "not a purchase quote or USD total" in format_view("Cost", current)
    assert session.check_availability("jlcpcb:" + CODE, "L1")["ordered"] is None


def test_cli_registry_official_and_zetaris_combination(monkeypatch, tmp_path):
    from argparse import Namespace
    from partlens.cli import catalogs_from_args

    for key, value in {"JLC_APP_ID": "TEST-app", "JLC_ACCESS_KEY": "TEST-access", "JLC_SECRET_KEY": "TEST-secret",
                       "ZETARIS_BASE_URL": "http://localhost:3000", "ZETARIS_ORG_ID": "1",
                       "ZETARIS_API_KEY": "TEST-key", "PARTLENS_ZETARIS_PARTS_TABLE": "TEST.parts"}.items():
        monkeypatch.setenv(key, value)
    args = Namespace(jlc=True, zetaris=False, catalog=[], evidence=[])
    assert isinstance(catalogs_from_args(args)[0], JLCCatalog)
    args.zetaris = True
    assert isinstance(catalogs_from_args(args)[0], JLCZetarisCatalog)
    monkeypatch.delenv("JLC_SECRET_KEY")
    with pytest.raises(SystemExit, match="JLC_SECRET_KEY"):
        catalogs_from_args(args)
