from decimal import Decimal

import pytest

from partlens.core.bom import import_bom_csv, package_from_footprint, split_refs
from partlens.core.units import UnitError, format_value, parse_percent, parse_value


@pytest.mark.parametrize("text,unit,value", [
    ("10k", "ohm", Decimal("10000")),
    ("4k7", "ohm", Decimal("4700")),
    ("4R7", "ohm", Decimal("4.7")),
    ("100nF", "F", Decimal("1E-7")),
    ("0.1 uF", "F", Decimal("1E-7")),
    ("4.7µF", "F", Decimal("0.0000047")),
    ("16V", "V", Decimal("16")),
    ("6.3V", "V", Decimal("6.3")),
    ("1/16W", "W", Decimal("0.0625")),
    ("2.2mH", "H", Decimal("0.0022")),
])
def test_parse_value(text, unit, value):
    v, u = parse_value(text, unit)
    assert v == value and u == unit


def test_parse_value_rejects_wrong_unit():
    with pytest.raises(UnitError):
        parse_value("16V", "F")


def test_percent_and_format():
    assert parse_percent("±1%") == Decimal("1")
    assert format_value(Decimal("1E-7"), "F") == "100nF"
    assert format_value(Decimal("4700"), "ohm") == "4.7kΩ"


def test_refs_and_packages():
    assert split_refs("R1-R3, R7") == ("R1", "R2", "R3", "R7")
    assert package_from_footprint("Capacitor_SMD:C_0402_1005Metric") == "0402"
    assert package_from_footprint("Package_TO_SOT_SMD:SOT-23-5") is None


def test_import_kicad_bom(bom):
    assert [ln.id for ln in bom.lines] == ["L1", "L2", "L3", "L4", "L5"]
    l1 = bom.line("L1")
    assert l1.refs == ("C1", "C2", "C3", "C4") and l1.qty_per_board == 4
    assert l1.category == "capacitor" and l1.package == "0402"
    assert l1.mpn == "TESTCAP-0402-104-X7R-16"
    assert bom.line("L4").issues == ("no MPN or supplier part number",)
    assert bom.line("L5").dnp and len(bom.placed_lines) == 4
    assert l1.evidence.locator.endswith("#row2")


def test_import_jlc_style_bom_with_lcsc():
    text = "Comment,Designator,Footprint,LCSC Part #\n100nF,\"C1,C2\",0402,c1525\n10k,R1,0402,BAD\n"
    b = import_bom_csv(text=text, name="jlc")
    assert b.lines[0].supplier_pn == "C1525" and b.lines[0].qty_per_board == 2
    assert any("not a valid LCSC" in i for i in b.lines[1].issues)


def test_quantity_mismatch_is_reported():
    b = import_bom_csv(text="Reference,Value,Qty\n\"R1,R2\",10k,3\n")
    assert any("differs from reference count" in i for i in b.lines[0].issues)
