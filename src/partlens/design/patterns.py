"""Small reviewed reference library, not a catalogue of certified or manufacturing-ready circuits.

Only paraphrased facts/role requirements are included. Manufacturer documents and live supplier records
retain their terms. A missing role identity or unreviewed connection always remains an explicit omission.
"""

from dataclasses import dataclass
from decimal import Decimal

from ..core.model import Evidence, EvidenceKind, to_jsonable

ESP = "https://documentation.espressif.com/esp32-c3-mini-1_datasheet_en.pdf"
POWER = "https://www.ti.com/lit/ds/symlink/tps63031.pdf"
LED = "https://www.lumissil.com/assets/pdf/core/IS31FL3731_DS.pdf"
IMU = "https://www.st.com/resource/en/datasheet/lsm6dso.pdf"
NFC = "https://www.st.com/resource/en/datasheet/st25dv04kc.pdf"
CHARGE = "https://ww1.microchip.com/downloads/aemDocuments/documents/APID/ProductDocuments/DataSheets/MCP73831-Family-Data-Sheet-DS20001984H.pdf"
PROTECTION = "https://www.ti.com/lit/ds/symlink/bq2970.pdf"
MIC = "https://www.knowles.com/docs/default-source/model-downloads/sph0645lm4h-b-datasheet-rev-c.pdf"


@dataclass(frozen=True)
class Role:
    name: str
    prefix: str
    quantity: int
    category: str
    value: str
    package: str = ""
    manufacturer: str = ""
    mpn: str = ""
    codes: tuple[str, ...] = ()
    parameters: tuple[tuple[str, str], ...] = ()
    nets: tuple[str, ...] = ()
    omissions: tuple[str, ...] = ()
    reference: str = ""


@dataclass(frozen=True)
class Pattern:
    id: str
    block: str
    function: str
    reference: str
    location: str
    roles: tuple[Role, ...]
    supply: tuple[str, str] | None = None
    interface: str = ""
    # Addresses are not guessed from part names. Unknown addressing blocks a bus-collision pass.
    addresses: tuple[int, ...] | None = None
    omissions: tuple[str, ...] = ()
    reviewed: bool = True
    version: str = "1"
    gpio_pins: tuple[str, ...] = ()

    def evidence(self, field: str, value: str) -> Evidence:
        return Evidence(EvidenceKind.DATASHEET, self.reference + "#" + self.location, field, value,
                        "2026-10-23", "")

    def view(self) -> dict:
        return {**to_jsonable(self), "validation_status": "reference facts reviewed; implementation unverified"
                if self.reviewed else "reference not fully reviewed; unresolved pattern",
                "hardware_validated": False}


def cap(name, value, quantity=1, codes=(), parameters=(), nets=("3V3", "GND")):
    if value == "100nF" and tuple(codes) == ("C1525",):
        return Role(name, "C", quantity, "capacitor", value, "0402", "Samsung Electro-Mechanics",
                    "CL05B104KO5NNNC", tuple(codes),
                    (("capacitance", value), ("voltage_rating", "16V"), ("dielectric", "X7R"),
                     ("tolerance_pct", "10%")), nets,
                    ("effective capacitance, ESR, ripple, temperature and physical implementation remain unverified",),
                    "https://product.samsungsem.com/mlcc/CL05B104KO5NNN.do")
    if value == "10uF" and tuple(codes) == ("C19702",):
        return Role(name, "C", quantity, "capacitor", value, "0603", "Samsung Electro-Mechanics",
                    "CL10A106KP8NNNC", tuple(codes),
                    (("capacitance", value), ("voltage_rating", "10V"), ("dielectric", "X5R"),
                     ("tolerance_pct", "10%")), nets,
                    ("effective capacitance under bias and operating conditions remain unverified",),
                    "https://product.samsungsem.com/mlcc/CL10A106KP8NNN.do")
    return Role(name, "C", quantity, "capacitor", value, "0402" if value == "100nF" else "",
                codes=tuple(codes), parameters=(("capacitance", value), *parameters), nets=nets,
                omissions=("effective capacitance, ESR, voltage/temperature margin and footprint review required",))


PATTERNS = {
    "ble.esp32c3_mini": Pattern("ble.esp32c3_mini", "controller", "BLE phone control using a radio module",
        ESP, "page=34", (
            Role("ble_module", "U", 1, "ic", "BLE MCU module", "", "Espressif Systems", "ESP32-C3-MINI-1-N4X",
                 ("C9900263492",), nets=("3V3", "GND", "EN", "UART_TX", "UART_RX"),
                 omissions=("module land pattern, antenna keepout, boot straps and RF compliance review",)),
            cap("local_bypass", "100nF", codes=("C1525",)), cap("bulk_bypass", "10uF", codes=("C19702",)),
            Role("enable_pullup", "R", 1, "resistor", "10k", "0402", parameters=(("resistance", "10k"),), nets=("3V3", "EN")),
            cap("enable_delay", "1uF", nets=("EN", "GND")),
            Role("reset_button", "SW", 1, "switch", "momentary reset", nets=("EN", "GND")),
            Role("boot_button", "SW", 1, "switch", "download boot strap", nets=("BOOT", "GND")),
        ), ("3.0", "3.6"), omissions=("15 GPIO is an upper bound; 3 strapping GPIO and debug functions must be reserved",
                                         "external supply recommendation >= 0.5 A; not average MCU consumption"),
        gpio_pins=("GPIO0","GPIO1","GPIO3","GPIO4","GPIO5","GPIO6","GPIO7","GPIO10")),
    "power.tps63031": Pattern("power.tps63031", "power", "Fixed 3.3 V buck-boost proposal",
        POWER, "page=10", (
            Role("converter", "U", 1, "ic", "3.3V buck-boost", "", "Texas Instruments", "TPS63031DSKR", ("C15516",),
                 nets=("VBAT", "3V3", "GND", "SW1", "SW2")),
            Role("inductor", "L", 1, "inductor", "1.5uH", "", "Coilcraft", "LPS3015-1R5",
                 nets=("SW1", "SW2"), omissions=("saturation current, ripple, DCR and exact ordering suffix not established",)),
            cap("input_bulk", "10uF", parameters=(("voltage_rating", "6.3V"),), nets=("VBAT", "GND")),
            cap("output_bulk", "10uF", 2, parameters=(("voltage_rating", "6.3V"),)),
            cap("analog_bypass", "100nF", codes=("C1525",), nets=("VINA", "GND")),
        ), omissions=("0.5 A boost capability is conditional on VIN > 2.4 V; not a blanket output-current guarantee",
                      "VINA/EN/PS-SYNC/FB/ground wiring and thermal/transient design remain unvalidated")),
    "led.is31fl3731": Pattern("led.is31fl3731", "led_matrix", "Cross-plexed individual monochrome LEDs",
        LED, "page=1", (
            Role("driver", "U", 1, "ic", "144 channel LED matrix driver", "", "Lumissil Microsystems",
                 "IS31FL3731-QFLS2-TR", ("C191206",), nets=("3V3", "GND", "I2C_SDA", "I2C_SCL", "LED_CA", "LED_CB"),
                 omissions=("ISSI/Lumissil corporate identity must be explicitly resolved before transferring manufacturer evidence",)),
            Role("current_setting", "R", 1, "resistor", "20k", "0402", parameters=(("resistance", "20k"),), nets=("REXT", "GND")),
            cap("local_bypass", "100nF", codes=("C1525",)), cap("bulk_bypass", "10uF", codes=("C19702",)),
            Role("led_elements", "LED", 1, "led", "individual monochrome LEDs; quantity expanded from requirements",
                 nets=("LED_CA", "LED_CB"), omissions=("exact LED, forward voltage, brightness and current rating not selected",)),
        ), ("2.7", "5.5"), "i2c", None,
        ("20k gives a stated typical 3.2mA average per LED; other currents need reviewed resistor calculations",
         "matrix cross-plexing, SDB, AD, interrupt and unused audio-pin terminations require pin-level review"),version="2"),
    "imu.lsm6dso": Pattern("imu.lsm6dso", "imu", "Six-axis motion sensing",
        IMU, "page=34", (
            Role("imu", "U", 1, "ic", "6-axis IMU", "", "STMicroelectronics", "LSM6DSOTR", ("C2655100",),
                 nets=("3V3", "GND", "I2C_SDA", "I2C_SCL", "IMU_INT")),
            cap("supply_bypass", "100nF", 2, codes=("C1525",)),
        ), ("1.71", "3.6"), "i2c", None,
        ("I/O supply, CS/SDO/address straps and interrupt configuration require explicit connections",)),
    "nfc.st25dv_tag": Pattern("nfc.st25dv_tag", "nfc", "Dynamic NFC Type 5 tag, not a reader",
        NFC, "page=1", (
            Role("nfc_tag", "U", 1, "ic", "NFC Type 5 tag", "", "STMicroelectronics", "ST25DV04KC-IE6S3", ("C3304276",),
                 nets=("3V3", "GND", "I2C_SDA", "I2C_SCL", "NFC_ANT1", "NFC_ANT2")),
            cap("local_bypass", "100nF", codes=("C1525",)),
            Role("antenna", "L", 1, "inductor", "13.56MHz NFC antenna and matching network",
                 nets=("NFC_ANT1", "NFC_ANT2"), omissions=("coil geometry, tuning/matching components and RF verification unresolved",)),
        ), ("1.8", "5.5"), "i2c", None,
        ("I2C address configuration/collision and RF tuning unverified",)),
    "microphone.sph0645": Pattern("microphone.sph0645", "microphone", "I2S microphone investigation",
        MIC, "datasheet-rev-c", (
            Role("microphone", "U", 1, "ic", "digital microphone", "", "Knowles", "SPH0645LM4H-B", ("C2686054", "C255205"),
                 nets=("3V3", "GND", "I2S_BCLK", "I2S_WS", "I2S_DATA")),
            cap("local_bypass", "100nF", codes=("C1525",)),
        ), interface="i2s", reviewed=False,
        omissions=("manufacturer PDF fetch failed; supply, clock limits, select wiring and lifecycle not reviewed",)),
    "charge.mcp73831": Pattern("charge.mcp73831", "charging", "Single-cell charger reference; not protection or power path",
        CHARGE, "page=18", (
            Role("charger", "U", 1, "ic", "single-cell charger", "", "Microchip", "MCP73831T-2ACI/OT", ("C424093",),
                 nets=("USB_5V", "VBAT", "GND", "CHARGE_PROG")),
            cap("input_bypass", "4.7uF", nets=("USB_5V", "GND")), cap("battery_bypass", "4.7uF", nets=("VBAT", "GND")),
            Role("charge_program", "R", 1, "resistor", "charge-current programming resistor: unresolved",
                 nets=("CHARGE_PROG", "GND"), omissions=("cell charging specification/temperature and thermal dissipation required",)),
        ), omissions=("does not supply cell protection, temperature qualification or simultaneous-load power-path management",)),
    "protection.bq29700": Pattern("protection.bq29700", "protection", "Cell protection reference investigation",
        PROTECTION, "page=18", (
            Role("protector", "U", 1, "ic", "cell protection IC", "", "Texas Instruments", "BQ29700DSER",
                 nets=("CELL_POS", "CELL_NEG", "VBAT", "GND")),
            Role("protection_fets", "Q", 2, "transistor", "back-to-back protection MOSFETs: unresolved",
                 omissions=("VDS, RDS(on), current threshold, cell and layout evidence required",)),
            Role("filter_resistors", "R", 2, "resistor", "protection filter values: unresolved"),
            cap("filter", "100nF", codes=("C1525",)),
            Role("cell", "BT", 1, "battery", "single-cell rechargeable battery: unresolved",
                 omissions=("exact cell/certification, protection, charge/discharge limits and dimensions required",)),
        ), omissions=("variant thresholds, FET/filter selection, sense return and cell safety not qualified",)),
    "debug.uart": Pattern("debug.uart", "debug", "Programming/reset/boot connector roles",
        ESP, "page=34", (
            Role("programming_header", "J", 1, "connector", "3.3V UART, EN/BOOT, GND header",
                 nets=("3V3", "GND", "UART_TX", "UART_RX", "EN", "BOOT")),
            Role("charging_connector", "J", 1, "connector", "5V charging input connector",
                 nets=("USB_5V", "GND"), omissions=("connector pinout, USB-C CC resistors if chosen, ESD/fusing unresolved",)),
        ), omissions=("exact connectors and footprint unknown; no USB data circuit is generated",)),
}


def required_blocks(features: list[str]) -> set[str]:
    blocks={"debug"}
    if "ble" in features: blocks.add("controller")
    blocks |= set(features) & {"led_matrix", "imu", "nfc", "microphone", "temperature"}
    if "rechargeable" in features: blocks |= {"power", "charging", "protection"}
    return blocks


def library() -> dict:
    return {"schema": "partlens.patterns/1", "patterns": [p.view() for p in PATTERNS.values()],
            "note": "A reviewed reference is not a validated implementation. Missing identities and support roles remain unresolved."}


def all_patterns():
    from .extensions import load_extensions
    return {**load_extensions(),**PATTERNS}


def get_pattern(pid):
    return all_patterns()[pid]
