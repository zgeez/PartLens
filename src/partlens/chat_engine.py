"""Chat presentation over the existing bounded agents; only existing deterministic tools decide engineering."""
from collections import Counter
import hashlib
import json
from pathlib import Path

from .agent import Agent,ToolCall
from .local_provider import OllamaProvider
from .records import RunRecorder,read_events
from .memory.hmem import HMemBridge,DecisionMemory
from .session import Session
from .sources.audit import AuditedCatalog
from .design.agent import DesignAgent
from .design.session import DesignSession
from .design.cli import export
from .design.interaction import revise_from_owner
from .core.model import to_jsonable
from .secrets import redact


class UserCancelled(RuntimeError):pass


class _Observed:
    def _execute(self,call,*,actor='model'):
        if self.chat_cancel.is_set():raise UserCancelled('Stopped by user before the next operation')
        self.chat_notify('activity',{'name':call.name,'actor':actor,'phase':'started'})
        result=super()._execute(call,actor=actor)
        self.chat_notify('activity',{'name':call.name,'actor':actor,'phase':'failed' if result.get('is_error') else 'finished'})
        return result


class ChatAgent(_Observed,Agent):pass
class ChatDesignAgent(_Observed,DesignAgent):pass


class ObservedProvider:
    def __init__(self,base,notify,cancel):self.base,self.notify,self.cancel=base,notify,cancel
    def __getattr__(self,name):return getattr(self.base,name)
    def next_turn(self,*args):
        if self.cancel.is_set():raise UserCancelled('Stopped before the next model request')
        self.notify('status','Local model working…')
        return self.base.next_turn(*args)


def design_summary(report,*,cancelled=False):
    checks=(report.get('architecture') or {}).get('checks',[]);counts=Counter(c['status'] for c in checks)
    qualified=sum(r.get('qualification',{}).get('status')=='verified' for r in report.get('bom',[]) if r.get('qualification'))
    partial=bool((report.get('controller') or {}).get('stop_reason'))
    lines=['Stopped with a partial report.' if cancelled else 'A partial engineering report has been saved.' if partial else 'Your preliminary engineering report is ready.',
        f"{len(report.get('bom',[]))} component roles · {counts['fail']} failed screens · {counts['unverified']} unresolved screens.",
        f'{qualified} roles meet their checked reference specification. Full application suitability is separate.']
    lines+=['\n'+c['message'] for c in checks if c['status']=='fail'][:3]
    if not report.get('architecture'):lines.append('No architecture was established. Review the recorded failure and unanswered requirements.')
    if (report.get('controller') or {}).get('stop_reason'):lines.append('Workflow: '+str(report['controller']['stop_reason']))
    lines.append('\nOpen Evidence for requirements, sources, checks and cost coverage. This is not a manufacturing-ready circuit.')
    return '\n\n'.join(lines)


def commentary_context(report):
    """Bound context without changing the authoritative report or hiding its unresolved state."""
    if report.get('mode')!='new_design':
        return {'recorded_bom_review':{k:v for k,v in report.items() if k not in {'Run record','Evidence'}},
                'scope':'Recorded results; recheck current sources before using inventory/qualification'}
    return {'scope':'Recorded preliminary engineering results; not current inventory or manufacturing acceptance',
        'requirements':report['requirements']['requirements'],'acceptance':report.get('acceptance'),
        'checks':(report.get('architecture') or {}).get('checks',[]),
        'costs':report.get('costs'),'parts':[{'line':r['line_id'],'role':r['role']['name'],
            'mpn':(r.get('component') or {}).get('mpn',r['role'].get('mpn')),
            'role_status':(r.get('qualification') or {}).get('status','unverified'),
            'application':(r.get('qualification') or {}).get('application_status','unverified'),
            'source':(r.get('component') or {}).get('source')} for r in report.get('bom',[])]}


class ChatEngine:
    def __init__(self,state,catalogs,store,*,provider_factory=OllamaProvider):
        self.state=Path(state).resolve();self.catalogs=catalogs;self.store=store;self.provider_factory=provider_factory

    def _runner(self,cls,session,ask,notify,cancel,**kwargs):
        provider=ObservedProvider(self.provider_factory(),notify,cancel)
        runner=cls(session,provider,ask,**kwargs);runner.chat_notify=notify;runner.chat_cancel=cancel
        return runner

    def _finish(self,chat,session,root,*,cancelled=False):
        if isinstance(session,DesignSession):
            path=Path(export(session,root/'artifacts'))/'report.json'
            report=json.loads(path.read_text(encoding='utf-8'));text=design_summary(report,cancelled=cancelled)
        else:
            from .ui import review_snapshot
            root.joinpath('artifacts').mkdir(parents=True,exist_ok=False)
            report=review_snapshot(session);report['record']=str(session.recorder.path);report['mode']='bom_review'
            path=root/'artifacts/report.json';path.write_text(json.dumps(to_jsonable(report),indent=2),encoding='utf-8')
            decisions=report.get('Qualifications',[]);counts=Counter(r.get('status','unverified') for r in decisions)
            text=('Stopped with a partial BOM review.' if cancelled else 'Your BOM review has been recorded.')+(
                f"\n\n{counts['verified']} specification-equivalent · {counts['rejected']} rejected · {counts['unverified']} unverified alternatives.\n\n"
                'Application suitability, sourcing and costs remain separate. Open Evidence for the complete checks and unresolved inputs.')
        return {'report':str(path),'record':str(session.recorder.path),'mode':chat.mode,'text':text,'cancelled':cancelled}

    def run(self,chat,text,ask,notify,cancel,*,bom_path=None,allow_proposals=True):
        rec=RunRecorder.create(self.state/'chat-runs');root=self.state/'chat-artifacts'/rec.run_id
        rec.log('chat_workflow_started',mode=chat.mode,conversation_id=chat.id,task=text)
        memory=self.state/'chat-memory'/chat.id
        with HMemBridge(memory) as bridge:
            rec.log('memory_engine',info=bridge.info)
            catalogs=[AuditedCatalog(c) for c in self.catalogs]
            if chat.mode=='design':
                session=DesignSession(rec,catalogs,description=text,design_id='chat-'+chat.id,
                    memory=DecisionMemory(bridge,'chat-'+chat.id),engineering_mode=True,interaction_mode=True)
                runner=self._runner(ChatDesignAgent,session,ask,notify,cancel,allow_proposals=allow_proposals,
                    should_stop=cancel.is_set,max_steps=40,max_tool_calls=80,max_total_tokens=300000)
                try:runner.send('Develop a preliminary electronic design from this description: '+text,origin='chat_task')
                except UserCancelled:rec.log('chat_cancelled',actor='user')
            else:
                if bom_path is None:raise ValueError('Attach a CSV BOM before starting its review')
                from .workflow import WorkflowRequest
                session=Session(rec,catalogs,memory=DecisionMemory(bridge,'chat-'+chat.id))
                runner=self._runner(ChatAgent,session,ask,notify,cancel,max_steps=40,max_tool_calls=100)
                try:runner.send(text,workflow=WorkflowRequest(str(bom_path),design='chat-'+chat.id,costs=True),origin='user')
                except UserCancelled:rec.log('chat_cancelled',actor='user')
            return self._finish(chat,session,root,cancelled=cancel.is_set())

    def explain(self,chat,text,notify,cancel):
        report=self.store.report(chat)
        if report is None:return 'No engineering report is available yet. Start a new review to establish one.'
        rec=RunRecorder.create(self.state/'chat-runs');rec.log('user_message',text=text,origin='user')
        context=json.dumps(to_jsonable(commentary_context(report)),ensure_ascii=False)
        # Full supplier/check details remain in the inspector; the model cannot change this context.
        if len(context)>65000:context=json.dumps({'summary':design_summary(report) if chat.mode=='design' else 'BOM report available in Evidence',
            'acceptance':report.get('acceptance'),'requirements':report.get('requirements'),'detail_limit':True})
        system=('Explain the supplied recorded PartLens report. You are read-only: no tool calls, no new engineering facts, '
            'no changed requirements, no live inventory claims and no qualification/cost overrides. Cite available source '
            'references when relevant. Say when evidence is absent. To change a requirement, direct the user to Update requirement; '
            'only that independent revalidation action can apply it. Your prose is commentary, not an engineering decision.')
        provider=ObservedProvider(self.provider_factory(),notify,cancel)
        turn=provider.next_turn(system,[{'role':'user','content':'Recorded report:\n'+context}, {'role':'user','content':text}],[])
        rec.log('chat_commentary_turn',text=turn.text,usage=turn.usage,tool_calls_requested=len(turn.tool_calls),authority='none')
        if turn.tool_calls or turn.stop_reason not in {'end_turn','stop_sequence'}:raise ValueError('Commentary was incomplete; no engineering state changed')
        return redact(turn.text)

    def _original_events(self,path,seen=None):
        seen=seen or set();path=self.store.owned_path(path)
        if str(path) in seen or len(seen)>12:raise ValueError('Invalid recorded context chain')
        seen.add(str(path));events=read_events(path);combined=list(events)
        for event in events:
            if event['type']=='design_context_restored':
                source=self.store.owned_path(event['source_record'])
                if hashlib.sha256(source.read_bytes()).hexdigest()!=event['source_sha256']:raise ValueError('Original context record changed')
                combined+=self._original_events(source,seen)
        return combined

    def revalidate(self,chat,notify,cancel,*,parameter=None,answer=None):
        old=self.store.report(chat)
        if not old or old.get('mode')!='new_design':raise ValueError('This action requires a generated New Design report')
        from .design.restore import restore_requirements
        source=self.store.owned_path(old['record']);events=self._original_events(source)
        spec=restore_requirements(old['requirements'],events)
        rec=RunRecorder.create(self.state/'chat-runs');root=self.state/'chat-artifacts'/rec.run_id
        with HMemBridge(self.state/'chat-memory'/chat.id) as bridge:
            session=DesignSession(rec,[AuditedCatalog(c) for c in self.catalogs],description=spec.description,
                design_id=spec.design_id,memory=DecisionMemory(bridge,spec.design_id),_record_description=False,
                engineering_mode=True,interaction_mode=True)
            session.spec=spec
            rec.log('design_context_restored',source_record=str(source),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
                    requirements=spec.view(),inherited_verification=False,new_owner_answer=False)
            rec.log('new_design_start',description=spec.description,design_id=spec.design_id,description_source=spec.description_source)
            from .tools import DESIGN_NAMES
            runner=self._runner(ChatAgent,session,lambda _:None,notify,cancel,tool_names=DESIGN_NAMES|{'ask_user'})
            def call(name,args=None):
                result=runner._execute(ToolCall('chat-controller-'+str(rec.seq+1),name,args or {}),actor='controller')
                if result.get('is_error'):raise ValueError(json.loads(result['content']).get('error','Independent operation failed'))
                return json.loads(result['content'])
            try:
                call('select_design_patterns',{'selections':old['architecture']['selections'],
                    'justification':'Recheck the recorded architecture; no inherited verification'})
                if parameter is not None:
                    revise_from_owner(session,parameter,answer,runner._execute)
                else:
                    call('compare_design_alternatives')
                    for name in ('generate_design_bom','source_design_roles','qualify_design','design_cost_scenarios','remember_design'):call(name)
                rec.log('chat_revalidation_result',report=session.design_report(),model_called=False)
            except UserCancelled:rec.log('chat_cancelled',actor='user')
            return self._finish(chat,session,root,cancelled=cancel.is_set())
