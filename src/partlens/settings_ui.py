"""One settings dialog; changes start a new session and never rewrite historical decisions."""
from pathlib import Path
from .settings import AppSettings, DEFAULTS, SECRET_KEYS, MODES, import_env, save_settings


def open_settings(app, home, current, apply):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    if app.busy or any(isinstance(w,tk.Toplevel) for w in app.root.winfo_children()):
        messagebox.showinfo('Settings','Finish the current operation and close workspace windows before changing settings.',parent=app.root)
        return
    win=tk.Toplevel(app.root);win.title('PartLens Settings');win.geometry('760x690');win.transient(app.root)
    win.grab_set()
    ttk.Label(win,text='PartLens Settings',font=('Segoe UI',16,'bold')).pack(anchor='w',padx=18,pady=12)
    ttk.Label(win,text='Local inference only. Credentials are encrypted for this Windows user; never bundled into the executable.',wraplength=710).pack(anchor='w',padx=18)
    tabs=ttk.Notebook(win);tabs.pack(fill='both',expand=True,padx=18,pady=12)
    values={k:tk.StringVar(value=current.preferences.get(k,'')) for k in DEFAULTS}
    values.update({k:tk.StringVar(value=current.credentials.get(k,'')) for k in SECRET_KEYS})
    def pane(name,fields):
        frame=ttk.Frame(tabs,padding=12);tabs.add(frame,text=name);frame.columnconfigure(1,weight=1)
        for i,(key,label,choices) in enumerate(fields):
            ttk.Label(frame,text=label).grid(row=i,column=0,sticky='w',padx=(0,12),pady=7)
            if choices:
                entry=ttk.Combobox(frame,textvariable=values[key],values=choices,state='readonly')
            else:entry=ttk.Entry(frame,textvariable=values[key],show='*' if key in SECRET_KEYS else '')
            entry.grid(row=i,column=1,sticky='ew',pady=7)
        return frame
    pane('Local model',[(k,label,options) for k,label,options in [
        ('PARTLENS_LOCAL_MODEL','Installed Ollama model',None),('PARTLENS_LOCAL_URL','Loopback Ollama URL',None),
        ('PARTLENS_LOCAL_PROTOCOL','Action transport',('native','json-schema')),
        ('PARTLENS_LOCAL_CONTEXT','Context tokens',None),('PARTLENS_LOCAL_TIMEOUT','Request timeout (seconds)',None)]])
    f=pane('Suppliers',[
        ('supplier_mode','Supplier mode',tuple(MODES)),('JLC_APP_ID','JLCPCB app ID',None),
        ('JLC_ACCESS_KEY','JLCPCB access key',None),('JLC_SECRET_KEY','JLCPCB secret key',None),('JLC_APP_NAME','JLCPCB app name (optional)',None)])
    ttk.Label(f,text='offline: original synthetic data only\njlc: official public-component API\njlc_zetaris: official JLCPCB observations queried by Zetaris\nzetaris: configured existing supplier table\n\nJLCPCB operations remain read-only. Unknown prices/fees/eligibility stay unknown.',wraplength=650).grid(row=6,column=0,columnspan=2,sticky='w',pady=12)
    pane('Zetaris',[(k,label,None) for k,label in [
        ('ZETARIS_BASE_URL','SQL UI gateway origin'),('ZETARIS_ORG_ID','Organization ID'),
        ('ZETARIS_API_KEY','API key'),('ZETARIS_ENGINE_ID','Engine ID (optional)'),
        ('PARTLENS_ZETARIS_PARTS_TABLE','Existing supplier table'),('PARTLENS_ZETARIS_BOM_SUPPLIER','Table supplier (lcsc / jlcpcb)')]])
    about=ttk.Frame(tabs,padding=15);tabs.add(about,text='Storage & services')
    ttk.Label(about,text=f'Settings: {home}\nRun records and memory: {Path(home)/"state"}\n\nThe executable includes Python, the desktop and the Node/H-MEM bridge.\nOllama/model files and Zetaris/Docker remain separate installations.\nUse Check services on the main screen to verify live availability.\n\nSaving starts a new session; all previous records remain preserved.\nGit commit signing is unrelated to launching PartLens.',wraplength=650,justify='left').pack(anchor='w')
    def notices():
        from .paths import resource_root
        folder=resource_root()/'licenses'
        if not folder.exists():
            messagebox.showinfo('Licenses','Source installation: see LICENSE, NOTICE and THIRD_PARTY.md in the repository.',parent=win);return
        viewer=tk.Toplevel(win);viewer.title('PartLens third-party notices');viewer.geometry('850x650')
        content=tk.Text(viewer,wrap='word');content.pack(fill='both',expand=True)
        for file in sorted(folder.iterdir()):
            if file.is_file():content.insert('end',file.name+'\n\n'+file.read_text(encoding='utf-8',errors='replace')+'\n\n')
        content.configure(state='disabled')
    ttk.Button(about,text='View bundled licenses and notices',command=notices).pack(anchor='w',pady=16)
    def imported():
        path=filedialog.askopenfilename(parent=win,title='Import existing .env.local',filetypes=[('Local environment','*.local'),('All files','*.*')])
        if not path:return
        try:
            result=import_env(Path(path),AppSettings({k:values[k].get() for k in DEFAULTS},{k:values[k].get() for k in SECRET_KEYS}))
            for k,v in {**result.preferences,**result.credentials}.items():values[k].set(v)
            messagebox.showinfo('Imported','Configuration loaded into the form. Save to encrypt credentials and apply it.',parent=win)
        except Exception:messagebox.showerror('Import failed','Could not import this supported configuration. Credential values have not been logged.',parent=win)
    def save():
        try:
            result=AppSettings({k:values[k].get() for k in DEFAULTS},{k:values[k].get() for k in SECRET_KEYS}).validate()
            # Construct connections before replacing settings; configuration errors leave the previous session intact.
            prepared=apply(result,preview=True)
            save_settings(home,result)
            apply(result,prepared=prepared)
            win.destroy()
        except Exception as exc:
            from .secrets import redact
            messagebox.showerror('Settings not applied',redact(str(exc)),parent=win)
    buttons=ttk.Frame(win);buttons.pack(fill='x',padx=18,pady=12)
    ttk.Button(buttons,text='Import .env.local',command=imported).pack(side='left')
    ttk.Button(buttons,text='Save & start new session',command=save).pack(side='right')
    ttk.Button(buttons,text='Cancel',command=win.destroy).pack(side='right',padx=8)
    return win
