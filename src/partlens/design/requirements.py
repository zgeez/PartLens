"""Requirements preserve exact messages; delegated defaults remain provisional, never user-confirmed."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum
import re
from typing import Any

from ..core.model import digest, to_jsonable

SCHEMA = "partlens.requirements/1"


class State(StrEnum):
    CONFIRMED = "confirmed"
    INFERRED = "inferred"
    OPTIONAL = "optional"
    CONFLICTING = "conflicting"
    UNANSWERED = "unanswered"


# Unitless numbers are accepted only for counts. Engineering quantities require explicit units.
FIELDS = {
    "led_count": ("functional", "count"), "led_arrangement": ("mechanical", "text"),
    "led_drive": ("electrical", ("matrix_constant_current", "direct_gpio", "addressable")),
    "led_rows": ("functional", "count"), "led_columns": ("functional", "count"),
    "led_type": ("functional", ("mono", "rgb", "addressable")),
    "nfc_mode": ("interfaces", ("tag", "reader")),
    "microphone_use": ("functional", ("sound_reactive", "audio_recording", "voice")),
    "battery_capacity": ("power", "mAh"), "battery_min": ("power", "V"),
    "battery_max": ("power", "V"), "runtime": ("power", "h"),
    "led_average_current": ("power", "mA"), "logic_voltage": ("electrical", "V"),
    "width": ("mechanical", "mm"), "height": ("mechanical", "mm"),
    "board_quantity": ("manufacturing", "count"), "parts_budget": ("manufacturing", "USD"),
    "brightness": ("functional", "text"), "charging_use": ("power", ("off_while_charging", "simultaneous")),
}
BREADBOARD_FIELDS = {
    "input_interface": ("interfaces", ("usb_c", "barrel_jack", "dual_input")),
    "input_voltage_min": ("power", "V"), "input_voltage_max": ("power", "V"),
    "secondary_rail_voltage": ("power", "V"), "rail_current_max": ("power", "mA"),
    "rail_selection": ("functional", ("fixed_dual_rail", "jumper_selectable", "switch_controlled")),
}
ALL_FIELDS = {**FIELDS, **BREADBOARD_FIELDS}
DEPENDENCIES = {
    "led_average_current": ("led_type", "led_rows", "led_columns"),
    "runtime": ("battery_capacity", "led_average_current"),
    "nfc_mode": (), "microphone_use": (), "parts_budget": ("board_quantity",),
    "rail_current_max": ("input_voltage_max", "logic_voltage"),
    "secondary_rail_voltage": ("input_voltage_min", "input_voltage_max"),
    "input_voltage_max": ("input_interface",), "input_voltage_min": ("input_interface",),
}
QUESTIONS = {
    "led_count": "How many physical LED positions in total? Confirm separately from matrix dimensions; 32 and 128 are different designs.",
    "led_arrangement": "What physical arrangement is required (matrix, ring, scattered, or other)? This does not specify drive topology.",
    "led_drive": "Is drive topology constrained: matrix_constant_current, direct_gpio, or addressable? Leave unanswered if undecided.",
    "led_rows": "How many matrix rows? Rows times columns gives physical positions, not brightness or drive topology.",
    "led_columns": "How many matrix columns? Confirm independently of total count and arrangement.",
    "led_type": "Monochrome, RGB, or addressable LEDs?",
    "nfc_mode": "Should NFC be a phone-readable tag or an active reader?",
    "microphone_use": "Sound-reactive lighting, audio recording, or voice processing?",
    "battery_capacity": "What battery capacity and discharge capability are available?",
    "battery_min": "What is the minimum battery operating voltage?",
    "battery_max": "What is the maximum charged battery voltage?",
    "runtime": "What operating time is required?",
    "led_average_current": "What average LED current or brightness target should be used?",
    "logic_voltage": "What logic supply voltage is required, if constrained?",
    "width": "What maximum board width?", "height": "What maximum board height?",
    "board_quantity": "How many boards will be assembled?", "parts_budget": "What parts budget and currency?",
    "brightness": "What brightness or viewing conditions?",
    "charging_use": "Must the badge operate while charging?",
    "input_interface": "Which DC power input connector would you like (**USB-C**, **Barrel Jack**, or **Dual Input**)?",
    "input_voltage_min": "What is the minimum DC input supply voltage (V)?",
    "input_voltage_max": "What is the maximum DC input supply voltage (V)?",
    "secondary_rail_voltage": "What voltage is required on the secondary breadboard rail (V)?",
    "rail_current_max": "What maximum continuous load current is required from the regulated rail (mA)?",
    "rail_selection": "How should the breadboard output rails be configured (**Jumper-selectable**, **Fixed dual-rail**, or **Switch-controlled**)?",
}
FEATURES = {"ble": ("bluetooth", "ble"), "led_matrix": ("led matrix", "matrix"),
            "nfc": ("nfc",), "microphone": ("microphone",), "imu": ("imu",),
            "rechargeable": ("rechargeable", "li-ion", "lipo"), "temperature": ("temperature", "thermometer"),
            "breadboard_power": ("breadboard", "power supply", "dual rail")}


def parse(parameter: str, text: str) -> tuple[Any, str | None]:
    if parameter not in ALL_FIELDS:
        raise ValueError("unsupported requirement parameter")
    kind = ALL_FIELDS[parameter][1]
    if isinstance(kind, tuple):
        if text not in kind:
            raise ValueError(f"{parameter} must be one of {kind}")
        return text, None
    if kind == "text":
        if not text.strip() or len(text) > 300:
            raise ValueError("requirement text must be 1..300 characters")
        return text.strip(), None
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*([A-Za-z]+)?\s*", text)
    if not match:
        raise ValueError("positive decimal quantity and explicit unit required")
    value, unit = Decimal(match[1]), match[2]
    if not value.is_finite() or value <= 0:
        raise ValueError("requirement must be finite and positive")
    if kind == "count":
        if unit is not None or value != value.to_integral_value() or value > 100000:
            raise ValueError("count must be a positive whole number <= 100000 without a unit")
        return int(value), None
    if unit != kind:
        raise ValueError(f"{parameter} requires {kind}, not {unit or 'a missing unit'}")
    return value, unit


@dataclass(frozen=True)
class Entry:
    parameter: str
    value: Any
    unit: str | None
    state: State
    source: str
    quote: str = ""
    rationale: str = ""
    dependencies: tuple[str, ...] = ()
    revision: int = 1

    @property
    def binding(self) -> bool:
        return self.state is State.CONFIRMED and bool(self.quote) and self.source.startswith("user:")


@dataclass
class Requirements:
    design_id: str
    description: str
    description_source: str
    entries: list[Entry] = field(default_factory=list)
    revision: int = 1

    @property
    def features(self) -> list[str]:
        text = self.description.casefold()
        return [key for key, words in FEATURES.items() if any(re.search(r"\b" + re.escape(w) + r"\b", text) for w in words)]

    @property
    def current(self) -> dict[str, Entry]:
        return {e.parameter: e for e in self.entries}

    @property
    def fingerprint(self) -> str:
        return digest(self.view())

    def record(self, parameter: str, text: str, *, source: str, quote: str = "", confirmed: bool = False,
               optional: bool = False, replace: bool = False, rationale: str = "") -> Entry:
        value, unit = parse(parameter, text)
        # Confirmation requires provenance and the actual value, not merely any words from a user message.
        numeric = isinstance(value, (int, Decimal))
        if confirmed and (not source.startswith("user:") or not quote):
            confirmed = False
        if confirmed:
            if numeric:
                pattern = r"(?<![\w.])" + re.escape(str(value)) + (r"\s*" + re.escape(unit) if unit else r"(?![\w.])")
                confirmed = bool(re.search(pattern, quote))
            else:
                v_cf = str(value).casefold()
                q_cf = quote.casefold()
                confirmed = (v_cf in q_cf or v_cf.replace("_", "-") in q_cf.replace(" ", "-")
                             or (parameter in BREADBOARD_FIELDS and v_cf.split("_")[0] in q_cf))
        state = State.CONFIRMED if confirmed else State.OPTIONAL if optional else State.INFERRED
        old = self.current.get(parameter)
        if old and (old.binding or old.state is State.CONFLICTING) and old.value != value and not replace:
            state = State.CONFLICTING
        if replace and old and old.binding and not confirmed:
            state = State.CONFLICTING  # model cannot overwrite a binding requirement using its own default
        self.revision += 1
        entry = Entry(parameter, value, unit, state, source if confirmed else "proposal:" + source,
                      quote if confirmed else "", rationale, DEPENDENCIES.get(parameter, ()), self.revision)
        self.entries.append(entry)
        return entry

    def get(self, key: str, default=None):
        item = self.current.get(key)
        return item.value if item and item.state is not State.CONFLICTING else default

    def gaps(self, *, interview: bool = False) -> list[dict]:
        needed = {"width", "height", "board_quantity", "parts_budget"}
        if "led_matrix" in self.features:
            needed |= {"led_rows", "led_columns", "led_type", "led_average_current", "brightness"}
            if interview:needed |= {"led_count", "led_arrangement", "led_drive"}
        if "nfc" in self.features:
            needed.add("nfc_mode")
        if "microphone" in self.features:
            needed.add("microphone_use")
        if "rechargeable" in self.features:
            needed |= {"battery_capacity", "battery_min", "battery_max", "runtime", "charging_use"}
        if "breadboard_power" in self.features:
            needed |= {"logic_voltage", "secondary_rail_voltage", "input_voltage_min", "input_voltage_max",
                       "rail_current_max", "input_interface", "rail_selection"}
        result=[]
        for key in sorted(needed):
            item=self.current.get(key)
            if not item or not item.binding:
                result.append({"id": key, "state": item.state.value if item else State.UNANSWERED.value,
                               "value": to_jsonable(item.value) if item else None, "question": QUESTIONS[key],
                               "dependencies": DEPENDENCIES.get(key, ()), "binding": False})
        return result

    def view(self) -> dict:
        return {"schema": SCHEMA, "design_id": self.design_id, "revision": self.revision,
                "description": self.description, "description_source": self.description_source,
                "features": self.features,
                "requirements": {k: {**to_jsonable(v), "binding": v.binding, "domain": ALL_FIELDS[k][0]}
                                 for k,v in self.current.items()},
                "history": to_jsonable(self.entries)}
