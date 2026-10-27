"""Ceramic capacitor temperature characteristics (EIA RS-198 codes).

Class II codes such as X7R encode: low temperature (X/Y/Z), high temperature (4..9) and the maximum
capacitance change over that range (R = +-15 %, S = +-22 %, ...). A candidate dielectric is an acceptable
replacement when its temperature range covers the original's and its capacitance-change band lies within the
original's band. Class I (C0G/NP0) replaces any class II code.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

LOW_TEMP = {"X": -55, "Y": -30, "Z": 10}
HIGH_TEMP = {"2": 45, "4": 65, "5": 85, "6": 105, "7": 125, "8": 150, "9": 200}
# letter -> (max decrease %, max increase %)
CHANGE = {
    "A": ("1.0", "1.0"), "B": ("1.5", "1.5"), "C": ("2.2", "2.2"), "D": ("3.3", "3.3"), "E": ("4.7", "4.7"),
    "F": ("7.5", "7.5"), "P": ("10", "10"), "R": ("15", "15"), "S": ("22", "22"), "T": ("33", "22"),
    "U": ("56", "22"), "V": ("82", "22"),
}
CLASS_I = {"C0G", "NP0", "COG", "NPO"}


@dataclass(frozen=True)
class TempCharacteristic:
    code: str
    low_c: int
    high_c: int
    max_decrease_pct: Decimal
    max_increase_pct: Decimal
    class_i: bool = False


def parse(code: str) -> TempCharacteristic | None:
    c = (code or "").strip().upper()
    if c in CLASS_I:
        # C0G: 0 +- 30 ppm/C over -55..125 C, i.e. < 0.3 % change; treated as stricter than any class II code.
        return TempCharacteristic("C0G", -55, 125, Decimal("0.3"), Decimal("0.3"), class_i=True)
    if len(c) != 3 or c[0] not in LOW_TEMP or c[1] not in HIGH_TEMP or c[2] not in CHANGE:
        return None
    dec, inc = CHANGE[c[2]]
    return TempCharacteristic(c, LOW_TEMP[c[0]], HIGH_TEMP[c[1]], Decimal(dec), Decimal(inc))


def replaces(candidate: str, original: str) -> tuple[bool | None, str]:
    """(True/False, reason) when both codes are known; (None, reason) when either is unknown."""
    cand, orig = parse(candidate), parse(original)
    if cand is None or orig is None:
        unknown = candidate if cand is None else original
        return None, f"unknown temperature characteristic {unknown!r}"
    if cand.class_i:
        return True, f"{cand.code} (class I) is at least as stable as {orig.code}"
    if orig.class_i:
        return False, f"{cand.code} (class II) cannot replace class I {orig.code}"
    problems = []
    if cand.low_c > orig.low_c:
        problems.append(f"minimum temperature {cand.low_c} C above {orig.low_c} C")
    if cand.high_c < orig.high_c:
        problems.append(f"maximum temperature {cand.high_c} C below {orig.high_c} C")
    if cand.max_decrease_pct > orig.max_decrease_pct or cand.max_increase_pct > orig.max_increase_pct:
        problems.append(
            f"capacitance change -{cand.max_decrease_pct}/+{cand.max_increase_pct} % exceeds "
            f"-{orig.max_decrease_pct}/+{orig.max_increase_pct} %"
        )
    if problems:
        return False, f"{cand.code} vs {orig.code}: " + "; ".join(problems)
    return True, f"{cand.code} covers {orig.code} (temperature range and capacitance change)"
