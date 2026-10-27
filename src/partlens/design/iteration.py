"""Bounded alternatives preserve requirements. A research trial is never an accepted design."""
from decimal import Decimal

from ..core.model import to_jsonable,digest
from .architecture import propose,check_circuit
from .patterns import all_patterns
from .completion import reviewed_roles
from .validation import validate,acceptance


def alternatives(spec,current):
    failed=[c.check for c in current.checks if c.status.value=='fail']
    choices=[('current',dict(current.selections))]
    if 'power' in current.selections:
        for p in all_patterns(spec.features).values():
            if p.block=='power' and p.id!=current.selections['power']:
                choices.append(('power:'+p.id,{**current.selections,'power':p.id}))
    rows=[]
    for name,selections in choices[:3]:
        circuit=propose(spec,selections,{'power':'Compare reviewed converter capability without changing any requirement'})
        reviewed_roles(circuit);check_circuit(spec,circuit);validate(spec,circuit)
        gate=acceptance(spec,circuit)
        rows.append({'id':digest({'requirements':spec.fingerprint,'choices':selections})[:16],
            'name':name,'selections':selections,'requirements_fingerprint':spec.fingerprint,
            'circuit':circuit.view(),'acceptance':gate,'failed_constraints':gate['failed'],
            'resolved_failures':sorted(set(failed)-set(gate['failed'])),
            'new_failures':sorted(set(gate['failed'])-set(failed)),
            'investigation_only':True,'requirements_changed':False})
    remedies=[]
    if 'power.runtime_bound' in failed:
        capacity=spec.get('battery_capacity');target=spec.get('runtime');hi=spec.get('battery_max');voltage=spec.get('logic_voltage')
        current_A=current.estimates.get('led_average_A')
        if all(v is not None for v in (capacity,target,hi,voltage,current_A)):
            minimum=target*voltage*Decimal(current_A)/hi*1000
            remedies.append({'affected':['battery','power','led_matrix','charging','mechanical'],
                'requirement':'runtime','minimum_ideal_LED_only_capacity_mAh':str(minimum),
                'derivation':f'{target} h * {voltage} V * {current_A} A / {hi} V * 1000',
                'meaning':'necessary ideal lower bound only; exact cell, other loads, losses, discharge profile and mechanical fit unresolved',
                'selected_battery':None,'requirement_changed':False})
    return {'schema':'partlens.architecture-alternatives/1','requirements_fingerprint':spec.fingerprint,
            'trigger_failures':failed,'affected_blocks':sorted(set(current.selections)&{'power','controller','led_matrix','charging','protection','input_power','rail_output','indicator'}),
            'alternatives':to_jsonable(rows),'energy_remedies':remedies,'accepted_design':None,
            'rule':'Only a fully evidenced accepted gate can select a final design. Investigating an alternative does not accept it.'}
