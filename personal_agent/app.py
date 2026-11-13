from __future__ import annotations
import asyncio
import json
import mimetypes
import re
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import FastAPI, Request, HTTPException, UploadFile, File
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field

from .config import DATA_DIR
from .libraries import manager

_library_id=ContextVar('personal_agent_library',default=None)

def get_context(library_id=None):
    """Routes use the bound request; workers/importers may name their library."""
    return manager.get_context(_library_id.get() if library_id is None else library_id)

class _ContextMember:
    def __init__(self,name):self.name=name
    def __getattr__(self,key):return getattr(getattr(get_context(),self.name),key)

# These resolve at request entry. Bound Engine methods always retain their own
# concrete Store/Services, including tasks that outlive a library selection.
config=_ContextMember('config');store=_ContextMember('store')
services=_ContextMember('services');mcp=_ContextMember('mcp');engine=_ContextMember('engine')
background=set()

def spawn(coro):
    task=asyncio.create_task(coro); background.add(task); task.add_done_callback(background.discard)
    return task

@asynccontextmanager
async def lifespan(app):
    await manager.start()
    yield
    for task in background:task.cancel()
    if background:await asyncio.gather(*background,return_exceptions=True)
    await manager.close()

app=FastAPI(title='Personal Agent',version='0.3.0',lifespan=lifespan,docs_url=None,redoc_url=None)
app.add_middleware(TrustedHostMiddleware,allowed_hosts=['127.0.0.1','localhost','[::1]','testserver'])

@app.middleware('http')
async def same_origin(request,call_next):
    origin=request.headers.get('origin')
    if request.method not in ('GET','HEAD','OPTIONS') and origin:
        supplied=urlsplit(origin); target=urlsplit(str(request.url))
        if supplied.netloc!=target.netloc or supplied.scheme!=target.scheme:
            return JSONResponse({'detail':'请从 Personal Agent 窗口执行操作。'},status_code=403)
    identifier=request.headers.get('x-personal-library') or request.query_params.get('library') or manager.selected_id
    try:context=manager.get_context(identifier)
    except ValueError:return JSONResponse({'detail':'资料库不存在'},status_code=404)
    token=_library_id.set(context.id)
    request.state.library=context
    try:response=await call_next(request)
    finally:_library_id.reset(token)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='no-referrer'
    response.headers['X-Frame-Options']='DENY'
    response.headers['Cache-Control']='no-store' if request.url.path.startswith('/api') else 'no-cache'
    if request.url.path.startswith('/api'):response.headers['X-Personal-Library']=context.id
    return response

@app.exception_handler(ValueError)
async def invalid(request,error):return JSONResponse({'detail':config.redact(error)},status_code=400)

def existing(value):
    if value is None:raise HTTPException(404,'内容不存在或已归档')
    return value

class MessageInput(BaseModel):
    channel:str='inbox'
    content:str=Field(default='',max_length=300000)
    reply_to:str|None=None
    attachment_ids:list[str]=Field(default_factory=list,max_length=20)
    flush:bool=False

class ChannelInput(BaseModel):channel:str='inbox'
class MemoryInput(BaseModel):
    content:str=Field(min_length=1,max_length=5000)
    kind:str='preference'
    source_ids:list[str]|None=None

class NoteInput(BaseModel):
    title:str=Field(min_length=1,max_length=160)
    body:str=Field(default='',max_length=1500000)
    category:str=Field(default='收件箱',max_length=160)
    kind:str='note'
    source_ids:list[str]|None=None
    source_url:str=''
    original:str=''
    tags:list[str]|None=None

@app.get('/api/health')
async def health():return {'ok':True,'app':'PersonalAgent','version':'0.3.0'}

@app.get('/api/libraries')
async def libraries():return {'libraries':manager.list(),'selected_id':get_context().id}

class LibrarySelection(BaseModel):id:str

@app.post('/api/libraries/select')
async def select_library(payload:LibrarySelection):
    selected=manager.select(payload.id)
    return {'library':selected.public(),'selected_id':selected.id}

@app.get('/api/state')
async def state():
    cfg=config.values
    return {'library':get_context().public(),'channels':store.channels(),'stats':store.stats(),
            'settings':{'model':cfg['model'],'provider':urlsplit(cfg['base_url']).hostname,
                'buffer_seconds':cfg['buffer_seconds'],'daily_time':cfg['daily_time'],'daily_timezone':cfg['daily_timezone'],'daily_enabled':cfg['daily_enabled'],'data_dir':str(get_context().data_dir)},
            'service_status':{'model':bool(cfg['api_key']),'vision':bool(cfg['vision_key']),
                              'transcription':bool(cfg['groq_key']),'search':bool(cfg['brave_key'] or (cfg['api_key'] and urlsplit(cfg['base_url']).hostname=='api.deepseek.com'))},
            'pending':{c['id']:engine.state(c['id']) for c in store.channels()}}

@app.get('/api/messages')
async def messages(channel:str='inbox',before:str|None=None,limit:int=100):
    return {'messages':store.messages(channel,limit=min(limit,300),before=before,include_archived=False),'pending':engine.state(channel)}

@app.get('/api/messages/{id}')
async def message_by_id(id:str):return {'message':existing(store.get_message(id))}

@app.post('/api/messages')
async def send_message(payload:MessageInput):
    if not payload.content.strip() and not payload.attachment_ids:raise HTTPException(400,'先写点什么或添加文件')
    if payload.channel not in {c['id'] for c in store.channels()}:raise HTTPException(400,'会话不存在')
    if payload.reply_to:
        quoted=existing(store.get_message(payload.reply_to))
        if quoted['channel']=='transfer' and payload.channel!='transfer':raise HTTPException(400,'请在当前会话重新发送要收藏的传输内容')
    finish=payload.content.strip() in ('发完了','说完了','我发完了')
    msg=store.add_message(payload.channel,'user',payload.content,reply_to=payload.reply_to,
                          attachment_ids=payload.attachment_ids,status='done' if payload.channel=='transfer' else 'pending')
    if payload.channel!='transfer':engine.schedule(payload.channel,0 if finish or payload.flush else None)
    return {'message':msg,'pending':engine.state(payload.channel)}

@app.post('/api/flush')
async def flush(payload:ChannelInput):engine.flush(payload.channel);return {'ok':True}

@app.post('/api/stop')
async def stop(payload:ChannelInput):engine.stop(payload.channel);return {'ok':True}

@app.post('/api/upload')
async def upload(files:list[UploadFile]=File(...)):
    if len(files)>20:raise HTTPException(400,'每次最多添加20个文件')
    results=[]
    for file in files:
        name=Path(file.filename or '文件').name[:180]
        suffix=Path(name).suffix[:15]
        path=store.attachments_dir/(uuid.uuid4().hex+suffix)
        size=0
        try:
            with path.open('wb') as stream:
                while block:=await file.read(1024*1024):
                    size+=len(block)
                    if size>1024*1024*1024:raise HTTPException(413,'单个文件最大1GB')
                    stream.write(block)
            result=store.add_attachment(name,str(path),file.content_type or mimetypes.guess_type(name)[0] or 'application/octet-stream',size)
            results.append({k:v for k,v in result.items() if k!='path'})
        except BaseException:
            path.unlink(missing_ok=True);raise
        finally:await file.close()
    return {'attachments':results}

@app.get('/api/attachments/{id}')
async def attachment(id:str):return {'attachment':{k:v for k,v in existing(store.get_attachment(id)).items() if k!='path'}}

@app.get('/api/files/{id}')
async def download(id:str,download:bool=False):
    a=existing(store.get_attachment(id)); p=Path(a['path']).resolve()
    if not p.is_relative_to(store.attachments_dir.resolve()) or not p.is_file():raise HTTPException(404,'文件不存在')
    inline=a['mime'] in ('image/png','image/jpeg','image/webp','image/gif','audio/mpeg','audio/wav','video/mp4') and not download
    return FileResponse(p,filename=a['name'],media_type=a['mime'] if inline else 'application/octet-stream',content_disposition_type='inline' if inline else 'attachment')

@app.get('/api/notes')
async def notes(q:str='',category:str='',kind:str=''):return {'notes':store.list_notes(q,category,kind)}

@app.get('/api/notes/{id}')
async def note(id:str):return {'note':existing(store.get_note(id))}

@app.post('/api/notes')
async def create_note(payload:NoteInput):return {'note':store.save_note(**payload.model_dump())}

@app.put('/api/notes/{id}')
async def update_note(id:str,payload:NoteInput):
    old=existing(store.get_note(id)); fields=payload.model_dump()
    fields.update(source_ids=old['source_ids'],source_url=old['source_url'],original=old['original'],note_id=id)
    return {'note':store.save_note(**fields)}

@app.delete('/api/notes/{id}')
async def delete_note(id:str):existing(store.get_note(id));store.delete_note(id);return {'ok':True}

@app.get('/api/notes/{id}/revisions')
async def note_revisions(id:str):return {'revisions':store.notes_revision(id)}

@app.get('/api/notes/{id}/export')
async def export_note(id:str):
    n=existing(store.get_note(id));return FileResponse(n['export_path'],filename=Path(n['export_path']).name,media_type='text/markdown; charset=utf-8')

@app.get('/api/memories')
async def memories():return {'memories':store.list_memories()}

@app.post('/api/memories')
async def create_memory(payload:MemoryInput):return {'memory':store.save_memory(**payload.model_dump())}

@app.put('/api/memories/{id}')
async def edit_memory(id:str,payload:MemoryInput):
    old=existing(next((m for m in store.list_memories() if m['id']==id),None))
    return {'memory':store.save_memory(payload.content,kind=payload.kind,source_ids=old['source_ids'],memory_id=id)}

@app.delete('/api/memories/{id}')
async def delete_memory(id:str):store.delete_memory(id);return {'ok':True}

@app.get('/api/reports')
async def reports():return {'reports':store.list_reports()}

@app.post('/api/reports/generate')
async def generate_report():
    if not engine.report_running:spawn(engine.generate_report(manual=True))
    return {'ok':True,'running':True}

@app.get('/api/reports/status')
async def reports_status():return {'running':engine.report_running,'error':engine.report_error}

@app.get('/api/reports/{id}')
async def report(id:str):return {'report':existing(store.get_report(id))}

@app.get('/api/settings')
async def settings():return config.public()

@app.put('/api/settings')
async def save_settings(request:Request):
    value=await request.json()
    if not isinstance(value,dict):raise HTTPException(400,'设置格式不正确')
    if 'settings' in value:value={**value,**value.pop('settings')}
    if 'buffer_seconds' in value:
        value['buffer_seconds']=int(value['buffer_seconds'])
        if not 0<=value['buffer_seconds']<=600:raise HTTPException(400,'等待时间应为0到600秒')
    if 'daily_time' in value and not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d',str(value['daily_time'])):raise HTTPException(400,'时间格式应为HH:MM')
    if 'daily_timezone' in value:
        try:ZoneInfo(value['daily_timezone'])
        except (ZoneInfoNotFoundError,TypeError):raise HTTPException(400,'时区无效')
    if 'base_url' in value:
        parsed=urlsplit(value['base_url'])
        if parsed.scheme not in ('http','https') or not parsed.hostname or parsed.username:raise HTTPException(400,'模型地址无效')
    if 'model' in value and not str(value['model']).strip():raise HTTPException(400,'模型名不能为空')
    if 'daily_enabled' in value and not isinstance(value['daily_enabled'],bool):raise HTTPException(400,'日报开关格式不正确')
    config.save(value)
    return {'ok':True,**config.public()}

@app.post('/api/settings/test')
async def test_settings():
    try:
        answer=await services.complete([{'role':'user','content':'只回复连接正常'}],max_tokens=30)
        return {'ok':True,'message':answer.get('content','')}
    except Exception as e:return {'ok':False,'error':config.redact(e)[:300]}

@app.get('/api/mcp')
async def mcp_status():return {'servers':await mcp.list_servers(),'config':mcp.redacted_config()}

@app.put('/api/mcp')
async def save_mcp(request:Request):
    data=await request.json(); value=data.get('config',data)
    if not isinstance(value,dict) or not isinstance(value.get('mcpServers'),dict):raise HTTPException(400,'请提供标准 mcpServers JSON')
    for name,srv in value['mcpServers'].items():
        if not isinstance(srv,dict):raise HTTPException(400,'MCP服务配置应为对象')
    await mcp.save_servers(value)
    return {'ok':True}

@app.post('/api/mcp/test')
async def mcp_test():
    definitions=await mcp.tools();return {'servers':await mcp.list_servers(),'tools_count':len(definitions)}

@app.get('/api/search')
async def search(q:str=''):return {'notes':store.search(q,limit=30),'messages':store.search_messages(q,limit=30)}

@app.get('/api/context')
async def context(channel:str='inbox'):
    return {'summary':store.get_summary(channel),'memory_count':len(store.list_memories()),'message_count':len(store.messages(channel,limit=100000))}

@app.post('/api/context/compact')
async def compact(payload:ChannelInput):
    try:await engine.compact(payload.channel,force=True);return {'ok':True}
    except Exception as e:raise HTTPException(502,config.redact(e)[:300])

@app.post('/api/parse')
async def parse(request:Request):
    data=await request.json();return await services.read_url(str(data.get('url','')))

from .import_api import router as import_router
app.include_router(import_router)

WEB=Path(__file__).resolve().parents[1]/'web'
@app.get('/')
async def home():return FileResponse(WEB/'index.html',media_type='text/html')
app.mount('/',StaticFiles(directory=str(WEB),check_dir=False),name='web')
