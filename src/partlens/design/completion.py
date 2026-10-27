"""Bounded public code leads and independently reviewed passive choices, never supplier snapshots."""
from dataclasses import replace

from .patterns import Role, cap

# These URLs establish research leads only. Runtime observations must come from the official adapter.
ROLE_LEADS={
    ('controller','enable_pullup'):(('C25744','0402WGF1002TCE'),),
    ('led_matrix','current_setting'):(('C25765','0402WGF2002TCE'),),
    ('input_power','cc_pulldown'):(('C25905','0402WGF5101TCE'),),
    ('input_power','protection_diode'):(('C8598','B5819W SL'),),
    ('indicator','led_resistor'):(('C11702','0402WGF1001TCE'),),
    ('power','regulator'):(('C347376','XC6206P332MR'),),
}


def reviewed_roles(circuit):
    rows=[]
    for item in circuit.roles:
        role=item.role
        if role.category=='capacitor' and not role.mpn:
            choice=None
            if role.value=='10uF':
                choice=cap(role.name,'10uF',role.quantity,codes=('C19702',),nets=role.nets)
            elif role.value in {'4.7uF','1uF'}:
                large=role.value=='4.7uF'
                mpn='CL10A475KO8NNNC' if large else 'CL05A105KA5NQNC'
                choice=Role(role.name,'C',role.quantity,'capacitor',role.value,'0603' if large else '0402',
                    'Samsung Electro-Mechanics',mpn,('C19666',) if large else ('C52923',),
                    (('capacitance',role.value),('voltage_rating','16V' if large else '25V'),
                     ('dielectric','X5R'),('tolerance_pct','10%')),role.nets,
                    (*role.omissions,'effective capacitance, tolerance, bias and application remain unverified',
                     *(('manufacturer marks selected 4.7uF ordering family NRND',) if large else ())),
                    'https://product.samsungsem.com/mlcc/'+('CL10A475KO8NNN' if large else 'CL05A105KA5NQN')+'.do')
            if choice and (not role.package or choice.package==role.package):role=choice
        rows.append(replace(item,role=role))
    circuit.roles=rows
    from .patterns import get_pattern
    if any(get_pattern(pid).interface=='i2c' for pid in circuit.selections.values()):
        from .architecture import GeneratedRole
        from .patterns import IMU
        from ..core.model import Evidence,EvidenceKind
        number=max((int(ref[1:]) for row in rows for ref in row.refs if ref.startswith('R') and ref[1:].isdigit()),default=0)
        for signal in ('SDA','SCL'):
            name='i2c_'+signal.lower()+'_pullup'
            if any(row.role.name==name for row in rows):continue
            number+=1
            role=Role(name,'R',1,'resistor','I2C pull-up value unresolved; bus capacitance/rise-time/sink limits needed',
                nets=('3V3','I2C_'+signal),omissions=('pull-up value and bus electrical contract not established',))
            rows.append(GeneratedRole('L'+str(len(rows)+1),'bus',None,role,('R'+str(number),),
                Evidence(EvidenceKind.DATASHEET,IMU+'#page=34','I2C bus pullup role','pull-ups to the I/O supply','2026-10-24')))
    # Added support roles must also appear in named net intent. Pin numbers remain deliberately unknown.
    endpoints={}
    for row in rows:
        for net in row.role.nets:
            endpoints.setdefault(net,[]).extend({'reference':ref,'port':net,'pin':None} for ref in row.refs)
    circuit.connections=[{'net':net,'endpoints':values,'validated':False} for net,values in sorted(endpoints.items())]


def role_inventory(circuit):
    return [{'line':r.line_id,'block':r.block,'role':r.role.name,'required_value':r.role.value,
             'required_parameters':dict(r.role.parameters),'required_package':r.role.package or None,
             'expected_manufacturer':r.role.manufacturer or None,'expected_mpn':r.role.mpn or None,
             'codes':list(r.role.codes)+[code for code,_ in ROLE_LEADS.get((r.block,r.role.name),())],
             'lead_sources':['https://jlcpcb.com/partdetail/'+code for code,_ in ROLE_LEADS.get((r.block,r.role.name),())],
             'remaining_requirements':list(r.role.omissions) or
                ([] if r.role.mpn else ['exact electrical/mechanical/pin and application contract must be established before selection'])}
            for r in circuit.roles]
