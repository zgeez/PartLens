"""Tool-independent proposed circuits and bounded, evidence-carrying feasibility checks.

Port/net intent is deliberately not an electrical netlist: no symbol pins, layout, ERC or validated
connectivity are implied. Calculations based on provisional requirements are explicitly conditional.
"""

from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal

from ..core.model import CheckResult, CheckStatus, Evidence, EvidenceKind, digest, to_jsonable
from .patterns import PATTERNS, Pattern, Role, required_blocks, all_patterns, get_pattern
from .requirements import Requirements, State

SCHEMA = "partlens.circuit/1"


@dataclass(frozen=True)
class GeneratedRole:
    line_id: str
    block: str
    pattern_id: str | None
    role: Role
    refs: tuple[str, ...]
    evidence: Evidence | None


@dataclass
class Circuit:
    design_id: str
    requirements_fingerprint: str
    requirements_revision: int
    selections: dict[str, str]
    justifications: dict[str, str]
    roles: list[GeneratedRole] = field(default_factory=list)
    checks: list[CheckResult] = field(default_factory=list)
    rails: list[dict] = field(default_factory=list)
    buses: list[dict] = field(default_factory=list)
    assignments: dict[str, str] = field(default_factory=dict)
    connections: list[dict] = field(default_factory=list)
    estimates: dict = field(default_factory=dict)
    unresolved: list[str] = field(default_factory=list)

    @property
    def fingerprint(self) -> str:
        return digest({"design": self.design_id, "requirements": self.requirements_fingerprint,
                       "patterns": {b: get_pattern(p).view() for b,p in self.selections.items()},
                       "roles": self.roles})

    def view(self) -> dict:
        feats=("breadboard_power",) if ({"input_power","rail_output","indicator"}&set(self.selections) or "power.xc6206_ldo" in self.selections.values()) else ()
        return {"schema": SCHEMA, **to_jsonable(self), "fingerprint": self.fingerprint,
                "block_alternatives":{block:[p.id for p in all_patterns(feats).values() if p.block==block]
                                      for block in self.selections},
                "status": "preliminary", "manufacturing_ready": False,
                "connectivity": "named port/net intent only; pins, nets and ERC not validated"}


def propose(spec: Requirements, selections: dict[str, str], justifications: dict[str, str] | None = None) -> Circuit:
    PATTERNS=all_patterns(spec.features)
    needed=required_blocks(spec.features)
    if set(selections)-needed:
        raise ValueError("pattern selected for a block not required by the current product features")
    for block,pid in selections.items():
        if pid not in PATTERNS or PATTERNS[pid].block!=block:
            raise ValueError("pattern does not implement the selected block")
    # JSON object order is not engineering intent. Canonicalize before generating ordered checks/buses.
    circuit=Circuit(spec.design_id,spec.fingerprint,spec.revision,dict(sorted(selections.items())),justifications or {})
    count=Counter()
    for block in sorted(needed):
        pattern=PATTERNS[selections[block]] if block in selections else None
        roles=pattern.roles if pattern else (Role("unresolved_block", "U", 1, "ic", "required block not implemented"),)
        for role in roles:
            quantity=role.quantity
            if role.name=="led_elements":
                rows,cols=spec.get("led_rows"),spec.get("led_columns")
                if rows is not None and cols is not None:
                    quantity=rows*cols*(3 if spec.get("led_type")=="rgb" else 1)
                else:
                    circuit.unresolved.append("LED count unresolved; one role placeholder does not establish a purchase quantity")
            if quantity>4096:
                raise ValueError("generated role exceeds the 4096-component expansion ceiling")
            refs=tuple(f"{role.prefix}{count[role.prefix]+i+1}" for i in range(quantity))
            count[role.prefix]+=quantity
            from dataclasses import replace
            role=replace(role,quantity=quantity)
            evidence=pattern.evidence("role:"+role.name,role.value) if pattern and pattern.reviewed else None
            circuit.roles.append(GeneratedRole("L"+str(len(circuit.roles)+1),block,pattern.id if pattern else None,role,refs,evidence))
        if pattern:
            circuit.unresolved.extend(f"{block}: {text}" for text in pattern.omissions)
        else:
            circuit.unresolved.append(f"{block}: no circuit pattern selected")
    endpoints={}
    for item in circuit.roles:
        for net in item.role.nets:
            endpoints.setdefault(net,[]).extend({"reference":r,"port":net,"pin":None} for r in item.refs)
    circuit.connections=[{"net":n,"endpoints":v,"validated":False} for n,v in sorted(endpoints.items())]
    check_circuit(spec,circuit)
    return circuit


def check_circuit(spec: Requirements, circuit: Circuit) -> None:
    PATTERNS=all_patterns(spec.features)
    circuit.checks.clear()
    def add(name,status,message,evidence=()):
        circuit.checks.append(CheckResult(name,spec.design_id,status,message,evidence=tuple(evidence)))
    def calc(field,value):
        return Evidence(EvidenceKind.CALCULATION,"calc:design:"+spec.fingerprint,field,str(value),
                        excerpt="Conditional on the recorded proposed requirements; not a measured hardware result")
    P,F,U=CheckStatus.PASS,CheckStatus.FAIL,CheckStatus.UNVERIFIED
    for block,pid in circuit.selections.items():
        pattern=PATTERNS[pid]
        present={r.role.name:r.role.quantity for r in circuit.roles if r.block==block}
        missing=[r.name for r in pattern.roles if present.get(r.name,0)<r.quantity]
        add('support.'+block,F if missing else P if pattern.reviewed else U,
            'missing required support roles: '+', '.join(missing) if missing else 'required reference roles present; identities/application still need qualification',
            (pattern.evidence('required_roles',','.join(r.name for r in pattern.roles)),) if pattern.reviewed else ())
    for key,entry in spec.current.items():
        if entry.state is State.CONFLICTING:
            add("requirements.conflict."+key,F,f"conflicting {key}; resolve with actual user provenance")
    for block in sorted(required_blocks(spec.features)):
        pattern=PATTERNS.get(circuit.selections.get(block,""))
        if not pattern or not pattern.reviewed or not pattern.reference:
            add("pattern."+block,U,"missing reviewed pattern evidence for "+block)
        else:
            add("pattern."+block,P,"manufacturer reference reviewed; circuit implementation still unverified",
                (pattern.evidence("reference",pattern.location),))
    voltage=spec.get("logic_voltage")
    if "breadboard_power" in spec.features:
        vin_lo,vin_hi=spec.get("input_voltage_min"),spec.get("input_voltage_max")
        sec_v=spec.get("secondary_rail_voltage")
        load_ma=spec.get("rail_current_max")
        iface=spec.get("input_interface")
        circuit.rails=[{"name":"3V3","voltage":to_jsonable(voltage),"source":"proposed logic_voltage","qualified":False},
                       {"name":"5V_RAIL","voltage":to_jsonable(sec_v),"source":"proposed secondary_rail_voltage","qualified":False},
                       {"name":"VIN","minimum":to_jsonable(vin_lo),"maximum":to_jsonable(vin_hi),"qualified":False}]
        for block,pid in circuit.selections.items():
            pattern=PATTERNS[pid]
            if pattern.supply and voltage is not None and pattern.reviewed:
                lower,upper=map(Decimal,pattern.supply)
                add("voltage."+block,P if lower<=voltage<=upper else F,
                    f"proposed {voltage} V rail versus recommended {lower}..{upper} V; conditional feasibility only",
                    (pattern.evidence("recommended_supply",f"{lower}..{upper} V"),calc("logic_voltage",voltage)))
            elif block not in {"power","charging","protection","debug","input_power","rail_output"}:
                add("voltage."+block,U,"rail voltage or reviewed recommended operating range unavailable")
        if vin_lo is not None and vin_hi is not None:
            add("input.voltage_envelope",P if vin_lo<vin_hi else F,
                f"proposed DC input envelope {vin_lo}..{vin_hi} V",(calc("input_voltage_range",f"{vin_lo}..{vin_hi}"),))
            if circuit.selections.get("input_power")=="input_power.usb_c_5v":
                in_pat=PATTERNS["input_power.usb_c_5v"]
                ok_iface=(iface in {None,"usb_c"} and Decimal("4.5")<=vin_lo<vin_hi<=Decimal("5.5"))
                add("input.connector_compatibility",P if ok_iface else F,
                    f"USB-C 5 V sink input pattern (4.5..5.5 V) versus proposed interface={iface or 'unspecified'}, range {vin_lo}..{vin_hi} V",
                    (in_pat.evidence("usb_c_vbus","4.5..5.5 V nominal 5 V sink"),calc("input_envelope",f"{iface}:{vin_lo}..{vin_hi} V")))
        else:
            add("input.voltage_envelope",U,"DC input voltage envelope unresolved")
        power_id=circuit.selections.get("power")
        if power_id in PATTERNS and vin_lo is not None and vin_hi is not None:
            p_pat=PATTERNS[power_id]
            max_vin=Decimal("6.0") if power_id=="power.xc6206_ldo" else Decimal("5.5")
            min_vin=Decimal("1.3") if power_id=="power.tps63802" else Decimal("1.8")
            add("power.input_range",P if min_vin<=vin_lo<vin_hi<=max_vin and (power_id!="power.tps63802" or vin_lo>Decimal("1.8")) else F,
                f"DC input {vin_lo}..{vin_hi} V versus {power_id} recommended operating input {min_vin}..{max_vin} V",
                (p_pat.evidence("input_range",f"{min_vin}..{max_vin} V"),calc("input_voltage_range",f"{vin_lo}..{vin_hi}")))
            if voltage is not None:
                add("power.output",P if voltage==Decimal("3.3") else F,
                    f"selected {power_id} reference provides nominal 3.3 V; proposed primary rail is {voltage} V",
                    (p_pat.evidence("output_voltage","3.3 V"),calc("logic_voltage",voltage)))
        else:
            add("power.input_range",U,"regulator or DC input voltage envelope unresolved")
        circuit.estimates={"conditional":True,"measured":False}
        if load_ma is not None:
            ind_ma=Decimal("0.5") if "indicator" in circuit.selections else Decimal("0")
            req_a=(load_ma+ind_ma)/Decimal("1000")
            circuit.estimates["rail_load_A"]=str(load_ma/Decimal("1000"))
            circuit.estimates["indicator_A"]=str(ind_ma/Decimal("1000"))
            circuit.estimates["total_3v3_rail_A"]=str(req_a)
            if power_id=="power.xc6206_ldo":
                p_pat=PATTERNS["power.xc6206_ldo"]
                add("power.design_budget",P if req_a<=Decimal("0.25") else F,
                    f"proposed 3.3 V rail load {req_a} A (including indicator) versus XC6206P332MR 0.25 A maximum output current",
                    (p_pat.evidence("max_output_current","250 mA"),calc("total_3v3_rail_A",req_a)))
                if vin_hi is not None and voltage is not None:
                    pd=(vin_hi-voltage)*req_a
                    circuit.estimates["ldo_worst_case_dissipation_W"]=str(pd)
                    add("power.thermal_dissipation",F if pd>Decimal("0.25") else U,
                        f"worst-case LDO dissipation ({vin_hi} V - {voltage} V) * {req_a} A = {pd} W versus SOT-23 0.25 W package rating",
                        (p_pat.evidence("sot23_power_dissipation","250 mW"),calc("ldo_dissipation_W",pd)))
                else:
                    add("power.thermal_dissipation",U,"input/output voltage required to evaluate linear regulator dissipation")
            elif power_id in {"power.tps63031","power.tps63802"}:
                p_pat=PATTERNS[power_id]
                limit=Decimal("2.0") if power_id=="power.tps63802" else (Decimal("0.8") if vin_lo is not None and vin_lo>=Decimal("3.3") else Decimal("0.5"))
                add("power.design_budget",P if req_a<=limit else F,
                    f"proposed 3.3 V rail load {req_a} A versus {power_id} conditional {limit} A output capability",
                    (p_pat.evidence("conditional_output_A",str(limit)),calc("total_3v3_rail_A",req_a)))
                add("power.thermal_dissipation",U,
                    "switched-mode converter efficiency, inductor DCR losses and PCB thermal impedance require board-level verification")
        else:
            add("power.design_budget",U,"maximum continuous rail current requirement unresolved")
            add("power.thermal_dissipation",U,"rail load current unresolved")
        if sec_v is not None:
            if sec_v==Decimal("5"):
                add("power.secondary_rail",U,
                    "secondary 5 V breadboard rail is fed from USB-C VBUS through Schottky protection diode B5819W SL (~0.45..0.60 V forward drop); load regulation and strict 5.0 V tolerance remain unverified")
            elif sec_v==voltage:
                add("power.secondary_rail",P,
                    f"both breadboard rails strapped to regulated {voltage} V output; total combined load must stay within regulator budget",
                    (calc("secondary_rail_voltage",sec_v),))
            else:
                add("power.secondary_rail",F,
                    f"selected single-regulator architecture provides 3.3 V and pass-through 5 V VBUS only, not an independent {sec_v} V rail",
                    (calc("secondary_rail_voltage",sec_v),))
        else:
            add("power.secondary_rail",U,"secondary breadboard rail voltage target unresolved")
        add("mechanical.breadboard_fit",U,"physical 2.54 mm header span across MB-102 breadboard power strips (~48.26 mm rail pitch) requires CAD footprint verification")
        add("connectivity.pins",U,"named nets are circuit intent; no validated pin-level connectivity or ERC")
        for item in circuit.roles:
            if not item.role.mpn or not item.role.package:
                msg = f"{item.line_id} {item.block}.{item.role.name}: exact identity or land pattern unresolved"
                if msg not in circuit.unresolved:
                    circuit.unresolved.append(msg)
            for g in item.role.omissions:
                msg = f"{item.line_id}: {g}"
                if msg not in circuit.unresolved:
                    circuit.unresolved.append(msg)
        return
    circuit.rails=[{"name":"3V3","voltage":to_jsonable(voltage),"source":"proposed logic_voltage",
                    "qualified":False},
                   {"name":"VBAT","minimum":to_jsonable(spec.get("battery_min")),
                    "maximum":to_jsonable(spec.get("battery_max")),"qualified":False}]
    for block,pid in circuit.selections.items():
        pattern=PATTERNS[pid]
        if pattern.supply and voltage is not None and pattern.reviewed:
            lower,upper=map(Decimal,pattern.supply)
            add("voltage."+block,P if lower<=voltage<=upper else F,
                f"proposed {voltage} V rail versus recommended {lower}..{upper} V; conditional feasibility only",
                (pattern.evidence("recommended_supply",f"{lower}..{upper} V"),calc("logic_voltage",voltage)))
        elif block not in {"power","charging","protection","debug"}:
            add("voltage."+block,U,"rail voltage or reviewed recommended operating range unavailable")
    lo,hi=spec.get("battery_min"),spec.get("battery_max")
    if lo is not None and hi is not None:
        add("battery.range",P if lo<hi else F,f"proposed battery range {lo}..{hi} V",(calc("battery_range",f"{lo}..{hi}"),))
        if circuit.selections.get("power")=="power.tps63031":
            pattern=PATTERNS["power.tps63031"]
            add("power.input_range",P if Decimal('1.8')<=lo<hi<=Decimal('5.5') else F,
                "proposed battery envelope versus converter recommended input range",
                (pattern.evidence("input_range","1.8..5.5 V"),calc("battery_range",f"{lo}..{hi}")))
            if voltage is not None:
                add("power.output",P if voltage==Decimal('3.3') else F,
                    "fixed-output TPS63031 provides nominal 3.3 V; another rail requires another pattern",
                    (pattern.evidence("output_voltage","3.3 V"),calc("logic_voltage",voltage)))
    else:
        add("battery.range",U,"battery voltage envelope unresolved")
    rows,cols=spec.get("led_rows"),spec.get("led_columns")
    count=rows*cols*(3 if spec.get("led_type")=="rgb" else 1) if rows and cols else None
    if "led_matrix" in required_blocks(spec.features):
        pattern=PATTERNS.get(circuit.selections.get("led_matrix",""))
        requested=spec.get('led_count')
        if requested is not None:
            add('led.count_consistency',U if not rows or not cols else P if requested==rows*cols else F,
                f'Recorded physical count {requested}; proposed rows/columns {rows} x {cols}. '
                'Count, geometry, color channels and brightness are separate; contradictory targets cannot be accepted.',
                (calc('physical_count',requested),calc('matrix_dimensions',f'{rows} x {cols}')))
        if spec.get('led_drive') is not None:
            drive=spec.get('led_drive')
            add('led.drive_topology',F if pattern and drive!='matrix_constant_current' else U,
                f'Recorded drive topology {drive}; reviewed matrix pattern uses constant-current multiplexed drive. '
                'Pin mapping, programming and operating waveforms remain unverified.',
                (pattern.evidence('reference',pattern.location),) if pattern else ())
        if pattern and count is not None:
            add("led.capacity",P if count<=144 and spec.get("led_type")=="mono" else F,
                f"proposed {count} channels, type {spec.get('led_type')}; reviewed pattern supports <=144 discrete monochrome channels. "
                "Changing dimensions does not resolve an addressable/RGB protocol mismatch; revise a provisional LED type or leave this block unresolved.",
                (pattern.evidence("channels","144"),calc("led_channels",count)))
        else:
            add("led.capacity",U,"matrix dimensions/type or driver unresolved")
    if "nfc" in circuit.selections:
        add("nfc.function",P if spec.get("nfc_mode")=="tag" else F if spec.get("nfc_mode")=="reader" else U,
            "selected reference implements an NFC tag, not an active reader",
            (PATTERNS[circuit.selections["nfc"]].evidence("function","NFC Type 5 tag"),))
    if spec.get("charging_use")=="simultaneous" and "charging" in circuit.selections:
        add("charging.power_path",F,"selected standalone charger has no reviewed simultaneous-load power-path implementation")
    else:
        add("charging.safety",U,"cell protection, charge current, thermal conditions and load isolation require review")
    if circuit.selections.get('charging')=='charge.mcp73831':
        pattern=PATTERNS['charge.mcp73831']
        if hi is not None and hi!=Decimal('4.2'):
            add('charging.setpoint',F,
                f'MCP73831-2 nominal 4.2 V setpoint conflicts with proposed charged-cell target {hi} V',
                (Evidence(EvidenceKind.DATASHEET,pattern.reference+'#page=3','VREG for MCP7383X-2',
                          '4.168..4.232 V, typical 4.20 V under stated table conditions','2026-10-23'),calc('battery_max',hi)))
        else:
            add('charging.setpoint',U,
                'Nominal charge target alone cannot qualify the cell: charge-voltage tolerance, chemistry, current and temperature need exact cell evidence')
    circuit.buses=[]
    for interface in ("i2c","i2s","spi"):
        participants=[b for b,p in circuit.selections.items() if PATTERNS[p].interface==interface]
        if participants:
            circuit.buses.append({"name":interface.upper()+"0","participants":participants,
                                  "pins_validated":False,"clock_hz":None})
        if interface=="i2c" and participants:
            addresses=[a for b in participants for a in (PATTERNS[circuit.selections[b]].addresses or ())]
            complete=all(PATTERNS[circuit.selections[b]].addresses is not None for b in participants)
            if len(addresses)!=len(set(addresses)):
                add("i2c.addresses",F,"selected devices collide on a configured I2C address")
            elif complete:
                add("i2c.addresses",P,"configured I2C addresses do not collide",(calc("addresses",addresses),))
            else:
                add("i2c.addresses",U,"address straps/configuration are not reviewed for every I2C participant")
    if "controller" in circuit.selections:
        pins=PATTERNS[circuit.selections['controller']].gpio_pins
        resources=[]
        if any(b["name"]=="I2C0" for b in circuit.buses): resources += ["I2C_SDA","I2C_SCL"]
        if any(b["name"]=="I2S0" for b in circuit.buses): resources += ["I2S_BCLK","I2S_WS","I2S_DATA"]
        if "imu" in circuit.selections: resources.append("IMU_INT")
        if "led_matrix" in circuit.selections: resources.append("LED_SHUTDOWN")
        circuit.assignments=dict(zip(resources,pins))
        pattern=PATTERNS[circuit.selections["controller"]]
        add("mcu.gpio_budget",P if len(resources)<=len(pins) else F,
            f"{len(resources)} assigned signals versus {len(pins)} proposed usable GPIO after straps/debug reservations",
            (pattern.evidence("gpio_upper_bound","15 GPIO, 3 strapping pins"),calc("reserved_pin_allocation",circuit.assignments)))
        add("mcu.pin_mux",U,"GPIO allocation is proposed; mux, boot, drive, pin numbers and concurrent peripheral use need pin-level review")
    else:
        add("mcu.resources",U,"controller and peripheral resources unresolved")
    add("clock.contracts",U,"bus clocks, I2S format and timing contracts not fully established")
    current=spec.get("led_average_current")
    circuit.estimates={"conditional":True,"measured":False}
    if count is not None and current is not None:
        led_current=Decimal(count)*current/1000
        circuit.estimates["led_average_A"]=str(led_current)
        # Reserve is an engineering supply requirement, deliberately not average MCU current.
        reserve=Decimal('0.5') if "controller" in circuit.selections else Decimal(0)
        required=reserve+led_current
        circuit.estimates["supply_reserve_plus_led_A"]=str(required)
        if "led_matrix" in circuit.selections:
            add('led.current_programming',U,
                'REXT=20k reference gives typical 3.2 mA average per LED; proposed brightness/current needs resistor/PWM and worst-case validation')
        capacity,target=spec.get('battery_capacity'),spec.get('runtime')
        if capacity is not None and target is not None and hi is not None and voltage is not None:
            optimistic=hi*(capacity/1000)/(voltage*led_current)
            circuit.estimates['optimistic_led_only_runtime_bound_h']=str(optimistic)
            circuit.estimates['runtime_bound_assumptions']='Vmax*proposed Ah / LED rail power; 100% efficiency, no MCU/peripheral load; not measured runtime'
            add('power.runtime_bound',F if optimistic<target else U,
                f'conditional optimistic LED-only bound {optimistic} h versus proposed target {target} h; other loads/losses reduce runtime',
                (calc('runtime_bound',f'{hi} V * {capacity}/1000 Ah / ({voltage} V * {led_current} A); ideal efficiency; excludes other loads'),))
        if circuit.selections.get("power")=="power.tps63031" and lo is not None and lo>Decimal('2.4'):
            add("power.design_budget",P if required<=Decimal('0.5') else F,
                f"proposed load reserve {required} A versus conditional boost output 0.5 A; other loads not yet included",
                (PATTERNS["power.tps63031"].evidence("boost_output","up to 0.5 A for VIN > 2.4 V"),
                 PATTERNS["ble.esp32c3_mini"].evidence("supply_recommendation",">=0.5 A"),calc("reserve_plus_led",required)))
    add("power.runtime",U,"battery runtime requires average load profiles, conversion efficiency, usable capacity and temperature; peak supply reserve is not average consumption")
    add("mechanical.fit",U,"board dimensions alone do not validate component/antenna/connector/battery fit")
    add("connectivity.pins",U,"named nets are circuit intent; no validated pin-level connectivity or ERC")
    for item in circuit.roles:
        if not item.role.mpn or not item.role.package:
            circuit.unresolved.append(f"{item.line_id} {item.block}.{item.role.name}: exact identity or land pattern unresolved")
        circuit.unresolved.extend(f"{item.line_id}: {g}" for g in item.role.omissions)
