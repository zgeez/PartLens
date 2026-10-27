"""Additional independently sourced structural checks. These are not pin-level circuit signoff."""
from decimal import Decimal

from ..core.model import CheckResult,CheckStatus,Evidence,EvidenceKind
from .patterns import ESP,all_patterns,get_pattern

SOC='https://documentation.espressif.com/esp32-c3_datasheet_en.pdf'
MODULE_PINS={'GPIO0':12,'GPIO1':13,'GPIO3':6,'GPIO4':18,'GPIO5':19,'GPIO6':20,'GPIO7':21,'GPIO10':16}


def validate(spec,circuit):
    P,F,U=CheckStatus.PASS,CheckStatus.FAIL,CheckStatus.UNVERIFIED
    def evidence(url,field,value):return Evidence(EvidenceKind.DATASHEET,url,field,value,'2026-10-24')
    def calc(field,value):return Evidence(EvidenceKind.CALCULATION,'calc:design:'+spec.fingerprint,field,str(value),
        excerpt='Conditional on explicit proposed inputs; not measured hardware performance')
    def add(name,status,message,ev=()):
        circuit.checks[:]=[c for c in circuit.checks if c.check!=name]
        circuit.checks.append(CheckResult(name,spec.design_id,status,message,evidence=tuple(ev)))
    voltage,lo,hi=spec.get('logic_voltage'),spec.get('battery_min'),spec.get('battery_max')
    power=circuit.selections.get('power')
    if 'breadboard_power' in spec.features:
        vin_lo,vin_hi=spec.get('input_voltage_min'),spec.get('input_voltage_max')
        load_ma=spec.get('rail_current_max')
        ind_ma=Decimal('0.5') if 'indicator' in circuit.selections else Decimal('0')
        req_a=(load_ma+ind_ma)/Decimal('1000') if load_ma is not None else None
        if power in {'power.tps63031','power.tps63802','power.xc6206_ldo'}:
            pattern=get_pattern(power)
            if power=='power.xc6206_ldo':
                if vin_lo is not None and vin_hi is not None:
                    add('power.input_range',P if Decimal('1.8')<=vin_lo<vin_hi<=Decimal('6.0') else F,
                        'Torex XC6206 datasheet specifies 1.8..6.0 V recommended operating input (LCSC C347376 lists 8 V; manufacturer limit governs)',
                        (pattern.evidence('recommended_operating_input','1.8..6.0 V'),calc('input_envelope',f'{vin_lo}..{vin_hi}')))
                if voltage is not None:
                    add('power.output',P if voltage==Decimal('3.3') else F,
                        'Fixed 3.3 V XC6206P332MR nominal output; dropout and load tolerance require review',
                        (pattern.evidence('nominal_reference','3.3 V'),calc('proposed_logic_V',voltage)))
                if req_a is not None:
                    add('power.design_budget',P if req_a<=Decimal('0.25') else F,
                        f'Proposed 3.3 V rail load {req_a} A versus XC6206P332MR 0.25 A current limit',
                        (pattern.evidence('output_current_limit','0.25 A'),calc('total_3v3_rail_A',req_a)))
                    if vin_hi is not None and voltage is not None:
                        pd=(vin_hi-voltage)*req_a
                        add('power.thermal_dissipation',F if pd>Decimal('0.25') else U,
                            f'Worst-case LDO dissipation ({vin_hi} V - {voltage} V) * {req_a} A = {pd} W versus SOT-23 0.25 W package limit',
                            (pattern.evidence('sot23_power_dissipation','0.25 W'),calc('ldo_dissipation_W',pd)))
                add('power.peak_thermal',U,'Inrush, short-circuit foldback, ambient derating and PCB copper thermal resistance remain unverified')
            else:
                alt=power=='power.tps63802'
                minimum=Decimal('1.3') if alt else Decimal('1.8')
                if vin_lo is not None and vin_hi is not None:
                    add('power.input_range',P if minimum<=vin_lo<vin_hi<=Decimal('5.5') and (not alt or vin_lo>Decimal('1.8')) else F,
                        'DC input envelope versus converter recommended input/startup conditions',
                        (pattern.evidence('input/startup','1.3..5.5 V; startup >1.8 V' if alt else '1.8..5.5 V'),calc('input_envelope',f'{vin_lo}..{vin_hi}')))
                if voltage is not None:
                    add('power.output',P if voltage==Decimal('3.3') else F,
                        'Reviewed 3.3 V nominal reference; tolerance/transient rail envelope still requires review',
                        (pattern.evidence('nominal_reference','3.3 V'),calc('proposed_logic_V',voltage)))
                if req_a is not None:
                    valid=vin_lo is not None and voltage==Decimal('3.3') and (vin_lo>=Decimal('2.3') if alt else vin_lo>Decimal('2.4'))
                    limit=Decimal('2') if alt else (Decimal('0.8') if vin_lo is not None and vin_lo>=Decimal('3.3') else Decimal('0.5'))
                    add('power.design_budget',P if valid and req_a<=limit else F if valid else U,
                        f'Proposed 3.3 V rail load {req_a} A versus conditional {limit} A converter reference; transients remain unqualified',
                        (pattern.evidence('conditional_output_A',str(limit)),calc('total_3v3_rail_A',req_a)))
                add('power.thermal_dissipation',U,'Switched-mode converter efficiency, inductor losses and PCB thermal impedance require board-level verification')
                add('power.peak_thermal',U,'Peak loads, current limit, inductor saturation/ripple, efficiency, capacitor bias and junction temperature not fully evidenced')
                if alt:
                    nominal=Decimal('.5')*(1+Decimal(511)/91)
                    circuit.estimates['feedback_nominal_V']=str(nominal)
                    add('power.feedback',U,'511k/91k manufacturer reference gives nominal '+str(nominal)+' V; exact resistor tolerances, feedback accuracy and resulting rail margins require qualification',
                        (pattern.evidence('feedback_example','511k/91k, 0.5 V FB'),calc('nominal_V',nominal)))
        for row in circuit.roles:
            add('footprint.'+row.line_id,U,'Exact land pattern/pad mapping and implementation not validated'+('' if row.role.package else '; package requirement also unknown'))
        return
    if power in {'power.tps63031','power.tps63802'}:
        alt=power=='power.tps63802';pattern=get_pattern(power)
        minimum=Decimal('1.3') if alt else Decimal('1.8')
        if lo is not None and hi is not None:
            add('power.input_range',P if minimum<=lo<hi<=Decimal('5.5') and (not alt or lo>Decimal('1.8')) else F,
                'Battery envelope versus recommended input/startup conditions',
                (pattern.evidence('input/startup','1.3..5.5 V; startup >1.8 V' if alt else '1.8..5.5 V'),calc('battery_envelope',f'{lo}..{hi}')))
        if voltage is not None:
            # TI's 511k/91k example is nominally ~3.308 V, not exact zero-error 3.300 V.
            add('power.output',P if voltage==Decimal('3.3') else F,
                'Reviewed 3.3 V nominal reference; tolerance/transient rail envelope still requires review',
                (pattern.evidence('nominal_reference','3.3 V'),calc('proposed_logic_V',voltage)))
        reserve=Decimal('0.5') if 'controller' in circuit.selections else Decimal(0)
        led=Decimal(circuit.estimates.get('led_average_A','0'))
        proposed=reserve+led
        valid=lo is not None and voltage==Decimal('3.3') and (lo>=Decimal('2.3') if alt else lo>Decimal('2.4'))
        limit=Decimal('2') if alt else Decimal('0.5')
        add('power.design_budget',P if valid and proposed<=limit else F if valid else U,
            f'Conservative controller supply reserve plus proposed LED load {proposed} A versus conditional {limit} A reference; other loads and transients remain unqualified',
            (pattern.evidence('conditional_output_A',str(limit)),calc('reserve_plus_LED_A',proposed)))
        add('power.peak_thermal',U,'Peak loads, current limit, inductor saturation/ripple, efficiency, capacitor bias and junction temperature not fully evidenced')
        if alt:
            nominal=Decimal('.5')*(1+Decimal(511)/91)
            circuit.estimates['feedback_nominal_V']=str(nominal)
            add('power.feedback',U,'511k/91k manufacturer reference gives nominal '+str(nominal)+' V; exact resistor tolerances, feedback accuracy and resulting rail margins require qualification',
                (pattern.evidence('feedback_example','511k/91k, 0.5 V FB'),calc('nominal_V',nominal)))
    if 'controller' in circuit.selections:
        assigned=list(circuit.assignments.values())
        legal=all(p in MODULE_PINS for p in assigned) and len(assigned)==len(set(assigned))
        add('mcu.module_pin_existence',P if legal else F,
            'Assigned GPIO correspond to distinct exposed module pins; strap/UART/USB pins excluded. This checks existence, not complete mux/timing or wiring.',
            (evidence(ESP+'#page=11','module GPIO/pin table',str(MODULE_PINS)),calc('assignment',circuit.assignments)))
        add('mcu.matrix_capability',P if legal else U,
            'GPIO matrix supports digital input/output routing; actual firmware routing, JTAG configuration and pin-level connections remain unverified',
            (evidence(SOC+'#page=36','GPIO matrix','peripheral inputs/outputs route to IO pins'),))
    for bus in circuit.buses:
        bus['module_pin_candidates']={signal:MODULE_PINS.get(gpio) for signal,gpio in circuit.assignments.items() if signal.startswith(bus['name'][:-1])}
        add('bus.'+bus['name']+'.electrical',U,'Clock choice, pull-up sizing, capacitance/rise time, device addresses/straps and signal pin mapping require complete evidence')
    if 'temperature' in circuit.selections:
        pattern=get_pattern(circuit.selections['temperature'])
        add('temperature.interface',U,'TMP117 supports 1..400 kHz I2C and ADD0-dependent address; actual ADD0 strap, bus rate and pull-ups not yet established',
            (pattern.evidence('interface_contract','I2C; ADD0 selection; 1..400 kHz'),))
    for row in circuit.roles:
        add('footprint.'+row.line_id,U,'Exact land pattern/pad mapping and implementation not validated'+('' if row.role.package else '; package requirement also unknown'))
    if any(p.interface=='i2c' for k,p in all_patterns().items() if k in circuit.selections.values()):
        names={r.role.name for r in circuit.roles}
        pullups={'i2c_sda_pullup','i2c_scl_pullup'}<=names
        add('support.i2c_pullups',U if pullups else F,
            'Pull-up roles present but values, topology and rise/sink limits unverified' if pullups else 'No explicit I2C pull-up roles; add a reviewed bus implementation')
    if 'rechargeable' in spec.features and 'led_matrix' not in spec.features:
        add('power.runtime_bound',U,'No characterized total average load profile: battery runtime cannot be established from MCU supply reserve or sensor typical current')


def acceptance(spec,circuit,qualifications=None):
    failed=[c.check for c in circuit.checks if c.status is CheckStatus.FAIL]
    unknown=[c.check for c in circuit.checks if c.status is CheckStatus.UNVERIFIED]
    gaps=[g['id'] for g in spec.gaps()]
    roles_ok=bool(qualifications) and all(q['status']=='verified' and q.get('application_status')=='verified'
        and q.get('sourcing') and all(c['status']=='pass' for c in q['sourcing']) for q in qualifications.values())
    accepted=not (failed or unknown or gaps) and roles_ok
    return {'status':'supported_checks_satisfied' if accepted else 'unresolved',
            'accepted':accepted, 'failed':failed,'unverified':unknown,
            'requirements_needing_confirmation':gaps,'manufacturing_ready':False,
            'role_qualification_complete':roles_ok}
