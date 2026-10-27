"""New Design window inside the existing desktop; isolated requirements and no inherited demo quantity."""

import json
from pathlib import Path
import queue
import threading

from ..core.model import to_jsonable
from ..local_provider import OllamaProvider
from ..memory.hmem import HMemBridge, DecisionMemory
from ..records import RunRecorder
from ..sources.audit import AuditedCatalog
from .agent import DesignAgent
from .cli import export
from .session import DesignSession
from .views import readable_presentation
from .interaction import revise_from_owner
from .requirements import FIELDS


def presentation(report,explanation=None):
    """UI and CLI use the same authoritative report and factual renderer."""
    from .agent import render
    arch=report.get('architecture') or {}
    return {'Requirements':report['requirements'],'Architecture':arch,
        'Alternatives':{'comparisons':report.get('alternatives'),'history':report.get('architecture_history'),
                        'acceptance':report.get('acceptance')},
        'Generated BOM':report['bom'],'Checks':arch.get('checks',[]),
        'Sourcing':{'current':[{k:r.get(k) for k in ('line_id','source_status','component')} for r in report['bom']],
                    'research_history':report.get('sourcing_history')},
        'Cost':report['costs'],'Explanation':explanation or render(report)}


def open_new_design(parent,catalogs,state,fees=None):
    import tkinter as tk
    from tkinter import ttk,simpledialog

    window=tk.Toplevel(parent)
    window.title('PartLens | New Design — preliminary engineering')
    window.geometry('1180x850')
    ttk.Label(window,text='New Design — requirements → architecture → preliminary BOM',font=('Segoe UI',15,'bold')).pack(anchor='w',padx=15,pady=10)
    ttk.Label(window,text='Describe a new product. This does not open private design files or inherit the Easyduino quantity.').pack(anchor='w',padx=15)
    description=tk.Text(window,height=4,wrap='word')
    description.pack(fill='x',padx=15,pady=8)
    delegated=tk.BooleanVar(value=False)
    ttk.Checkbutton(window,text='Delegate missing choices as provisional assumptions (never user-confirmed)',variable=delegated).pack(anchor='w',padx=15)
    status=tk.StringVar(value='No design generated. All output is preliminary; no schematic/ERC validation.')
    notebook=ttk.Notebook(window)
    texts={}
    for name in ('Overview','Requirements','Architecture','Alternatives','Generated BOM','Checks','Sourcing','Cost','Explanation','Provenance','Audit'):
        frame=ttk.Frame(notebook);notebook.add(frame,text=name)
        scroll=ttk.Scrollbar(frame);scroll.pack(side='right',fill='y')
        text=tk.Text(frame,wrap='word',yscrollcommand=scroll.set);text.pack(fill='both',expand=True)
        scroll.configure(command=text.yview);text.configure(state='disabled');texts[name]=text
    events=queue.Queue();answer_ready=threading.Event();answer={'value':None};state_values={};closed=threading.Event()

    def ask(question):
        if closed.is_set():return None
        answer_ready.clear();answer['value']=None
        events.put(('question',question))
        answer_ready.wait()
        return answer['value']

    def work():
        idea=description.get('1.0','end').strip()
        if not idea:status.set('Enter a product description first.');return
        allow=delegated.get()
        button.configure(state='disabled');edit_button.configure(state='disabled');parameter_box.configure(state='disabled');description.configure(state='disabled')
        status.set('Local agent working; independent checks and unresolved roles will be saved. No cloud fallback.')
        def run():
            bridge=None
            try:
                rec=RunRecorder.create(Path(state)/'new-design-runs')
                root=Path(state)/'new-design'/rec.run_id
                bridge=HMemBridge(root/'hmem')
                design_id='new-'+rec.run_id
                s=DesignSession(rec,[AuditedCatalog(c) for c in catalogs],description=idea,design_id=design_id,
                                memory=DecisionMemory(bridge,design_id),fees=fees,engineering_mode=True,interaction_mode=True)
                state_values['session']=s
                state_values['root']=root
                rec.log('memory_engine',info=bridge.info,process_id=bridge._proc.pid)
                agent=DesignAgent(s,OllamaProvider(),ask,allow_proposals=allow,should_stop=closed.is_set,
                                  max_steps=40,max_tool_calls=80,max_total_tokens=300000)
                state_values['agent']=agent
                explanation=agent.send('Develop a new preliminary electronic design: '+idea,origin='new_design_ui_task')
                artifact=export(s,root/'artifacts')
                events.put(('done',(s.design_report(),explanation,str(rec.path),artifact)))
            except Exception as exc:
                from ..secrets import redact
                events.put(('error',redact(type(exc).__name__+': '+str(exc))))
            finally:
                if bridge:bridge.close()
        threading.Thread(target=run,daemon=True).start()

    def edit_requirement():
        if 'session' not in state_values:return
        parameter=selected_parameter.get()
        kind=FIELDS[parameter][1]
        hint=', '.join(kind) if isinstance(kind,tuple) else str(kind)
        value=simpledialog.askstring('Revise requirement',
            f'{parameter}: enter an explicit value ({hint}).\nThis records your exact answer and reruns dependent checks.\nCancel keeps the current design.',parent=window)
        if not value:return
        from .interaction import typed_answer
        if typed_answer(parameter,value) is None:
            status.set('Edit not applied: use an allowed value or the exact unit shown.');return
        button.configure(state='disabled');edit_button.configure(state='disabled');parameter_box.configure(state='disabled')
        description.configure(state='disabled')
        status.set('Owner edit: previous results are being invalidated and independently rechecked. No model call.')
        for text in texts.values():
            text.configure(state='normal');text.delete('1.0','end')
            text.insert('1.0','Previous display cleared. Owner revision and independent revalidation in progress.');text.configure(state='disabled')
        def revise():
            bridge=None
            try:
                s=state_values['session'];root=state_values['root']
                bridge=HMemBridge(root/'hmem');s.memory=DecisionMemory(bridge,s.design_name)
                s.recorder.log('memory_engine',info=bridge.info,process_id=bridge._proc.pid,operation='owner_revision')
                report=revise_from_owner(s,parameter,value,state_values['agent']._execute)
                artifacts=export(s,root/'revisions'/str(s.recorder.seq)/'artifacts')
                events.put(('done',(report,None,str(s.recorder.path),artifacts)))
            except Exception as exc:
                from ..secrets import redact
                events.put(('error',redact(type(exc).__name__+': '+str(exc))))
            finally:
                if bridge:bridge.close()
        threading.Thread(target=revise,daemon=True).start()

    button=ttk.Button(window,text='Generate with local agent',command=work)
    button.pack(anchor='w',padx=15,pady=8)
    edit_row=ttk.Frame(window);edit_row.pack(fill='x',padx=15)
    ttk.Label(edit_row,text='Inspect or revise a requirement:').pack(side='left')
    selected_parameter=tk.StringVar(value='led_type')
    parameter_box=ttk.Combobox(edit_row,textvariable=selected_parameter,values=sorted(FIELDS),state='readonly',width=25)
    parameter_box.pack(side='left',padx=8)
    edit_button=ttk.Button(edit_row,text='Edit and revalidate',command=edit_requirement,state='disabled')
    edit_button.pack(side='left')
    ttk.Label(window,textvariable=status,wraplength=1020).pack(anchor='w',padx=15,pady=5)
    notebook.pack(fill='both',expand=True,padx=15,pady=10)

    def pump():
        try:
            while True:
                kind,value=events.get_nowait()
                if kind=='question':
                    answer['value']=simpledialog.askstring('Design requirement',value,parent=window)
                    answer_ready.set()
                elif kind=='error':
                    status.set('Incomplete: '+value)
                    if s:=state_values.get('session'):
                        for name,content in readable_presentation(s.design_report()).items():
                            text=texts[name];text.configure(state='normal');text.delete('1.0','end')
                            text.insert('1.0',content);text.configure(state='disabled')
                else:
                    report,explanation,record,artifacts=value
                    arch=report.get('architecture') or {}
                    shown={**readable_presentation(report),
                        'Provenance':presentation(report,explanation),
                        'Audit':{'run':record,'artifacts':artifacts,'mode':'actual local agent; supplier operations depend on configuration'}}
                    for name,content in shown.items():
                        text=texts[name];text.configure(state='normal');text.delete('1.0','end')
                        text.insert('1.0',content if isinstance(content,str) else json.dumps(to_jsonable(content),indent=2,ensure_ascii=False))
                        text.configure(state='disabled')
                    stop=(report.get('controller') or {}).get('stop_reason')
                    status.set(('Incomplete workflow: '+stop+'. ' if stop else 'Preliminary results saved. ')+
                               'Missing evidence and failed checks prevent manufacturing release. '+record)
                if kind in {'done','error'}:
                    button.configure(state='normal');description.configure(state='normal')
                    edit_button.configure(state='normal' if 'session' in state_values else 'disabled')
                    parameter_box.configure(state='readonly')
        except queue.Empty:pass
        if window.winfo_exists():window.after(100,pump)
    def close():
        closed.set();answer['value']=None;answer_ready.set();window.destroy()
    window.protocol('WM_DELETE_WINDOW',close)
    window.after(100,pump)
    return window
