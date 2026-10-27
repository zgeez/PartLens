"""Synthetic transport fixtures; operational sponsor success requires a separate real query."""

import json
from io import BytesIO
from types import SimpleNamespace
from urllib.error import HTTPError

import pytest

from partlens.records import RunRecorder, read_events
from partlens.sources import zetaris


class Response:
    status = 200
    headers = {"X-Request-ID": "TEST-server-request"}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def read(self):
        return json.dumps({"queryId": "TEST-query", "status": "succeeded",
                           "rows": [{"supplier": "fixture", "supplier_pn": "TEST-part"}]}).encode()


def test_query_records_server_evidence_and_result_ids(tmp_path, monkeypatch):
    monkeypatch.setattr(zetaris, "urlopen", lambda *args, **kw: Response())
    rec = RunRecorder.create(tmp_path)
    client = zetaris.ZetarisClient(zetaris.ZetarisConfig("https://zetaris.test", "1", "TEST-key"), recorder=rec)
    rows, query = client.query("SELECT * FROM TEST_parts LIMIT 5", 5)
    assert query.status == "succeeded" and query.http_status == 200
    assert query.server_query_id == "TEST-query" and query.server_request_id == "TEST-server-request"
    assert query.result_identifiers == ("fixture:TEST-part",) and query.response_digest
    assert read_events(rec.path)[-1]["type"] == "zetaris_query"
    assert "TEST-key" not in rec.path.read_text()


def test_failure_is_preserved_without_echoing_credentials(tmp_path, monkeypatch):
    def fail(*args, **kwargs):
        raise HTTPError("https://zetaris.test", 401, "TEST", {}, BytesIO(b"TEST-secret"))

    monkeypatch.setattr(zetaris, "urlopen", fail)
    rec = RunRecorder.create(tmp_path)
    client = zetaris.ZetarisClient(zetaris.ZetarisConfig("https://zetaris.test", "1", "TEST-secret"), recorder=rec)
    with pytest.raises(zetaris.ZetarisError):
        client.query("SELECT * FROM TEST_parts")
    assert client.log[-1].status == "failed" and client.log[-1].http_status == 401
    assert "TEST-secret" not in rec.path.read_text()


@pytest.mark.parametrize("payload", [
    {"status": "failed", "rows": []}, {"success": False, "data": []}, {"errors": ["TEST"], "data": []},
    {"columns": ["a", "b"], "rows": [[1]]}, {"data": {"error": "TEST"}},
    {"headers": ["a", "a"], "data": [[1, 2]]}, {"headers": [{"type": "string"}], "data": [[1]]},
])
def test_error_and_malformed_rows_never_become_success(payload):
    with pytest.raises(zetaris.ZetarisError):
        zetaris.rows_from_payload(payload)


def test_column_row_response():
    assert zetaris.rows_from_payload({"columns": [{"name": "mpn"}], "data": [["TEST-part"]]}) == [
        {"mpn": "TEST-part"}]


def test_gateway_header_response():
    assert zetaris.rows_from_payload({"headers": ["supplier", "supplier_pn"],
                                     "data": [["fixture", "TEST-part"]], "total": 1, "timeUsed": 39}) == [
        {"supplier": "fixture", "supplier_pn": "TEST-part"}]


def test_gateway_query_records_timing_without_inventing_server_ids(tmp_path, monkeypatch):
    response = Response()
    response.headers = {}
    response.read = lambda: json.dumps({"headers": ["supplier", "supplier_pn"],
                                       "data": [["fixture", "TEST-part"]], "timeUsed": 39}).encode()
    monkeypatch.setattr(zetaris, "urlopen", lambda *a, **kw: response)
    rec = RunRecorder.create(tmp_path)
    client = zetaris.ZetarisClient(zetaris.ZetarisConfig("https://zetaris.test", "1", "TEST-key"), recorder=rec)
    rows, query = client.query("SELECT * FROM TEST_parts")
    assert query.server_elapsed_ms == 39 and query.response_digest
    assert query.server_query_id is None and query.server_request_id is None
    assert query.result_identifiers == ("fixture:TEST-part",)


def test_invalid_gateway_configuration_is_preserved(tmp_path, monkeypatch):
    from partlens import cli

    monkeypatch.setattr(cli, "STATE", tmp_path)
    monkeypatch.setenv("ZETARIS_BASE_URL", "http://zetaris.test/api/v1.0")
    monkeypatch.setenv("ZETARIS_ORG_ID", "1")
    monkeypatch.setenv("ZETARIS_API_KEY", "TEST-secret")
    with pytest.raises(SystemExit, match="Invalid Zetaris configuration"):
        cli.cmd_smoke_zetaris(SimpleNamespace(sql=None))
    event = read_events(next((tmp_path / "runs").glob("*.jsonl")))[-1]
    assert event["type"] == "integration_blocked" and "origin" in event["reason"]


@pytest.mark.parametrize("reviewed", [False, True])
def test_query_evidence_is_isolated_per_session(tmp_path, monkeypatch, reviewed):
    from partlens.session import Session
    from partlens.sources.review import ReviewedCatalog

    monkeypatch.setattr(zetaris, "urlopen", lambda *a, **kw: Response())
    client = zetaris.ZetarisClient(zetaris.ZetarisConfig("https://zetaris.test", "1", "TEST-key"))
    catalog = zetaris.ZetarisCatalog(client, "TEST_parts")
    if reviewed:
        review = tmp_path / "review.json"
        review.write_text("[]")
        catalog = ReviewedCatalog(catalog, review)
    rec1, rec2 = RunRecorder.create(tmp_path), RunRecorder.create(tmp_path)
    first, second = Session(rec1, [catalog]), Session(rec2, [catalog])
    first.get_part("fixture:TEST-part")
    assert not rec2.path.exists()
    second.get_part("fixture:TEST-part")
    first.get_part("fixture:TEST-part")
    assert sum(e["type"] == "zetaris_query" for e in read_events(rec1.path)) == 2
    assert sum(e["type"] == "zetaris_query" for e in read_events(rec2.path)) == 1
    assert client.recorder is None  # shared source must not redirect later queries to the latest session
