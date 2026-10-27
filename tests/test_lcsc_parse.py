"""LCSC record mapping, on a synthetic record shaped like the product-detail response (no network)."""

from partlens.sources.catalog import record_from_row
from partlens.sources.lcsc import row_from_raw
from partlens.sources.lcsc import CollectionDisabled, fetch_raw, snapshot
import pytest

RAW = {
    "productCode": "C999999", "productModel": "TESTMODEL-104", "brandNameEn": "TestCo",
    "catalogName": "Ceramic Capacitors", "parentCatalogName": "Capacitors", "encapStandard": "0402",
    "productDescEn": "100nF ±10% 16V Ceramic Capacitor X7R 0402", "stockNumber": 1234, "minBuyNumber": 100,
    "split": 100, "productCycle": "normal", "pdfUrl": "https://example.invalid/ds.pdf",
    "productPriceList": [{"ladder": 100, "usdPrice": 0.0038}, {"ladder": 1000, "usdPrice": 0.0029}],
    "paramVOList": [
        {"paramNameEn": "Capacitance", "paramValueEn": "100nF"},
        {"paramNameEn": "Temperature Coefficient", "paramValueEn": "X7R"},
        {"paramNameEn": "Tolerance", "paramValueEn": "±10%"},
        {"paramNameEn": "Voltage Rating", "paramValueEn": "16V"},
        {"paramNameEn": "Operating Temperature", "paramValueEn": "-55℃~+125℃"},
    ],
    "alternatePartList": [{"productCode": "C1"}, {"productCode": "C2"}],
}


def test_lcsc_row_maps_to_part_record():
    row = row_from_raw(RAW, "2026-10-22T00:30:00Z")
    assert row["alternates"] == ["C1", "C2"] and row["lifecycle"] == "active"
    p = record_from_row(row)
    assert p.key == "lcsc:C999999" and p.category == "capacitor" and p.package == "0402"
    assert str(p.params["capacitance"].value) == "1E-7" and p.params["dielectric"].value == "X7R"
    assert p.params["temp_range"].value == "-55~125"
    assert p.params["voltage_rating"].evidence.locator == "https://www.lcsc.com/product-detail/C999999.html#param:Voltage Rating"
    assert p.moq == 100 and p.order_multiple == 100 and p.price_at(700).unit_price == p.price_at(100).unit_price
    assert p.assembly_class is None  # LCSC does not state assembly classes


def test_flat_csv_round_trip(tmp_path):
    import csv

    from partlens.sources.catalog import export_flat_csv

    row = row_from_raw(RAW, "2026-10-22T00:30:00Z")
    export_flat_csv([row], tmp_path / "parts.csv")
    back = next(csv.DictReader((tmp_path / "parts.csv").open(encoding="utf-8")))
    a, b = record_from_row(row), record_from_row(back)
    assert a == b


def test_collection_is_disabled_without_changing_existing_snapshot(tmp_path):
    path = tmp_path / "TEST-snapshot.json"
    path.write_text("TEST original internal fixture")
    with pytest.raises(CollectionDisabled):
        fetch_raw("TEST-no-network")
    with pytest.raises(CollectionDisabled):
        snapshot(["TEST-no-network"], path)
    assert path.read_text() == "TEST original internal fixture"
