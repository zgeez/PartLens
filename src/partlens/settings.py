"""Validated desktop preferences; credentials are encrypted for the current Windows user."""
from dataclasses import dataclass, field
import base64
import ctypes
from ctypes import wintypes
import json
import os
from pathlib import Path
from urllib.parse import urlsplit
import uuid

DEFAULTS = {'supplier_mode':'offline','PARTLENS_LOCAL_MODEL':'qwen3.5:9b',
    'PARTLENS_LOCAL_URL':'http://127.0.0.1:11434','PARTLENS_LOCAL_PROTOCOL':'native',
    'PARTLENS_LOCAL_CONTEXT':'32768','PARTLENS_LOCAL_TIMEOUT':'180','JLC_APP_NAME':'',
    'ZETARIS_BASE_URL':'http://localhost:3000','ZETARIS_ORG_ID':'','ZETARIS_ENGINE_ID':'',
    'PARTLENS_ZETARIS_PARTS_TABLE':'','PARTLENS_ZETARIS_BOM_SUPPLIER':'lcsc'}
SECRET_KEYS = ('JLC_APP_ID','JLC_ACCESS_KEY','JLC_SECRET_KEY','ZETARIS_API_KEY')
MODES = {'offline':'Synthetic demo (no supplier calls)', 'jlc':'Official JLCPCB',
         'jlc_zetaris':'Official JLCPCB through Zetaris','zetaris':'Configured Zetaris table'}


@dataclass
class AppSettings:
    preferences: dict = field(default_factory=lambda:dict(DEFAULTS))
    credentials: dict = field(default_factory=dict,repr=False)

    def validate(self):
        if set(self.preferences)!=set(DEFAULTS) or set(self.credentials)-set(SECRET_KEYS):
            raise ValueError('Unsupported settings fields')
        if any(not isinstance(v,str) or '\n' in v or '\r' in v or len(v)>4096
               for v in [*self.preferences.values(),*self.credentials.values()]):
            raise ValueError('Settings must be single-line text')
        p=self.preferences
        if p['supplier_mode'] not in MODES:raise ValueError('Select a supported supplier mode')
        from .local_provider import OllamaProvider
        OllamaProvider(model=p['PARTLENS_LOCAL_MODEL'],base_url=p['PARTLENS_LOCAL_URL'])
        if p['PARTLENS_LOCAL_PROTOCOL'] not in {'native','json-schema'}:raise ValueError('Unsupported local protocol')
        try:
            context,timeout=int(p['PARTLENS_LOCAL_CONTEXT']),int(p['PARTLENS_LOCAL_TIMEOUT'])
        except ValueError:raise ValueError('Context and timeout must be whole numbers') from None
        if not 4096<=context<=131072 or not 1<=timeout<=600:raise ValueError('Context: 4096–131072; timeout: 1–600 seconds')
        if p['PARTLENS_ZETARIS_BOM_SUPPLIER'] not in {'lcsc','jlcpcb'}:raise ValueError('Zetaris supplier must be lcsc or jlcpcb')
        if p['supplier_mode'] in {'jlc_zetaris','zetaris'}:
            url=urlsplit(p['ZETARIS_BASE_URL'])
            if url.scheme not in {'http','https'} or not url.hostname or url.username or url.password or url.query or url.fragment:
                raise ValueError('Zetaris needs an HTTP(S) origin without embedded credentials')
        return self

    def apply(self):
        self.validate()
        for key,value in {**self.preferences,**{k:self.credentials.get(k,'') for k in SECRET_KEYS}}.items():
            if key!='supplier_mode':os.environ[key]=value
        os.environ.update(PARTLENS_LLM_PROVIDER='ollama',PARTLENS_ALLOW_PAID_INFERENCE='disabled',
                          PARTLENS_MODEL_FALLBACK='disabled')


class _Blob(ctypes.Structure):
    _fields_=[('cbData',wintypes.DWORD),('pbData',ctypes.POINTER(ctypes.c_ubyte))]


def _dpapi(data: bytes, *, decrypt=False) -> bytes:
    if os.name!='nt':raise RuntimeError('Credential storage requires Windows DPAPI')
    buf=ctypes.create_string_buffer(data)
    source=_Blob(len(data),ctypes.cast(buf,ctypes.POINTER(ctypes.c_ubyte)));out=_Blob()
    crypt=ctypes.WinDLL('crypt32',use_last_error=True);kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.LocalFree.argtypes=[ctypes.c_void_p];kernel.LocalFree.restype=ctypes.c_void_p
    if decrypt:
        fn=crypt.CryptUnprotectData
        fn.argtypes=[ctypes.POINTER(_Blob),ctypes.c_void_p,ctypes.c_void_p,ctypes.c_void_p,
                     ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(_Blob)]
        ok=fn(ctypes.byref(source),None,None,None,None,1,ctypes.byref(out))
    else:
        fn=crypt.CryptProtectData
        fn.argtypes=[ctypes.POINTER(_Blob),wintypes.LPCWSTR,ctypes.c_void_p,ctypes.c_void_p,
                     ctypes.c_void_p,wintypes.DWORD,ctypes.POINTER(_Blob)]
        ok=fn(ctypes.byref(source),'PartLens credentials',None,None,None,1,ctypes.byref(out))
    if not ok:raise RuntimeError('Windows could not protect/unlock PartLens credentials for this user')
    try:return ctypes.string_at(out.pbData,out.cbData)
    finally:kernel.LocalFree(ctypes.cast(out.pbData,ctypes.c_void_p))


def load_settings(home: Path) -> AppSettings:
    path=Path(home)/'settings.json'
    if not path.exists():return AppSettings()
    try:
        value=json.loads(path.read_text(encoding='utf-8'))
        if value['version']!=1:raise ValueError()
        secrets=json.loads(_dpapi(base64.b64decode(value['credentials'],validate=True),decrypt=True)) if value['credentials'] else {}
        return AppSettings(value['preferences'],secrets).validate()
    except Exception:
        raise ValueError('Settings could not be loaded. Keep the existing file and restore it using the original Windows user.') from None


def save_settings(home: Path, settings: AppSettings):
    settings.validate();home=Path(home);home.mkdir(parents=True,exist_ok=True)
    credentials={k:v for k,v in settings.credentials.items() if v}
    value={'version':1,'preferences':settings.preferences,'credentials':
        base64.b64encode(_dpapi(json.dumps(credentials).encode())).decode() if credentials else ''}
    temp=home/('settings-'+uuid.uuid4().hex+'.tmp')
    with temp.open('x',encoding='utf-8') as f:json.dump(value,f,indent=2)
    os.replace(temp,home/'settings.json')


def import_env(path: Path, previous: AppSettings) -> AppSettings:
    path=Path(path)
    if any(x in str(path.resolve()).casefold() for x in ('experiments','benchmark','badge')):
        raise ValueError('Excluded private configuration cannot be imported')
    values={}
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        if not line.strip() or line.lstrip().startswith('#') or '=' not in line:continue
        k,v=line.split('=',1);k=k.strip()
        if k in DEFAULTS or k in SECRET_KEYS:values[k]=v.strip().strip('"').strip("'")
    prefs={**previous.preferences,**{k:v for k,v in values.items() if k in DEFAULTS}}
    creds={**previous.credentials,**{k:v for k,v in values.items() if k in SECRET_KEYS}}
    if all(creds.get(k) for k in ('JLC_APP_ID','JLC_ACCESS_KEY','JLC_SECRET_KEY')):
        prefs['supplier_mode']='jlc_zetaris' if creds.get('ZETARIS_API_KEY') and prefs['ZETARIS_ORG_ID'] else 'jlc'
    return AppSettings(prefs,creds).validate()
