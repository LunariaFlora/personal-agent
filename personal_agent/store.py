"""Local durable archive, editable notes, and explicit personal memory.

Application code lives separately from this store's database and user files.
All connections are short lived; original messages and note source text survive edits.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import os
import re
import sqlite3
import threading
import unicodedata
import uuid


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="microseconds")


def _json(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _text(value, name, maximum=2_000_000, required=False):
    if not isinstance(value, str) or len(value) > maximum or (required and not value.strip()):
        raise ValueError(f"{name}为空、格式无效或过长")
    return value


def _strings(value, name, maximum=200):
    if value is None:
        return []
    if not isinstance(value, (list, tuple)) or len(value) > maximum:
        raise ValueError(f"{name}格式无效或过长")
    result = []
    for entry in value:
        _text(entry, name, 1000, True)
        if entry not in result:
            result.append(entry)
    return result


def _safe_component(value, fallback="未分类"):
    value = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", value).strip(" .")[:80]
    if re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", value):
        value = "_" + value
    return value or fallback


def _normalized(value):
    return unicodedata.normalize("NFKC", value or "").casefold()


def _score(query, fields):
    """Substring plus overlapping CJK bigrams; no English-tokenizer dependency."""
    query = _normalized(query).strip()
    if not query:
        return 0.0
    words = set(re.findall(r"[a-z0-9_+.#-]{2,}", query))
    runs = re.findall(r"[\u3400-\u9fff]+", query)
    grams = {part[i:i + 2] for part in runs for i in range(len(part) - 1)}
    grams -= {"什么", "这个", "那个", "我的", "我们", "关于", "之前", "一下", "有没有", "怎么"}
    single = {part for part in runs if len(part) == 1}
    score = 0.0
    for text, weight in fields:
        text = _normalized(text)
        if query in text:
            score += 18 * weight
        score += sum(weight * (3 if word in text else 0) for word in words)
        score += sum(weight * (1.4 if gram in text else 0) for gram in grams)
        # One-character searches work, but long natural-language queries don't
        # match everything merely because a common Chinese character occurs.
        if len(query) == 1 or (not grams and not words):
            score += sum(weight if char in text else 0 for char in single)
    return score


class Store:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir).expanduser().resolve()
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.path = self.data_dir / "personal-agent.sqlite3"
        self.attachments_dir = self.data_dir / "attachments"
        self.notes_dir = self.data_dir / "notes"
        self.reports_dir = self.data_dir / "reports"
        self.revisions_dir = self.data_dir / "revisions"
        for folder in (self.attachments_dir, self.notes_dir, self.reports_dir, self.revisions_dir):
            folder.mkdir(parents=True, exist_ok=True)
        self._write_lock = threading.RLock()
        with self._db() as db:
            version = db.execute("PRAGMA user_version").fetchone()[0]
            if version > 1:
                raise ValueError("资料版本较新，请更新 Personal Agent 后打开")
            db.executescript("""
                CREATE TABLE IF NOT EXISTS channels(
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT NOT NULL, mode TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS messages(
                    seq INTEGER PRIMARY KEY AUTOINCREMENT, id TEXT UNIQUE NOT NULL,
                    channel TEXT NOT NULL REFERENCES channels(id), role TEXT NOT NULL,
                    content TEXT NOT NULL, created_at TEXT NOT NULL, reply_to TEXT,
                    attachment_ids TEXT NOT NULL DEFAULT '[]', status TEXT NOT NULL,
                    meta TEXT NOT NULL DEFAULT '{}');
                CREATE INDEX IF NOT EXISTS messages_channel ON messages(channel,seq);
                CREATE INDEX IF NOT EXISTS messages_pending ON messages(channel,status,seq);
                CREATE TABLE IF NOT EXISTS message_versions(
                    id INTEGER PRIMARY KEY, message_id TEXT NOT NULL, content TEXT NOT NULL,
                    attachment_ids TEXT NOT NULL, reply_to TEXT, saved_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS attachments(
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, path TEXT NOT NULL,
                    mime TEXT NOT NULL, size INTEGER NOT NULL, created_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS notes(
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                    category TEXT NOT NULL, kind TEXT NOT NULL, source_ids TEXT NOT NULL,
                    source_url TEXT NOT NULL, original TEXT NOT NULL, tags TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    revision INTEGER NOT NULL DEFAULT 1, archived INTEGER NOT NULL DEFAULT 0,
                    export_path TEXT NOT NULL DEFAULT '', export_hash TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS notes_category ON notes(archived,category,updated_at);
                CREATE TABLE IF NOT EXISTS note_versions(
                    note_id TEXT NOT NULL, revision INTEGER NOT NULL, snapshot TEXT NOT NULL,
                    saved_at TEXT NOT NULL, PRIMARY KEY(note_id,revision));
                CREATE TABLE IF NOT EXISTS memories(
                    id TEXT PRIMARY KEY, content TEXT NOT NULL, kind TEXT NOT NULL,
                    source_ids TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    archived INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS summaries(
                    channel TEXT PRIMARY KEY REFERENCES channels(id), content TEXT NOT NULL,
                    through_id TEXT NOT NULL, updated_at TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS reports(
                    id TEXT PRIMARY KEY, title TEXT NOT NULL, body TEXT NOT NULL,
                    day TEXT UNIQUE NOT NULL, source_ids TEXT NOT NULL,
                    created_at TEXT NOT NULL, updated_at TEXT NOT NULL,
                    export_path TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY,value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS import_records(
                    source_key TEXT PRIMARY KEY, message_id TEXT UNIQUE NOT NULL,
                    payload TEXT NOT NULL, imported_at TEXT NOT NULL);
                PRAGMA user_version=1;
            """)
            db.executemany("INSERT OR IGNORE INTO channels VALUES(?,?,?,?)", [
                ("inbox", "随手记", "发给我，聊一聊，也把值得留下的内容整理起来。", "auto"),
                ("chat", "聊一聊", "讨论问题，继续之前的话题。", "chat"),
                ("collect", "收藏夹", "收下文字、链接、图片和文件，整理成笔记。", "collect"),
                ("transfer", "文件传输", "只保存和传输，不发送给模型。", "transfer"),
            ])

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.path, timeout=30)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA journal_mode=WAL")
        try:
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _decode(row):
        if row is None:
            return None
        value = dict(row)
        for key in ("attachment_ids", "source_ids", "tags", "meta"):
            if key in value:
                value[key] = json.loads(value[key])
        value.pop("export_hash", None)
        value.pop("seq", None)
        return value

    @staticmethod
    def _channel(db, channel):
        if not db.execute("SELECT 1 FROM channels WHERE id=?", (channel,)).fetchone():
            raise ValueError("会话不存在")

    @staticmethod
    def _sources(db, source_ids):
        sources = _strings(source_ids, "来源")
        for source in sources:
            row = db.execute("SELECT channel FROM messages WHERE id=?", (source,)).fetchone()
            if row and row[0] == "transfer":
                raise ValueError("文件传输内容不会自动进入笔记或记忆，请在收藏会话中另行发送")
        return sources

    def channels(self):
        with self._db() as db:
            return [dict(row) for row in db.execute("SELECT * FROM channels ORDER BY rowid")]

    def messages(self, channel, limit=100, before=None):
        limit = max(1, min(100_000, int(limit)))
        with self._db() as db:
            self._channel(db, channel)
            params = [channel]
            clause = ""
            if before:
                prior = db.execute("SELECT seq,channel FROM messages WHERE id=?", (before,)).fetchone()
                if prior:
                    if prior["channel"] != channel:
                        raise ValueError("分页位置不属于当前会话")
                    clause = " AND seq<?"
                    params.append(prior["seq"])
                else:
                    # ISO timestamps are also accepted for date-based pagination.
                    try:
                        datetime.fromisoformat(str(before).replace("Z", "+00:00"))
                    except ValueError:
                        raise ValueError("分页位置不存在") from None
                    clause = " AND created_at<?"
                    params.append(before)
            rows = db.execute("SELECT * FROM messages WHERE channel=?" + clause + " ORDER BY seq DESC LIMIT ?", (*params, limit)).fetchall()
            return [self._decode(row) for row in reversed(rows)]

    def add_message(self, channel, role, content, reply_to=None, attachment_ids=None, status="done", meta=None):
        _text(content, "消息")
        if role not in ("user", "assistant", "system", "tool"):
            raise ValueError("消息角色无效")
        if status not in ("pending", "processing", "paused", "done", "error", "archived"):
            raise ValueError("消息状态无效")
        attachments = _strings(attachment_ids, "附件")
        if not isinstance(meta or {}, dict):
            raise ValueError("消息元数据无效")
        identifier = uuid.uuid4().hex
        with self._write_lock, self._db() as db:
            self._channel(db, channel)
            if reply_to:
                if not db.execute("SELECT 1 FROM messages WHERE id=?", (reply_to,)).fetchone():
                    raise ValueError("引用的消息不存在")
            for attachment in attachments:
                if not db.execute("SELECT 1 FROM attachments WHERE id=?", (attachment,)).fetchone():
                    raise ValueError("附件不存在")
            db.execute("INSERT INTO messages(id,channel,role,content,created_at,reply_to,attachment_ids,status,meta) VALUES(?,?,?,?,?,?,?,?,?)",
                       (identifier, channel, role, content, _now(), reply_to, _json(attachments), status, _json(meta or {})))
        return self.get_message(identifier)

    def import_message(self, source_key, content, created_at, meta, attachment_ids=None, channel="inbox", raw=None):
        """Idempotent immutable historical ingestion; importing does not execute a turn."""
        _text(source_key, "来源标识", 2000, True)
        _text(content, "原消息")
        parsed = datetime.fromisoformat(str(created_at).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError("原消息时间必须包含时区")
        timestamp = parsed.astimezone(timezone.utc).isoformat(timespec="microseconds")
        identifier = uuid.uuid5(uuid.NAMESPACE_URL, "personal-agent:" + source_key).hex
        attachments = _strings(attachment_ids, "附件")
        with self._write_lock, self._db() as db:
            self._channel(db, channel)
            prior = db.execute("SELECT message_id FROM import_records WHERE source_key=?", (source_key,)).fetchone()
            if prior:
                return {"message": self.get_message(prior[0]), "created": False}
            for attachment in attachments:
                if not db.execute("SELECT 1 FROM attachments WHERE id=?", (attachment,)).fetchone():
                    raise ValueError("附件不存在")
            db.execute("INSERT INTO messages(id,channel,role,content,created_at,reply_to,attachment_ids,status,meta) VALUES(?,?,?,?,?,?,?,?,?)",
                       (identifier, channel, "user", content, timestamp, None, _json(attachments), "archived", _json(meta)))
            db.execute("INSERT INTO import_records VALUES(?,?,?,?)", (source_key, identifier, _json(raw if raw is not None else meta), _now()))
        return {"message": self.get_message(identifier), "created": True}

    def imported_record(self, id):
        with self._db() as db:
            row = db.execute("SELECT * FROM import_records WHERE message_id=?", (id,)).fetchone()
            return {**dict(row), "payload": json.loads(row["payload"])} if row else None

    def link_imported_reply(self, id, reply_to):
        with self._write_lock, self._db() as db:
            if not db.execute("SELECT 1 FROM import_records WHERE message_id=?", (id,)).fetchone():
                raise ValueError("只能关联导入消息的原引用")
            if not db.execute("SELECT 1 FROM messages WHERE id=? AND channel<>'transfer'", (reply_to,)).fetchone():
                raise ValueError("引用消息不存在")
            db.execute("UPDATE messages SET reply_to=? WHERE id=? AND reply_to IS NULL", (reply_to, id))

    def enrich_imported_media(self, id, attachment_ids, media_status):
        """A later export may recover media; the historical text stays immutable."""
        with self._write_lock, self._db() as db:
            row = db.execute("SELECT * FROM messages WHERE id=?", (id,)).fetchone()
            if not row or not db.execute("SELECT 1 FROM import_records WHERE message_id=?", (id,)).fetchone():
                raise ValueError("原始导入记录不存在")
            ids = list(dict.fromkeys(json.loads(row['attachment_ids']) + attachment_ids))
            for aid in ids:
                if not db.execute("SELECT 1 FROM attachments WHERE id=?", (aid,)).fetchone():
                    raise ValueError("附件不存在")
            meta = json.loads(row['meta'])
            if media_status:meta['media_status'] = media_status
            db.execute("UPDATE messages SET attachment_ids=?,meta=? WHERE id=?", (_json(ids), _json(meta), id))

    def refresh_imported_metadata(self, id, projection, raw):
        """Improve a decoded representation without replacing its original evidence."""
        with self._write_lock, self._db() as db:
            record=db.execute('SELECT payload FROM import_records WHERE message_id=?',(id,)).fetchone()
            row=db.execute('SELECT meta FROM messages WHERE id=?',(id,)).fetchone()
            if not record or not row:raise ValueError('导入原件不存在')
            original=json.loads(record[0])
            for key in ('text','content','sent_at_unix_ms','created_at'):
                if key in original and key in raw and original[key]!=raw[key]:
                    raise ValueError('同一消息ID的原文或时间不一致，原记录已保留')
            meta=json.loads(row[0])
            for key in ('provenance','source_kind','share','forwarded','quote','parse_warning'):
                if key in projection:meta[key]=projection[key]
            db.execute('UPDATE messages SET meta=? WHERE id=?',(_json(meta),id))

    def queue_imported(self, ids):
        ids = _strings(ids, "消息", 200)
        queued, skipped = [], []
        with self._write_lock, self._db() as db:
            for identifier in ids:
                row = db.execute("SELECT * FROM messages WHERE id=?", (identifier,)).fetchone()
                if not row or not db.execute("SELECT 1 FROM import_records WHERE message_id=?", (identifier,)).fetchone():
                    raise ValueError("导入的原消息不存在")
                if row["channel"] == "transfer":
                    raise ValueError("文件传输内容不参与整理")
                if row["status"] not in ("archived", "error"):
                    skipped.append(identifier)
                    continue
                meta = json.loads(row["meta"])
                meta["replay_mode"] = "organize"
                db.execute("UPDATE messages SET status='pending',meta=? WHERE id=?", (_json(meta), identifier))
                queued.append(identifier)
        return {"queued": queued, "skipped": skipped}

    def message_context(self, id, radius=2):
        focus = self.get_message(id)
        if not focus:
            raise ValueError("消息不存在")
        radius = max(0, min(int(radius), 10))
        provenance = focus.get("meta", {}).get("provenance", {})
        conversation = provenance.get("conversation_id")
        with self._db() as db:
            rows = [self._decode(row) for row in db.execute("SELECT * FROM messages WHERE channel=? ORDER BY created_at,seq", (focus["channel"],))]
        if conversation:
            rows = [m for m in rows if m.get("meta", {}).get("provenance", {}).get("conversation_id") == conversation]
        index = next(i for i, row in enumerate(rows) if row["id"] == id)
        result = rows[max(0, index-radius):index+radius+1]
        quoted = focus
        seen = {m["id"] for m in result}
        traversed = {focus['id']}
        for _ in range(8):
            quoted = self.get_message(quoted.get("reply_to")) if quoted.get("reply_to") else None
            if not quoted or quoted["channel"] == "transfer" or quoted["id"] in traversed:
                break
            traversed.add(quoted['id'])
            if quoted['id'] not in seen:
                seen.add(quoted["id"])
                result.insert(0, quoted)
        return result

    def source_transcript(self, source_ids, include_context=True):
        """Render evidence from immutable messages, never from an LLM paraphrase."""
        evidence = {}
        selected = set(source_ids)
        for identifier in source_ids:
            focus = self.get_message(identifier)
            if not focus or focus["channel"] == "transfer":
                continue
            # Explicit quote chains belong to the evidence. Adjacent unselected
            # topics stay available in the context viewer, not copied into notes.
            for message in self.message_context(identifier, 0):
                evidence[message["id"]] = message
        sections = []
        with self._db() as db:
            sequence = {row['id']:row['seq'] for row in db.execute('SELECT id,seq FROM messages')}
        def forwarded_text(entries, depth=0):
            parts=[]
            for entry in entries:
                parts.append(f"\n{'  '*depth}转发 · {entry.get('sender_name', '原作者')} {entry.get('time', '')}\n{entry.get('content', '')}")
                if entry.get('quote'):
                    q=entry['quote'];parts.append(f"\n引用 {q.get('sender_name','')}：{q.get('content','')}")
                if entry.get('forwarded'):parts.append(forwarded_text(entry['forwarded'],depth+1))
            return ''.join(parts)
        for m in sorted(evidence.values(), key=lambda x: (x["created_at"], sequence[x['id']])):
            meta = m.get("meta") or {}
            p = meta.get("provenance") or {}
            sender = p.get("sender_name") or ("用户" if m["role"] == "user" else "助手")
            label = "原消息" if m["id"] in selected else "上下文"
            kind = '分享卡片' if meta.get('share') else ('合并转发' if meta.get('forwarded') else label)
            text = f"[{m['created_at']}] {sender} · {kind}\n{m['content']}"
            quote = meta.get("quote") or {}
            if quote:
                text += f"\n引用 {quote.get('sender_name', '')} {quote.get('time', '')}：\n{quote.get('content', '')}"
            text += forwarded_text(meta.get('forwarded') or [])
            for aid in m.get("attachment_ids", []):
                attachment = self.get_attachment(aid)
                if attachment:
                    text += f"\n附件：{attachment['name']}"
            for source in meta.get("parsed") or []:
                if source.get("text"):
                    text += f"\n来源材料 {source.get('url') or source.get('title') or ''}（{source.get('scope', '')} / {source.get('status', '')}）：\n{source['text']}"
            sections.append(text)
        return "\n\n".join(sections)

    def get_message(self, id):
        with self._db() as db:
            return self._decode(db.execute("SELECT * FROM messages WHERE id=?", (id,)).fetchone())

    def update_message(self, id, **fields):
        if set(fields) - {"content", "status", "meta"}:
            raise ValueError("不支持修改消息身份、时间或来源")
        with self._write_lock, self._db() as db:
            row = db.execute("SELECT * FROM messages WHERE id=?", (id,)).fetchone()
            if row is None:
                raise ValueError("消息不存在")
            if "status" in fields and fields["status"] not in ("pending", "processing", "paused", "done", "error"):
                raise ValueError("消息状态无效")
            if "content" in fields:
                _text(fields["content"], "消息")
                if row["role"] == "user" and fields["content"] != row["content"]:
                    raise ValueError("用户原始消息不可覆盖")
                if fields["content"] != row["content"]:
                    db.execute("INSERT INTO message_versions(message_id,content,attachment_ids,reply_to,saved_at) VALUES(?,?,?,?,?)",
                               (id, row["content"], row["attachment_ids"], row["reply_to"], _now()))
            if "meta" in fields:
                if not isinstance(fields["meta"], dict):
                    raise ValueError("消息元数据无效")
                fields["meta"] = _json(fields["meta"])
            if fields:
                db.execute("UPDATE messages SET " + ",".join(key + "=?" for key in fields) + " WHERE id=?", (*fields.values(), id))
        return self.get_message(id)

    def pending_messages(self, channel):
        with self._db() as db:
            return [self._decode(row) for row in db.execute("SELECT * FROM messages WHERE channel=? AND status IN ('pending','processing') ORDER BY seq", (channel,))]

    def clear_pending(self, channel, ids):
        ids = _strings(ids, "消息", 1000)
        if not ids:
            return
        with self._write_lock, self._db() as db:
            db.execute("UPDATE messages SET status='done' WHERE channel=? AND id IN (" + ",".join("?" for _ in ids) + ")", (channel, *ids))

    def add_attachment(self, name, path, mime, size):
        _text(name, "文件名", 1000, True)
        _text(mime, "文件类型", 200)
        path = Path(path).resolve()
        if not path.is_relative_to(self.data_dir) or not path.is_file():
            raise ValueError("附件必须是资料目录中的实际文件")
        actual_size = path.stat().st_size
        if int(size) != actual_size or actual_size < 0:
            raise ValueError("附件大小与实际文件不一致")
        identifier = uuid.uuid4().hex
        with self._write_lock, self._db() as db:
            db.execute("INSERT INTO attachments VALUES(?,?,?,?,?,?)", (identifier, name, str(path), mime, actual_size, _now()))
        return self.get_attachment(identifier)

    def get_attachment(self, id):
        with self._db() as db:
            return self._decode(db.execute("SELECT * FROM attachments WHERE id=?", (id,)).fetchone())

    def list_attachments(self):
        with self._db() as db:
            return [self._decode(row) for row in db.execute("SELECT * FROM attachments ORDER BY created_at DESC")]

    def _note_markdown(self, note):
        metadata = {key: note[key] for key in ("id", "title", "category", "kind", "tags", "source_ids", "source_url", "created_at", "updated_at")}
        text = "---\n" + "\n".join(key + ": " + _json(value) for key, value in metadata.items()) + "\n---\n\n"
        text += "# " + note["title"].replace("\n", " ") + "\n\n" + note["body"].rstrip() + "\n"
        if note["original"]:
            text += "\n## 原文\n\n" + "\n".join("> " + line if line else ">" for line in note["original"].splitlines()) + "\n"
        if note["source_url"]:
            text += "\n## 来源\n\n" + note["source_url"] + "\n"
        return text

    def _write_export(self, path, text, previous_hash=""):
        path = Path(path).resolve()
        if not path.is_relative_to(self.data_dir):
            raise ValueError("笔记导出必须保存在资料目录")
        encoded = text.encode("utf-8")
        if path.exists():
            previous = path.read_bytes()
            digest = hashlib.sha256(previous).hexdigest()
            if previous != encoded and digest != previous_hash:
                # Edits made in a Markdown editor are retained before regeneration.
                backup = self.revisions_dir / (path.stem + "-" + digest[:16] + ".md")
                if not backup.exists():
                    backup.write_bytes(previous)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
        try:
            temporary.write_bytes(encoded)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        return hashlib.sha256(encoded).hexdigest()

    def list_notes(self, query="", category="", kind=""):
        with self._db() as db:
            rows = [self._decode(row) for row in db.execute("SELECT * FROM notes WHERE archived=0 ORDER BY updated_at DESC")]
        if category:
            rows = [row for row in rows if row["category"] == category or row["category"].startswith(category.rstrip("/") + "/")]
        if kind:
            rows = [row for row in rows if row["kind"] == kind]
        return self._rank_notes(query, rows, 500) if query.strip() else rows

    def get_note(self, id):
        with self._db() as db:
            return self._decode(db.execute("SELECT * FROM notes WHERE id=?", (id,)).fetchone())

    def save_note(self, title, body, category="收件箱", kind="note", source_ids=None, source_url="", original="", tags=None, note_id=None):
        _text(title, "标题", 500, True)
        _text(body, "笔记内容")
        _text(category, "分类", 500, True)
        _text(kind, "笔记类型", 100, True)
        _text(source_url, "来源链接", 8000)
        _text(original, "原文")
        if any(part.strip() in (".", "..") for part in re.split(r"[/\\]", category)):
            raise ValueError("分类路径不能包含上级目录")
        category = "/".join(part.strip() for part in re.split(r"[/\\]", category) if part.strip()) or "收件箱"
        with self._write_lock, self._db() as db:
            previous = db.execute("SELECT * FROM notes WHERE id=?", (note_id,)).fetchone() if note_id else None
            if note_id and previous is None:
                raise ValueError("笔记不存在")
            old = self._decode(previous) if previous else None
            identifier = note_id or uuid.uuid4().hex
            sources = self._sources(db, source_ids if source_ids is not None else (old["source_ids"] if old else []))
            note = dict(id=identifier, title=title.strip(), body=body, category=category, kind=kind,
                        source_ids=sources, source_url=source_url or (old["source_url"] if old else ""),
                        original=(old["original"] + ("\n\n" + original if original and set(sources)-set(old["source_ids"]) and original not in old["original"] else "")) if old else original,
                        tags=_strings(tags if tags is not None else (old["tags"] if old else []), "标签"),
                        created_at=old["created_at"] if old else _now(), updated_at=_now(),
                        revision=old["revision"] + 1 if old else 1, archived=0)
            folder = self.notes_dir.joinpath(*(_safe_component(part) for part in category.split("/")))
            path = folder / (_safe_component(note["title"], "笔记") + "-" + identifier[:10] + ".md")
            note["export_path"] = str(path)
            export_hash = self._write_export(path, self._note_markdown(note), previous["export_hash"] if previous and previous["export_path"] == str(path) else "")
            values = [note[key] if key not in ("source_ids", "tags") else _json(note[key]) for key in ("id", "title", "body", "category", "kind", "source_ids", "source_url", "original", "tags", "created_at", "updated_at", "revision", "archived", "export_path")]
            db.execute("INSERT INTO notes VALUES(" + ",".join("?" for _ in range(15)) + ") ON CONFLICT(id) DO UPDATE SET " + ",".join(key + "=excluded." + key for key in note if key != "id") + ",export_hash=excluded.export_hash", (*values, export_hash))
            db.execute("INSERT INTO note_versions VALUES(?,?,?,?)", (identifier, note["revision"], _json(note), note["updated_at"]))
            if previous and previous["export_path"] != str(path):
                old_path = Path(previous["export_path"]).resolve()
                if old_path.is_relative_to(self.notes_dir) and old_path.is_file() and hashlib.sha256(old_path.read_bytes()).hexdigest() == previous["export_hash"]:
                    old_path.unlink()  # Only the unchanged generated copy moves.
        return self.get_note(identifier)

    def delete_note(self, id):
        with self._write_lock, self._db() as db:
            row = db.execute("SELECT * FROM notes WHERE id=?", (id,)).fetchone()
            if row is None:
                raise ValueError("笔记不存在")
            if row["archived"]:
                return
            now = _now()
            db.execute("UPDATE notes SET archived=1,updated_at=?,revision=revision+1 WHERE id=?", (now, id))
            value = self._decode(db.execute("SELECT * FROM notes WHERE id=?", (id,)).fetchone())
            db.execute("INSERT INTO note_versions VALUES(?,?,?,?)", (id, value["revision"], _json(value), now))

    def notes_revision(self, id):
        with self._db() as db:
            return [dict(revision=row["revision"], saved_at=row["saved_at"], **{"note": json.loads(row["snapshot"])}) for row in db.execute("SELECT * FROM note_versions WHERE note_id=? ORDER BY revision DESC", (id,))]

    note_revisions = notes_revision

    @staticmethod
    def _rank_notes(query, rows, limit):
        found = []
        for row in rows:
            value = _score(query, [(row["title"], 4), (" ".join(row["tags"]), 3), (row["category"], 1.5), (row["body"], 1), (row["original"], 1)])
            if value > 0:
                found.append({**row, "score": round(value, 3)})
        return sorted(found, key=lambda row: (row["score"], row["updated_at"]), reverse=True)[:limit]

    def search(self, query, limit=8):
        _text(query, "查询", 2000)
        if not query.strip():
            return []
        return self._rank_notes(query, self.list_notes(), max(1, min(100, int(limit))))

    def search_messages(self, query, limit=20):
        _text(query, "查询", 2000)
        if not query.strip():
            return []
        with self._db() as db:
            rows = [self._decode(row) for row in db.execute("SELECT * FROM messages WHERE channel<>'transfer' ORDER BY seq DESC")]
        found = []
        for row in rows:
            value = _score(query, [(row["content"], 1)])
            if value > 0:
                found.append({**row, "score": round(value, 3)})
        return sorted(found, key=lambda row: (row["score"], row["created_at"]), reverse=True)[:max(1, min(100, int(limit)))]

    def list_memories(self):
        with self._db() as db:
            return [self._decode(row) for row in db.execute("SELECT * FROM memories WHERE archived=0 ORDER BY updated_at DESC")]

    def save_memory(self, content, kind="preference", source_ids=None, memory_id=None):
        _text(content, "记忆", 100_000, True)
        _text(kind, "记忆类型", 100, True)
        with self._write_lock, self._db() as db:
            old = db.execute("SELECT * FROM memories WHERE id=?", (memory_id,)).fetchone() if memory_id else None
            if memory_id and old is None:
                raise ValueError("记忆不存在")
            identifier = memory_id or uuid.uuid4().hex
            sources = self._sources(db, source_ids if source_ids is not None else (json.loads(old["source_ids"]) if old else []))
            now = _now()
            db.execute("INSERT INTO memories VALUES(?,?,?,?,?,?,0) ON CONFLICT(id) DO UPDATE SET content=excluded.content,kind=excluded.kind,source_ids=excluded.source_ids,updated_at=excluded.updated_at,archived=0",
                       (identifier, content, kind, _json(sources), old["created_at"] if old else now, now))
            return self._decode(db.execute("SELECT * FROM memories WHERE id=?", (identifier,)).fetchone())

    def delete_memory(self, id):
        with self._write_lock, self._db() as db:
            db.execute("UPDATE memories SET archived=1,updated_at=? WHERE id=?", (_now(), id))

    def get_summary(self, channel):
        with self._db() as db:
            row = db.execute("SELECT content,through_id,updated_at FROM summaries WHERE channel=?", (channel,)).fetchone()
            return dict(row) if row else {"content": "", "through_id": "", "updated_at": ""}

    def set_summary(self, channel, content, through_id):
        _text(content, "上下文摘要")
        with self._write_lock, self._db() as db:
            self._channel(db, channel)
            if channel == "transfer":
                raise ValueError("文件传输会话不建立模型上下文")
            if through_id and not db.execute("SELECT 1 FROM messages WHERE id=? AND channel=?", (through_id, channel)).fetchone():
                raise ValueError("摘要边界消息不属于当前会话")
            db.execute("INSERT INTO summaries VALUES(?,?,?,?) ON CONFLICT(channel) DO UPDATE SET content=excluded.content,through_id=excluded.through_id,updated_at=excluded.updated_at", (channel, content, through_id or "", _now()))
        return self.get_summary(channel)

    def list_reports(self):
        with self._db() as db:
            return [self._decode(row) for row in db.execute("SELECT * FROM reports ORDER BY day DESC,created_at DESC")]

    def get_report(self, id):
        with self._db() as db:
            return self._decode(db.execute("SELECT * FROM reports WHERE id=?", (id,)).fetchone())

    def save_report(self, title, body, day, source_ids=None):
        _text(title, "日报标题", 500, True)
        _text(body, "日报正文")
        try:
            datetime.strptime(day, "%Y-%m-%d")
        except (ValueError, TypeError):
            raise ValueError("日报日期须为 YYYY-MM-DD") from None
        with self._write_lock, self._db() as db:
            old = db.execute("SELECT * FROM reports WHERE day=?", (day,)).fetchone()
            identifier, now = (old["id"] if old else uuid.uuid4().hex), _now()
            sources = self._sources(db, source_ids)
            path = self.reports_dir / (day + ".md")
            text = "---\nid: " + _json(identifier) + "\nday: " + _json(day) + "\nsource_ids: " + _json(sources) + "\n---\n\n# " + title.replace("\n", " ") + "\n\n" + body.rstrip() + "\n"
            self._write_export(path, text)
            db.execute("INSERT INTO reports VALUES(?,?,?,?,?,?,?,?) ON CONFLICT(day) DO UPDATE SET title=excluded.title,body=excluded.body,source_ids=excluded.source_ids,updated_at=excluded.updated_at,export_path=excluded.export_path",
                       (identifier, title, body, day, _json(sources), old["created_at"] if old else now, now, str(path)))
        return self.get_report(identifier)

    def get_setting(self, key, default=None):
        with self._db() as db:
            row = db.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
            return json.loads(row[0]) if row else default

    def set_setting(self, key, value):
        _text(key, "设置名", 200, True)
        with self._write_lock, self._db() as db:
            db.execute("INSERT INTO settings VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (key, _json(value)))

    def stats(self):
        with self._db() as db:
            return {"notes": db.execute("SELECT count(*) FROM notes WHERE archived=0").fetchone()[0],
                    "messages": db.execute("SELECT count(*) FROM messages").fetchone()[0],
                    "memories": db.execute("SELECT count(*) FROM memories WHERE archived=0").fetchone()[0],
                    "files": db.execute("SELECT count(*) FROM attachments").fetchone()[0],
                    "reports": db.execute("SELECT count(*) FROM reports").fetchone()[0]}
