"""Engineering value parsing with exact decimal results.

Values are returned in base SI units (ohm, farad, henry, volt, ampere, watt, hertz) as ``Decimal`` so that
comparisons and cost arithmetic stay exact and reproducible.
"""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

PREFIX = {
    "p": Decimal("1e-12"),
    "n": Decimal("1e-9"),
    "u": Decimal("1e-6"),
    "µ": Decimal("1e-6"),
    "μ": Decimal("1e-6"),
    "m": Decimal("1e-3"),
    "": Decimal(1),
    "k": Decimal("1e3"),
    "K": Decimal("1e3"),
    "M": Decimal("1e6"),
    "G": Decimal("1e9"),
}

UNIT_ALIASES = {
    "ohm": "ohm", "ohms": "ohm", "Ω": "ohm", "r": "ohm", "R": "ohm",
    "f": "F", "F": "F",
    "h": "H", "H": "H",
    "v": "V", "V": "V",
    "a": "A", "A": "A",
    "w": "W", "W": "W",
    "hz": "Hz", "Hz": "Hz", "HZ": "Hz",
}

_VALUE = re.compile(
    r"^\s*(?P<num>[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?)\s*(?P<prefix>[pnuµμmkKMG]?)\s*(?P<unit>ohms?|Ω|[rRfFhHvVaAwW]|hz|Hz|HZ)?\s*$"
)
# RKM code: 4k7, 4R7, 2M2, 0R1
_RKM = re.compile(r"^\s*(?P<a>[0-9]+)(?P<sep>[pnuµμmkKMGRr])(?P<b>[0-9]+)\s*(?P<unit>ohms?|Ω|[fFhH])?\s*$")
_FRACTION = re.compile(r"^\s*(?P<n>[0-9]+)\s*/\s*(?P<d>[0-9]+)\s*(?P<unit>[wW])\s*$")


class UnitError(ValueError):
    pass


def parse_value(text: str, expected_unit: str | None = None) -> tuple[Decimal, str | None]:
    """Parse ``10k``, ``4k7``, ``100nF``, ``16V``, ``1/10W``, ``0.1 uF`` into (base value, unit).

    ``expected_unit`` (one of ohm, F, H, V, A, W, Hz) is used when the text carries no unit, and a
    conflicting explicit unit raises ``UnitError``.
    """
    s = str(text).strip()
    if not s:
        raise UnitError("empty value")

    m = _FRACTION.match(s)
    if m:
        return _check(Decimal(m["n"]) / Decimal(m["d"]), "W", expected_unit, s)

    m = _RKM.match(s)
    if m:
        sep = m["sep"]
        mult = Decimal(1) if sep in "Rr" else PREFIX[sep]
        unit = UNIT_ALIASES.get(m["unit"] or "", None)
        if sep in "Rr":
            unit = unit or "ohm"
        num = Decimal(f"{m['a']}.{m['b']}")
        return _check(num * mult, unit, expected_unit, s)

    m = _VALUE.match(s)
    if not m:
        raise UnitError(f"cannot parse value {s!r}")
    try:
        num = Decimal(m["num"])
    except InvalidOperation as e:  # pragma: no cover - regex guarantees a number
        raise UnitError(str(e)) from e
    prefix = m["prefix"] or ""
    unit_text = m["unit"]
    # "m" with no unit after it is milli; "M" is mega. A bare "F"/"H" after a prefix is a unit.
    unit = UNIT_ALIASES.get(unit_text, None) if unit_text else None
    return _check(num * PREFIX[prefix], unit, expected_unit, s)


def _check(value: Decimal, unit: str | None, expected: str | None, text: str) -> tuple[Decimal, str | None]:
    if expected and unit and unit != expected:
        raise UnitError(f"{text!r}: expected unit {expected}, got {unit}")
    return value.normalize(), unit or expected


def parse_percent(text: str) -> Decimal:
    """``±1%``, ``1 %``, ``0.5%`` -> Decimal('1'), Decimal('0.5') (percent points)."""
    s = str(text).strip().lstrip("±+").rstrip("%").strip()
    try:
        return Decimal(s).normalize()
    except InvalidOperation as e:
        raise UnitError(f"cannot parse percentage {text!r}") from e


def format_value(value: Decimal, unit: str | None) -> str:
    """Human-readable engineering form, e.g. Decimal('1e-7'), 'F' -> '100nF'."""
    if not value.is_finite():
        return str(value) + _unit_symbol(unit)
    if unit == "%":
        return f"{_trim(value)}%"
    if value == 0:
        return f"0{_unit_symbol(unit)}"
    for p, mult in (("G", "1e9"), ("M", "1e6"), ("k", "1e3"), ("", "1"), ("m", "1e-3"), ("u", "1e-6"),
                    ("n", "1e-9"), ("p", "1e-12")):
        scaled = value / Decimal(mult)
        if abs(scaled) >= 1:
            return f"{_trim(scaled)}{p}{_unit_symbol(unit)}"
    return f"{_trim(value / Decimal('1e-12'))}p{_unit_symbol(unit)}"


def _trim(d: Decimal) -> str:
    s = format(d.normalize(), "f")
    return s.rstrip("0").rstrip(".") if "." in s else s


def _unit_symbol(unit: str | None) -> str:
    return {"ohm": "Ω", None: ""}.get(unit, unit)
