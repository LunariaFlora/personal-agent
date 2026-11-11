"""User configuration belongs to the app data directory, never the software tree."""
from __future__ import annotations
import json
import os
import threading
from pathlib import Path

_default_data = Path(Path(__file__).resolve().anchor)/'AppData'/'PersonalAgent' if os.name=='nt' else Path.home()/'.local/share/PersonalAgent'
DATA_DIR = Path(os.environ.get('PERSONAL_AGENT_DATA', str(_default_data))).resolve()
DEFAULTS = {
    'model': 'deepseek-flash', 'base_url': 'https://api.deepseek.com', 'api_key': '',
    'vision_model': 'kimi-k3', 'vision_base_url': 'https://api.moonshot.cn/v1', 'vision_key': '',
    'groq_model': 'whisper-large-v3', 'groq_base_url': 'https://api.groq.com/openai/v1', 'groq_key': '',
    'brave_key': '', 'tikhub_key': '', 'buffer_seconds': 60, 'daily_time': '09:00',
    'daily_timezone': 'America/Los_Angeles', 'daily_enabled': True, 'system_prompt': '',
    'context_chars': 36000,
}
SECRET_KEYS = {'api_key','vision_key','groq_key','brave_key','tikhub_key'}
SHARED_KEYS = SECRET_KEYS | {'model','base_url','vision_model','vision_base_url','groq_model','groq_base_url'}

class Config:
    def __init__(self, data_dir=DATA_DIR, *, shared=None, defaults=None):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir/'config.json'
        self.lock = threading.RLock()
        self.shared = shared
        self._children = []
        self.values = dict(DEFAULTS)
        self.values.update(defaults or {})
        if self.path.exists():
            loaded = json.loads(self.path.read_text(encoding='utf-8'))
            self.values.update({k:v for k,v in loaded.items() if k in DEFAULTS and (not shared or k not in SHARED_KEYS)})
        else:
            if not shared:
                self.values.update({k:os.environ[e] for k,e in {'api_key':'DEEPSEEK_API_KEY','vision_key':'KIMI_API_KEY','groq_key':'GROQ_API_KEY','brave_key':'BRAVE_API_KEY','tikhub_key':'TIKHUB_API_KEY'}.items() if os.environ.get(e)})
            self.save({})
        if shared:
            shared._children.append(self)
            self._sync_shared()

    def _sync_shared(self):
        if self.shared:
            with self.lock:
                self.values.update({k:self.shared.values[k] for k in SHARED_KEYS})

    def save(self, values):
        if self.shared:
            shared_values = {k:v for k,v in values.items() if k in SHARED_KEYS}
            if shared_values:self.shared.save(shared_values)
        with self.lock:
            for k,v in values.items():
                if k not in DEFAULTS: continue
                if self.shared and k in SHARED_KEYS:continue
                if k in SECRET_KEYS and (not v or str(v).startswith('••')): continue
                self.values[k] = v
            self._sync_shared()
            tmp = self.path.with_suffix('.tmp')
            persisted={k:v for k,v in self.values.items() if not self.shared or k not in SHARED_KEYS}
            tmp.write_text(json.dumps(persisted,ensure_ascii=False,indent=2),encoding='utf-8')
            tmp.replace(self.path)
        for child in self._children:child._sync_shared()
    def public(self):
        return {'settings':{k:v for k,v in self.values.items() if k not in SECRET_KEYS},'credentials':{k:bool(self.values.get(k)) for k in SECRET_KEYS},'data_dir':str(self.data_dir)}
    def redact(self, value):
        result = str(value)
        for k in SECRET_KEYS:
            secret = self.values.get(k)
            if secret: result = result.replace(secret,'[凭据已隐藏]')
        return result
