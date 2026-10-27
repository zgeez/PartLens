import json

import pytest

from partlens.sources.review import ReviewedCatalog


def review_file(tmp_path, manufacturer="TEST manufacturer", rating="recommended_operating"):
    path = tmp_path / "TEST-review.json"
    path.write_text(json.dumps([{"part_key": "fixture:TEST-LDO-A", "mpn": "TESTLDO-33-A",
        "manufacturer": manufacturer, "reviewed_at": "2026-10-22T00:00:00Z",
        "params": {"supply_voltage_max": {"value": "6V", "rating_kind": rating,
            "evidence": {"kind": "datasheet", "locator": "https://manufacturer.test/TEST.pdf#page=4"}}},
        "notes": ["TEST review"]}]))
    return path


def test_review_cannot_transfer_limits_between_manufacturers(catalog, tmp_path):
    reviewed = ReviewedCatalog(catalog, review_file(tmp_path, "TEST-other-manufacturer"))
    with pytest.raises(ValueError, match="manufacturer/MPN"):
        reviewed.get("fixture:TEST-LDO-A")


def test_absolute_rating_cannot_be_loaded_as_recommended(catalog, tmp_path):
    original = catalog.get("fixture:TEST-LDO-A")
    reviewed = ReviewedCatalog(catalog, review_file(tmp_path, original.manufacturer, "absolute_maximum"))
    with pytest.raises(ValueError, match="recommended_operating"):
        reviewed.get(original.key)


def test_review_preserves_original_supplier_record(catalog, tmp_path):
    original = catalog.get("fixture:TEST-LDO-A")
    reviewed = ReviewedCatalog(catalog, review_file(tmp_path, original.manufacturer)).get(original.key)
    assert reviewed.params["supply_voltage_max"].evidence.kind.value == "datasheet"
    assert reviewed.params["supply_voltage_max"].rating_kind == "recommended_operating"
    assert reviewed.engineering_notes == ("TEST review",)
    assert catalog.get(original.key) == original
    assert reviewed.retrieved_at == original.retrieved_at  # datasheet review cannot refresh supplier stock
