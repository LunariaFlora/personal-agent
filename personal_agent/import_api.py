"""The HTTP and MCP entry points share the same durable ingestion path."""
from __future__ import annotations
import asyncio
import json
import uuid
from fastapi import APIRouter, Request, HTTPException
from pydantic import BaseModel, Field
from .chat_import import import_chat, import_file

router=APIRouter()
_jobs={}
_locks={}


class ImportInput(BaseModel):
    path: str | None = None
    payload: dict | None = None
    self_id: str = ''
    background: bool = False


class OrganizeInput(BaseModel):
    message_ids: list[str] = Field(min_length=1, max_length=200)


@router.post('/api/imports')
async def import_original(payload:ImportInput, request:Request):
    context=request.state.library
    if bool(payload.path) == bool(payload.payload):
        raise HTTPException(400,'请提供原始聊天文件路径或 JSON 内容中的一种')
    async def execute():
        async with _locks.setdefault(context.id,asyncio.Lock()):
            if payload.path:
                receipt=await asyncio.to_thread(import_file,context.store,payload.path,payload.self_id)
            else:
                receipt=await asyncio.to_thread(import_chat,context.store,payload.payload,None,payload.self_id)
            return {'library_id':context.id,**receipt}
    if not payload.background:return await execute()
    identifier=uuid.uuid4().hex
    folder=context.data_dir/'imports';folder.mkdir(parents=True,exist_ok=True)
    path=folder/('job-'+identifier+'.json')
    state={'job_id':identifier,'library_id':context.id,'status':'running'}
    def persist(value):
        temporary=path.with_suffix('.tmp')
        temporary.write_text(json.dumps(value,ensure_ascii=False),encoding='utf-8')
        temporary.replace(path)
    persist(state)
    async def run():
        try:result={**state,'status':'done','result':await execute()}
        except Exception as error:result={**state,'status':'error','error':context.config.redact(error)[:500]}
        persist(result)
    task=asyncio.create_task(run())
    _jobs[(context.id,identifier)]=task
    task.add_done_callback(lambda unused:_jobs.pop((context.id,identifier),None))
    return state


@router.get('/api/imports/jobs/{id}')
async def import_status(id:str,request:Request):
    context=request.state.library
    if len(id)!=32 or any(c not in '0123456789abcdef' for c in id):raise HTTPException(404,'导入任务不存在')
    path=context.data_dir/'imports'/('job-'+id+'.json')
    if not path.is_file():raise HTTPException(404,'导入任务不存在')
    result=json.loads(path.read_text(encoding='utf-8'))
    if result['status']=='running' and (context.id,id) not in _jobs:
        result.update(status='interrupted',error='服务在导入期间重启，请重新导入；已保存的原消息不会重复。')
    return result


@router.get('/api/imports/messages')
async def original_messages(request:Request,q:str='',offset:int=0,limit:int=100):
    context=request.state.library
    rows=context.store.messages('inbox',limit=100000)
    rows=[m for m in rows if m.get('meta',{}).get('provenance')]
    if q:
        if len(q)>500:raise HTTPException(400,'搜索词过长')
        words=q.casefold()
        rows=[m for m in rows if words in (m['content']+' '+str(m.get('meta',{}).get('forwarded',''))).casefold()]
    rows.sort(key=lambda m:m['created_at'])
    offset=max(0,offset);limit=max(1,min(200,limit))
    return {'messages':rows[offset:offset+limit],'total':len(rows),'offset':offset,'has_more':offset+limit<len(rows)}


@router.post('/api/imports/organize')
async def organize(payload:OrganizeInput, request:Request):
    context=request.state.library
    if context.engine.state('inbox').get('phase'):
        raise HTTPException(409,'这一批还在整理，请完成后再提交下一批')
    result=context.store.queue_imported(payload.message_ids)
    if result['queued']:context.engine.schedule('inbox',0)
    return {**result,'pending':context.engine.state('inbox')}


@router.get('/api/messages/{id}/context')
async def original_context(id:str,request:Request,radius:int=2):
    return {'messages':request.state.library.store.message_context(id,radius),'focus_id':id}


@router.get('/api/messages/{id}/original')
async def original_record(id:str,request:Request):
    record=request.state.library.store.imported_record(id)
    if not record:raise HTTPException(404,'未找到导入的原记录')
    return record
