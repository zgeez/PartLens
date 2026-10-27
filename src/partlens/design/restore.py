"""Operator-only restoration from an actual run; model tools cannot supply a requirement snapshot."""

from ..core.model import to_jsonable
from .requirements import Entry, Requirements, State, parse


def restore_requirements(snapshot: dict, events: list[dict]) -> Requirements:
    if snapshot.get('schema')!='partlens.requirements/1':
        raise ValueError('unsupported requirements schema')
    source=snapshot['description_source']
    if not any(e['type']=='user_message' and e.get('origin','user')=='user' and e['text']==snapshot['description']
               and source==f"user:{e['run']}#seq{e['seq']}" for e in events):
        raise ValueError('description lacks original user provenance')
    confirmed=[]
    for e in events:
        if e['type']!='tool_call' or e.get('error'):continue
        output=e.get('output',{})
        if e.get('name')=='record_design_requirement':confirmed.append(output.get('entry',{}))
        if e.get('name')=='record_design_requirements':
            confirmed.extend(row.get('entry',{}) for row in output.get('recorded',[]))
    entries=[]
    for row in snapshot['history']:
        value,unit=parse(row['parameter'],str(row['value'])+(row['unit'] or ''))
        state=State(row['state'])
        if state is State.CONFIRMED:
            original=next((c for c in confirmed if c.get('binding') and all(c.get(k)==row.get(k)
                for k in ('parameter','value','unit','source','quote','revision'))),None)
            if not original or not any(e['type']=='user_message' and e.get('origin','user')=='user'
                and row['quote'] and row['quote'] in e['text'] and row['source']==f"user:{e['run']}#seq{e['seq']}"
                for e in events):
                raise ValueError('confirmed requirement lacks its original successful tool result and quoted user message')
        entries.append(Entry(row['parameter'],value,unit,state,row['source'],row['quote'],row['rationale'],
                             tuple(row['dependencies']),row['revision']))
    result=Requirements(snapshot['design_id'],snapshot['description'],source,entries,snapshot['revision'])
    if result.view()!={k:snapshot[k] for k in result.view()}:
        raise ValueError('restored requirements differ from the recorded typed snapshot')
    return result
