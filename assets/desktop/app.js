'use strict';
const $=id=>document.getElementById(id);
const icons={guide:'M4 5a2 2 0 0 1 2-2h13v15H6a2 2 0 0 0-2 2V5Zm0 15a2 2 0 0 1 2-2h13M8 7h7M8 11h5',plus:'M12 5v14M5 12h14',chat:'M20 11a8 8 0 0 1-8 8H5l-3 3v-10a9 9 0 1 1 18-1Z',parts:'M8 8h8v8H8ZM9 3v3m6-3v3M9 18v3m6-3v3M3 9h3m-3 6h3m12-6h3m-3 6h3',settings:'M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM10 3h4l1 3 3 1 3 3v4l-3 1-1 3-3 3h-4l-1-3-3-1-3-3v-4l3-1 1-3Z',activity:'M2 12h5l3-8 4 16 3-8h5',arrow:'M5 12h14m-5-5 5 5-5 5',folder:'M3 6h7l2 2h9v12H3ZM3 6V4h6l2 2',lens:'M16 16l5 5M10 3a7 7 0 1 0 0 14 7 7 0 0 0 0-14Z',attach:'m8 12 6-6a3 3 0 0 1 4 4l-8 8a5 5 0 0 1-7-7l8-8',send:'M12 20V4m-6 6 6-6 6 6',sliders:'M4 7h16M4 17h16M9 4v6m6 4v6',question:'M9 8a3 3 0 1 1 5 2c-1 1-2 1-2 3m0 4h.01M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z',close:'m6 6 12 12M18 6 6 18',upload:'M12 16V3m-5 5 5-5 5 5M4 15v6h16v-6',check:'m5 12 4 4L19 6',spark:'m12 2 3 7 7 3-7 3-3 7-3-7-7-3 7-3Z',memory:'M8 4H5v16h14V4h-3M9 2h6v5H9Zm0 9h6m-6 4h6',refresh:'M20 8a8 8 0 1 0 0 8m0-13v5h-5',edit:'m4 16 12-12 4 4L8 20H4Zm9-9 4 4',lock:'M6 10h12v11H6Zm3 0V6a3 3 0 0 1 6 0v4',server:'M3 4h18v6H3Zm0 10h18v6H3ZM7 7h.1M7 17h.1',copy:'M8 8h12v12H8ZM4 16H2V2h14v2'};
function icon(name){const svg=document.createElementNS('http://www.w3.org/2000/svg','svg');svg.setAttribute('viewBox','0 0 24 24');svg.setAttribute('aria-hidden','true');const path=document.createElementNS(svg.namespaceURI,'path');path.setAttribute('d',icons[name]||icons.parts);svg.append(path);return svg;}
function hydrate(root=document){root.querySelectorAll('[data-icon]').forEach(n=>{const svg=icon(n.dataset.icon);svg.classList.add(...n.classList);n.replaceWith(svg);});}
function el(tag,cls,text){const n=document.createElement(tag);if(cls)n.className=cls;if(text!==undefined)n.textContent=text;return n;}
function button(text,cls,action,iconName){const n=el('button',cls,text);if(iconName)n.prepend(icon(iconName));n.addEventListener('click',()=>guard(action));return n;}
function empty(title,detail){const n=el('div','empty-state');n.append(icon('parts'),el('strong','',title),el('p','',detail));return n;}
let state=null,page='chat',bomTab='Parts',qualificationFilter='all',evidenceSection='',inspectorVisible=false,settingsData=null,settingsTab='Local model',clearedKeys=new Set(),lastMessages='',lastBom='',lastHistory='',followEnd=true,serviceRequested=false,bomQuestionId='',polling=false,toastTimer;
const settingsTabs=[['Local model','spark'],['Suppliers','parts'],['Zetaris','server'],['Storage & services','lock']];
const fields={
 'Local model':{title:'Your local intelligence',description:'Choose the model already installed in Ollama. PartLens never silently switches to paid inference.',fields:[
 ['PARTLENS_LOCAL_MODEL','Installed model','qwen3.5:9b','Use an exact local Ollama model ID.',true],['PARTLENS_LOCAL_URL','Ollama address','http://127.0.0.1:11434','Only loopback addresses are accepted.',true],['PARTLENS_LOCAL_PROTOCOL','Tool transport',['native','json-schema'],'The selected protocol is recorded. There is no silent transport fallback.'],['PARTLENS_LOCAL_CONTEXT','Context size','32768','Tokens available to the local model.'],['PARTLENS_LOCAL_TIMEOUT','Request timeout','180','Seconds; an active request may take this long to stop.']]},
 'Suppliers':{title:'Evidence from authorized suppliers',description:'Choose synthetic examples or your authorized official supplier connection. All operations are read-only.',fields:[['supplier_mode','Source of component data',null,'Unknown pricing terms, assembly fees and eligibility remain unknown.',true],['JLC_APP_ID','JLCPCB application ID','',null],['JLC_APP_NAME','Application name (optional)','',null],['JLC_ACCESS_KEY','Access key','',null],['JLC_SECRET_KEY','Secret key','',null]]},
 'Zetaris':{title:'Your Zetaris connection',description:'Use your owner-authorized SQL gateway. A real query must succeed before integration availability is claimed.',fields:[['ZETARIS_BASE_URL','SQL gateway origin','http://localhost:3000','Your authorized deployed gateway, not a supplier website.',true],['ZETARIS_ORG_ID','Organization ID','',null],['ZETARIS_ENGINE_ID','Engine ID (optional)','',null],['ZETARIS_API_KEY','API key','',null,true],['PARTLENS_ZETARIS_PARTS_TABLE','Existing supplier table','','Leave unknown when it has not been configured.',true],['PARTLENS_ZETARIS_BOM_SUPPLIER','Table supplier',['lcsc','jlcpcb'],null]]}
};
const secretKeys=['JLC_APP_ID','JLC_ACCESS_KEY','JLC_SECRET_KEY','ZETARIS_API_KEY'];
async function api(action,payload={}){const response=await window.pywebview.api.request(action,payload,window.pywebview.token);if(!response.ok)throw Error(response.error||'Operation did not complete');if(response.state)render(response.state);return response.result;}
async function guard(action){try{return await action();}catch(error){toast(error.message||String(error),true);return null;}}
function toast(text,error=false){const host=$('modal').open?$('modal'):document.body;if($('toast').parentNode!==host)host.append($('toast'));$('toast').textContent=text;$('toast').classList.remove('hidden');$('toast').classList.toggle('error',error);clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.add('hidden'),6500);}
async function navigate(target){if(!['chat','bom','settings'].includes(target))return;if(target==='settings'&&!settingsData){settingsData=await api('settings_open');clearedKeys.clear();renderSettings();}page=target;document.querySelectorAll('.page').forEach(n=>n.classList.toggle('hidden',n.id!==target+'-page'));document.querySelectorAll('[data-page]').forEach(n=>n.classList.toggle('active',n.dataset.page===target));$('eyebrow').textContent='WORKSPACE / '+({chat:'CONVERSATION',bom:'BOM REVIEW',settings:'SETTINGS'}[target]);$('page-title').textContent=target==='chat'?(state?.chat?.title||'New conversation'):target==='bom'?'BOM workspace':'Settings';$('evidence-button').classList.toggle('hidden',target==='settings');$('open-report').classList.toggle('hidden',target==='settings');if(target==='settings')showInspector(false);if(target==='bom')renderBom();}
function render(next){state=next;$('sidebar-model').textContent=state.model;$('supplier-label').textContent=state.supplier;$('page-title').textContent=page==='chat'?(state.chat?.title||'New conversation'):page==='bom'?'BOM workspace':'Settings';const historyKey=JSON.stringify([state.history,state.chat?.id]);if(historyKey!==lastHistory){renderHistory();lastHistory=historyKey;}renderMessages();renderActivity();renderQueue();if(page==='bom')renderBom();renderInspector();$('chat-status').textContent=state.status;$('bom-status').textContent=state.status;for(const id of ['chat-status','bom-status'])$(id).classList.toggle('working',state.busy);const answering=!!state.question&&state.question.target==='chat';$('question-bar').classList.toggle('hidden',!answering);$('send').disabled=false;$('stop').classList.toggle('hidden',!state.busy);$('message-input').disabled=false;$('message-input').placeholder=answering?'Your exact answer, with units when needed…':'Describe an idea, ask about your report, or attach a BOM…';$('chat-mode').disabled=!!state.chat||state.busy;$('chat-mode').value=state.chat?.mode||$('chat-mode').value;$('attach-bom').disabled=false;$('proposals').disabled=state.busy;$('attachment').classList.toggle('hidden',!state.attachment);$('attachment').textContent=state.attachment||'';for(const id of ['new-chat','bom-demo','bom-import','bom-review','bom-agent','bom-new','bom-recall','bom-compare','settings-save','settings-import','settings-reset'])$(id).disabled=state.busy;const available=state.services?Object.values(state.services.checks).filter(c=>c.available).length:null;$('service-status').textContent=available===null?'Check local services':available+'/4 services available';if(!state.busy&&serviceRequested&&state.services){serviceRequested=false;showServices();}if(state.question?.target==='bom'){const id=state.question.text;if(bomQuestionId!==id){bomQuestionId=id;showBomQuestion(state.question.text);}}else if(bomQuestionId){bomQuestionId='';if($('modal').dataset.type==='bom-question')$('modal').close();}}
function renderHistory(){const list=$('history');list.replaceChildren();if(!state.history.length){list.append(el('div','empty-history','Your conversations will appear here.'));return;}for(const chat of state.history){const row=el('div','history-item'+(state.chat?.id===chat.id?' active':''));const n=button(chat.title,'history-row'+(state.chat?.id===chat.id?' active':''),async()=>{await api('select_chat',{id:chat.id});followEnd=true;lastMessages='';await navigate('chat');renderMessages();});n.title=chat.title;const del=el('button','history-delete');del.title='Delete conversation';del.setAttribute('aria-label','Delete conversation');del.append(icon('close'));del.addEventListener('click',e=>{e.stopPropagation();if(!del.classList.contains('confirm')){del.classList.add('confirm');del.title='Click again to delete. The journal stays on disk.';setTimeout(()=>{del.classList.remove('confirm');del.title='Delete conversation';},3000);return;}guard(async()=>{await api('delete_chat',{id:chat.id});lastHistory='';lastMessages='';});});row.append(n,del);list.append(row);}}
function mdNode(tag,cls,text){const n=el(tag,cls);const re=/(\*\*[^*\n]+\*\*|`[^`\n]+`|\*[^*\n]+\*)/g;let last=0,m;const s=String(text).replace(/\\\*/g,'');const un=t=>t.replace(//g,'*');while((m=re.exec(s))!==null){if(m.index>last)n.append(document.createTextNode(un(s.slice(last,m.index))));const tok=m[0];if(tok.startsWith('**'))n.append(el('strong','',un(tok.slice(2,-2))));else if(tok.startsWith('`'))n.append(el('code','inline-code',un(tok.slice(1,-1))));else n.append(el('em','',un(tok.slice(1,-1))));last=re.lastIndex;}if(last<s.length)n.append(document.createTextNode(un(s.slice(last))));return n;}
function richText(text){const root=el('div','message-body');let code=false,buffer=[],list=null,listTag='';function flush(){if(buffer.length){root.append(code?el('pre','',buffer.join('\n')):mdNode('p','',buffer.join('\n')));buffer=[];}list=null;listTag='';}for(const line of String(text).split('\n')){if(line.trim().startsWith('```')){flush();code=!code;continue;}if(code){buffer.push(line);continue;}if(/^#{1,4}\s/.test(line)){flush();root.append(mdNode('h3','',line.replace(/^#{1,4}\s+/,'')));continue;}if(/^\s*[-*]\s+/.test(line)){if(buffer.length)flush();if(!list||listTag!=='ul'){list=el('ul');listTag='ul';root.append(list);}list.append(mdNode('li','',line.replace(/^\s*[-*]\s+/,'')));continue;}if(/^\s*\d+\.\s+/.test(line)){if(buffer.length)flush();if(!list||listTag!=='ol'){list=el('ol');listTag='ol';root.append(list);}list.append(mdNode('li','',line.replace(/^\s*\d+\.\s+/,'')));continue;}if(!line.trim()){flush();continue;}list=null;listTag='';buffer.push(line);}flush();return root;}
function renderMessages(){const key=JSON.stringify([state.chat?.id,state.messages,state.job==='revalidate',state.question?.text]);if(key===lastMessages)return;lastMessages=key;const root=$('messages');root.replaceChildren();if(!state.messages.length){root.append($('welcome-template').content.cloneNode(true));hydrate(root);root.querySelectorAll('[data-starter]').forEach(n=>n.addEventListener('click',()=>guard(()=>starter(n.dataset.starter))));return;}const list=el('div','messages-list');if(state.job==='revalidate')list.append(el('div','historical-banner','Revalidating independently. Results from the previous revision remain historical until the current checks finish.'));for(const message of state.messages){const n=el('article','message '+message.role+' '+(message.kind||''));const heading=el('div','message-label');if(message.role!=='user'){const mark=el('span','role-mark');mark.append(icon(message.kind==='question'?'question':'lens'));heading.append(mark);}heading.append(document.createTextNode(message.role==='user'?'You':message.role==='system'?'Workspace':message.kind==='report'?'PartLens · Engineering report':message.kind==='commentary'?'PartLens · Commentary, not a decision':message.kind==='question'?'PartLens · Requirement':'PartLens'));n.append(heading,richText(message.text));if(message.role==='assistant'){const tools=el('div','message-actions');tools.append(button('Copy','',()=>copyText(message.text)));if(message.kind==='question'&&state.question?.target==='chat'&&message===state.messages[state.messages.length-1]){tools.append(button('Specify in chat ↓','',()=>{$('message-input').focus();}));tools.append(button('Let AI set requirement','',()=>api('answer',{delegate:true})));tools.append(button('Leave unanswered','',()=>api('answer',{text:null})));}if(message.kind==='report'){tools.append(button('View evidence ↗','',()=>showInspector(true)));if(state.report?.mode==='new_design'&&state.report?.bom?.length)tools.append(button('Open in BOM workspace ↗','',async()=>{await api('bom_from_design');await navigate('bom');}));tools.append(button('Open files ↗','',()=>api('open_report',{workspace:'chat'})));}n.append(tools);}list.append(n);}root.append(list);if(followEnd)requestAnimationFrame(()=>$('transcript').scrollTop=$('transcript').scrollHeight);}
async function starter(kind){if(state.busy)return;if(kind==='idea'){$('chat-mode').value='design';$('message-input').value='Design a Bluetooth temperature monitor.';}else if(kind==='demo'){await api('demo_bom');$('chat-mode').value='bom';$('message-input').value='Review this BOM and investigate sourcing alternatives.';}else{await api('select_bom');if(state.attachment){$('chat-mode').value='bom';$('message-input').value='Review this BOM and investigate sourcing alternatives.';}}autoSize();$('message-input').focus();}
function autoSize(){const n=$('message-input');n.style.height='auto';n.style.height=Math.min(180,Math.max(54,n.scrollHeight))+'px';}
async function send(){const text=$('message-input').value.trim();if(!text)return;const payload={text,mode:$('chat-mode').value,proposals:$('proposals').checked};const queued=await api(state.question?.target==='chat'?'answer':'send',payload);$('message-input').value='';autoSize();followEnd=true;if(queued==='queued')toast('Queued. It will be sent when PartLens finishes the current job.');}
function renderQueue(){const box=$('queue-note');const items=state.queued||[];box.classList.toggle('hidden',!items.length);if(!items.length)return;box.replaceChildren(el('span','',items.length===1?'1 message waiting: “'+items[0].slice(0,80)+(items[0].length>80?'…':'')+'”':items.length+' messages waiting for the current job'),button('Cancel','text-button',()=>api('unqueue')));}
function showInspector(visible){inspectorVisible=visible;$('inspector').classList.toggle('hidden',!visible);if(visible)renderInspector();}
function renderActivity(){if(evidenceSection==='Activity')renderInspector();}
function statusBadge(tok){
  const t=String(tok||'').trim().toLowerCase();
  if(['verified','pass','confirmed','user_confirmed','source_found'].includes(t))return el('span','badge verified',tok);
  if(['rejected','fail','failed'].includes(t))return el('span','badge rejected',tok);
  if(['unverified','inferred','provisional','provisional_hypothetical','hypothetical','unresolved'].includes(t))return el('span','badge unverified',tok);
  return el('span','ev-chip',tok);
}
function renderStructuredEvidence(root,sectionName,text){
  root.replaceChildren();
  const raw=String(text||'').trim();
  if(!raw){root.append(empty('No evidence recorded yet','Run a design or BOM check to populate this section.'));return;}
  if(sectionName==='Explanation'){const card=el('div','ev-card');card.append(richText(raw));root.append(card);return;}
  if(raw.startsWith('{')||raw.startsWith('[')){
    try{
      const obj=JSON.parse(raw);
      if(obj&&typeof obj==='object'&&!Array.isArray(obj)){
        const card=el('div','ev-card');
        const head=el('div','ev-card-head');
        head.append(el('strong','ev-card-title',obj.mpn||obj.decision_id||obj.key||sectionName));
        if(obj.status)head.append(statusBadge(obj.status));
        else if(obj.assembly_class)head.append(statusBadge(obj.assembly_class));
        card.append(head);
        if(obj.manufacturer||obj.package||obj.key){
          const sub=el('div','ev-chips');
          for(const v of [obj.manufacturer,obj.package,obj.key,obj.category].filter(Boolean))sub.append(el('span','ev-chip',String(v)));
          card.append(sub);
        }
        if(obj.stock!==undefined||obj.retrieved_at){
          const meta=el('div','ev-detail');
          meta.textContent=`Stock: ${obj.stock??'unknown'} · Retrieved: ${obj.retrieved_at||'unknown'}`;
          card.append(meta);
        }
        if(obj.params&&typeof obj.params==='object'){
          const pwrap=el('div','ev-sublist');
          for(const [k,v] of Object.entries(obj.params)){
            const row=el('div','ev-kv');
            row.append(el('span','ev-k',k.replaceAll('_',' ')),el('strong','ev-v',String(v?.value??v)));
            pwrap.append(row);
          }
          card.append(pwrap);
        }
        if(Array.isArray(obj.checks)){
          const cwrap=el('div','ev-sublist');
          for(const c of obj.checks){
            const crow=el('div','ev-check-row');
            crow.append(statusBadge(c.status||'unverified'),el('strong','',c.check||'check'),document.createTextNode(' '+String(c.message||'')));
            cwrap.append(crow);
          }
          card.append(cwrap);
        }
        const det=el('details','ev-raw');
        det.append(el('summary','','Full provenance record (JSON)'),el('pre','',raw));
        card.append(det);
        root.append(card);
        return;
      }
    }catch(_){}
  }
  const lines=raw.split('\n');
  let currentCard=null,currentStatus='';
  function flushCard(){if(currentCard){root.append(currentCard);currentCard=null;}}
  for(const line of lines){
    if(!line.trim()){flushCard();continue;}
    const trimmed=line.trim();
    if(/^(FAIL|UNVERIFIED|PASS)$/.test(trimmed)){
      flushCard();currentStatus=trimmed.toLowerCase();
      const ban=el('div','ev-banner');ban.append(statusBadge(trimmed),el('strong','',trimmed==='FAIL'?'Failed checks':trimmed==='PASS'?'Conditional passes':'Unverified / missing evidence'));
      root.append(ban);continue;
    }
    if(/^[A-Z0-9\s—\-/()]{10,}$/.test(trimmed)&&trimmed===trimmed.toUpperCase()&&/[A-Z]/.test(trimmed)){
      flushCard();
      const ban=el('div','ev-banner');
      if(trimmed.includes('USER-CONFIRMED'))ban.append(statusBadge('confirmed'));
      else if(trimmed.includes('PROVISIONAL')||trimmed.includes('NOT CONFIRMED')||trimmed.includes('NOT MANUFACTURING-READY'))ban.append(statusBadge('provisional'));
      ban.append(el('strong','',trimmed));
      root.append(ban);continue;
    }
    const checkMatch=trimmed.match(/^(PASS|FAIL|UNVERIFIED)\s+([A-Za-z0-9_.-]+):\s*(.*)$/);
    if(checkMatch){
      if(!currentCard)currentCard=el('div','ev-card');
      const crow=el('div','ev-check-row');
      crow.append(statusBadge(checkMatch[1]),el('strong','',checkMatch[2]+': '),document.createTextNode(checkMatch[3]));
      currentCard.append(crow);continue;
    }
    if(line.startsWith('  ')||trimmed.startsWith('• ')){
      if(!currentCard)currentCard=el('div','ev-card');
      const d=el('div','ev-detail');
      const clean=trimmed.replace(/^•\s*/,'');
      const kv=clean.match(/^([A-Za-z0-9_ /()-]+):\s*(.+)$/);
      if(kv&&kv[1].length<34){
        d.append(el('span','ev-k',kv[1]+': '));
        const parts=kv[2].split(/\s*\|\s*/);
        parts.forEach((p,i)=>{
          if(i>0)d.append(document.createTextNode(' · '));
          const subkv=p.match(/^(Role equivalence|application|binding|accepted|complete):\s*(.+)$/i);
          if(subkv){d.append(el('span','ev-k',subkv[1]+': '),statusBadge(subkv[2]));}
          else if(['verified','unverified','rejected','pass','fail','confirmed','inferred','true','false'].includes(p.trim().toLowerCase()))d.append(statusBadge(p.trim()));
          else d.append(document.createTextNode(p));
        });
      }else{
        d.textContent=clean;
      }
      currentCard.append(d);continue;
    }
    flushCard();
    currentCard=el('div','ev-card');
    const head=el('div','ev-card-head');
    if(currentStatus&&sectionName==='Checks'){
      const cm=trimmed.match(/^([A-Za-z0-9_.-]+):\s*(.*)$/);
      head.append(statusBadge(currentStatus));
      if(cm){head.append(el('strong','ev-card-title',cm[1]));currentCard.append(head,el('div','ev-detail',cm[2]));continue;}
    }
    const segs=trimmed.split(/\s*\|\s*/);
    const first=segs[0];
    const colon=first.match(/^([A-Za-z0-9_.-]+):\s*(.+)$/);
    if(colon&&segs.length>1){
      head.append(el('strong','ev-card-title',colon[1].replaceAll('_',' ')),el('span','ev-val',colon[2]));
    }else{
      head.append(el('strong','ev-card-title',first));
    }
    if(segs.length>1){
      const chips=el('div','ev-chips');
      for(const s of segs.slice(1))chips.append(statusBadge(s));
      head.append(chips);
    }
    currentCard.append(head);
  }
  flushCard();
}
function renderInspector(){const sections={...(page==='bom'?state?.bom_views:state?.views)};sections.Activity=(state?.activity||[]).map(r=>`${r.actor==='controller'?'Controller':'Agent requested'} | ${r.name.replaceAll('_',' ')} | ${r.phase}`).join('\n')||'No tool activity in this view. Full journals remain with the report.';if(Object.keys(sections).length===1)sections.Overview='Requirements, parts, sources, checks and costs will appear here after a workflow. Model commentary is separate.';const select=$('evidence-section');const previous=evidenceSection;const keys=Object.keys(sections);const changed=JSON.stringify([...select.options].map(o=>o.value))!==JSON.stringify(keys);if(changed){select.replaceChildren();for(const name of keys){const option=el('option','',name);option.value=name;select.append(option);}}evidenceSection=Object.hasOwn(sections,previous)&&!(changed&&previous==='Activity')?previous:(Object.hasOwn(sections,'Overview')?'Overview':keys[0]);select.value=evidenceSection;const pills=$('evidence-pills');if(pills){pills.replaceChildren();for(const name of keys){pills.append(button(name,'ev-pill'+(evidenceSection===name?' active':''),()=>{evidenceSection=name;select.value=name;renderInspector();}));}}renderStructuredEvidence($('evidence-content'),evidenceSection,sections[evidenceSection]||'');const editable=page==='chat'&&state?.can_revalidate&&!state?.busy;$('recheck').disabled=!editable;$('edit-requirement').disabled=!editable;$('evidence-note').textContent=state?.job==='revalidate'?'Revalidating. Displayed results are historical.':'Recorded evidence · recheck for current availability. Application suitability is separate.';}
function openEvidenceText(title,text){showInspector(true);evidenceSection=title;$('evidence-section').replaceChildren();const option=el('option','',title);option.value=title;$('evidence-section').append(option);renderStructuredEvidence($('evidence-content'),title,text);}
function badge(value,historical=false){const status=['verified','rejected','unverified','pass','fail'].includes(value)?value:'unverified';return el('span','badge '+(historical?'':status),historical?status+' · historical':status);}
function metric(label,value,note){const n=el('div','metric-card');n.append(el('span','metric-label',label),el('strong','',String(value)),el('small','',note));return n;}
const bomTabs=[['Parts','Parts'],['Requirements','Requirements'],['Qualifications','Replacements'],['Sourcing','Sourcing'],['Cost','Costs'],['Explanation','Explanation'],['Evidence','Sources']];
function renderBom(){if(!state)return;const key=JSON.stringify([state.bom,bomTab,qualificationFilter]);if(key===lastBom)return;lastBom=key;const bom=state.bom,lines=bom.Parts?.lines||[],qual=bom.Qualifications||[];const current=qual.filter(q=>q.current_context!==false);$('bom-summary').replaceChildren(metric('Component lines',lines.length,'Imported BOM, read-only'),metric('Specification-equivalent',current.filter(q=>q.status==='verified').length,'Application checks are separate'),metric('Rejected alternatives',current.filter(q=>q.status==='rejected').length,'Independent engineering results'),metric('Unverified alternatives',current.filter(q=>q.status==='unverified').length,'Missing evidence stays unresolved'));const tabs=$('bom-tabs');tabs.replaceChildren();for(const [key,label] of bomTabs)tabs.append(button(label,'tab'+(bomTab===key?' active':''),()=>{bomTab=key;renderBom();}));const root=$('bom-content');root.replaceChildren();const head=el('div','panel-heading');const title=el('div');title.append(el('h3','',bomTabs.find(t=>t[0]===bomTab)?.[1]||bomTab),el('p','',bomTab==='Qualifications'?'Original-specification equivalence and application suitability are distinct.':bomTab==='Parts'?'Select a line to inspect its recorded supplier evidence.':bomTab==='Cost'?'Component cost and assembled estimates remain separate; unknown terms are disclosed.':'Authoritative recorded outputs from the existing Python workflow.'));head.append(title);root.append(head);if(bomTab==='Parts'){if(!lines.length){root.append(empty('Bring your first BOM','Load the configured demo or import a CSV. PartLens keeps design files unchanged.'));return;}const table=makeTable(['Line / references','Value / package','Per board','Matched component']);for(const row of lines){const tr=el('tr');let td=el('td');td.append(el('span','part-primary',row.line),el('small','part-secondary',row.refs));tr.append(td);td=el('td');td.append(el('span','part-primary',row.value),el('small','part-secondary',row.package));tr.append(td,el('td','',String(row.qty_per_board)));td=el('td');if(row.matched_part)td.append(el('span','badge verified',row.matched_part));else if(!row.purchased)td.append(el('span','ev-chip','Open role / DNP'));else td.append(el('span','badge unverified','Unmatched identity'));tr.append(td);tr.addEventListener('click',()=>{const part=bom.Evidence?.[row.matched_part];openEvidenceText('Part '+row.line,part?JSON.stringify(part,null,2):'No exact supplier identity is established for this line. Missing evidence remains unverified.');});table.body.append(tr);}root.append(table.wrapper);}else if(bomTab==='Qualifications'){const filters=el('div','filter-group');for(const filter of ['all','verified','rejected','unverified'])filters.append(button(filter[0].toUpperCase()+filter.slice(1),' '+(qualificationFilter===filter?'active':''),()=>{qualificationFilter=filter;renderBom();}));head.append(filters);const rows=qual.filter(q=>qualificationFilter==='all'||q.status===qualificationFilter);if(!rows.length){root.append(empty('No replacement decisions here yet','Run deterministic checks or a local agent review. A model cannot assign verified status.'));return;}const table=makeTable(['Line','Original','Candidate','Specification','Application']);for(const row of rows){const tr=el('tr');tr.append(el('td','',row.line));for(const key of ['original','candidate']){const p=row.comparison?.[key];const td=el('td');td.append(el('span','part-primary',p?.mpn||row[key]),el('small','part-secondary',p?.manufacturer||'Manufacturer unresolved'));tr.append(td);}const td=el('td');td.append(badge(row.status,row.current_context===false));tr.append(td);const app=el('td');app.append(badge(row.application?.status||'unverified',row.current_context===false));tr.append(app);tr.addEventListener('click',()=>openEvidenceText('Decision '+row.line,JSON.stringify(row,null,2)));table.body.append(tr);}root.append(table.wrapper);}else{const text=state.bom_views?.[bomTab]||'No recorded output for this section yet.';const wrap=el('div','panel-structured');renderStructuredEvidence(wrap,bomTab,text);root.append(wrap);}}
function makeTable(headings){const wrapper=el('div','table-wrap'),table=el('table','data-table'),head=el('thead'),row=el('tr'),body=el('tbody');for(const title of headings)row.append(el('th','',title));head.append(row);table.append(head,body);wrapper.append(table);return{wrapper,body};}
function renderSettings(){if(!settingsData)return;const nav=$('settings-nav');nav.replaceChildren();for(const [title,mark] of settingsTabs)nav.append(button(title,settingsTab===title?'active':'',()=>{settingsTab=title;renderSettings();},mark));const root=$('settings-form');root.replaceChildren();const card=el('section','settings-card'),head=el('div','settings-card-head'),body=el('div','settings-card-body');if(settingsTab==='Storage & services'){head.append(el('h3','','Private by default'),el('p','','Your credentials, conversations and evidence stay on this computer.'));for(const [label,path] of [['Settings and encrypted credentials',settingsData.storage],['Run records, caches and memory',settingsData.storage+' / state']]){const item=el('div','storage-item');item.append(el('strong','',label),el('code','',path));body.append(item);}body.append(el('p','modal-description','Credentials use Windows user-scoped DPAPI. This application does not store credentials in browser storage or include them in the executable.'));const list=el('ul','runtime-list');for(const text of ['Included: Python engineering engine and real Node/H-MEM bridge.','Windows components: WebView2 Runtime and .NET Framework 4.6.2+.','External: Ollama with installed model; authorized Zetaris service.','PartLens never edits design files in place or orders components.'])list.append(el('li','',text));body.append(list,button('Check local services','button',async()=>{serviceRequested=true;await api('services');},'activity'),document.createTextNode(' '),button('Licenses & notices','button',showNotices,'folder'));}else{const spec=fields[settingsTab];head.append(el('h3','',spec.title),el('p','',spec.description));const grid=el('div','form-grid');for(const [key,label,placeholder,help,full] of spec.fields){const field=el('div','field'+(full?' full':''));const labelNode=el('label','',label);labelNode.htmlFor='setting-'+key;field.append(labelNode);let input;if(key==='supplier_mode'||Array.isArray(placeholder)){input=el('select');const options=key==='supplier_mode'?Object.entries(settingsData.modes):placeholder.map(v=>[v,v==='native'?'Native tool calling':v==='json-schema'?'JSON-schema transport':v]);for(const [value,title] of options){const n=el('option','',title);n.value=value;input.append(n);}input.value=settingsData.preferences[key];}else{input=el('input');input.type=secretKeys.includes(key)?'password':'text';input.autocomplete='off';input.spellcheck=false;input.value=secretKeys.includes(key)?(settingsData.changes?.[key]||''):settingsData.preferences[key]||'';input.placeholder=secretKeys.includes(key)&&settingsData.configured[key]?'Saved securely · leave blank to keep':String(placeholder||'');}input.id='setting-'+key;input.dataset.setting=key;input.addEventListener('input',()=>{if(secretKeys.includes(key)){settingsData.changes??={};settingsData.changes[key]=input.value;}else settingsData.preferences[key]=input.value;$('settings-note').textContent='Unsaved changes · saving starts a new session.';});field.append(input);if(help)field.append(el('small','',help));if(secretKeys.includes(key)){if(settingsData.configured[key]){field.append(el('span','configured-note','Stored with Windows encryption'));const clear=button(clearedKeys.has(key)?'Keep saved value':'Clear saved value','clear-key'+(clearedKeys.has(key)?' marked':''),()=>{if(clearedKeys.has(key))clearedKeys.delete(key);else{clearedKeys.add(key);settingsData.changes??={};settingsData.changes[key]='';}renderSettings();$('settings-note').textContent='Credential changes apply only when you save.';});field.append(clear);}}grid.append(field);}body.append(grid);const info=el('div','info-box');info.append(el('strong','',settingsTab==='Local model'?'Your model explains. Independent checks decide.':settingsTab==='Suppliers'?'A supplier observation is not manufacturer engineering evidence.':'Configuration is separate from successful integration.'));info.append(document.createElement('br'),document.createTextNode(settingsTab==='Local model'?'No cloud fallback. Model output cannot override a failed check or confirm a requirement.':settingsTab==='Suppliers'?'Identity, technical evidence, stock, assembly classification and commercial terms keep distinct provenance.':'Use Check local services to record a real read-only operation. A saved connection does not prove availability.'));body.append(info);}card.append(head,body);root.append(card);}
function modal(title,description,type='info'){if($('modal').open)$('modal').close();$('modal-title').textContent=title;$('modal-content').replaceChildren();$('modal-actions').replaceChildren();$('modal').dataset.type=type;if(description)$('modal-content').append(el('p','modal-description',description));$('modal').showModal();return $('modal-content');}
function showServices(){const root=modal('Local service status','These are actual connection checks. They do not imply engineering qualification or complete cost coverage.');for(const [name,value] of Object.entries(state.services.checks)){const row=el('div','service-row'),text=el('div');text.append(el('strong','',{ollama:'Local model (Ollama)',jlcpcb:'JLCPCB official API',zetaris:'Zetaris SQL gateway',meterless:'Meterless H-MEM memory'}[name]||name),el('small','',value.available?'Operation succeeded':value.action||'Unavailable'));row.append(text,el('span','badge '+(value.available?'verified':'unverified'),value.available?'Available':'Unavailable'));root.append(row);}root.append(el('p','modal-description','Evidence record: '+state.services.record));}
function showBomQuestion(question){const root=modal('A requirement needs your answer','Your exact words are recorded. Leaving this unanswered does not confirm a requirement, and letting AI set it records a provisional default.','bom-question');root.append(el('div','question-copy',question));const input=el('input','modern-input');input.placeholder='Enter your answer, with units when needed';root.append(input);$('modal-actions').append(button('Leave unanswered','button',async()=>{await api('answer',{text:null});$('modal').close();}),button('Let AI set requirement','button',async()=>{await api('answer',{delegate:true});$('modal').close();},'spark'),button('Record answer','button primary',async()=>{await api('answer',{text:input.value});$('modal').close();}));input.focus();input.addEventListener('keydown',e=>{if(e.key==='Enter'){e.preventDefault();guard(async()=>{await api('answer',{text:input.value});$('modal').close();});}});}
function showEdit(){const root=modal('Update a requirement','Your exact typed answer is recorded. Dependent results are invalidated and independently rechecked.','edit');const select=el('select','modern-input');for(const [key,unit] of Object.entries(state.requirement_fields)){const n=el('option','',key.replaceAll('_',' ')+' · '+unit);n.value=key;select.append(n);}root.append(select);const input=el('input','modern-input');input.placeholder='An explicit value with the required unit';input.style.marginTop='13px';root.append(input);$('modal-actions').append(button('Cancel','button',()=>$('modal').close()),button('Apply & recheck','button primary',async()=>{await api('revalidate',{parameter:select.value,answer:input.value});$('modal').close();showInspector(true);}));}
function showSetup(){const root=modal('Add your API keys','PartLens looks up real parts with your own keys. They are encrypted for your Windows user on this computer and never stored in the project, the executable or browser storage. You can change them later in Settings.','setup');const values={};const group=(title,detail,items)=>{const section=el('section','setup-group');section.append(el('h3','',title),el('p','modal-description',detail));const grid=el('div','form-grid');for(const [key,label,secret,placeholder,full] of items){const field=el('div','field'+(full?' full':'')),labelNode=el('label','',label),input=el('input');labelNode.htmlFor='setup-'+key;input.id='setup-'+key;input.type=secret?'password':'text';input.autocomplete='off';input.spellcheck=false;input.placeholder=placeholder||'';input.addEventListener('input',()=>{values[key]=input.value.trim();});field.append(labelNode,input);grid.append(field);}section.append(grid);root.append(section);};group('JLCPCB parts data','Official read-only component lookup. Create the keys in your JLCPCB open-platform account.',[['JLC_APP_ID','Application ID',true],['JLC_ACCESS_KEY','Access key',true],['JLC_SECRET_KEY','Secret key',true,'',true]]);group('Zetaris (optional)','Your own authorized SQL gateway. Leave these empty if you do not run Zetaris.',[['ZETARIS_BASE_URL','Gateway origin',false,'http://localhost:3000'],['ZETARIS_ORG_ID','Organization ID',false],['ZETARIS_API_KEY','API key',true],['PARTLENS_ZETARIS_PARTS_TABLE','Existing supplier table',false,'SCHEMA.table']]);const error=el('p','setup-error hidden');root.append(error);api('settings_open').then(current=>{for(const k of secretKeys)if(current.configured[k]&&$('setup-'+k))$('setup-'+k).placeholder='Saved securely · leave blank to keep';for(const k of ['ZETARIS_BASE_URL','ZETARIS_ORG_ID','PARTLENS_ZETARIS_PARTS_TABLE'])if(current.preferences[k]&&$('setup-'+k))$('setup-'+k).placeholder=current.preferences[k];}).catch(()=>{});const fail=message=>{error.textContent=message;error.classList.remove('hidden');};const saved=async result=>{settingsData=result;clearedKeys.clear();renderSettings();$('modal').close();toast('Keys saved with Windows encryption. Use Check local services to confirm they work.');showGuide();};$('modal-actions').append(button('Import .env file','button',async()=>{try{const staged=await api('settings_import');if(!Object.values(staged.configured).some(Boolean))return;await saved(await api('settings_save',{preferences:staged.preferences,credentials:{},clear:[]}));}catch(e){fail(e.message||String(e));}},'folder'),button(state?.setup_needed?'Skip for now':'Not now','button',async()=>{if(state?.setup_needed){await api('setup_skip');toast(/Synthetic/.test(state.supplier)?'Using synthetic examples. Add keys any time from Start guide or Settings.':'Setup skipped; your saved configuration is unchanged.');}$('modal').close();showGuide();}),button('Save keys','button primary',async()=>{try{const jlc=['JLC_APP_ID','JLC_ACCESS_KEY','JLC_SECRET_KEY'].filter(k=>values[k]);if(jlc.length&&jlc.length<3)return fail('Enter all three JLCPCB values, or leave them all empty.');if(!jlc.length&&!values.ZETARIS_API_KEY)return fail('Enter your keys, or choose Skip for now.');const current=await api('settings_open'),preferences={...current.preferences};for(const k of ['ZETARIS_BASE_URL','ZETARIS_ORG_ID','PARTLENS_ZETARIS_PARTS_TABLE'])if(values[k])preferences[k]=values[k];if(!jlc.length&&!['JLC_APP_ID','JLC_ACCESS_KEY','JLC_SECRET_KEY'].every(k=>current.configured[k]))preferences.supplier_mode='zetaris';const credentials={};for(const k of secretKeys)if(values[k])credentials[k]=values[k];await saved(await api('settings_save',{preferences,credentials,clear:[]}));}catch(e){fail(e.message||String(e));}}));}
const tourSteps=[
['chat','#message-input','Describe your board','Type an idea in plain words, for example “a USB-C breadboard power supply with 3.3 V and 5 V rails, 500 mA each, 5 boards”, then press Enter.'],
['chat','#chat-mode','Choose the workflow','New design turns an idea into a preliminary design. BOM review checks a bill of materials you already have.'],
['chat','#attach-bom','Attach a BOM','Attach a CSV to review it in this conversation.'],
['chat','#assumptions-trigger','Assumptions','Decide whether PartLens may propose values you did not give. Proposals stay provisional until you confirm them.'],
['chat','.composer-area','Answer its questions','PartLens asks about missing requirements. Specify in chat confirms with your own words, Let AI set requirement keeps it provisional, Leave unanswered keeps it open.'],
['chat','#evidence-button','Evidence','Every check, source and requirement behind an answer. Recheck and Update requirement are here too.'],
['chat','#open-report','Reports','Open the saved report files for this conversation.'],
['chat','.history','Your conversations','Every conversation is saved here and can be reopened.'],
['bom','#bom-demo','The BOM workspace','Load the demo or Import CSV. A generated design arrives here with Open in BOM workspace.'],
['bom','#bom-review','Run checks','Matches parts and checks availability and replacements with deterministic rules. No AI involved.'],
['bom','#bom-agent','Local agent review','The local model investigates and asks for the build quantity. It cannot override a failed check.'],
['bom','#bom-compare','Compare costs','Your quantity against a hypothetical 60 boards. Unknown supplier terms keep the cost marked incomplete.'],
['bom','#bom-recall','Recall & recheck','Brings back earlier decisions from memory and re-runs their checks on current data.'],
['bom','.tabs','Results','Parts, requirements, replacements, sourcing, costs, explanation, sources and engineer review. Click any row for its evidence.'],
['bom','#project-select','Projects and revisions','Every import is saved as a revision you can return to.'],
['bom','#bom-export','Export','After engineer review, export a reviewed proposal. Your original BOM is never changed.'],
['settings','#settings-nav','Settings','Local model, Suppliers (source and keys), Zetaris connection, and Storage & services. Save changes applies them; nothing earlier is deleted.'],
[null,'#services-button','Service status','Shows which services actually respond right now.'],
[null,'#guide-button','Replay any time','Open this tour again from here.']];
let tourIndex=-1;
function endTour(){tourIndex=-1;$('tour')?.remove();}
async function showGuide(at=0,dir=1){if($('modal').open)$('modal').close();showInspector(false);let target=null;for(;at>=0&&at<tourSteps.length;at+=dir){const [where,selector]=tourSteps[at];if(where&&where!==page)await navigate(where);target=document.querySelector(selector);if(target&&target.offsetWidth&&target.getClientRects().length)break;target=null;}
if(!target){endTour();await navigate('chat');return;}
tourIndex=at;target.scrollIntoView({block:'nearest'});const [,,title,text]=tourSteps[at];let root=$('tour');if(!root){root=el('div','tour');root.id='tour';document.body.append(root);}root.replaceChildren();const rect=target.getBoundingClientRect(),spot=el('div','tour-spot');Object.assign(spot.style,{left:rect.left-6+'px',top:rect.top-6+'px',width:rect.width+12+'px',height:rect.height+12+'px'});const card=el('div','tour-card');card.setAttribute('role','dialog');card.setAttribute('aria-label',title);card.append(el('small','',`${at+1} of ${tourSteps.length}`),el('strong','',title),el('p','',text));const actions=el('div','tour-actions');actions.append(button('Skip tour','button quiet',async()=>{endTour();await navigate('chat');}));if(at>0)actions.append(button('Back','button',()=>showGuide(at-1,-1)));actions.append(button(at===tourSteps.length-1?'Finish':'Next','button primary',()=>showGuide(at+1,1)));card.append(actions);root.append(spot,card);
const width=card.offsetWidth,height=card.offsetHeight,below=rect.bottom+18+height<innerHeight-16,beside=rect.height>innerHeight*.4&&rect.right+18+width<innerWidth-16;if(beside){card.style.top=Math.max(16,rect.top)+'px';card.style.left=rect.right+18+'px';}else{card.style.top=(below?rect.bottom+18:Math.max(16,rect.top-18-height))+'px';card.style.left=Math.min(Math.max(16,rect.left),innerWidth-width-16)+'px';}actions.lastChild.focus();}
async function showNotices(){const notices=await api('notices');const root=modal('Licenses & notices','Bundled third-party components retain their own licenses.');const nav=el('div','notice-nav'),body=el('pre','notice-text');for(const item of notices)nav.append(button(item.name,'button',()=>{body.textContent=item.text;}));root.append(nav,body);if(notices.length)body.textContent=notices[0].text;}
async function copyText(text){if(navigator.clipboard?.writeText)await navigator.clipboard.writeText(text);else{const n=el('textarea');n.value=text;document.body.append(n);n.select();document.execCommand('copy');n.remove();}toast('Copied to clipboard');}
// Projects and human review are local controller actions, outside the model tool registry.
bomTabs.push(['Reviews','Engineer review']);
const renderBomEvidence=renderBom;
renderBom=function(){
  if(!state)return;
  renderProject();
  renderBomEvidence();
  if(bomTab==='Reviews')renderReviews();
};
function fillOptions(select,rows,value,placeholder){
  const items=rows.map(r=>[r.id,r.label]);
  if(JSON.stringify(items)!==select.dataset.items){
    select.replaceChildren();const blank=el('option','',placeholder);blank.value='';select.append(blank);
    for(const [id,label] of items){const n=el('option','',label);n.value=id;select.append(n);}
    select.dataset.items=JSON.stringify(items);
  }
  select.value=value||'';
}
function renderProject(){
  const p=state.project;
  fillOptions($('project-select'),p.projects.map(r=>({id:r.id,label:r.title})),p.id,'No project selected');
  fillOptions($('revision-select'),p.revisions.map(r=>({id:r.id,label:'r'+r.number+' · '+r.filename})),p.revision,'Import a BOM');
  for(const id of ['project-select','revision-select','project-create','bom-export'])$(id).disabled=state.busy;
  $('bom-export').disabled=state.busy||p.historical||!p.reviews.some(r=>r.action==='accept');
  const interrupted=p.jobs[0]?.status==='interrupted';
  $('project-notice').textContent=interrupted?'Previous operation was interrupted. Saved evidence is preserved. Run checks to start a new operation from this revision; no model or API call resumes automatically.':p.historical?'Historical results · Run checks to recheck saved inputs before reviewing or exporting. Earlier approvals stay in their original revision.':p.id?'Autosaved locally · Imports create immutable revisions. Engineer acceptance covers checked reference attributes only; application qualification and manufacturing release remain incomplete.':'Create a project or import a BOM. The original file is never changed.';
}
function currentReviews(){
  const map=new Map();for(const r of state.project.reviews)if(!map.has(r.decision_id))map.set(r.decision_id,r);return map;
}
function renderReviews(){
  const root=$('bom-content');root.replaceChildren();const head=el('div','panel-heading'),title=el('div');
  title.append(el('h3','','Engineer review'),el('p','','Accept checked reference attributes, reject a proposal, or request evidence. A human review cannot override a failed or unverified check.'));
  head.append(title);root.append(head);
  const decisions=new Map();for(const d of state.bom.Qualifications||[])decisions.set(d.decision_id,d);
  if(!decisions.size){root.append(empty('No proposals to review','Run checks first. Saved historical results require a fresh recheck.'));return;}
  const reviews=currentReviews(),table=makeTable(['Line','Candidate','Reference attributes','Application','Review']);
  for(const d of decisions.values()){
    const tr=el('tr');tr.append(el('td','',d.line),el('td','',d.comparison?.candidate?.mpn||d.candidate));
    for(const status of [d.status,d.application?.status||'unverified']){const td=el('td');td.append(badge(status,d.current_context===false));tr.append(td);}
    const td=el('td'),r=reviews.get(d.decision_id);
    const b=button('Review','button',()=>showHumanReview(d));b.disabled=state.busy||state.project.historical||d.current_context!==true;if(b.disabled)b.title=state.project.historical?'Saved results are historical. Run checks first.':'Evidence or context changed since this check. Run checks again to review it.';td.append(b);
    if(r)td.append(el('small','part-secondary',r.action+' · '+r.reviewer+' · '+r.at+' (recorded review; see history)'));
    tr.append(td);table.body.append(tr);
  }
  root.append(table.wrapper);
  const history=el('details','review-history');history.append(el('summary','','Review history and qualification scope'));
  history.append(el('pre','panel-text',JSON.stringify({reviews:state.project.reviews,scope:state.project.scope},null,2)));root.append(history);
}
// Decimal exponents ("1E+1") are exact but unreadable; plain notation keeps every digit.
function plainNumber(text){const m=/^(-?)(\d+)(?:\.(\d+))?E([+-]?\d+)(.*)$/i.exec(text);if(!m)return text;let digits=m[2]+(m[3]||''),point=m[2].length+Number(m[4]);if(point<=0)digits='0'.repeat(1-point)+digits,point=1;digits=digits.padEnd(point,'0');const whole=digits.slice(0,point).replace(/^0+(?=\d)/,''),frac=digits.slice(point).replace(/0+$/,'');return m[1]+whole+(frac?'.'+frac:'')+m[5];}
function showHumanReview(d){
  const root=modal('Review '+d.line,'This is a reviewed proposal, not manufacturing approval. Reviewer names are entered locally; this version has no authenticated engineering accounts.','human-review');
  const comparison=makeTable(['Attribute','Original','Candidate']);
  const original=d.comparison?.original||{},candidate=d.comparison?.candidate||{};
  const attributes=['manufacturer','mpn','package',...new Set([...Object.keys(original.params||{}),...Object.keys(candidate.params||{})])];
  for(const key of attributes){const tr=el('tr');tr.append(el('td','',key.replaceAll('_',' ')));for(const p of [original,candidate]){const value=p.params?.[key]?.value??p[key]??'Unknown';tr.append(el('td','',plainNumber(String(value))));}comparison.body.append(tr);}
  const checks=el('div','review-checks');
  for(const c of d.checks||[]){const line=el('p');line.append(badge(c.status),document.createTextNode(' '+c.message));checks.append(line);}
  const sources=el('details');sources.append(el('summary','','Full evidence and application checks'),el('pre','review-comparison',JSON.stringify(d,null,2)));
  const name=el('input','modern-input');name.placeholder='Reviewer name';name.setAttribute('aria-label','Reviewer name');name.maxLength=120;
  const reason=el('textarea','modern-input');reason.placeholder='Engineering rationale / remaining evidence';reason.setAttribute('aria-label','Review rationale');reason.maxLength=2000;reason.rows=3;
  const label=el('label','scope-ack'),ack=el('input');ack.type='checkbox';label.append(ack,document.createTextNode('I accept only the checked reference attributes. Application suitability, operating characteristics and manufacturing release remain unresolved.'));
  root.append(comparison.wrapper,checks,sources,name,reason,label);
  const save=action=>async()=>{await api('bom_human_review',{decision_id:d.decision_id,action,reviewer:name.value,reason:reason.value,acknowledge:ack.checked});$('modal').close();toast('Review recorded. Check results are unchanged.');};
  const accept=button('Accept checked attributes','button primary',save('accept'));accept.disabled=d.status!=='verified';
  $('modal-actions').append(button('Needs evidence','button',save('needs_evidence')),button('Reject proposal','button',save('reject')),accept);
}
$('project-create').onclick=()=>{const root=modal('New project','BOM revisions, records and reviews are saved in this local profile.');const input=el('input','modern-input');input.placeholder='Project name';input.maxLength=120;root.append(input);$('modal-actions').append(button('Create project','button primary',async()=>{await api('project_create',{title:input.value});$('modal').close();}));input.focus();};
$('project-select').onchange=e=>{if(e.target.value)guard(()=>api('project_select',{id:e.target.value}));};
$('revision-select').onchange=e=>{if(e.target.value)guard(()=>api('project_select',{id:state.project.id,revision:e.target.value}));};
$('bom-export').onclick=()=>guard(async()=>{const result=await api('bom_export');const root=modal('Reviewed proposal exported','Application qualification and manufacturing release remain incomplete. Recorded costs are not a quote for the manually selected proposal.');root.append(el('code','export-path',result.path));root.append(button('Copy folder path','button',()=>copyText(result.path)));});
hydrate();
document.querySelectorAll('[data-page]').forEach(n=>n.addEventListener('click',()=>guard(()=>navigate(n.dataset.page))));document.querySelector('.brand').addEventListener('click',e=>{e.preventDefault();guard(()=>navigate('chat'));});
$('new-chat').onclick=()=>guard(async()=>{await api('new_chat');$('message-input').value='';autoSize();followEnd=true;await navigate('chat');$('message-input').focus();});
$('send').onclick=()=>guard(send);$('message-input').addEventListener('input',autoSize);$('message-input').addEventListener('keydown',e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();guard(send);}});
$('transcript').addEventListener('scroll',()=>{const n=$('transcript');followEnd=n.scrollHeight-n.scrollTop-n.clientHeight<70;});
$('attach-bom').onclick=()=>guard(async()=>{await api('select_bom');if(state.attachment)$('chat-mode').value='bom';});
$('assumptions-trigger').onclick=()=>$('assumptions-panel').classList.toggle('hidden');$('skip-question').onclick=()=>guard(()=>api('answer',{text:null}));$('ai-answer-question').onclick=()=>guard(()=>api('answer',{delegate:true}));$('stop').onclick=()=>guard(()=>api('stop'));
$('evidence-button').onclick=()=>showInspector(!inspectorVisible);$('close-evidence').onclick=()=>showInspector(false);$('evidence-section').onchange=e=>{evidenceSection=e.target.value;renderInspector();};
$('recheck').onclick=()=>guard(()=>api('revalidate'));$('edit-requirement').onclick=showEdit;$('open-report').onclick=()=>guard(()=>api('open_report',{workspace:page}));
$('guide-button').onclick=()=>guard(async()=>showGuide());$('services-button').onclick=()=>guard(async()=>{serviceRequested=true;await api('services');});
for(const [id,action,payload] of [['bom-demo','bom_load',{demo:true}],['bom-import','bom_load',{}],['bom-review','bom_manual',{}],['bom-agent','bom_live',{}],['bom-new','bom_new',{}],['bom-recall','bom_recall',{}],['bom-compare','bom_cost',{}]])$(id).onclick=()=>guard(()=>api(action,payload));
$('settings-import').onclick=()=>guard(async()=>{settingsData=await api('settings_import');clearedKeys.clear();renderSettings();$('settings-note').textContent='Imported into the form. Save to encrypt and apply.';});
$('settings-reset').onclick=()=>guard(async()=>{settingsData=await api('settings_open');clearedKeys.clear();renderSettings();$('settings-note').textContent='Unsaved changes discarded. Existing configuration preserved.';});
$('settings-save').onclick=()=>guard(async()=>{settingsData=await api('settings_save',{preferences:settingsData.preferences,credentials:settingsData.changes||{},clear:[...clearedKeys]});clearedKeys.clear();renderSettings();$('settings-note').textContent='Saved with Windows encryption. Previous evidence preserved.';toast('Settings saved. New session started.');});
$('modal-close').onclick=()=>{if($('modal').dataset.type==='bom-question')guard(()=>api('answer',{text:null}));$('modal').close();};$('modal').addEventListener('cancel',()=>{if($('modal').dataset.type==='bom-question')guard(()=>api('answer',{text:null}));});
addEventListener('resize',()=>{if(tourIndex>=0)showGuide(tourIndex);});document.addEventListener('keydown',e=>{if(tourIndex>=0){if(e.key==='Escape'){endTour();return;}if(e.key==='ArrowRight'){showGuide(tourIndex+1,1);return;}if(e.key==='ArrowLeft'&&tourIndex>0){showGuide(tourIndex-1,-1);return;}}if(!e.ctrlKey)return;if(e.key==='n'){e.preventDefault();$('new-chat').click();}if(e.key==='j'){e.preventDefault();showInspector(!inspectorVisible);}if(e.key===','){e.preventDefault();guard(()=>navigate('settings'));}});
let resolveReady;const ready=new Promise(resolve=>resolveReady=resolve);
async function poll(){if(polling||!window.pywebview?.api)return;polling=true;try{await api('snapshot',{since:state?.revision});}catch(error){$('chat-status').textContent='Desktop connection unavailable. Existing records are preserved.';}finally{polling=false;}}
async function init(){await guard(async()=>{await api('snapshot');await navigate('chat');resolveReady(true);if(state?.setup_needed)showSetup();});setInterval(poll,600);}
window.addEventListener('pywebviewready',init,{once:true});
window.PartLens=Object.freeze({ready,api,navigate,showSettingsTab:tab=>{settingsTab=tab;renderSettings();},richText,
  getState:()=>state,inspect:()=>({page,renderer:'WebView2',settingsOpen:!$('settings-page').classList.contains('hidden'),bomOpen:!$('bom-page').classList.contains('hidden'),inputRadius:getComputedStyle(document.querySelector('.composer')).borderRadius})});
