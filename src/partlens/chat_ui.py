"""Native chat workspace: presentation/history never confer engineering verification."""
import json
import os
from pathlib import Path
import queue
import threading
import time
import tkinter as tk
from tkinter import ttk,filedialog,messagebox

from .conversations import ConversationStore
from .chat_engine import ChatEngine,UserCancelled
from .paths import resource_root
from .secrets import redact

BG='#F7F7F2';WHITE='#FFFFFF';INK='#20342E';MUTED='#74807A';LINE='#DFE5DE'
SIDE='#13251F';SIDE_HOVER='#213C32';ACCENT='#26745D';PALE='#E9F1E9';USER='#E5EFE5'
FONT='Segoe UI'


class RoundedPanel(tk.Canvas):
    """A resizeable native surface with a rounded border and ordinary child widgets."""
    def __init__(self,parent,*,fill=WHITE,border=LINE,padding=14):
        super().__init__(parent,bg=parent.cget('bg'),highlightthickness=0,height=1)
        self.fill,self.border,self.padding=fill,border,padding
        self.body=tk.Frame(self,bg=fill);self.body_window=self.create_window((padding,padding),window=self.body,anchor='nw')
        self.body.bind('<Configure>',self.resize);self.bind('<Configure>',self.resize)
    def resize(self,event=None):
        w=max(1,self.winfo_width());p=self.padding;h=self.body.winfo_reqheight()+2*p;r=20
        self.configure(height=h);self.itemconfigure(self.body_window,width=max(1,w-2*p))
        self.delete('surface')
        self.create_polygon([r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1],
            smooth=True,splinesteps=24,fill=self.fill,outline=self.border,tags='surface')
        self.tag_lower('surface')


class SoftButton(tk.Canvas):
    def __init__(self,parent,text,command,*,width=120,height=38,bg=WHITE,fg=INK,border=LINE,canvas_bg=None):
        super().__init__(parent,width=width,height=height,bg=canvas_bg or parent.cget('bg'),highlightthickness=0,
                         cursor='hand2',takefocus=1)
        self.command=command;self.label=text;self.fill=bg;self.fg=fg;self.border=border;self.enabled=True
        self.bind('<Configure>',lambda _:self.draw());self.bind('<Button-1>',lambda _:self.invoke())
        self.bind('<Return>',lambda _:self.invoke());self.bind('<space>',lambda _:self.invoke())
        self.bind('<Enter>',lambda _:self.draw(True));self.bind('<Leave>',lambda _:self.draw())
        self.bind('<FocusIn>',lambda _:self.draw(True));self.bind('<FocusOut>',lambda _:self.draw())
        self.draw()
    def draw(self,hover=False):
        self.delete('all');w=max(self.winfo_width(),int(self.cget('width')));h=int(self.cget('height'));r=12
        points=[r,1,w-r,1,w-1,1,w-1,r,w-1,h-r,w-1,h-1,w-r,h-1,r,h-1,1,h-1,1,h-r,1,r,1,1]
        self.create_polygon(points,smooth=True,splinesteps=18,fill=self.fill,
                            outline=ACCENT if hover and self.enabled else self.border)
        self.create_text(w/2,h/2,text=self.label,fill=self.fg if self.enabled else MUTED,font=(FONT,10,'bold'))
    def invoke(self):
        if self.enabled:self.command()
    def set(self,*,text=None,enabled=None):
        if text is not None:self.label=text
        if enabled is not None:self.enabled=enabled
        self.draw()


class ChatApp:
    def __init__(self,catalogs,state,fees=None,*,demo_bom=None,design_name='easyduino-rp2040',**unused):
        self.root=tk.Tk();self.root.title('PartLens — Engineering, in conversation')
        sw,sh=self.root.winfo_screenwidth(),self.root.winfo_screenheight()
        self.root.geometry(f'{min(1360,sw-80)}x{min(860,sh-90)}');self.root.minsize(980,640);self.root.configure(bg=BG)
        self.catalogs,self.state,self.fees=catalogs,Path(state),fees
        self.demo_bom,self.design_name=demo_bom,design_name
        self.bridge=None;self.busy=False;self.closed=False;self.close_when_done=False
        self.events=queue.Queue();self.cancel=threading.Event();self.answer_ready=threading.Event();self.answer=None
        self.pending_question=False;self.pending_bom=None;self.chat=None;self.artifact=None
        self.store=ConversationStore(self.state);self.engine=ChatEngine(self.state,catalogs,self.store)
        self.status=tk.StringVar(value='Ready when you are.');self.configuration_text=tk.StringVar(value='Local model configured')
        self.mode=tk.StringVar(value='design');self.proposals=tk.BooleanVar(value=True);self.inspector_open=False
        self.settings_callback=None;self.images={};self.message_labels=[];self.activity=[];self.started=0;self.visible_messages=80;self.follow_end=True
        self._style();self._images();self._layout();self.new_session()
        self.root.protocol('WM_DELETE_WINDOW',self.close)
        self.root.bind('<Control-n>',lambda _:self.new_session());self.root.bind('<Control-j>',lambda _:self.toggle_inspector())
        self.root.bind('<Control-comma>',lambda _:self.open_settings())
        self.root.after(100,self.pump)

    def _style(self):
        style=ttk.Style(self.root);style.theme_use('clam')
        style.configure('TNotebook',background=BG,borderwidth=0)
        style.configure('TNotebook.Tab',padding=(12,9),font=(FONT,10),background=BG,foreground=MUTED)
        style.map('TNotebook.Tab',background=[('selected',WHITE)],foreground=[('selected',INK)])
        style.configure('TFrame',background=BG);style.configure('TLabel',background=BG,foreground=INK,font=(FONT,10))
        style.configure('TButton',font=(FONT,10),padding=7)
        style.configure('TEntry',padding=6,fieldbackground=WHITE)

    def _images(self):
        folder=resource_root()/'assets/brand'
        for key,name in [('logo','logo-32.png'),('mark','logo-64.png'),('hero','hero-320.png')]:
            if (folder/name).exists():self.images[key]=tk.PhotoImage(file=folder/name,master=self.root)
        if 'mark' in self.images:self.root.iconphoto(True,self.images['mark'])

    def _layout(self):
        self.root.columnconfigure(1,weight=1);self.root.rowconfigure(0,weight=1)
        side=tk.Frame(self.root,bg=SIDE,width=226);side.grid(row=0,column=0,sticky='nsew');side.pack_propagate(False)
        brand=tk.Frame(side,bg=SIDE);brand.pack(fill='x',padx=20,pady=(23,22))
        if 'logo' in self.images:tk.Label(brand,image=self.images['logo'],bg=SIDE).pack(side='left',padx=(0,10))
        tk.Label(brand,text='PartLens',bg=SIDE,fg='#F0F5EC',font=(FONT,19,'bold')).pack(side='left')
        SoftButton(side,'＋  New conversation',self.new_session,width=190,bg=SIDE_HOVER,fg='#EAF2E9',border='#355345').pack(padx=18,fill='x')
        tk.Label(side,text='YOUR WORKSPACE',bg=SIDE,fg='#8DA597',font=(FONT,8,'bold'),anchor='w').pack(fill='x',padx=22,pady=(28,10))
        bottom=tk.Frame(side,bg=SIDE);bottom.pack(fill='x',side='bottom',padx=18,pady=18)
        SoftButton(bottom,'BOM workspace  ↗',self.advanced,width=190,bg=SIDE,fg='#B6C9BB',border='#294438').pack(fill='x',pady=4)
        SoftButton(bottom,'Settings',self.open_settings,width=190,bg=SIDE,fg='#DCE7D9',border='#294438').pack(fill='x',pady=4)
        self.services_label=tk.Label(bottom,text='Services not checked',bg=SIDE,fg='#8DA597',font=(FONT,9),anchor='w',cursor='hand2')
        self.services_label.pack(fill='x',pady=(14,2));self.services_label.bind('<Button-1>',lambda _:self.check_services())
        tk.Label(bottom,text='Evidence before confidence.',bg=SIDE,fg='#789382',font=(FONT,9),anchor='w').pack(fill='x')
        history_canvas=tk.Canvas(side,bg=SIDE,highlightthickness=0,width=206);history_canvas.pack(fill='both',expand=True,padx=10)
        self.history=tk.Frame(history_canvas,bg=SIDE);history_window=history_canvas.create_window((0,0),window=self.history,anchor='nw')
        self.history.bind('<Configure>',lambda _:history_canvas.configure(scrollregion=history_canvas.bbox('all')))
        history_canvas.bind('<Configure>',lambda e:history_canvas.itemconfigure(history_window,width=e.width))
        self.history_canvas=history_canvas

        self.main=tk.Frame(self.root,bg=BG);self.main.grid(row=0,column=1,sticky='nsew');self.main.rowconfigure(1,weight=1);self.main.columnconfigure(0,weight=1)
        header=tk.Frame(self.main,bg=BG,height=72);header.grid(row=0,column=0,sticky='ew',padx=30,pady=(18,0))
        titleblock=tk.Frame(header,bg=BG);titleblock.pack(side='left',fill='x',expand=True)
        self.title=tk.Label(titleblock,text='New conversation',bg=BG,fg=INK,font=(FONT,13,'bold'),anchor='w',width=1);self.title.pack(fill='x')
        tk.Label(titleblock,textvariable=self.configuration_text,bg=BG,fg=MUTED,font=(FONT,9),anchor='w',width=1).pack(fill='x',pady=(4,12))
        SoftButton(header,'Evidence  ◫',self.toggle_inspector,width=110,bg=BG).pack(side='right',padx=(12,0))
        self.open_files_button=SoftButton(header,'Open report ↗',self.open_files,width=115,bg=BG)
        self.open_files_button.pack(side='right')

        transcript=tk.Frame(self.main,bg=BG);transcript.grid(row=1,column=0,sticky='nsew')
        self.canvas=tk.Canvas(transcript,bg=BG,highlightthickness=0)
        scroll=tk.Scrollbar(transcript,command=self.scroll_transcript,width=8,troughcolor=BG,bg=LINE,relief='flat')
        scroll.pack(side='right',fill='y');self.canvas.pack(side='left',fill='both',expand=True);self.canvas.configure(yscrollcommand=scroll.set)
        self.messages=tk.Frame(self.canvas,bg=BG)
        self.window=self.canvas.create_window((0,0),window=self.messages,anchor='nw')
        self.messages.bind('<Configure>',self.message_bounds)
        self.canvas.bind('<Configure>',self.resize_messages);self.root.bind_all('<MouseWheel>',self.mousewheel,add='+')

        self.composer_outer=tk.Frame(self.main,bg=BG);self.composer_outer.grid(row=2,column=0,sticky='ew',padx=30,pady=(10,16))
        self.progress=tk.Label(self.composer_outer,textvariable=self.status,bg=BG,fg=MUTED,font=(FONT,9),anchor='w')
        self.progress.pack(fill='x',pady=(0,8))
        panel=RoundedPanel(self.composer_outer);panel.pack(fill='x');shell=panel.body
        self.input=tk.Text(shell,bg=WHITE,fg=INK,insertbackground=ACCENT,height=3,wrap='word',relief='flat',
                           font=(FONT,12),padx=0,pady=2,undo=True)
        self.input.pack(fill='x');self.input.bind('<Return>',self.send_key);self.input.bind('<Shift-Return>',lambda _:None)
        self.input.bind('<Control-Return>',self.send_key)
        self.input.bind('<<Modified>>',self.input_changed)
        self.placeholder=tk.Label(self.input,text='Describe an idea, or ask about your engineering report…',bg=WHITE,fg='#9AA69E',font=(FONT,12),cursor='xterm')
        self.placeholder.place(x=2,y=3);self.placeholder.bind('<Button-1>',lambda _:self.input.focus_set())
        controls=tk.Frame(shell,bg=WHITE);controls.pack(fill='x',pady=(8,0))
        SoftButton(controls,'＋ Attach BOM',self.attach,width=118,height=32,bg=WHITE,border=WHITE).pack(side='left')
        self.mode_button=SoftButton(controls,'New design ▾',self.mode_menu,width=124,height=32,bg=BG);self.mode_button.pack(side='left',padx=6)
        self.attachment=tk.Label(controls,text='',bg=WHITE,fg=ACCENT,font=(FONT,9),cursor='hand2');self.attachment.pack(side='left',padx=4)
        self.attachment.bind('<Button-1>',lambda _:self.clear_attachment())
        self.send_button=SoftButton(controls,'Send ↑',self.send,width=86,height=34,bg=ACCENT,fg=WHITE,border=ACCENT)
        self.send_button.pack(side='right')
        self.skip_button=SoftButton(controls,'Leave unanswered',self.skip,width=140,height=32,bg=WHITE)
        self.stop_button=SoftButton(controls,'Stop',self.stop,width=60,height=32,bg=WHITE)
        footer=tk.Frame(self.composer_outer,bg=BG);footer.pack(fill='x',pady=(7,0))
        self.proposal_box=tk.Checkbutton(footer,text='Propose missing choices as assumptions',variable=self.proposals,
            bg=BG,fg=MUTED,activebackground=BG,activeforeground=INK,selectcolor=BG,font=(FONT,9),bd=0,highlightthickness=0)
        self.proposal_box.pack(side='left')
        tk.Label(footer,text='Enter to send · Shift+Enter for a new line',bg=BG,fg=MUTED,font=(FONT,8)).pack(side='right')

        self.inspector=tk.Frame(self.root,bg=WHITE,width=340,highlightbackground=LINE,highlightthickness=1)
        self.inspector.pack_propagate(False)
        top=tk.Frame(self.inspector,bg=WHITE);top.pack(fill='x',padx=18,pady=20)
        tk.Label(top,text='Evidence',font=(FONT,15,'bold'),bg=WHITE,fg=INK).pack(side='left')
        SoftButton(top,'×',self.toggle_inspector,width=30,height=28,bg=WHITE,border=WHITE).pack(side='right')
        self.evidence_stamp=tk.Label(self.inspector,text='Recorded results · not live inventory',bg=WHITE,fg=MUTED,font=(FONT,9),wraplength=300,justify='left')
        self.evidence_stamp.pack(fill='x',padx=18,pady=(0,12))
        actions=tk.Frame(self.inspector,bg=WHITE);actions.pack(fill='x',padx=16,pady=(0,12))
        self.recheck_button=SoftButton(actions,'Recheck',lambda:self.revalidate(),width=92,bg=PALE);self.recheck_button.pack(side='left')
        self.edit_button=SoftButton(actions,'Update requirement',self.edit,width=174,bg=WHITE);self.edit_button.pack(side='right')
        self.section=tk.StringVar(value='Overview')
        self.section_box=ttk.Combobox(self.inspector,textvariable=self.section,state='readonly',values=['Overview'])
        self.section_box.pack(fill='x',padx=18,pady=(0,10));self.section_box.bind('<<ComboboxSelected>>',lambda _:self.render_section())
        self.detail=tk.Text(self.inspector,wrap='word',bg=WHITE,fg=INK,font=(FONT,10),relief='flat',padx=18,pady=10)
        detail_scroll=tk.Scrollbar(self.inspector,command=self.detail.yview,width=8)
        detail_scroll.pack(side='right',fill='y');self.detail.pack(fill='both',expand=True);self.detail.configure(yscrollcommand=detail_scroll.set)
        self.views={};self.render_inspector()

    def add_settings(self,callback):self.settings_callback=callback
    def open_settings(self):
        if self.settings_callback:self.settings_callback()

    def refresh(self):
        self.engine.catalogs=self.catalogs;self.render_history();self.render_inspector()

    def new_session(self):
        if self.busy:self.status.set('Finish or stop the current reply before starting another conversation.');return
        self.chat=None;self.artifact=None;self.activity=[];self.pending_bom=None;self.pending_question=False;self.visible_messages=80
        self.mode.set('design');self.mode_button.set(text='New design ▾');self.title.configure(text='New conversation')
        self.input.delete('1.0','end');self.attachment.configure(text='');self.status.set('Ready when you are.')
        self.render_messages();self.render_history();self.render_inspector();self.input.focus_set()

    def render_history(self):
        for w in self.history.winfo_children():w.destroy()
        chats=self.store.list()
        if not chats:tk.Label(self.history,text='Your conversations will appear here.',bg=SIDE,fg='#789382',font=(FONT,10),wraplength=180,justify='left').pack(padx=12,pady=15)
        for chat in chats:
            selected=self.chat and chat.id==self.chat.id
            row=tk.Frame(self.history,bg=SIDE_HOVER if selected else SIDE,cursor='hand2');row.pack(fill='x',pady=2)
            label=tk.Label(row,text=chat.title,bg=row.cget('bg'),fg='#E3EBDF' if selected else '#B0C3B5',font=(FONT,10),anchor='w',wraplength=182,justify='left',padx=12,pady=10)
            label.pack(fill='x');label.bind('<Button-1>',lambda _,c=chat:self.select(c))

    def select(self,chat):
        if self.busy:self.status.set('Finish or stop the current reply before switching conversations.');return
        self.chat=chat;self.mode.set(chat.mode);self.pending_bom=None;self.attachment.configure(text='');self.visible_messages=80
        self.title.configure(text=chat.title);self.mode_button.set(text='New design ▾' if chat.mode=='design' else 'BOM review ▾')
        self.artifact=self.store.latest_artifact(chat);self.activity=[]
        self.status.set('Saved conversation. Recheck recorded evidence before relying on current availability.')
        self.render_messages();self.render_history();self.render_inspector()

    def render_messages(self,scroll_end=True):
        self.follow_end=scroll_end
        for w in self.messages.winfo_children():w.destroy()
        self.message_labels=[]
        events=self.store.events(self.chat) if self.chat else []
        messages=[e for e in events if e['type']=='chat_message']
        if not messages:self.welcome();return
        if len(messages)>self.visible_messages:
            SoftButton(self.messages,'Earlier messages',self.earlier_messages,width=160,bg=BG).pack(pady=12)
        for e in messages[-self.visible_messages:]:self.message_card(e)
        self.root.after_idle(lambda:self.canvas.yview_moveto(1 if scroll_end else 0))

    def earlier_messages(self):
        self.visible_messages+=80;self.render_messages(scroll_end=False)

    def message_bounds(self,event=None):
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        if self.follow_end:self.canvas.yview_moveto(1)

    def scroll_transcript(self,*args):
        self.follow_end=False;self.canvas.yview(*args)

    def welcome(self):
        frame=tk.Frame(self.messages,bg=BG);frame.pack(fill='both',expand=True,padx=30,pady=(12,15))
        if 'hero' in self.images:tk.Label(frame,image=self.images['hero'],bg=BG).pack(pady=(0,8))
        tk.Label(frame,text='What are we building?',bg=BG,fg=INK,font=(FONT,27,'bold')).pack()
        sub=tk.Label(frame,text='An idea to explore. A component to check.\nA clearer path through the evidence.',bg=BG,fg=MUTED,font=(FONT,12),justify='center')
        sub.pack(pady=(10,24))
        cards=tk.Frame(frame,bg=BG);cards.pack()
        for title,text in [('Explore an idea','Design a Bluetooth temperature monitor.'),('Review a BOM','Review the demo BOM and investigate sourcing alternatives.')]:
            SoftButton(cards,title,lambda t=text:self.suggestion(t),width=180,height=48,bg=WHITE).pack(side='left',padx=6)
        tk.Label(frame,text='Independent checks. Visible sources. Provisional means provisional.',bg=BG,fg=MUTED,font=(FONT,9)).pack(pady=(20,0))

    def suggestion(self,text):
        self.input.delete('1.0','end');self.input.insert('1.0',text);self.input.focus_set()
        if text.startswith('Review the demo'):
            self.mode.set('bom');self.pending_bom=self.demo_bom;self.mode_button.set(text='BOM review ▾');self.attachment.configure(text='Demo BOM  ×')

    def message_card(self,event):
        user=event['role']=='user';kind=event.get('kind','message')
        outer=tk.Frame(self.messages,bg=BG);outer.pack(fill='x',padx=30,pady=(10,14))
        if user:
            panel=RoundedPanel(outer,fill=USER,border=USER,padding=16);panel.pack(fill='x',padx=(65,0));card=panel.body
        else:
            card=tk.Frame(outer,bg=BG,padx=2,pady=6);card.pack(anchor='w',fill='x',padx=(0,24))
        heading='You' if user else ('PartLens · Commentary, not a decision' if kind=='commentary' else
            'PartLens · Engineering report' if kind=='report' else 'PartLens · Requirement' if kind=='question' else 'PartLens')
        tk.Label(card,text=heading,bg=card.cget('bg'),fg=ACCENT if not user else '#4C695A',font=(FONT,9,'bold'),anchor='w').pack(fill='x',pady=(0,7))
        label=tk.Label(card,text=event['text'],bg=card.cget('bg'),fg=INK,font=(FONT,12),justify='left',anchor='w',wraplength=680)
        label.pack(fill='x');self.message_labels.append((label,125 if user else 75))
        if not user:
            tools=tk.Frame(card,bg=BG);tools.pack(fill='x',pady=(8,0))
            copy=tk.Label(tools,text='Copy',bg=BG,fg=MUTED,font=(FONT,9),cursor='hand2');copy.pack(side='left')
            copy.bind('<Button-1>',lambda _,s=event['text']:self.copy(s))
            if kind=='report':
                link=tk.Label(tools,text='  View evidence ↗',bg=BG,fg=ACCENT,font=(FONT,9),cursor='hand2');link.pack(side='left')
                link.bind('<Button-1>',lambda _:self.show_inspector())
        self.resize_messages()

    def copy(self,text):self.root.clipboard_clear();self.root.clipboard_append(text)
    def resize_messages(self,event=None):
        width=max(250,self.canvas.winfo_width());self.canvas.itemconfigure(self.window,width=width)
        for label,margin in self.message_labels:label.configure(wraplength=max(150,width-margin-75))
    def mousewheel(self,event):
        widget=event.widget
        while widget is not None:
            if widget in {self.messages,self.canvas}:
                self.follow_end=False;self.canvas.yview_scroll(-int(event.delta/120),'units');break
            if widget in {self.history,self.history_canvas}:self.history_canvas.yview_scroll(-int(event.delta/120),'units');break
            widget=getattr(widget,'master',None)
    def input_changed(self,event=None):
        if self.input.get('1.0','end').strip():self.placeholder.place_forget()
        else:self.placeholder.place(x=2,y=3)
        self.input.edit_modified(False)
    def send_key(self,event):
        self.send();return 'break'
    def mode_menu(self):
        if self.busy or self.chat:return
        menu=tk.Menu(self.root,tearoff=False,font=(FONT,10))
        for value,title in [('design','New design'),('bom','BOM review')]:menu.add_command(label=title,command=lambda v=value,t=title:(self.mode.set(v),self.mode_button.set(text=t+' ▾')))
        menu.tk_popup(self.mode_button.winfo_rootx(),self.mode_button.winfo_rooty()+36)
    def attach(self):
        if self.busy:return
        if self.chat:self.status.set('Start a new conversation to attach a different BOM.');return
        path=filedialog.askopenfilename(parent=self.root,title='Attach a CSV BOM',filetypes=[('CSV BOM','*.csv')])
        if not path:return
        if any(p.casefold()=='experiments' or 'benchmark' in p.casefold() or 'badge' in p.casefold() for p in Path(path).resolve().parts):
            self.status.set('Excluded private material cannot be imported.');return
        self.pending_bom=Path(path);self.mode.set('bom');self.mode_button.set(text='BOM review ▾')
        self.attachment.configure(text=Path(path).name[:24]+'  ×')
        if not self.input.get('1.0','end').strip():self.input.insert('1.0','Review this BOM and identify missing requirements, sourcing risks and alternatives.')
    def clear_attachment(self):
        if not self.busy:self.pending_bom=None;self.attachment.configure(text='')

    def send(self):
        text=self.input.get('1.0','end').strip()
        if not text:return
        if len(text)>5000:self.status.set('Please keep a message under 5,000 characters.');return
        if self.pending_question:
            self.store.message(self.chat,'user',text,kind='requirement_answer')
            self.input.delete('1.0','end');self.pending_question=False;self.answer=text;self.answer_ready.set()
            self.skip_button.pack_forget();self.send_button.set(text='Send ↑',enabled=False);self.render_messages();return
        if self.busy:return
        if self.mode.get()=='bom' and not self.chat and self.pending_bom is None:
            self.status.set('Attach a CSV BOM or choose the demo suggestion first.');return
        if self.chat is None:self.chat=self.store.create(text,self.mode.get())
        self.store.message(self.chat,'user',text)
        self.input.delete('1.0','end');self.title.configure(text=self.chat.title)
        self.render_messages();self.render_history()
        if self.store.latest_artifact(self.chat):
            self.start(lambda:self.engine.explain(self.chat,text,self.notify,self.cancel),kind='commentary')
        else:
            bom=self.pending_bom;allow=self.proposals.get()
            self.start(lambda:self.engine.run(self.chat,text,self.ask,self.notify,self.cancel,bom_path=bom,allow_proposals=allow),kind='report')

    def notify(self,kind,value):self.events.put((kind,value))
    def ask(self,question):
        self.answer=None;self.answer_ready.clear();self.events.put(('question',question));self.answer_ready.wait()
        return None if self.cancel.is_set() else self.answer
    def skip(self):
        if not self.pending_question:return
        self.store.message(self.chat,'system','Requirement left unanswered.',kind='unanswered')
        self.pending_question=False;self.answer=None;self.answer_ready.set();self.skip_button.pack_forget()
        self.send_button.set(text='Send ↑',enabled=False);self.render_messages()
    def start(self,job,*,kind):
        if self.busy:return
        self.busy=True;self.cancel.clear();self.started=time.monotonic();self.send_button.set(enabled=False)
        self.stop_button.pack(side='right',padx=8);self.status.set('Starting…');self.proposal_box.configure(state='disabled')
        self.recheck_button.set(enabled=False);self.edit_button.set(enabled=False)
        def run():
            try:self.events.put(('done',{'value':job(),'kind':kind}))
            except Exception as exc:self.events.put(('error',redact(type(exc).__name__+': '+str(exc))))
        threading.Thread(target=run,daemon=True).start()
    def stop(self):
        if not self.busy:return
        self.cancel.set();self.answer_ready.set();self.pending_question=False;self.status.set('Stopping after the current operation…')
        self.skip_button.pack_forget()

    def pump(self):
        try:
            while True:
                kind,value=self.events.get_nowait()
                if kind=='question':
                    if self.cancel.is_set():self.answer_ready.set();continue
                    self.pending_question=True;self.store.message(self.chat,'assistant',value,kind='question');self.render_messages()
                    self.status.set('A requirement needs your answer. You can also leave it unanswered.')
                    self.send_button.set(text='Answer ↑',enabled=True);self.skip_button.pack(side='right',padx=8);self.input.focus_set()
                elif kind=='activity':
                    self.activity.append(value)
                    label=value['name'].replace('_',' ')
                    self.status.set(('Independent operation: ' if value['actor']=='controller' else 'Agent tool: ')+label+' · '+value['phase'])
                    if self.section.get()=='Activity':self.render_section()
                elif kind=='status':self.status.set(value)
                elif kind in {'done','error'}:
                    self.busy=False;self.pending_question=False;self.stop_button.pack_forget();self.skip_button.pack_forget()
                    self.proposal_box.configure(state='normal');self.send_button.set(text='Send ↑',enabled=True)
                    if kind=='error':
                        if self.chat:self.store.message(self.chat,'assistant','The operation did not complete. '+value+'\n\nEarlier evidence is preserved. No engineering status was promoted.',kind='error')
                        self.status.set('Operation incomplete. Check local services and the recorded error.')
                    elif value['kind']=='services':
                        report=value['value'];available=sum(v['available'] for v in report['checks'].values())
                        self.services_label.configure(text=f'{available}/4 services available')
                        text='\n'.join(k+': '+('available' if v['available'] else v['action']) for k,v in report['checks'].items())
                        messagebox.showinfo('Service checks',text,parent=self.root);self.status.set('Service checks saved. Availability is independent of engineering acceptance.')
                    elif value['kind']=='commentary':
                        self.store.message(self.chat,'assistant',value['value'],kind='commentary');self.status.set('Commentary only. Recorded engineering decisions are unchanged.')
                    else:
                        result=value['value'];self.store.append(self.chat,'chat_artifact',**{k:v for k,v in result.items() if k!='text'})
                        self.store.message(self.chat,'assistant',result['text'],kind='report')
                        self.artifact=self.store.latest_artifact(self.chat);self.status.set('Stopped; partial evidence saved.' if result.get('cancelled') else 'Report saved. Missing evidence remains unverified.')
                        self.show_inspector()
                    self.render_messages();self.render_history();self.render_inspector()
                    if self.close_when_done:self.root.destroy();self.closed=True;return
        except queue.Empty:pass
        if not self.closed:self.root.after(100,self.pump)

    def show_inspector(self):
        if not self.inspector_open:self.toggle_inspector()
    def toggle_inspector(self):
        self.inspector_open=not self.inspector_open
        if self.inspector_open:self.inspector.grid(row=0,column=2,sticky='nsew')
        else:self.inspector.grid_remove()
    def render_inspector(self):
        self.views={}
        try:report=self.store.report(self.chat) if self.chat else None
        except (ValueError,KeyError,OSError):report=None
        if report and report.get('mode')=='new_design':
            from .design.views import readable_presentation
            self.views=readable_presentation(report)
        elif report:
            from .ui import format_view
            self.views={name:format_view(name,value) for name,value in report.items() if name not in {'Run record','record','mode'}}
        if not self.views:self.views={'Overview':'Your engineering evidence will appear here.\n\nRequirements, source records, deterministic checks and costs remain separate from agent commentary.'}
        self.views['Activity']='\n'.join(f"{r['actor']} · {r['name']} · {r['phase']}" for r in self.activity) or 'No operations recorded in this view. Full tool journals remain with each report.'
        self.section_box.configure(values=list(self.views))
        if self.section.get() not in self.views:self.section.set(next(iter(self.views)))
        editable=bool(report and report.get('mode')=='new_design' and report.get('architecture')) and not self.busy
        self.recheck_button.set(enabled=editable);self.edit_button.set(enabled=editable)
        self.evidence_stamp.configure(text='Recorded engineering evidence · recheck for current availability' if report else 'No engineering report yet')
        self.render_section()
    def render_section(self):
        content=self.views.get(self.section.get(),'')
        if self.section.get()=='Activity':content='\n'.join(f"{r['actor']} · {r['name']} · {r['phase']}" for r in self.activity) or content
        self.detail.configure(state='normal');self.detail.delete('1.0','end');self.detail.insert('1.0',redact(content));self.detail.configure(state='disabled')
    def revalidate(self,parameter=None,answer=None):
        if self.busy or not self.chat:return
        if parameter is not None:self.store.message(self.chat,'user',answer,kind='requirement_edit',parameter=parameter)
        else:self.store.message(self.chat,'system','Independent recheck requested. This does not call the model.',kind='recheck')
        self.render_messages();self.views={'Overview':'Independent revalidation is running. Previous results remain historical until the current checks finish.'};self.section.set('Overview');self.render_section()
        self.start(lambda:self.engine.revalidate(self.chat,self.notify,self.cancel,parameter=parameter,answer=answer),kind='report')
    def edit(self):
        if self.busy or not self.chat:return
        from .design.requirements import FIELDS
        from .design.interaction import typed_answer
        win=tk.Toplevel(self.root);win.title('Update a requirement');win.configure(bg=BG);win.geometry('500x270');win.transient(self.root);win.grab_set()
        tk.Label(win,text='Update a requirement',font=(FONT,18,'bold'),bg=BG,fg=INK).pack(anchor='w',padx=22,pady=(22,10))
        tk.Label(win,text='Your exact answer is recorded. Dependent results are invalidated and rechecked.',bg=BG,fg=MUTED,wraplength=450,justify='left').pack(anchor='w',padx=22)
        parameter=tk.StringVar(value='led_count');box=ttk.Combobox(win,textvariable=parameter,values=list(FIELDS),state='readonly');box.pack(fill='x',padx=22,pady=10)
        answer=ttk.Entry(win);answer.pack(fill='x',padx=22)
        def apply():
            text=answer.get()
            if typed_answer(parameter.get(),text) is None:
                messagebox.showinfo('Explicit value required','Use an allowed value or the parameter’s exact unit: '+str(FIELDS[parameter.get()][1]),parent=win);return
            p=parameter.get();win.destroy();self.revalidate(p,text)
        SoftButton(win,'Apply & recheck',apply,width=170,bg=ACCENT,fg=WHITE,border=ACCENT).pack(anchor='e',padx=22,pady=16)
    def check_services(self):
        if self.busy:return
        from .preflight import run_preflight
        self.start(lambda:run_preflight(self.state),kind='services')
    def open_files(self):
        if not self.chat:return
        artifact=self.store.latest_artifact(self.chat)
        if artifact:
            folder=self.store.owned_path(artifact['report']).parent
            if os.name=='nt':os.startfile(folder)
    def advanced(self):
        if self.busy:return
        from .ui import ReviewApp
        window=tk.Toplevel(self.root)
        app=ReviewApp(self.catalogs,self.state/'bom-workspace',self.fees,demo_bom=self.demo_bom,design_name=self.design_name,root=window)
        self.legacy_workspace=app
    def close(self):
        if self.busy:
            self.close_when_done=True;self.stop();self.root.withdraw();return
        self.closed=True;self.answer_ready.set();self.root.destroy()
    def run(self):self.root.mainloop()
