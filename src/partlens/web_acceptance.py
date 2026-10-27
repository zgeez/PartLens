"""CMD-driven acceptance in the actual WebView2 renderer; synthetic data and real bundled memory only."""
import json
from pathlib import Path

from .conversations import ConversationStore
from .settings import AppSettings,load_settings
from .records import read_events
from .web_desktop import launch


SCRIPT=r'''(async()=>{
  const assert=(condition,message)=>{if(!condition)throw Error(message);};
  const wait=ms=>new Promise(resolve=>setTimeout(resolve,ms));
  const P=window.PartLens;
  await P.ready;
  const fixture=P.getState().history.find(c=>c.title==='TEST renderer fixture');
  assert(fixture,'Synthetic conversation missing');
  await P.api('select_chat',{id:fixture.id});
  assert(!document.querySelector('.message-body img'),'Untrusted message became HTML');
  assert(!window.TEST_UNTRUSTED_HTML,'Untrusted message script executed');
  assert(document.querySelector('.message-body').textContent.includes('<img'),'Message text lost');
  await P.navigate('settings');
  const localFields=document.querySelectorAll('[data-setting]').length;
  assert(localFields===5,'Local model form is incomplete');
  P.showSettingsTab('Suppliers');
  const passwordFields=[...document.querySelectorAll('input[type=password]')];
  assert(passwordFields.length===3&&passwordFields.every(n=>n.value===''),'Credentials exposed in form');
  const settings=await P.api('settings_open');
  assert(!JSON.stringify(settings).includes('TEST-renderer-secret'),'Saved secret crossed the bridge');
  await P.api('settings_save',{preferences:settings.preferences,credentials:{},clear:[]});
  P.showSettingsTab('Zetaris');
  assert(document.querySelectorAll('[data-setting]').length===6,'Zetaris form missing');
  P.showSettingsTab('Storage & services');
  assert(document.querySelector('.runtime-list').textContent.includes('WebView2'),'Runtime requirements missing');
  await P.navigate('bom');
  async function settle(answer){
    for(let i=0;i<400;i++){
      await wait(100);await P.api('snapshot');const s=P.getState();
      if(s.question){assert(answer!==undefined,'Unexpected owner question');await P.api('answer',{text:answer});}
      if(!s.busy){assert(!s.status.startsWith('Operation incomplete'),s.status);return s;}
    }
    throw Error('BOM operation timed out');
  }
  await P.api('bom_load',{demo:true});let s=await settle();
  const bomRows=s.bom.Parts.lines.length;
  assert(bomRows>0&&document.querySelectorAll('.data-table tbody tr').length===bomRows,'BOM table differs from controller data');
  await P.api('bom_manual');s=await settle('1');
  const statuses=[...new Set(s.bom.Qualifications.map(q=>q.status))].sort();
  assert(['verified','rejected','unverified'].every(v=>statuses.includes(v)),'Deterministic outcomes missing');
  await P.api('bom_cost');s=await settle();
  assert(s.bom.Cost.scenarios.length===2,'Owner/hypothetical cost scenarios missing');
  const quantities=s.bom.Cost.scenarios.map(r=>r.boards);
  assert(quantities[0]===1&&quantities[1]===60,'Quantity provenance scenarios changed');
  const project=s.project.id,revision=s.project.revision;
  const verified=s.bom.Qualifications.find(d=>d.status==='verified');
  const unverified=s.bom.Qualifications.find(d=>d.status==='unverified');
  let blocked=false;
  try{await P.api('bom_human_review',{decision_id:unverified.decision_id,action:'accept',reviewer:'TEST renderer',reason:'TEST forbidden override',acknowledge:true});}catch(e){blocked=true;}
  assert(blocked,'Human review overrode an unverified check');
  [...document.querySelectorAll('#bom-tabs button')].find(b=>b.textContent==='Engineer review').click();
  const rows=[...document.querySelectorAll('#bom-content tbody tr')];
  assert(rows.length>0,'Engineer review queue missing');
  const row=rows.find(r=>r.textContent.includes(verified.comparison.candidate.mpn));
  row.querySelector('button').click();
  document.querySelector('[aria-label="Reviewer name"]').value='TEST renderer';
  document.querySelector('[aria-label="Review rationale"]').value='Synthetic reference attributes inspected; application remains unresolved.';
  document.querySelector('.scope-ack input').checked=true;
  [...document.querySelectorAll('#modal-actions button')].find(b=>b.textContent==='Accept checked attributes').click();
  for(let i=0;i<100&&document.querySelector('#modal').open;i++)await wait(50);
  assert(!document.querySelector('#modal').open,'Engineer review did not save');
  const exported=await P.api('bom_export');
  assert(exported.accepted_lines===1&&exported.manufacturing_ready===false,'Proposal export scope changed');
  await P.api('project_select',{id:project,revision});
  assert(P.getState().project.historical&&P.getState().bom.Qualifications.every(d=>d.current_context===false),'Saved decisions incorrectly current');
  await P.api('bom_manual');s=await settle();
  assert(s.bom.Requirements.requirements.some(r=>r.id==='design.board_quantity'&&r.binding),'Quantity provenance not restored');
  blocked=false;try{await P.api('bom_export');}catch(e){blocked=true;}
  assert(blocked,'Prior approval incorrectly transferred to a fresh run');
  await P.api('bom_recall');s=await settle();
  assert(s.bom.Explanation.includes('Current deterministic memory comparisons'),'Cold recall not independently rechecked');
  await P.api('project_create',{title:'TEST isolated project'});
  await P.api('bom_load',{demo:true});await settle();
  await P.api('bom_recall');s=await settle();
  assert(!s.bom.Qualifications.length,'Decisions leaked across project memory scopes');
  await P.api('project_select',{id:project,revision});
  return {success:true,renderer:'edgechromium',userAgent:navigator.userAgent,localFields,
    maskedSupplierFields:passwordFields.length,bomRows,decisionStatuses:statuses,costQuantities:quantities,
    xssEscaped:true,noSecretsReturned:true,sameWindowPages:['chat','settings','bom'],
    immutableRevision:revision,projectPersistence:true,humanReview:true,proposalExport:exported,
    approvalOverrideBlocked:true,historicalApprovalBlocked:true,quantityProvenanceRestored:true,projectMemoryIsolation:true,
    composerRadius:P.inspect().inputRadius,externalScripts:document.querySelectorAll('script[src]').length,
    mode:'synthetic renderer and deterministic checks; real H-MEM; no model or supplier call'};
})().catch(error=>({success:false,error:String(error)}))'''


def renderer_acceptance(home,catalog):
    home=Path(home).resolve();settings=AppSettings(credentials={'JLC_SECRET_KEY':'TEST-renderer-secret'})
    store=ConversationStore(home/'state');chat=store.create('TEST renderer fixture','design')
    store.message(chat,'user','TEST only: <img src=x onerror="window.TEST_UNTRUSTED_HTML=true">')
    store.message(chat,'assistant','Synthetic rendering fixture only. No model or supplier operation occurred.',kind='commentary')
    acceptance={'script':SCRIPT};launch(home,settings,[catalog],acceptance=acceptance)
    if acceptance.get('error'):raise RuntimeError(acceptance['error'])
    result=acceptance.get('result')
    if not result or not result.get('success'):raise RuntimeError('Renderer acceptance failed: '+str(result))
    assert load_settings(home).credentials==settings.credentials
    # New native bridge after the first renderer exits: no model/supplier operation on reopen.
    from .web_desktop import DesktopBridge
    reopened=DesktopBridge(home,settings,[catalog])
    try:
        state=reopened.request('snapshot')['state']
        assert state['project']['historical'] and state['bom']['Qualifications']
        assert not reopened.request('bom_export')['ok']
        result['cold_profile_reopen']=True
    finally:reopened._projects.close()
    events=[e for path in (home/'state/web-bom-runs').glob('*.jsonl') for e in read_events(path)]
    recalls=[e for e in events if e['type']=='tool_call' and e.get('name')=='recall_decisions' and not e.get('error')]
    rechecks=[e for e in events if e['type']=='tool_call' and e.get('name')=='reverify_decision' and not e.get('error')]
    assert recalls and rechecks
    result['memory_rechecks']=len(rechecks)
    result['visual_acceptance']=False
    (home/'renderer-acceptance.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result
