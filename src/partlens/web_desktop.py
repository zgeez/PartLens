"""Local web presentation. The single explicit bridge dispatches existing Python engineering operations."""
from contextlib import contextmanager
import base64
import hmac
import json
import os
from pathlib import Path
import threading

from .agent import Agent,ScriptedProvider,ToolCall
from .chat_engine import ChatEngine,ChatAgent
from .conversations import ConversationStore
from .core.model import to_jsonable
from .paths import resource_root,example_bom
from .records import RunRecorder
from .secrets import redact
from .settings import AppSettings,DEFAULTS,SECRET_KEYS,MODES,save_settings,import_env
from .session import Session,part_view
from .ui import review_snapshot,format_view
from .projects import ProjectStore,qualification_scope


def frontend_html():
    root=resource_root();folder=root/'assets/desktop'
    html=(folder/'index.html').read_text(encoding='utf-8')
    css=(folder/'app.css').read_text(encoding='utf-8');js=(folder/'app.js').read_text(encoding='utf-8')
    for key,name in [('LOGO','logo-96.png'),('HERO','hero-480.png')]:
        html=html.replace('{{'+key+'}}','data:image/png;base64,'+base64.b64encode((root/'assets/brand'/name).read_bytes()).decode())
    return html.replace('/* APP_CSS */',css).replace('/* APP_JS */',js)


def allowed_input(path):
    path=Path(path).resolve()
    if any('experiments' in p.casefold() or 'benchmark' in p.casefold() or 'badge' in p.casefold() for p in path.parts):
        raise ValueError('Excluded private material cannot be imported')
    return path


def report_views(report):
    if not report:return {}
    if report.get('mode')=='new_design':
        from .design.views import readable_presentation
        return readable_presentation(report)
    return {k:format_view(k,v) for k,v in report.items() if k not in {'record','mode','Run record'}}


class DesktopBridge:
    """Only request() is exposed to the page; state/configuration objects remain private."""
    def __init__(self,home,settings,catalogs,*,token=None,engine_factory=ChatEngine):
        self._home=Path(home).resolve();self._state=self._home/'state';self._settings=settings
        self._catalogs=catalogs;self._lock=threading.RLock();self._token=token;self._window=None
        self._store=ConversationStore(self._state);self._engine=engine_factory(self._state,catalogs,self._store)
        self._chat=None;self._report=None;self._report_views={};self._messages=[];self._activity=[]
        self._busy=False;self._job_kind=None;self._cancel=threading.Event();self._answer_ready=threading.Event()
        self._answer=None;self._question=None;self._question_target=None;self._close_pending=False
        self._status='Ready when you are.';self._revision=0;self._services=None;self._selected_bom=None
        self._bom_snapshot={};self._staged_settings=None;self._bom_agent=None
        self._projects=ProjectStore(self._state);self._project=None;self._bom_revision=None
        self._bom_historical=False;self._project_job=None
        self._demo=example_bom(self._home,synthetic=settings.preferences['supplier_mode']=='offline')
        self._new_bom()
        last=self._projects.last_project()
        if last:
            try:self._project_select({'id':last})
            except ValueError as exc:
                self._project=last;self._bom_revision=self._projects.select(last);self._bom_historical=True
                self._status='Saved project needs recovery. Records preserved. '+self._error_text(str(exc))

    def request(self,action,payload=None,token=None):
        if self._token is not None and (not isinstance(token,str) or not hmac.compare_digest(token,self._token)):
            return {'ok':False,'error':'Untrusted desktop request'}
        if self._window is not None and str(self._window.get_current_url()) not in {'None','about:blank'}:
            return {'ok':False,'error':'Desktop actions are unavailable outside the bundled interface'}
        if not isinstance(action,str) or not isinstance(payload or {},dict):return {'ok':False,'error':'Invalid desktop request'}
        try:
            with self._lock:
                if action=='snapshot' and (payload or {}).get('since')==self._revision:
                    return {'ok':True,'unchanged':True}
                handlers={
                    'snapshot':lambda p:None,'new_chat':self._new_chat,'select_chat':self._select_chat,
                    'send':self._send,'answer':self._answer_question,'stop':self._stop,'select_bom':self._select_bom,
                    'demo_bom':self._demo_bom,'revalidate':self._revalidate,'services':self._check_services,
                    'settings_open':self._settings_open,'settings_import':self._settings_import,
                    'settings_save':self._settings_save,'notices':self._notices,'open_report':self._open_report,
                    'bom_load':self._bom_load,'bom_manual':self._bom_manual,'bom_live':self._bom_live,
                    'bom_cost':self._bom_cost,'bom_recall':self._bom_recall,'bom_new':self._bom_new,
                    'project_create':self._project_create,'project_select':self._project_select,
                    'bom_human_review':self._bom_human_review,'bom_export':self._bom_export,
                    'bom_audit':lambda p:self._bom_snapshot.get('Run record',{})}
                if action not in handlers:raise ValueError('Unsupported desktop action')
                if self._busy and action not in {'snapshot','answer','stop','notices'}:
                    raise ValueError('Finish or stop the current operation first')
                result=handlers[action](payload or {})
                return {'ok':True,'result':result,'state':self._snapshot()}
        except Exception as exc:
            # Settings request bodies and credential values are never journalled or reflected.
            return {'ok':False,'error':self._error_text(str(exc),payload)[:1600] or type(exc).__name__}

    def _error_text(self,text,payload=None):
        values=[*self._settings.credentials.values(),*((self._staged_settings.credentials.values()) if self._staged_settings else [])]
        if isinstance(payload,dict) and isinstance(payload.get('credentials'),dict):values+=list(payload['credentials'].values())
        for value in values:
            if isinstance(value,str) and len(value)>=4:text=text.replace(value,'[REDACTED]')
        return redact(text)

    def _touch(self):self._revision+=1
    def _new_bom(self):
        self._bom_session=Session(RunRecorder.create(self._state/'web-bom-runs'),self._catalogs)
        self._bom_session.recorder.log('ui_session',interface='local WebView2 desktop',synthetic=self._settings.preferences['supplier_mode']=='offline')
        self._bom_agent=None;self._bom_historical=False;self._publish_bom()
    def _publish_bom(self):
        self._bom_snapshot=to_jsonable(review_snapshot(self._bom_session))
        for decision in self._bom_snapshot.get('Qualifications',[]):
            decision['current_context']=self._decision_current(decision)
        self._bom_snapshot['Qualification scope']=qualification_scope()
        if self._project_job:
            self._projects.checkpoint(self._bom_revision,self._project_job,self._bom_session,self._bom_snapshot)
        self._touch()
    def _decision_current(self,decision):
        session=self._bom_session
        original=session.baseline.get(decision.get('line'));candidate=session.observed_parts.get(decision.get('candidate'))
        return bool(decision.get('decision_id') in session.decisions and original and candidate
                    and decision.get('context')==session.decision_context(decision['line'],original,candidate)
                    and decision.get('comparison')==to_jsonable({'original':part_view(original),'candidate':part_view(candidate)}))
    def _project_view(self):
        return {'projects':self._projects.list(),'id':self._project,'revision':self._bom_revision,
                'revisions':self._projects.revisions(self._project) if self._project else [],
                'historical':self._bom_historical,'reviews':self._projects.reviews(self._bom_revision) if self._bom_revision else [],
                'jobs':self._projects.jobs(self._bom_revision) if self._bom_revision else [],
                'scope':qualification_scope()}
    def _project_create(self,p):
        self._project=self._projects.create(p.get('title'));self._bom_revision=None;self._new_bom()
        self._status='Project created. Import a CSV to save its first revision.'
        return self._project
    def _project_select(self,p):
        revision=self._projects.select(p.get('id'),p.get('revision'))
        checkpoint=self._projects.latest(revision) if revision else None
        self._project=p['id'];self._bom_revision=revision;self._new_bom()
        if checkpoint:
            self._bom_snapshot=checkpoint['report']
            self._bom_snapshot['Qualifications']=[{**d,'current_context':False} for d in self._bom_snapshot.get('Qualifications',[])]
            self._bom_snapshot['Run record']={'path':checkpoint['record_path'],'historical':True}
        self._bom_historical=bool(revision)
        self._status='Saved revision. Results are historical; run checks before review or export.' if revision else 'Import a BOM to begin.'
        self._touch()
    def _project_import(self,path):
        path=allowed_input(path)
        if not self._project:self._project=self._projects.create(path.stem)
        revision=self._projects.add_revision(self._project,path)
        self._bom_revision=revision;self._new_bom()
        return self._projects.input_path(revision)
    def _bom_prepare(self):
        if not self._bom_revision:self._project_import(self._demo)
        if self._bom_historical:
            self._new_bom()
        if not self._bom_session.bom:
            quantity=self._projects.quantity_record(self._bom_revision)
            self._bom_tool('import_bom',path=str(self._projects.input_path(self._bom_revision)),name='project:'+self._project)
            self._bom_tool('match_parts');self._bom_tool('find_missing_information')
            if quantity:
                self._bom_session.restore_quantity(quantity);self._publish_bom()
    def _bom_human_review(self,p):
        if self._bom_historical:raise ValueError('Run a fresh recheck before reviewing saved results')
        decision=next((d for d in reversed(self._bom_snapshot.get('Qualifications',[])) if d.get('decision_id')==p.get('decision_id')),None)
        if not decision or not self._decision_current(decision):raise ValueError('Decision evidence or context changed; recheck before review')
        result=self._projects.review(self._bom_revision,self._bom_session.recorder.run_id,p.get('decision_id'),
            p.get('action'),p.get('reviewer'),p.get('reason'),acknowledge=p.get('acknowledge',False))
        self._touch();return result
    def _bom_export(self,p):
        if self._bom_historical:raise ValueError('Run a fresh recheck before exporting saved results')
        latest={}
        for review in self._projects.reviews(self._bom_revision):latest.setdefault(review['decision_id'],review)
        decisions={d['decision_id']:d for d in self._bom_snapshot.get('Qualifications',[])}
        for key,review in latest.items():
            if review['action']=='accept' and review['run_id']==self._bom_session.recorder.run_id:
                if key not in decisions or not self._decision_current(decisions[key]):
                    raise ValueError('Observed evidence or context changed; recheck before export')
        result=self._projects.export(self._bom_revision,self._bom_session.recorder.run_id)
        self._status='Reviewed proposal exported. Application qualification and manufacturing release remain incomplete.'
        self._touch();return result
    def _history(self):return [{'id':c.id,'title':c.title,'mode':c.mode} for c in self._store.list()]
    def _settings_view(self):
        s=self._staged_settings or self._settings
        return {'preferences':dict(s.preferences),'configured':{k:bool(s.credentials.get(k)) for k in SECRET_KEYS},
                'modes':MODES,'storage':str(self._home)}
    def _snapshot(self):
        from .design.requirements import FIELDS
        prefs=self._settings.preferences
        return redact(to_jsonable({'revision':self._revision,'busy':self._busy,'job':self._job_kind,'status':self._status,
            'model':prefs['PARTLENS_LOCAL_MODEL'],'supplier':MODES[prefs['supplier_mode']],
            'history':self._history(),'chat':{'id':self._chat.id,'title':self._chat.title,'mode':self._chat.mode} if self._chat else None,
            'messages':self._messages,'report':self._report,'views':self._report_views,'activity':self._activity[-120:],
            'question':{'text':self._question,'target':self._question_target} if self._question else None,
            'attachment':self._selected_bom.name if self._selected_bom else None,
            'bom':{k:v for k,v in self._bom_snapshot.items() if k!='Run record'},
            'project':self._project_view(),
            'bom_views':{k:format_view(k,v) for k,v in self._bom_snapshot.items() if k!='Run record'},
            'services':self._services,'requirement_fields':{k:str(v[1]) for k,v in FIELDS.items()},
            'can_revalidate':bool(self._report and self._report.get('mode')=='new_design' and self._report.get('architecture'))}))
    def _load_chat(self):
        self._messages=[e for e in self._store.events(self._chat) if e['type']=='chat_message'] if self._chat else []
        self._report=self._store.report(self._chat) if self._chat else None
        self._report_views=report_views(self._report);self._touch()
    def _new_chat(self,p):
        self._chat=None;self._selected_bom=None;self._activity=[];self._load_chat();self._status='Ready when you are.'
    def _select_chat(self,p):
        chat=next((c for c in self._store.list() if c.id==p.get('id')),None)
        if not chat:raise ValueError('Conversation not found')
        # Parse before replacing current state. A corrupt journal is preserved for recovery.
        self._store.events(chat);self._store.report(chat)
        self._chat=chat;self._selected_bom=None;self._activity=[];self._load_chat()
        self._status='Saved results. Recheck evidence before relying on current availability.'
    def _message(self,role,text,kind='message',**metadata):
        self._store.message(self._chat,role,text,kind=kind,**metadata);self._load_chat()
    def _send(self,p):
        text=p.get('text');mode=p.get('mode','design')
        if not isinstance(text,str) or not text.strip() or len(text)>5000:raise ValueError('Enter a message of 1–5,000 characters')
        text=text.strip()
        if mode not in {'design','bom'}:raise ValueError('Unsupported conversation mode')
        if not self._chat:
            if mode=='bom' and not self._selected_bom:raise ValueError('Attach a BOM or choose the demo first')
            self._chat=self._store.create(text,mode)
        self._message('user',text)
        if self._store.latest_artifact(self._chat):
            self._start(lambda:self._engine.explain(self._chat,text,self._notify,self._cancel),'commentary')
        else:
            if not isinstance(p.get('proposals',True),bool):raise ValueError('Invalid assumptions setting')
            self._start(lambda:self._engine.run(self._chat,text,self._ask,self._notify,self._cancel,
                bom_path=self._selected_bom,allow_proposals=p.get('proposals',True)),'chat')
    def _start(self,job,kind):
        if self._busy:raise ValueError('An operation is already running')
        if kind=='bom':
            if not self._bom_revision:self._project_import(self._demo)
            if self._bom_historical:
                # Keep the saved report for inspection until the explicit operation starts.
                self._new_bom()
            self._project_job=self._projects.start_job(self._bom_revision,self._bom_session.recorder.run_id)
        self._busy=True;self._job_kind=kind;self._cancel.clear();self._status='Starting…';self._touch()
        def run():
            outcome='completed';failure=''
            try:
                result=job()
                with self._lock:
                    if kind in {'chat','revalidate'}:
                        self._store.append(self._chat,'chat_artifact',**{k:v for k,v in result.items() if k!='text'})
                        self._message('assistant',result['text'],kind='report')
                        self._status='Stopped; partial evidence saved.' if result.get('cancelled') else 'Report saved. Missing evidence remains unverified.'
                    elif kind=='commentary':
                        self._message('assistant',result,kind='commentary');self._status='Commentary saved. Engineering results are unchanged.'
                    elif kind=='services':self._services=result;self._status='Service checks saved; availability is separate from engineering acceptance.'
                    else:self._publish_bom();self._status='BOM operation finished. Review checks and unresolved inputs.'
            except Exception as exc:
                outcome='failed'
                with self._lock:
                    error=self._error_text(type(exc).__name__+': '+str(exc))[:1800]
                    failure=error
                    if kind in {'chat','commentary','revalidate'} and self._chat:self._message('assistant','Operation incomplete. '+error+'\nEarlier evidence is preserved.',kind='error')
                    if kind=='bom':
                        self._bom_session.recorder.log('ui_error',error_type=type(exc).__name__,message=error);self._publish_bom()
                    self._status='Operation incomplete. '+error
            finally:
                with self._lock:
                    if self._project_job and kind=='bom':
                        try:
                            self._publish_bom()
                            self._projects.finish_job(self._project_job,'cancelled' if self._cancel.is_set() else outcome,failure)
                        except Exception as exc:
                            self._status='Checkpoint incomplete; existing records preserved. '+self._error_text(str(exc))
                        finally:self._project_job=None
                    self._busy=False;self._question=None;self._question_target=None;self._job_kind=None;self._touch()
                    if self._close_pending and self._window:self._window.destroy()
        threading.Thread(target=run,daemon=True).start()
    def _notify(self,kind,value):
        with self._lock:
            if kind=='activity':self._activity.append(value);self._status=f"{value['actor']}: {value['name'].replace('_',' ')} · {value['phase']}"
            elif kind=='status':self._status=value
            if kind=='activity' and self._project_job and value.get('phase') in {'finished','failed'}:
                self._publish_bom()
            self._touch()
    def _ask(self,question):
        with self._lock:
            if self._cancel.is_set():return None
            self._answer=None;self._answer_ready.clear();self._question=question
            self._question_target='bom' if self._job_kind=='bom' else 'chat'
            if self._project_job:self._projects.finish_job(self._project_job,'waiting')
            if self._question_target=='chat':self._message('assistant',question,kind='question')
            self._status='A requirement needs your answer. You can leave it unanswered.';self._touch()
        self._answer_ready.wait()
        if self._project_job:self._projects.finish_job(self._project_job,'running')
        return None if self._cancel.is_set() else self._answer
    def _answer_question(self,p):
        if not self._busy or not self._question:raise ValueError('No question is awaiting an answer')
        answer=p.get('text')
        if answer is not None and (not isinstance(answer,str) or not answer.strip() or len(answer)>5000):raise ValueError('Enter an answer or leave it unanswered')
        if self._question_target=='chat':
            self._message('user' if answer is not None else 'system',answer if answer is not None else 'Requirement left unanswered.',
                kind='requirement_answer' if answer is not None else 'unanswered')
        self._answer=answer;self._question=None;self._question_target=None;self._answer_ready.set();self._touch()
    def _stop(self,p):
        self._cancel.set();self._answer_ready.set();self._question=None;self._status='Stopping after the current operation…';self._touch()
    def _closing(self):
        with self._lock:
            if self._busy:self._close_pending=True;self._stop({});return False
            return True
    def _pick_file(self,types):
        if not self._window:raise ValueError('A desktop window is required for file selection')
        import webview
        selected=self._window.create_file_dialog(webview.FileDialog.OPEN,allow_multiple=False,file_types=types)
        return allowed_input(selected[0]) if selected else None
    def _select_bom(self,p):
        path=self._pick_file(('CSV BOM (*.csv)',))
        if path:
            if path.suffix.casefold()!='.csv':raise ValueError('Select a CSV BOM')
            self._selected_bom=path;self._touch()
        return path.name if path else None
    def _demo_bom(self,p):self._selected_bom=self._demo;self._touch()
    def _revalidate(self,p):
        if not self._chat or not self._report or not self._report.get('architecture'):raise ValueError('Generate a design architecture first')
        parameter=p.get('parameter');answer=p.get('answer')
        if parameter is not None:
            from .design.interaction import typed_answer
            if not isinstance(answer,str) or typed_answer(parameter,answer) is None:raise ValueError('Use an allowed value with the required unit')
            self._message('user',answer,kind='requirement_edit',parameter=parameter)
        else:self._message('system','Independent recheck requested. This does not call the model.',kind='recheck')
        self._start(lambda:self._engine.revalidate(self._chat,self._notify,self._cancel,parameter=parameter,answer=answer),'revalidate')
    def _check_services(self,p):
        from .preflight import run_preflight
        self._start(lambda:run_preflight(self._state),'services')
    def _settings_open(self,p):self._staged_settings=None;return self._settings_view()
    def _settings_import(self,p):
        path=self._pick_file(('Local environment (*.local)',))
        if path:self._staged_settings=import_env(path,self._staged_settings or self._settings)
        return self._settings_view()
    def _settings_save(self,p):
        prefs=p.get('preferences');changes=p.get('credentials',{});clear=p.get('clear',[])
        if not isinstance(prefs,dict) or set(prefs)!=set(DEFAULTS) or not isinstance(changes,dict) or set(changes)-set(SECRET_KEYS):raise ValueError('Unsupported settings fields')
        if not isinstance(clear,list) or any(k not in SECRET_KEYS for k in clear):raise ValueError('Unsupported credential fields')
        if any(not isinstance(v,str) for v in changes.values()):raise ValueError('Credential values must be text')
        old=self._staged_settings or self._settings;credentials=dict(old.credentials)
        for key in clear:credentials.pop(key,None)
        credentials.update({k:v for k,v in changes.items() if v})
        value=AppSettings(dict(prefs),credentials).validate()
        from .desktop import catalogs
        prepared=catalogs(value,self._state)
        save_settings(self._home,value);value.apply();self._settings=value;self._catalogs=prepared;self._engine.catalogs=prepared
        self._staged_settings=None;self._services=None;self._demo=example_bom(self._home,synthetic=prefs['supplier_mode']=='offline')
        self._new_bom();self._new_chat({});self._status='Settings applied. Previous conversations and evidence are preserved.';self._touch()
        return self._settings_view()
    def _notices(self,p):
        root=resource_root();folder=root/'licenses'
        files=sorted(folder.iterdir()) if folder.exists() else [root/'LICENSE',root/'NOTICE',root/'THIRD_PARTY.md']
        return [{'name':f.name,'text':f.read_text(encoding='utf-8',errors='replace')} for f in files if f.is_file()]
    def _open_report(self,p):
        if p.get('workspace')=='bom':folder=self._bom_session.recorder.path.parent
        else:
            if not self._chat:raise ValueError('No report is available yet')
            artifact=self._store.latest_artifact(self._chat)
            if not artifact:raise ValueError('No report is available yet')
            folder=self._store.owned_path(artifact['report']).parent
        if os.name=='nt':os.startfile(self._store.owned_path(folder))

    def _bom_tool(self,tool_name,**args):
        if self._bom_agent is None:
            self._bom_agent=ChatAgent(self._bom_session,ScriptedProvider([]),self._ask)
            self._bom_agent.chat_notify=self._notify;self._bom_agent.chat_cancel=self._cancel
        output=self._bom_agent._execute(ToolCall('desktop-'+str(self._bom_session.recorder.seq+1),tool_name,args),actor='controller')
        if output.get('is_error'):raise ValueError(json.loads(output['content']).get('error','Operation failed'))
        return json.loads(output['content'])
    @contextmanager
    def _bom_memory(self):
        from .memory.hmem import HMemBridge,DecisionMemory
        scope='project:'+self._project if self._project else 'desktop-bom'
        with HMemBridge(self._state/'project-memory'/self._project if self._project else self._state/'web-bom-memory') as bridge:
            self._bom_session.memory=DecisionMemory(bridge,scope)
            self._bom_session.recorder.log('memory_engine',info=bridge.info)
            try:yield
            finally:self._bom_session.memory=None
    def _bom_new(self,p):
        self._new_bom();self._bom_historical=bool(self._bom_revision)
        self._status='New session for this revision. Original inputs and prior records preserved; recheck to continue.'
    def _bom_load(self,p):
        if p.get('demo',False):path=self._demo
        else:
            path=self._pick_file(('CSV BOM (*.csv)',))
            if not path:return
        path=self._project_import(path)
        def run():
            self._bom_tool('import_bom',path=str(path),name='project:'+self._project)
            self._bom_tool('match_parts');self._bom_tool('find_missing_information')
        self._start(run,'bom')
    def _bom_manual(self,p):
        def run():
            with self._bom_memory():
                self._bom_prepare()
                self._bom_tool('find_missing_information')
                if self._bom_session._boards() is None:
                    reply=self._bom_tool('ask_user',question='How many boards will be assembled? Enter a whole number.',gap_id='design.board_quantity')['answer']
                    if reply is None:raise ValueError('Build quantity left unanswered; no requirement confirmed')
                    self._bom_tool('record_requirement',subject='design',parameter='board_quantity',op='==',value=reply.strip(),user_quote=reply)
                for line,original in list(self._bom_session.baseline.items()):
                    if self._cancel.is_set():break
                    if not original:continue
                    self._bom_tool('check_availability',part_key=original.key,line_id=line)
                    for candidate in self._bom_tool('search_candidates',line_id=line,limit=5)['candidates']:
                        self._bom_tool('check_substitute',line_id=line,candidate_key=candidate['key'])
                self._bom_tool('estimate_cost')
                self._bom_session.recorder.log('ui_review_complete',mode='deterministic; no model called')
        self._start(run,'bom')
    def _bom_live(self,p):
        def run():
            with self._bom_memory():
                self._bom_prepare()
                from .workflow import WorkflowRequest
                runner=self._engine._runner(ChatAgent,self._bom_session,self._ask,self._notify,self._cancel,max_steps=40,max_tool_calls=100)
                path=self._bom_session.bom.source if self._bom_session.bom else str(self._demo)
                runner.send('Review the BOM with actual supplier evidence and independent checks. Ask for missing build quantity. '
                    'Record exact owner answers, keep other missing conditions unresolved, compare hypothetical 60 boards without changing the owner quantity.',
                    workflow=WorkflowRequest(path,design='project:'+self._project,costs=True),origin='ui_task')
                self._bom_agent=None
        self._start(run,'bom')
    def _bom_cost(self,p):
        def run():
            self._bom_prepare();self._bom_tool('compare_cost_scenarios',hypothetical_boards=60)
        self._start(run,'bom')
    def _bom_recall(self,p):
        checkpoint=self._projects.latest(self._bom_revision) if self._bom_revision else None
        old=checkpoint['run_id'] if checkpoint else self._bom_session.recorder.run_id
        source_runs=[]
        for decision in (checkpoint['report'].get('Qualifications',[]) if checkpoint else []):
            # An identical recheck reinforces an earlier memory instead of creating a duplicate.
            # Query its actual persisted source run, not the newest controller run by assumption.
            prior=next((m for m in decision.get('prior_decisions_from_memory',[])
                        if m.get('memory_id')==decision.get('stored_in_memory')),None)
            source=prior.get('source','') if prior else ''
            run=source.split(':')[2] if source.startswith('partlens:run:') else old
            if run not in source_runs:source_runs.append(run)
        if not source_runs:source_runs=[old]
        self._new_bom()
        def run():
            with self._bom_memory():
                self._bom_prepare()
                memories=[]
                for run in source_runs[:5]:
                    memories.extend(self._bom_tool('recall_decisions',query='replacement decisions',run_id=run)['memories'])
                checked=0;seen=set()
                for memory in memories:
                    identity=(memory.get('line'),memory.get('candidate'));original=self._bom_session.baseline.get(memory.get('line'))
                    if identity in seen:continue
                    seen.add(identity)
                    if original and original.key==memory.get('original') and memory.get('candidate'):
                        self._bom_tool('reverify_decision',memory_id=memory['id']);checked+=1
                        if checked==3:break
                self._bom_session.recorder.log('ui_recall_complete',mode='real H-MEM retrieval and independent recheck; no model',prior_run=old,queried_memory_source_runs=source_runs[:5],memories_returned=len(memories),rechecked=checked)
        self._start(run,'bom')


def launch(home,settings,catalogs,*,acceptance=None):
    import webview
    from .records import new_run_id
    from webview.guilib import initialize
    gui=initialize('edgechromium')
    if gui.renderer!='edgechromium':raise RuntimeError('Install Microsoft WebView2 Runtime and .NET Framework 4.6.2+. No legacy renderer was opened.')
    home=Path(home).resolve();bridge=DesktopBridge(home,settings,catalogs,token=webview.token)
    webview.settings.update(ALLOW_DOWNLOADS=False,ALLOW_FILE_URLS=False,OPEN_DEVTOOLS_IN_DEBUG=False,
        OPEN_EXTERNAL_LINKS_IN_BROWSER=True)
    window=webview.create_window('PartLens',html=frontend_html(),js_api=bridge,width=1320,height=860,
        min_size=(900,620),background_color='#f7f8f5',hidden=acceptance is not None,text_select=True)
    bridge._window=window;window.events.closing+=bridge._closing
    if acceptance:
        def check():
            try:
                if not window.events.loaded.wait(45):raise TimeoutError('WebView2 did not finish loading the local interface')
                finished=threading.Event()
                def done(value):acceptance['result']=value;finished.set()
                window.evaluate_js(acceptance['script'],callback=done)
                if not finished.wait(90):raise TimeoutError('Renderer acceptance did not finish')
            except Exception as exc:acceptance['error']=redact(type(exc).__name__+': '+str(exc))
            finally:window.destroy()
        func=check
    else:func=None
    # Explicit modern renderer: never fall back to Internet Explorer or a remote frontend.
    cache=home/'webview'/new_run_id()
    if not cache.resolve().is_relative_to(home):raise ValueError('Browser cache is outside the local application profile')
    cache.mkdir(parents=True,exist_ok=False)
    try:
        webview.start(func,gui='edgechromium',debug=False,private_mode=True,
            storage_path=str(cache),icon=str(resource_root()/'assets/brand/PartLens.ico'))
    finally:bridge._projects.close()
    return acceptance
