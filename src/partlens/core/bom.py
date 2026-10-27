"""BOM import (CSV from KiCad or JLCPCB-style exports) and identity normalisation."""

from __future__ import annotations

import csv
import io
import re
from dataclasses import dataclass, field
from pathlib import Path

from .model import Evidence, EvidenceKind

# Header aliases, compared case-insensitively after stripping spaces, '#', '_' and '-'.
HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "refs": ("reference", "references", "designator", "designators", "refs", "ref", "refdes", "parts"),
    "qty": ("qty", "quantity", "quantityperpcb", "count"),
    "value": ("value", "val", "comment"),
    "footprint": ("footprint", "package", "jlcpcbfootprint"),
    "mpn": ("mpn", "manufacturerpartnumber", "mfrpartnumber", "mfrpn", "partnumber", "mfgpn", "mfrno", "manfpn"),
    "manufacturer": ("manufacturer", "mfr", "mfg", "manufacturername"),
    "lcsc": ("lcsc", "lcscpart", "lcscpartnumber", "lcscpn", "jlcpcbpart", "jlcpcbpartnumber", "supplierpart"),
    "description": ("description", "desc"),
    "dnp": ("dnp", "donotpopulate", "exclude", "excludefrombom", "dnf"),
}

LCSC_RE = re.compile(r"^C\d{1,9}$")
NO_PART_MARKERS = {"-", "n/a", "na", "none"}
NOT_PURCHASED = {"mechanical", "test_point"}  # mounting holes, test pads: features of the PCB, not parts
PACKAGE_RE = re.compile(r"(?<![0-9])(01005|0201|0402|0603|0805|1206|1210|1812|2010|2512)(?![0-9])")
REF_RE = re.compile(r"^([A-Za-z_#]+)(\d+)$")


@dataclass(frozen=True)
class BomLine:
    id: str                         # "L1", "L2", ... in file order
    refs: tuple[str, ...]
    qty_per_board: int
    value: str
    footprint: str
    mpn: str | None
    manufacturer: str | None
    supplier_pn: str | None         # LCSC "C" number when present
    description: str
    dnp: bool
    source_row: int
    evidence: Evidence
    issues: tuple[str, ...] = ()

    @property
    def ref_prefix(self) -> str:
        m = REF_RE.match(self.refs[0]) if self.refs else None
        return m.group(1).upper() if m else ""

    @property
    def package(self) -> str | None:
        return package_from_footprint(self.footprint)

    @property
    def category(self) -> str:
        return CATEGORY_BY_PREFIX.get(self.ref_prefix, "other")


CATEGORY_BY_PREFIX = {
    "R": "resistor", "RN": "resistor_array", "C": "capacitor", "L": "inductor", "FB": "ferrite_bead",
    "D": "diode", "LED": "led", "Q": "transistor", "U": "ic", "IC": "ic", "Y": "crystal", "X": "crystal",
    "J": "connector", "P": "connector", "CN": "connector", "SW": "switch", "F": "fuse", "TP": "test_point",
    "H": "mechanical", "MH": "mechanical", "BT": "battery", "K": "relay",
}


@dataclass
class Bom:
    name: str
    source: str
    lines: list[BomLine] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def line(self, line_id: str) -> BomLine:
        for ln in self.lines:
            if ln.id == line_id:
                return ln
        raise KeyError(line_id)

    @property
    def placed_lines(self) -> list[BomLine]:
        """Lines that are bought and assembled (not DNP, not PCB features such as mounting holes)."""
        return [ln for ln in self.lines if not ln.dnp and ln.category not in NOT_PURCHASED]


def norm_header(h: str) -> str:
    return re.sub(r"[\s#_\-.()/]", "", h.strip().lower())


def map_headers(headers: list[str]) -> dict[str, int]:
    out: dict[str, int] = {}
    normed = [norm_header(h) for h in headers]
    for key, aliases in HEADER_ALIASES.items():
        for i, h in enumerate(normed):
            if h in aliases and key not in out:
                out[key] = i
    return out


def normalise_mpn(mpn: str | None) -> str | None:
    """Canonical MPN for identity comparison: upper case, no whitespace. Packaging suffixes are kept
    (they can change the orderable part), so equality here is conservative."""
    if not mpn:
        return None
    s = re.sub(r"\s+", "", mpn).upper()
    return s or None


def normalise_lcsc(pn: str | None) -> str | None:
    if not pn:
        return None
    s = pn.strip().upper()
    return s if LCSC_RE.match(s) else None


def package_from_footprint(footprint: str) -> str | None:
    """Imperial chip size from a KiCad footprint name or package text, e.g. 'Capacitor_SMD:C_0402_1005Metric'."""
    m = PACKAGE_RE.search(footprint or "")
    return m.group(1) if m else None


def split_refs(text: str) -> tuple[str, ...]:
    parts = [p.strip() for p in re.split(r"[,;\s]+", text or "") if p.strip()]
    out: list[str] = []
    for p in parts:
        m = re.match(r"^([A-Za-z_]+)(\d+)-\1?(\d+)$", p)  # R1-R4 or R1-4
        if m:
            out.extend(f"{m.group(1)}{i}" for i in range(int(m.group(2)), int(m.group(3)) + 1))
        else:
            out.append(p)
    return tuple(out)


def import_bom_csv(path: str | Path | None = None, *, text: str | None = None, name: str | None = None) -> Bom:
    if text is None:
        if path is None:
            raise ValueError("path or text required")
        text = Path(path).read_text(encoding="utf-8-sig")
    source = str(path) if path else "inline"
    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t")
    except csv.Error:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    rows = [r for r in rows if any(c.strip() for c in r)]
    if not rows:
        raise ValueError(f"{source}: empty BOM")

    header_idx = next((i for i, r in enumerate(rows[:10]) if {"refs", "value"} <= map_headers(r).keys()
                       or {"refs", "mpn"} <= map_headers(r).keys()), None)
    if header_idx is None:
        raise ValueError(f"{source}: no header row with reference and value/MPN columns found")
    cols = map_headers(rows[header_idx])
    bom = Bom(name=name or (Path(path).stem if path else "bom"), source=source)

    def get(row: list[str], key: str) -> str:
        i = cols.get(key)
        return row[i].strip() if i is not None and i < len(row) else ""

    for n, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        refs = split_refs(get(row, "refs"))
        if not refs:
            bom.warnings.append(f"row {n}: no reference designators, skipped")
            continue
        issues: list[str] = []
        qty_text = get(row, "qty")
        if qty_text:
            try:
                qty = int(float(qty_text))
            except ValueError:
                qty = len(refs)
                issues.append(f"quantity {qty_text!r} not a number; using reference count {qty}")
            if qty != len(refs):
                issues.append(f"quantity {qty} differs from reference count {len(refs)}")
        else:
            qty = len(refs)
        raw_lcsc = get(row, "lcsc")
        if raw_lcsc.lower() in NO_PART_MARKERS:
            raw_lcsc = ""
        lcsc = normalise_lcsc(raw_lcsc)
        if raw_lcsc and not lcsc:
            issues.append(f"supplier part {raw_lcsc!r} is not a valid LCSC number")
        mpn = normalise_mpn(get(row, "mpn"))
        prefix = REF_RE.match(refs[0])
        unpurchased = prefix is not None and CATEGORY_BY_PREFIX.get(prefix.group(1).upper()) in NOT_PURCHASED
        if not mpn and not lcsc and not unpurchased:
            issues.append("no MPN or supplier part number")
        dnp_text = get(row, "dnp").lower()
        dnp = dnp_text in {"1", "yes", "y", "true", "dnp", "x"}
        line_id = f"L{len(bom.lines) + 1}"
        bom.lines.append(BomLine(
            id=line_id, refs=refs, qty_per_board=qty, value=get(row, "value"), footprint=get(row, "footprint"),
            mpn=mpn, manufacturer=get(row, "manufacturer") or None, supplier_pn=lcsc,
            description=get(row, "description"), dnp=dnp, source_row=n,
            evidence=Evidence(EvidenceKind.BOM, f"{source}#row{n}", "line", ",".join(row)),
            issues=tuple(issues),
        ))
    seen: dict[str, str] = {}
    for ln in bom.lines:
        for r in ln.refs:
            if r in seen:
                bom.warnings.append(f"reference {r} appears on {seen[r]} and {ln.id}")
            seen[r] = ln.id
    return bom


KICAD_FIELDS = "Reference,Value,Footprint,${QUANTITY},${DNP},LCSC,MPN,Manufacturer"
KICAD_LABELS = "Refs,Value,Footprint,Qty,DNP,LCSC,MPN,Manufacturer"


def find_kicad_cli() -> str | None:
    import os
    import shutil

    env = os.environ.get("KICAD_CLI")
    if env:
        return env
    found = shutil.which("kicad-cli")
    if found:
        return found
    for base in (Path("C:/Program Files/KiCad"), Path("/Applications/KiCad/KiCad.app/Contents/MacOS")):
        hits = sorted(base.glob("*/bin/kicad-cli.exe")) + sorted(base.glob("kicad-cli"))
        if hits:
            return str(hits[-1])
    return None


def import_kicad_schematic(sch_path: str | Path, name: str | None = None) -> Bom:
    """Export a grouped BOM from a KiCad schematic with ``kicad-cli`` (read-only) and import it."""
    import subprocess
    import tempfile

    cli = find_kicad_cli()
    if not cli:
        raise RuntimeError("kicad-cli not found; set KICAD_CLI or export the BOM to CSV")
    sch = Path(sch_path)
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "bom.csv"
        proc = subprocess.run(
            [cli, "sch", "export", "bom", "-o", str(out), "--fields", KICAD_FIELDS, "--labels", KICAD_LABELS,
             "--group-by", "Value,Footprint,LCSC", "--ref-range-delimiter", "", str(sch)],
            capture_output=True, text=True, timeout=120,
        )
        if proc.returncode != 0 or not out.exists():
            raise RuntimeError(f"kicad-cli BOM export failed: {proc.stderr.strip() or proc.stdout.strip()}")
        bom = import_bom_csv(text=out.read_text(encoding="utf-8-sig"), name=name or sch.stem)
    # Evidence must point at the schematic, not the temporary export.
    bom.source = str(sch)
    bom.lines = [BomLine(**{**ln.__dict__, "evidence": Evidence(
        EvidenceKind.BOM, f"{sch}#bom-group{ln.source_row - 1}", "line", ln.evidence.value)}) for ln in bom.lines]
    return bom
