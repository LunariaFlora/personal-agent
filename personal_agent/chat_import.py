"""Lossless chat ingestion and readable WeChat evidence, independent of Alpha."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import mimetypes
import shutil
import uuid
import xml.etree.ElementTree as ET


def _value(element, *paths):
    for path in paths:
        found = element.find(path)
        if found is not None and found.text:
            return found.text.strip()
    return ''


def _xml(text):
    # ElementTree does not resolve external entities. Reject DTD declarations as
    # well: chat content is data, and may contain arbitrary XML sent by others.
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('消息 XML 包含不支持的声明')
    return ET.fromstring(text[text.find('<'):])


def _forwarded(records, depth=0):
    if depth > 8:return []
    if records.tag != 'recordinfo':
        records = records.find('recordinfo')
    if records is None:return []
    result=[]
    for item in records.findall('./datalist/dataitem'):
        content=_value(item,'datadesc','datatitle')
        link=_value(item,'weburlitem/link','url')
        if link and link not in content:content+='\n'+link
        nested=item.find('recordxml')
        nested_items=[]
        if nested is not None:
            if len(nested):nested_items=_forwarded(nested,depth+1)
            elif nested.text and '<' in nested.text:
                nested_items=_forwarded(_xml(nested.text),depth+1)
        value={'sender_name':_value(item,'sourcename','dataitemsource/realchatname','dataitemsource/fromusr'),
               'sender_id':_value(item,'dataitemsource/fromusr'),
               'time':_value(item,'sourcetime','srcMsgCreateTime','dataitemsource/createtime'),
               'content':content or ('[转发聊天]' if nested is not None else '[附件]'),
               'type':item.get('datatype',''),'source_id':item.get('dataid',''),'forwarded':nested_items}
        ref=item.find('refermsgitem')
        if ref is not None:
            value['quote']={k:_value(ref,v) for k,v in {'source_id':'svrid','sender_name':'displayname','content':'content'}.items()}
            value['quote']['content']=rich_text(value['quote']['content'],depth+1)['content']
        result.append(value)
    return result


def rich_text(text, depth=0):
    """Keep authors, quotes, links and nested forwarded items, without execution."""
    result = {'content': text, 'forwarded': [], 'quote': None, 'share': None}
    if depth > 8 or '<' not in text[:150]:
        return result
    try:
        root = _xml(text)
    except (ET.ParseError, ValueError):
        return result
    app = root if root.tag == 'appmsg' else root.find('.//appmsg')
    if app is None:
        label=next((label for tag,label in [('img','图片'),('videomsg','视频'),('voicemsg','语音'),('emoji','表情')] if root.tag==tag or root.find('.//'+tag) is not None),None)
        if label:result['content']='['+label+']'
        elif root.tag in ('msg','sysmsg'):
            result['content']=_value(root,'.//content_template/plain','.//plain','.//content') or '[系统或富文本消息，完整原件已保存]'
        return result
    title, desc, url = (_value(app, k) for k in ('title', 'des', 'url'))
    app_type=_value(app,'type')
    if app_type not in ('1','19','57'):
        result['share']={'title':title,'description':desc,'url':url,'type':app_type,
                         'source_name':_value(app,'sourcedisplayname')}
    parts = list(dict.fromkeys(x for x in (title, desc, url) if x))
    quote = app.find('refermsg')
    if quote is not None:
        raw = _value(quote, 'content')
        result['quote'] = {
            'source_id': _value(quote, 'svrid'), 'sender_name': _value(quote, 'displayname'),
            'sender_id': _value(quote, 'fromusr'), 'time': _value(quote, 'createtime'),
            'content': rich_text(raw, depth+1)['content'], 'raw_content': raw,
        }
    record = _value(app, 'recorditem')
    if record:
        try:
            result['forwarded'] = _forwarded(_xml(record),depth)
        except (ET.ParseError, ValueError):
            result['parse_warning'] = '转发结构未能解析，完整 XML 已保留'
    if parts:
        result['content'] = '\n'.join(parts)
    elif result['forwarded']:
        result['content'] = '[合并转发]'
    else:
        # Do not silently discard an unsupported rich message.
        result['content'] = '[富文本消息，完整原件已保存]'
    return result


def _time(row):
    if row.get('sent_at_unix_ms'):
        return datetime.fromtimestamp(int(row['sent_at_unix_ms'])/1000, timezone.utc).isoformat(timespec='microseconds')
    value = row.get('created_at') or row.get('timestamp') or row.get('time')
    if value:
        dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if dt.tzinfo is None:
            raise ValueError('原消息时间需带时区')
        return dt.astimezone(timezone.utc).isoformat(timespec='microseconds')
    raise ValueError('原消息缺少时间')


def normalize(row, conversation, account_id='', self_id=''):
    original = row.get('_alpha_original') or row
    conversation_id = str(original.get('conversation_id') or conversation.get('id') or conversation.get('conversation_id') or '')
    identifier = original.get('platform_message_id') or original.get('server_id') or original.get('id') or original.get('source_id')
    if isinstance(identifier, float):
        raise ValueError('消息 ID 不能是浮点数，请传原始字符串')
    if not identifier or not conversation_id:
        raise ValueError('原消息需要稳定的消息 ID 和会话 ID')
    content = original.get('text', original.get('content', ''))
    if not isinstance(content, str):
        raise ValueError('原消息正文必须是文本')
    parsed = rich_text(content)
    if original.get('kind')=='xml' and parsed['content']==content and '<' in content[:150]:
        parsed['content']='[富文本消息，完整原件已保存]'
        parsed['parse_warning']='此消息结构暂未支持，完整 XML 已保存'
    if not parsed['content']:
        parsed['content'] = {'3':'[图片]','34':'[语音]','43':'[视频]','47':'[表情]'}.get(str(original.get('source_type')),'[附件]' if original.get('kind')=='media' else '[空消息]')
    sender_id = str(original.get('sender_id') or original.get('sender') or '')
    direction = str(original.get('direction', '')).lower()
    is_self = original.get('is_self')
    if not isinstance(is_self, bool):
        is_self = direction in ('outgoing', 'out', 'sent', 'send', '2') or bool(self_id and sender_id == self_id)
    created_at = _time(original)
    provenance = {
        'platform': 'wechat' if original.get('source_type') is not None or original.get('sent_at_unix_ms') else 'chat',
        'account_id': account_id, 'conversation_id': conversation_id,
        'conversation_title': conversation.get('title') or conversation.get('name') or conversation.get('display_name') or conversation_id,
        'conversation_kind': 'group' if conversation.get('kind') in (2,'group') or conversation_id.endswith('@chatroom') else 'direct',
        'source_id': str(identifier), 'alpha_id': str(original.get('id') or ''),
        'sender_id': sender_id, 'sender_name': str(original.get('sender_name') or original.get('author') or ('我' if is_self else sender_id or '原作者')),
        'source_time': created_at, 'is_self': is_self,
    }
    meta = {'provenance': provenance, 'archived': True, 'forwarded': parsed['forwarded'], 'quote': parsed['quote'], 'share':parsed['share'],
            'media_status': [], 'source_kind': original.get('kind') or original.get('type') or 'text'}
    if parsed.get('parse_warning'):
        meta['parse_warning'] = parsed['parse_warning']
    return {'key': f"{provenance['platform']}:{account_id}:{conversation_id}:{identifier}",
            'content': parsed['content'], 'created_at': created_at, 'meta': meta, 'raw': original}


def _manifest(archive_path):
    assets = Path(str(archive_path)+'.assets')
    path = assets/'media-manifest.json'
    if not path.is_file() and (archive_path.parent/'media-manifest.json').is_file():
        assets = archive_path.parent
        path = assets/'media-manifest.json'
    if not path.is_file():
        return assets, [], {}
    data = json.loads(path.read_text(encoding='utf-8-sig'))
    if isinstance(data, list):
        return assets, data, {}
    return assets, data.get('resources') or data.get('items') or data.get('media') or data.get('entries') or [], {k:v for k,v in data.items() if k not in ('resources','items','media','entries')}


def import_chat(store, payload, archive_path=None, self_id=''):
    if not isinstance(payload, dict) or not isinstance(payload.get('messages'), list):
        raise ValueError('请传 {conversation, messages} 格式的原始聊天 JSON')
    rows = payload['messages']
    if len(rows) > 100000:
        raise ValueError('单次最多导入十万条原消息')
    conversation = payload.get('conversation') or {}
    if not isinstance(conversation, dict):
        raise ValueError('会话信息格式错误')
    account = str(payload.get('account_id') or '')
    normalized = [normalize(row, conversation, account, self_id or str(payload.get('self_id') or '')) for row in rows]
    # Validate every input before modifying the archive; original chronology is retained.
    normalized.sort(key=lambda value: value['created_at'])
    assets, entries, media_summary = _manifest(Path(archive_path)) if archive_path else (None, [], {})
    by_message = {}
    for entry in entries:
        by_message.setdefault(str(entry.get('message_id', '')), []).append(entry)
    created, skipped, media_ok, media_missing = 0, 0, 0, 0
    mappings, linked = [], {}
    existing_attachments = {str(Path(a['path']).resolve()):a for a in store.list_attachments()}
    for item in normalized:
        p = item['meta']['provenance']
        stable_id = uuid.uuid5(uuid.NAMESPACE_URL, 'personal-agent:'+item['key']).hex
        prior = store.get_message(stable_id)
        attachments = []
        if not prior or entries or item['raw'].get('refs'):
            media = by_message.get(p['alpha_id']) or by_message.get(p['source_id']) or []
            for entry in media:
                state = {'kind': entry.get('media_kind'), 'status': entry.get('status'), 'error': entry.get('error_code', '')}
                relative = entry.get('relative_path')
                path = (assets/relative).resolve() if assets and relative else None
                if path and path.is_relative_to(assets.resolve()) and path.is_file():
                    with path.open('rb') as stream:
                        digest = hashlib.file_digest(stream,'sha256').hexdigest()
                    if entry.get('sha256') and digest.lower() != entry['sha256'].lower():
                        state.update(status='missing', error='附件校验失败')
                        media_missing += 1
                    else:
                        target = store.attachments_dir/(digest+path.suffix[:12])
                        if not target.exists():
                            shutil.copy2(path, target)
                        attachment = existing_attachments.get(str(target.resolve()))
                        if not attachment:
                            attachment = store.add_attachment(entry.get('original_filename') or path.name, str(target), entry.get('mime_type') or mimetypes.guess_type(path.name)[0] or 'application/octet-stream', target.stat().st_size)
                            existing_attachments[str(target.resolve())] = attachment
                        attachments.append(attachment['id'])
                        state['attachment_id'] = attachment['id']
                        state['status'] = 'available'
                        media_ok += 1
                else:
                    state['status'] = 'missing'
                    media_missing += 1
                item['meta']['media_status'].append(state)
            if item['raw'].get('refs') and not media:
                item['meta']['media_status'] = [{'kind': ref.get('kind'), 'status': 'missing', 'error': '导出中没有可用附件文件'} for ref in item['raw']['refs']]
                media_missing += len(item['raw']['refs'])
        result = store.import_message(item['key'], item['content'], item['created_at'], item['meta'], attachments, raw=item['raw'])
        created += int(result['created'])
        skipped += int(not result['created'])
        message = result['message']
        if not result['created']:
            store.enrich_imported_media(message['id'],attachments,item['meta']['media_status'])
            store.refresh_imported_metadata(message['id'],item['meta'],item['raw'])
        mappings.append({'source_id': p['source_id'], 'id': message['id'], 'time': message['created_at']})
        linked[p['source_id']] = message['id']
        if p['alpha_id']:
            linked[p['alpha_id']] = message['id']
    for item, mapping in zip(normalized, mappings):
        quote = item['meta'].get('quote') or {}
        target = linked.get(quote.get('source_id'))
        if not target and quote.get('source_id'):
            quote_key = item['key'].rsplit(':',1)[0]+':'+quote['source_id']
            candidate = uuid.uuid5(uuid.NAMESPACE_URL, 'personal-agent:'+quote_key).hex
            if store.get_message(candidate):target = candidate
        if target:
            store.link_imported_reply(mapping['id'], target)
    receipt = {'created': created, 'existing': skipped, 'total': len(rows), 'media_available': media_ok,
               'media_missing': media_missing, 'media_summary': media_summary,
               'conversation': conversation, 'messages': mappings}
    return receipt


def import_file(store, path, self_id=''):
    path = Path(path).expanduser().resolve()
    if not path.is_file() or path.suffix.lower() != '.json':
        raise ValueError('请指定存在的原始聊天 JSON 文件')
    if path.stat().st_size > 512*1024*1024:
        raise ValueError('单次原始聊天文件不能超过 512 MB')
    raw = path.read_bytes()
    payload = json.loads(raw.decode('utf-8-sig'))
    result = import_chat(store, payload, path, self_id)
    folder = store.data_dir/'imports'
    folder.mkdir(parents=True, exist_ok=True)
    original = folder/(hashlib.sha256(raw).hexdigest()+'.json')
    if not original.exists():
        original.write_bytes(raw)
    result['original_path'] = str(original)
    return result
