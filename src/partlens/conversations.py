"""Append-only chat history is a presentation journal, never engineering evidence or user-confirmation authority."""
from dataclasses import dataclass
import json
from pathlib import Path
import re

from .records import RunRecorder,read_events


@dataclass(frozen=True)
class Conversation:
    id: str
    title: str
    mode: str
    path: Path


class ConversationStore:
    def __init__(self,state):
        self.state=Path(state).resolve();self.folder=self.state/'conversations'
        self.folder.mkdir(parents=True,exist_ok=True)
        if not self.folder.resolve().is_relative_to(self.state):raise ValueError('Conversation folder is outside local state')

    def path(self,id):
        if not re.fullmatch(r'[0-9]{8}T[0-9]{6}Z-[a-f0-9]{6}',id):raise ValueError('Invalid conversation identifier')
        return self.folder/(id+'.jsonl')

    def create(self,title,mode):
        if mode not in {'design','bom'}:raise ValueError('Unsupported conversation mode')
        rec=RunRecorder.create(self.folder)
        title=' '.join(title.split())[:60] or 'New conversation'
        rec.log('conversation_created',title=title,mode=mode)
        return Conversation(rec.run_id,title,mode,rec.path)

    def events(self,chat):
        if chat.path!=self.path(chat.id):raise ValueError('Conversation outside its store')
        self.owned_path(chat.path)
        return read_events(chat.path)

    def append(self,chat,type_,**values):
        events=self.events(chat)
        return RunRecorder(chat.path,chat.id,events[-1]['seq'] if events else 0).log(type_,**values)

    def message(self,chat,role,text,kind='message',**metadata):
        if role not in {'user','assistant','system'} or not isinstance(text,str):raise ValueError('Invalid chat message')
        return self.append(chat,'chat_message',role=role,text=text,kind=kind,**metadata)

    def list(self):
        result=[]
        for path in sorted(self.folder.glob('*.jsonl'),key=lambda p:p.stat().st_mtime,reverse=True):
            try:
                if path.is_symlink():continue
                id=path.stem
                if path!=self.path(id):continue
                first=json.loads(path.read_text(encoding='utf-8').splitlines()[0])
                if first['type']=='conversation_created':result.append(Conversation(id,first['title'],first['mode'],path))
            except (ValueError,KeyError,IndexError):continue
        return result

    def latest_artifact(self,chat):
        return next((e for e in reversed(self.events(chat)) if e['type']=='chat_artifact'),None)

    def owned_path(self,path):
        path=Path(path).resolve()
        if not path.is_relative_to(self.state):raise ValueError('Artifact is outside local conversation state')
        return path

    def report(self,chat):
        artifact=self.latest_artifact(chat)
        if not artifact:return None
        result=json.loads(self.owned_path(artifact['report']).read_text(encoding='utf-8'))
        if not isinstance(result,dict) or result.get('mode') not in {'new_design','bom_review'}:
            raise ValueError('Unsupported recorded report')
        return result
