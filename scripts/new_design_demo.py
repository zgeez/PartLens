"""Original deterministic reference for New Design. No LLM, supplier or sponsor success is claimed."""

import json
from pathlib import Path

from partlens.agent import Agent,ScriptedProvider,ToolCall
from partlens.design.agent import render
from partlens.design.cli import export
from partlens.design.patterns import PATTERNS
from partlens.design.session import DesignSession
from partlens.records import RunRecorder
from partlens.sources.audit import AuditedCatalog
from partlens.sources.catalog import LocalCatalog


def main():
    rec=RunRecorder.create('.partlens/design-reference-runs')
    rec.log('design_reference',live_llm=False,live_supplier=False,zetaris=False,hmem=False,
            default_author='scripted scenario, not owner confirmation',licence='Apache-2.0 original example')
    session=DesignSession(rec,[AuditedCatalog(LocalCatalog([],name='synthetic-empty'))],
        description='Design a rechargeable smart LED badge with Bluetooth phone control, an LED matrix, NFC, microphone and IMU.',
        design_id='new-reference-'+rec.run_id)
    runner=Agent(session,ScriptedProvider([]),lambda question:None)
    values={'led_rows':'8','led_columns':'8','led_type':'mono','nfc_mode':'tag','microphone_use':'sound_reactive',
            'logic_voltage':'3.3V','battery_min':'3.0V','battery_max':'4.2V','battery_capacity':'500mAh',
            'runtime':'4h','board_quantity':'1','width':'50mm','height':'50mm','led_average_current':'3.2mA',
            'charging_use':'off_while_charging'}
    calls=[('start_new_design',{}),('record_design_requirements',{'requirements_json':json.dumps([
        {'parameter':k,'value':v,'rationale':'scripted provisional example'} for k,v in values.items()])}),
        ('propose_design_architecture',{'selections_json':json.dumps({p.block:p.id for p in PATTERNS.values()})}),
        ('generate_design_bom',{}),('source_design_roles',{}),('qualify_design',{}),('design_cost_scenarios',{})]
    for name,args in calls:
        result=runner._execute(ToolCall('reference-'+str(rec.seq),name,args),actor='deterministic_reference')
        if result.get('is_error'):raise RuntimeError(result['content'])
    report=session.design_report()
    rec.log('design_reference_result',report=report)
    artifacts=export(session,Path('.partlens/new-design-reference')/rec.run_id)
    print('DETERMINISTIC ORIGINAL EXAMPLE — no model, supplier, Zetaris or H-MEM operation.\n')
    print(render(report))
    print(json.dumps({'record':str(rec.path),'artifacts':artifacts}))


if __name__=='__main__':main()
