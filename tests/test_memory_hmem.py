"""Decision memory on the real Meterless H-MEM reference engine (Node bridge process, no mocks)."""

import pytest

from partlens.checks.compat import check_substitute
from partlens.memory.hmem import DecisionMemory, HMemBridge, HMemError


@pytest.fixture
def bridge_factory(tmp_path):
    opened = []

    def make():
        try:
            b = HMemBridge(tmp_path / "hmem")
        except HMemError as e:
            pytest.skip(f"H-MEM bridge unavailable: {e}")
        opened.append(b)
        return b

    yield make
    for b in opened:
        b.close()


def test_rejected_decision_persists_and_is_recalled_with_provenance(bridge_factory, catalog, bom):
    orig = catalog.get("fixture:TEST-C100N-X7R-16V")
    cand = catalog.get("fixture:TEST-C100N-Y5V-16V")
    decision = check_substitute(bom.line("L1"), orig, cand)
    assert decision.status.value == "rejected"

    b1 = bridge_factory()
    assert b1.info["engine"] == "meterless-hmem-reference"
    rec = DecisionMemory(b1, "demo-board").remember(decision, run_id="run-test-1")
    assert rec["source"] == f"partlens:run:run-test-1:decision:{decision.id}"
    b1.close()

    # New process, same store: the decision survives.
    b2 = bridge_factory()
    mem = DecisionMemory(b2, "demo-board")
    recalled = mem.recall(orig.key, cand.key)
    assert len(recalled) == 1
    r = recalled[0]
    assert r.status == "rejected" and r.decision_id == decision.id
    assert r.source.startswith("partlens:run:run-test-1")
    assert DecisionMemory(b2, "TEST-different-design").recall(orig.key, cand.key) == []
    assert DecisionMemory(b2, "TEST-different-design").search(cand.key) == []
    assert mem.recall(orig.key, cand.key, line_id="TEST-other-line") == []
    assert len(mem.recall(orig.key, cand.key, line_id=bom.line("L1").id)) == 1
    found = mem.search(cand.key)
    assert any(m["original"] == orig.key and m["candidate"] == cand.key and m["line"] == "L1" for m in found)
    exact = mem.search("TEST arbitrary query words", run_id="run-test-1")
    assert len(exact) == 1 and exact[0]["source"] == rec["source"]
    assert exact[0]["retrieval"] == "exact_design_and_run_source" and exact[0]["relevance"] is None
    assert mem.search(cand.key, run_id="TEST-wrong-run") == []
    assert DecisionMemory(b2, "TEST-different-design").search(cand.key, run_id="run-test-1") == []
    failed = [c for c in r.details["checks"] if c["status"] == "fail"]
    assert {c["check"] for c in failed} >= {"req.dielectric"}
    assert any(e["kind"] == "supplier_record" for c in failed for e in c["evidence"])

    # The engine's append-only ledger shows the write and the recall read.
    actions = [e["action"] for e in mem.history(r.memory_id)]
    assert actions[0] == "create" and "read" in actions

    # Unrelated pair: nothing recalled.
    assert mem.recall(orig.key, "fixture:TEST-C100N-X5R-25V") == []


def test_hmem_rejects_memory_without_source(bridge_factory):
    b = bridge_factory()
    with pytest.raises(HMemError, match="no source"):
        b.call("add", content="x", source="")


def test_bridge_launch_suppresses_extra_windows(bridge_factory, monkeypatch):
    from partlens.memory import hmem
    original = hmem.subprocess.Popen
    flags = []
    def launch(*args, **kwargs):
        flags.append(kwargs.get("creationflags"))
        return original(*args, **kwargs)
    monkeypatch.setattr(hmem.subprocess, "Popen", launch)
    bridge_factory()
    assert flags == [hmem.subprocess.CREATE_NO_WINDOW if hmem.os.name == "nt" else 0]
