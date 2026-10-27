"""Readable, authoritative views; raw provenance stays available in the desktop and exports."""

from collections import Counter


def readable_presentation(report):
    from .agent import render
    req=report['requirements'];arch=report.get('architecture') or {};bom=report.get('bom',[])
    checks=arch.get('checks',[]);counts=Counter(c['status'] for c in checks)
    confirmed=[(k,v) for k,v in req['requirements'].items() if v['binding']]
    assumptions=[(k,v) for k,v in req['requirements'].items() if not v['binding']]
    failed=[c for c in checks if c['status']=='fail'];unknown=[c for c in checks if c['status']=='unverified']
    overview=['PRELIMINARY DESIGN — NOT MANUFACTURING-READY',
              f"{len(confirmed)} confirmed choices; {len(assumptions)} provisional assumptions; {len(bom)} component roles.",
              f"Engineering screens: {counts['pass']} conditional pass, {len(failed)} fail, {len(unknown)} unverified.",
              'Role equivalence and application compatibility are separate. No validated schematic/netlist/ERC.',
              '\nFailed constraints:']
    if controller:=report.get('controller'):
        overview.insert(1,'Workflow: '+(controller['stop_reason'] or 'required steps attempted')+
                        ' | operational pipeline complete: '+str(controller['operational_pipeline_complete']))
    if report.get('source_failures'):
        overview.insert(2,f"Supplier operations incomplete: {len(report['source_failures'])} recorded failures. Inspect Sourcing; unavailable evidence is not zero stock.")
    overview.extend('• '+c['check']+': '+c['message'] for c in failed)
    if not failed:overview.append('No failed screen recorded; unresolved evidence still prevents acceptance.')
    overview+=['\nNext useful questions:']
    overview.extend('• '+g['question']+' — '+g['why_it_matters'] for g in req.get('clarification_plan',[])[:5])
    overview+=['\nChanges preserved:']
    overview.extend('• '+h['reason']+'; previous failures: '+', '.join(c['check'] for c in h['circuit']['checks'] if c['status']=='fail')
                    for h in report.get('architecture_history',[]))
    requirements=[]
    for title,items in [('USER-CONFIRMED REQUIREMENTS',confirmed),('PROVISIONAL ASSUMPTIONS — NOT CONFIRMED',assumptions)]:
        requirements.append(title)
        if not items:requirements.append('None recorded.')
        for key,v in items:
            requirements.append(f"{key}: {v['value']} {v['unit'] or ''} | {v['state']}")
            requirements.append('  Source: '+v['source']+(f" | exact quote: {v['quote']}" if v['binding'] else ''))
            if v.get('rationale'):requirements.append('  '+v['rationale'])
        requirements.append('')
    requirements.append('Edit a requirement above using an explicit value/unit. All dependent results are invalidated and rechecked; previous records remain.')
    values=req['requirements']
    rows=values.get('led_rows',{}).get('value');cols=values.get('led_columns',{}).get('value')
    if rows is not None and cols is not None:
        requirements.append(f'Derived physical LED positions: {rows} x {cols} = {int(rows)*int(cols)}. '
            'This calculation is not owner confirmation of count, arrangement, brightness or drive topology.')
    architecture=['PROPOSED SYSTEM ARCHITECTURE']
    architecture.extend(f"{block}: {pattern}" for block,pattern in arch.get('selections',{}).items())
    architecture+=['','Pin allocations and named nets are preliminary intent; no pin-accurate connectivity claim.']
    for bus in arch.get('buses',[]):architecture.append(f"{bus['name']}: {', '.join(bus['participants'])}; pins/clock not fully verified")
    alternatives=['COMPARED ARCHITECTURES — RESEARCH ONLY']
    comparison=report.get('alternatives') or {}
    for row in comparison.get('alternatives',[]):
        stats=Counter(c['status'] for c in row['circuit']['checks'])
        alternatives.extend([row['name']+' | '+str(row['selections'].get('power','no converter')),
            f"  {stats['pass']} conditional pass / {stats['fail']} fail / {stats['unverified']} unverified; accepted: {row['acceptance']['accepted']}",
            '  Resolved: '+(', '.join(row['resolved_failures']) or 'none'),
            '  New failures: '+(', '.join(row['new_failures']) or 'none'),
            '  Remaining failures: '+(', '.join(row['failed_constraints']) or 'none; evidence gaps remain')])
    for option in comparison.get('runtime_options',{}).get('options',[]):
        alternatives+=['',option['name']+' — NOT APPLIED',
            '  Derived necessary bound: '+str(option.get('necessary_bound'))+' '+option.get('unit',''),
            '  '+option['consequences'],'  Runtime/application: unverified; assembled cost unknown.',
            '  Owner confirmation required before any requirement change.']
        trial=option.get('recalculation') or {}
        trial_counts=Counter(c['status'] for c in trial.get('checks',[]))
        alternatives.append(f"  Counterfactual screens: {trial_counts['pass']} conditional pass / {trial_counts['fail']} fail / {trial_counts['unverified']} unverified.")
        for c in trial.get('checks',[]):
            if c['status']=='fail' or c['check'].startswith('power.'):
                alternatives.append('    '+c['status'].upper()+' '+c['check']+': '+c['message'])
    components=['GENERATED ROLE BOM — NOT A COMPLETE CIRCUIT BOM']
    sourcing=['SOURCING RISKS AND BLOCKERS']
    for failure in report.get('source_failures',[]):
        sourcing.append('Supplier operation failed: '+failure.get('catalogue','supplier')+' / '+failure.get('line','all roles')+' / '+failure.get('error_type','unknown')+'. No stock conclusion is supported.')
    triage={r['line']:r for r in report.get('sourcing_triage',[])}
    for row in bom:
        part=row.get('component') or {};q=row.get('qualification') or {};role=row['role']
        components.extend([f"{row['line_id']} | {', '.join(row['refs'])} × {role['quantity']} | {row['block']}.{role['name']}",
            '  '+(f"{part['manufacturer']} / {part['mpn']} / {part['key']}" if part else 'Exact sourced identity unresolved'),
            f"  Required: {role['value']} | package: {role.get('package') or 'unknown'}",
            f"  Role equivalence: {q.get('status','unverified')} | application: {q.get('application_status','unverified')}"])
        if part:components.append(f"  Evidence: {part['source']} | retrieved: {part['retrieved_at']}")
        sourcing.append(row['line_id']+' | '+row['block']+'.'+role['name'])
        if part:sourcing.append(f"  Observed stock: {part.get('stock','unknown')} | assembly classification: {part.get('assembly_class') or 'unknown'}")
        sourcing.extend('  '+r['category']+': '+r['message'] for r in triage.get(row['line_id'],{}).get('reasons',[]))
    engineering=['DETERMINISTIC ENGINEERING SCREENS — PASSES ARE CONDITIONAL ON RECORDED INPUTS']
    for status in ('fail','unverified','pass'):
        engineering+=['',status.upper()]
        for c in checks:
            if c['status']!=status:continue
            engineering.append(c['check']+': '+c['message'])
            engineering.extend('  Source: '+e['locator'] for e in c['evidence'])
    costs=['COST COVERAGE — INCOMPLETE; NOT A QUOTE']
    for scenario in (report.get('costs') or {}).get('scenarios',[]):
        cost=scenario['cost']
        costs.extend([f"{scenario['boards']} boards | {scenario['scenario']}",
            f"  Component subtotal: {cost['parts_total']} (partial bookkeeping only; not a complete component cost)",
            f"  Assembled total: {cost['total'] if cost['total'] is not None else 'unknown'} | complete: {cost['complete']}"])
        costs.extend('  Missing/conditional: '+p for p in cost['problems'])
    if not (report.get('costs') or {}).get('scenarios'):costs.append('No priced scenario available; quantity or commercial evidence is missing.')
    costs.append('A zero known subtotal does not mean a free BOM. Undocumented price currency, MOQ, order multiples and assembly eligibility remain unknown.')
    return {name:'\n'.join(value) for name,value in {'Overview':overview,'Requirements':requirements,
            'Architecture':architecture,'Alternatives':alternatives,'Generated BOM':components,
            'Checks':engineering,'Sourcing':sourcing,'Cost':costs}.items()} | {'Explanation':render(report)}
