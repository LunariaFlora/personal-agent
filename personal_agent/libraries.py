"""Independent personal libraries with shared model connection settings."""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

from .config import Config, DATA_DIR
from .store import Store
from .connectors import Services
from .mcp_client import MCPManager
from .engine import Engine


@dataclass
class LibraryContext:
    id: str
    title: str
    data_dir: Path
    config: Config
    store: Store
    services: Services
    mcp: MCPManager
    engine: Engine

    def public(self):
        return {'id':self.id,'title':self.title,'data_dir':str(self.data_dir)}


class LibraryManager:
    def __init__(self, root=DATA_DIR):
        self.root=Path(root).resolve()
        self.root.mkdir(parents=True,exist_ok=True)
        self.path=self.root/'libraries.json'
        self.lock=threading.RLock()
        self.selected_id='daily'
        registry={}
        if self.path.exists():
            try:
                loaded=json.loads(self.path.read_text(encoding='utf-8'))
                if isinstance(loaded,dict):registry=loaded
            except (OSError,ValueError,TypeError):pass
        shared=Config(self.root)
        self.contexts={}
        definitions=[('daily','日常资料库',self.root,shared),
                     ('mantingfang','满庭芳回放库',self.root/'libraries'/'mantingfang',None)]
        self.extra_definitions=[]
        seen={'daily','mantingfang'}
        extras=registry.get('libraries',[])
        for item in extras if isinstance(extras,list) else []:
            if not isinstance(item,dict):continue
            identifier=item.get('id','')
            title=item.get('title','')
            if not isinstance(identifier,str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,47}',identifier):continue
            if identifier in seen or not isinstance(title,str) or not title.strip():continue
            seen.add(identifier)
            title=title.strip()[:80]
            self.extra_definitions.append({'id':identifier,'title':title})
            definitions.append((identifier,title,self.root/'libraries'/identifier,None))
        for identifier,title,path,config in definitions:
            config=config or Config(path,shared=shared,defaults={'daily_enabled':False})
            store=Store(path)
            services=Services(path,config.values)
            mcp=MCPManager(path/'mcp.json')
            engine=Engine(store,config,services,mcp)
            self.contexts[identifier]=LibraryContext(identifier,title,path,config,store,services,mcp,engine)
        selected=registry.get('selected_id')
        if isinstance(selected,str) and selected in self.contexts:self.selected_id=selected

    def get_context(self, library_id=None):
        identifier=self.selected_id if library_id is None else library_id
        if identifier not in self.contexts:raise ValueError('资料库不存在')
        return self.contexts[identifier]

    def list(self):return [context.public() for context in self.contexts.values()]

    def select(self, library_id):
        context=self.get_context(library_id)
        with self.lock:
            tmp=self.path.with_suffix('.tmp')
            tmp.write_text(json.dumps({'selected_id':library_id,'libraries':self.extra_definitions},ensure_ascii=False,indent=2),encoding='utf-8')
            tmp.replace(self.path)
            self.selected_id=library_id
        return context

    async def start(self):
        for context in self.contexts.values():await context.engine.start()

    async def close(self):
        for context in self.contexts.values():await context.engine.close()


manager=LibraryManager()
