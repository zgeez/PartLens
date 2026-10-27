"""Clarification, counterfactual bounds and sourcing reasons never change engineering verdicts."""

from decimal import Decimal, ROUND_CEILING, ROUND_FLOOR
from copy import deepcopy
from dataclasses import replace
import json

from ..core.model import to_jsonable
from ..agent import ToolCall
from ..session import ToolError
from .requirements import QUESTIONS, State, parse


def clarification_plan(spec, circuit=None):
    """Rank only relevant, unconfirmed gaps; the agent asks a bounded subset."""
    ranks={'led_type':100,'runtime':98,'led_count':97,'led_rows':96,'led_columns':95,
           'led_average_current':94,'charging_use':93,'nfc_mode':92,'microphone_use':91,
           'input_interface':96,'input_voltage_max':94,'rail_current_max':92,
           'secondary_rail_voltage':90,'input_voltage_min':89,'rail_selection':88,
           'battery_capacity':88,'width':86,'height':85,'board_quantity':80,'parts_budget':78,
           'brightness':77,'battery_min':70,'battery_max':69}
    reasons={
        'led_type':'LED protocol and driver architecture',
        'led_count':'physical LED count must agree with rows times columns; do not substitute 128 for an unconfirmed 32',
        'led_arrangement':'physical geometry is separate from dimensions and electrical multiplexing',
        'led_drive':'electrical topology and current programming, separate from LED color and brightness',
        'led_rows':'channel count, load and physical size',
        'led_columns':'channel count, load and physical size',
        'led_average_current':'brightness, average energy and driver operating point',
        'brightness':'viewing conditions; brightness cannot be inferred from current alone',
        'runtime':'required energy and battery size',
        'charging_use':'power-path architecture and charging safety',
        'nfc_mode':'tag and active reader require different architectures',
        'microphone_use':'audio interface, processing and data requirements',
        'battery_capacity':'available energy; exact cell safety remains independent',
        'input_interface':'connector selection, USB-C CC termination and reverse-polarity protection',
        'input_voltage_min':'regulator dropout margin and undervoltage startup limit',
        'input_voltage_max':'regulator maximum operating input voltage and linear thermal dissipation',
        'secondary_rail_voltage':'secondary breadboard rail topology and pass-through voltage drop',
        'rail_current_max':'regulator continuous current capability and thermal ceiling',
        'rail_selection':'breadboard rail header strapping and switch topology',
        'width':'mechanical envelope and battery accommodation',
        'height':'mechanical envelope and battery accommodation',
        'board_quantity':'stock and purchase-quantity scenarios',
        'parts_budget':'cost tradeoffs; unknown commercial terms remain unknown',
    }
    failed={c.check for c in circuit.checks if c.status.value=='fail'} if circuit else set()
    rows=[]
    for gap in spec.gaps(interview=True):
        key=gap['id'];priority=ranks.get(key,60)
        if 'power.runtime_bound' in failed and key in {'battery_capacity','led_average_current','runtime'}:
            priority+=20
        if ('power.design_budget' in failed or 'power.thermal_dissipation' in failed) and key in {'rail_current_max','input_voltage_max'}:
            priority+=20
        rows.append({**gap,'priority':priority,'why_it_matters':reasons.get(key,'operating envelope'),
                     'question':QUESTIONS[key]})
    return sorted(rows,key=lambda r:(-r['priority'],r['id']))


def typed_answer(parameter, answer):
    """Accept explicit typed answers only, without extracting numbers from arbitrary prose."""
    value=answer.strip()
    low=value.casefold().replace('-','_').replace(' ','_')
    if parameter=='led_type' and value.casefold()=='monochrome':value='mono'
    elif parameter=='input_interface':
        if low in {'usb_c','usbc','type_c','usb_type_c'}:value='usb_c'
        elif low in {'barrel_jack','barrel','dc_jack'}:value='barrel_jack'
        elif low in {'dual_input','dual','both'}:value='dual_input'
    elif parameter=='rail_selection':
        if low in {'jumper_selectable','jumper','jumpers'}:value='jumper_selectable'
        elif low in {'fixed_dual_rail','fixed'}:value='fixed_dual_rail'
        elif low in {'switch_controlled','switch','switched'}:value='switch_controlled'
    try:parse(parameter,value)
    except ValueError:return None
    return value


def runtime_options(spec, circuit):
    """Necessary LED-only bounds, never selected cells, sufficient designs or fabricated prices."""
    if 'breadboard_power' in spec.features:
        vin_hi,rail,load_ma=(spec.get(k) for k in ('input_voltage_max','logic_voltage','rail_current_max'))
        if any(v is None for v in (vin_hi,rail,load_ma)) or vin_hi<=rail:
            return {'status':'unverified','reason':'input voltage envelope, rail voltage and load current required','options':[]}
        ind_ma=Decimal('0.5') if 'indicator' in circuit.selections else Decimal('0')
        thermal_max_ma=max(Decimal('1'),(Decimal('0.25')/(vin_hi-rail)*Decimal('1000')-ind_ma).quantize(Decimal('.001'),rounding=ROUND_FLOOR))
        bound_ma=min(Decimal('249.5'),thermal_max_ma)
        ev={'kind':'calculation','locator':'calc:breadboard-options:'+circuit.fingerprint,
            'inputs':{'input_voltage_max_V':str(vin_hi),'rail_V':str(rail),'rail_current_max_mA':str(load_ma),'indicator_mA':str(ind_ma)},
            'assumptions':'Linear LDO SOT-23 250 mW package dissipation ceiling and 250 mA current limit'}
        def recalc(parameter,value):
            from .architecture import propose,check_circuit
            from .completion import reviewed_roles
            from .validation import validate
            trial=deepcopy(spec)
            old=trial.current[parameter]
            trial.revision+=1
            trial.entries.append(replace(old,value=value,state=State.INFERRED,quote='',source='calculation:counterfactual',
                                         revision=trial.revision,rationale='Unapplied necessary-bound scenario, not a user requirement'))
            tested=propose(trial,circuit.selections,{})
            reviewed_roles(tested);check_circuit(trial,tested);validate(trial,tested)
            return {'counterfactual':True,'applied':False,'accepted':False,'trial_value':str(value),
                    'checks':to_jsonable(tested.checks),'estimates':tested.estimates}
        common={'applied':False,'accepted':False,'application_status':'unverified','selected_component':None,
                'evidence':ev,'runtime_check':{'status':'unverified','reason':'Counterfactual thermal/current bound only; board copper and ambient derating remain unknown'},
                'assembly_cost':None}
        item=spec.current.get('rail_current_max')
        return {'status':'conditional_analysis','requirements_changed':False,'options':[
            {**common,'name':'Lower continuous 3.3 V rail current (for SOT-23 LDO)','parameter':'rail_current_max',
             'necessary_bound':str(bound_ma),'unit':'mA',
             'changes_confirmed_requirement':bool(item and item.binding),'requires_owner_confirmation':True,
             'consequences':'At most this continuous load current fits within both the 250 mA XC6206 limit and the 250 mW SOT-23 dissipation limit at maximum input voltage.',
             'recalculation':recalc('rail_current_max',bound_ma)},
            {**common,'name':'Alternative switched-mode converter architecture','parameter':None,'necessary_bound':None,
             'requires_owner_confirmation':True,'changes_confirmed_requirement':False,
             'recalculation':{'checks':to_jsonable(circuit.checks),'baseline_only':True,
                              'note':'Reviewed buck-boost alternatives (TPS63802 / TPS63031) are evaluated in the architecture comparison above.'},
             'consequences':'Switching to a reviewed buck-boost converter clears the 500 mA current and linear SOT-23 thermal screens without lowering the owner load requirement.'}
        ]}
    capacity,target,hi,rail=(spec.get(k) for k in ('battery_capacity','runtime','battery_max','logic_voltage'))
    current=circuit.estimates.get('led_average_A')
    rows,cols=spec.get('led_rows'),spec.get('led_columns')
    if any(v is None for v in (capacity,target,hi,rail,current,rows,cols)):
        return {'status':'unverified','reason':'LED load, battery envelope and runtime required','options':[]}
    current=Decimal(current)
    if not current:return {'status':'unverified','reason':'positive LED load required','options':[]}
    count=Decimal(rows*cols*(3 if spec.get('led_type')=='rgb' else 1))
    minimum=target*rail*current/hi*1000
    if minimum<=capacity:
        return {'status':'no_LED_only_shortfall','requirements_changed':False,'options':[],
                'reason':'Optimistic LED-only bound does not fail; actual total-load runtime remains unverified.'}
    max_average=capacity/1000*hi/(target*rail)
    factor=min(Decimal(1),max_average/current)
    ev={'kind':'calculation','locator':'calc:runtime-options:'+circuit.fingerprint,
        'inputs':{'capacity_mAh':str(capacity),'runtime_h':str(target),'battery_max_V':str(hi),
                  'rail_V':str(rail),'LED_average_A':str(current),'LED_channels':str(count)},
        'assumptions':'100% conversion, maximum cell voltage throughout discharge, LED-only load; optimistic necessary bounds'}
    def recalculate(parameter,value):
        from .architecture import propose,check_circuit
        from .completion import reviewed_roles
        from .validation import validate
        trial=deepcopy(spec)
        old=trial.current[parameter]
        trial.revision+=1
        trial.entries.append(replace(old,value=value,state=State.INFERRED,quote='',source='calculation:counterfactual',
                                     revision=trial.revision,rationale='Unapplied necessary-bound scenario, not a user requirement'))
        tested=propose(trial,circuit.selections,{})
        reviewed_roles(tested);check_circuit(trial,tested);validate(trial,tested)
        return {'counterfactual':True,'applied':False,'accepted':False,'trial_value':str(value),
                'checks':to_jsonable(tested.checks),'estimates':tested.estimates}
    capacity_trial=recalculate('battery_capacity',minimum.quantize(Decimal('.000001'),rounding=ROUND_CEILING))
    current_trial=recalculate('led_average_current',(max_average/count*1000).quantize(Decimal('.000000000001'),rounding=ROUND_FLOOR))
    common={'applied':False,'accepted':False,'application_status':'unverified','selected_component':None,
            'evidence':ev,
            'runtime_check':{'status':'unverified','reason':'Derived boundary is necessary only; average total load, efficiency and usable capacity are unknown'},
            'assembly_cost':None}
    def option(name,parameter,value,unit,consequences):
        item=spec.current.get(parameter)
        return {**common,'name':name,'parameter':parameter,'necessary_bound':str(value),'unit':unit,
                'changes_confirmed_requirement':bool(item and item.binding),
                'requires_owner_confirmation':True,'consequences':consequences}
    return {'status':'conditional_analysis','requirements_changed':False,'options':[
        {**option('Larger battery','battery_capacity',minimum,'mAh',
            'At least this ideal LED-only capacity is necessary. Exact cell availability, discharge/charge limits, protection, size, mass and cost are unknown.'),
            'recalculation':capacity_trial},
        {**option('Lower average LED current','led_average_current',max_average/count*1000,'mA per channel',
            'Maximum ideal LED-only average per channel. Lower average current can reduce brightness; peak current, PWM and total-load validation remain required.'),
            'recalculation':current_trial},
        {**option('Lower effective duty','led_average_current',factor,'relative average-current factor',
            'Scale the present average LED load by at most this factor. This is not an absolute PWM duty: the present duty, LED peak current, scan ratio and brightness are unknown.'),
            'absolute_duty_cycle':None,'recalculation':current_trial},
        {**common,'name':'Alternative power architecture','parameter':None,'necessary_bound':None,
         'requires_owner_confirmation':True,'changes_confirmed_requirement':False,
         'recalculation':{'checks':to_jsonable(circuit.checks),'baseline_only':True,
                          'note':'Both reviewed converter trials are recalculated in the architecture comparison above.'},
         'consequences':'Higher output capability can clear the supply-reserve screen but cannot establish runtime. Real efficiency, transients, thermal design and support-part sizing remain unverified.'}
    ]}


def sourcing_triage(report):
    """Separate blocked requirements/identity/evidence from observed candidate and supply problems."""
    history=(report.get('sourcing_history') or [])
    latest={r['line']:r for r in history[-1]['rows']} if history else {}
    rows=[]
    for row in report.get('bom',[]):
        role=row['role'];part=row.get('component');q=row.get('qualification') or {}
        researched=latest.get(row['line_id'],{})
        candidates=researched.get('candidate_evaluations',[])
        reasons=[]
        def add(kind,message):reasons.append({'category':kind,'message':message})
        if not part:
            add('missing_exact_identity','No usable official observation for the expected identity.' if role.get('mpn') else 'No justified exact manufacturer/MPN selected.')
            if not role.get('package') or (not role.get('parameters') and not role.get('mpn')):
                add('missing_manufacturer_evidence','Electrical/package/reference contract is incomplete; no random part search.')
            if role['name'] in {'cell','charge_program','led_elements','current_setting','breadboard_rail_headers','rail_selector_header'}:
                add('missing_user_requirement','Cell/charge or LED operating target needs confirmation and independent evidence.')
        for failure in report.get('source_failures',[]):
            if failure.get('line') in {None,row['line_id']}:
                add('supplier_operation_failed',failure.get('catalogue','supplier')+': '+failure.get('error_type','operation failed')+'; do not interpret this as no stock or no matching part.')
        for candidate in candidates:
            if candidate['status']=='rejected':add('incompatible_candidate',candidate['candidate']+' failed deterministic role checks; not selected.')
            elif not candidate.get('identity_matches'):add('missing_exact_identity',candidate['candidate']+' does not match the required identity.')
        if part:
            if part.get('stock') is not None and Decimal(str(part['stock']))<=0:
                add('out_of_stock','Observed stock is zero; identity/engineering status is separate.')
            for check in q.get('sourcing',[]):
                if check['status']=='fail':add('supply_constraint',check['message'])
            for unknown in part.get('commercial_unknowns',[]):add('manufacturing_terms_unknown',unknown)
            if not part.get('currency'):add('manufacturing_terms_unknown','Price currency is undocumented.')
            if q.get('status')!='verified':add('missing_manufacturer_evidence','Role equivalence is not verified; inspect check evidence.')
            if q.get('application_status')!='verified':add('application_unverified','Full operating-point and implementation evidence is missing.')
        for omission in role.get('omissions',[]):add('missing_manufacturer_evidence',omission)
        rows.append({'line':row['line_id'],'role':row['block']+'.'+role['name'],
                     'research_priority':'bounded_exact_lookup' if role.get('codes') and role.get('mpn') else 'establish_contract_first',
                     'candidate_evaluations':candidates,'reasons':reasons})
    return rows


def revise_from_owner(session, parameter, answer, execute):
    """Operator-only edit path; not a model tool. Rebuild all affected results without accepting a design."""
    value=typed_answer(parameter,answer)
    if value is None:raise ToolError('Use the exact allowed value or a number with the specified unit; no inferred answer.')
    selections=dict(session.circuit.selections) if session.circuit else None
    session.recorder.log('user_message',text=answer,origin='user',input_kind='desktop_requirement_edit',parameter=parameter)
    def call(name,inputs=None):
        block=execute(ToolCall('owner-revision-'+str(session.recorder.seq+1),name,inputs or {}),actor='controller')
        if block.get('is_error'):raise ToolError(json.loads(block['content']).get('error','revision operation failed'))
        return json.loads(block['content'])
    out=call('record_design_requirement',{'parameter':parameter,'value':value,'user_quote':answer,'action':'replace',
            'rationale':'Actual owner edit; invalidate and independently revalidate dependent results'})
    if not out['entry']['binding']:raise ToolError('The supplied answer did not confirm this typed requirement.')
    if selections:
        call('select_design_patterns',{'selections':selections,'justification':'Recheck the previous architecture after an actual owner edit'})
        compared=call('compare_design_alternatives')
        improved=next((a for a in compared['alternatives'] if a['resolved_failures'] and not a['new_failures']
                       and a['selections']!=session.circuit.selections),None)
        if improved and session.correction_attempts<2:
            call('investigate_design_alternative',{'alternative_id':improved['id']})
        for name in ('generate_design_bom','source_design_roles','qualify_design','design_cost_scenarios'):
            call(name)
        if session.memory:call('remember_design')
    report=session.design_report()
    session.recorder.log('owner_revision_result',parameter=parameter,report=report,actor='controller',model_calls=0)
    return report


def ai_default_for_gap(spec, gap_id: str) -> tuple[str, str]:
    """Return a sensible engineering provisional default (value, rationale) when the operator delegates a requirement."""
    is_bb = "breadboard_power" in getattr(spec, "features", [])
    defaults = {
        "logic_voltage": ("3.3V", "AI provisional default: standard 3.3 V primary logic rail"),
        "secondary_rail_voltage": ("5V", "AI provisional default: standard 5 V secondary breadboard rail"),
        "input_voltage_min": ("4.75V", "AI provisional default: USB-C VBUS 5 V lower operating bound"),
        "input_voltage_max": ("5.25V", "AI provisional default: USB-C VBUS 5 V upper operating bound"),
        "rail_current_max": ("500mA", "AI provisional default: 500 mA maximum continuous load current"),
        "input_interface": ("usb_c", "AI provisional default: USB-C 5 V sink input with 5.1 kOhm CC1/CC2 pulldowns"),
        "rail_selection": ("jumper_selectable", "AI provisional default: 1x3P 2.54 mm shunt jumper headers per breadboard side"),
        "width": ("53mm" if is_bb else "45mm", "AI provisional default: standard compact PCB width"),
        "height": ("32mm" if is_bb else "45mm", "AI provisional default: standard compact PCB height"),
        "board_quantity": ("5", "AI provisional default: 5 prototype boards"),
        "parts_budget": ("4USD" if is_bb else "12USD", "AI provisional default: target component-only budget per board"),
        "runtime": ("24h", "AI provisional default: 24-hour battery runtime target"),
        "battery_capacity": ("500mAh", "AI provisional default: 500 mAh LiPo pouch cell"),
        "battery_min": ("3.0V", "AI provisional default: 3.0 V LiPo discharge cutoff"),
        "battery_max": ("4.2V", "AI provisional default: 4.2 V LiPo full charge voltage"),
        "charging_use": ("usb_c_onboard", "AI provisional default: onboard USB-C linear LiPo charger"),
        "led_rows": ("5", "AI provisional default: 5 LED matrix rows"),
        "led_columns": ("5", "AI provisional default: 5 LED matrix columns"),
        "led_count": ("25", "AI provisional default: 25 LEDs"),
        "led_type": ("monochrome", "AI provisional default: monochrome SMD LEDs"),
        "led_arrangement": ("matrix_grid", "AI provisional default: matrix grid arrangement"),
        "led_brightness": ("indoor_indicator", "AI provisional default: indoor indicator brightness"),
        "led_drive": ("direct_gpio", "AI provisional default: direct GPIO / matrix drive"),
        "led_average_current": ("2mA", "AI provisional default: 2 mA average current per LED"),
        "nfc_mode": ("tag_only", "AI provisional default: passive NFC tag mode"),
        "microphone_use": ("pdm_digital", "AI provisional default: digital PDM MEMS microphone"),
    }
    return defaults.get(gap_id, ("1", f"AI provisional default for {gap_id}"))

