"""Behaviour tests for the storage and import layers.

Only the standard library is needed: these modules talk to SQLite and to
plain dicts, so no server, model call or network access is involved.
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from personal_agent.chat_import import normalize
from personal_agent.engine import compact_json, json_result, reference_title
from personal_agent.store import Store


class NoteTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_note_round_trip(self):
        note = self.store.save_note('Diagonalisation', 'Eigenvalues first.', category='math')
        loaded = self.store.get_note(note['id'])
        self.assertEqual(loaded['title'], 'Diagonalisation')
        self.assertIn('Eigenvalues', loaded['body'])
        self.assertEqual(loaded['category'], 'math')

    def test_nested_category_is_kept(self):
        self.store.save_note('Series', 'Convergence tests.', category='教育/学习/数学')
        rows = self.store.list_notes(category='教育/学习/数学')
        self.assertEqual([row['title'] for row in rows], ['Series'])
        self.assertEqual(rows[0]['category'], '教育/学习/数学')

    def test_search_matches_chinese_text(self):
        self.store.save_note('矩阵', '特征值与特征向量')
        self.store.save_note('Training loop', 'learning rate schedule')
        hits = self.store.search('特征值')
        self.assertTrue(hits)
        self.assertIn('矩阵', json.dumps(hits, ensure_ascii=False))

    def test_update_keeps_one_note(self):
        note = self.store.save_note('Draft', 'first version')
        self.store.save_note('Draft', 'second version', note_id=note['id'])
        rows = self.store.list_notes()
        self.assertEqual(len(rows), 1)
        self.assertIn('second version', self.store.get_note(note['id'])['body'])

    def test_delete_archives_the_note(self):
        note = self.store.save_note('Temp', 'to be removed')
        self.store.delete_note(note['id'])
        self.assertEqual(self.store.list_notes(), [])
        self.assertTrue(self.store.get_note(note['id'])['archived'])

    def test_notes_do_not_leak_between_data_directories(self):
        with tempfile.TemporaryDirectory() as other:
            second = Store(Path(other))
            second.save_note('Other library', 'body')
            self.assertEqual(len(second.list_notes()), 1)
            self.assertEqual(self.store.list_notes(), [])


class MemoryAndReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_memory_round_trip_and_delete(self):
        memory = self.store.save_memory('prefers short answers', kind='preference')
        self.assertEqual(len(self.store.list_memories()), 1)
        self.store.delete_memory(memory['id'])
        self.assertEqual(self.store.list_memories(), [])

    def test_report_is_listed_with_its_day(self):
        self.store.save_report('Tuesday', 'Three things moved.', day='2026-11-18')
        rows = self.store.list_reports()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]['day'], '2026-11-18')

    def test_setting_round_trip(self):
        self.store.set_setting('digest_hour', 9)
        self.assertEqual(self.store.get_setting('digest_hour'), 9)
        self.assertEqual(self.store.get_setting('missing', 'fallback'), 'fallback')


class MessageTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.tmp.name))

    def tearDown(self):
        self.tmp.cleanup()

    def test_message_context_returns_neighbours(self):
        first = self.store.add_message('chat', 'user', 'one')
        self.store.add_message('chat', 'assistant', 'two')
        third = self.store.add_message('chat', 'user', 'three')
        context = self.store.message_context(third['id'], radius=2)
        ids = [row['id'] for row in context]
        self.assertIn(first['id'], ids)
        self.assertIn(third['id'], ids)

    def test_reimporting_the_same_source_does_not_duplicate(self):
        payload = {'content': 'hello', 'created_at': '2026-11-18T00:00:00+00:00'}
        first = self.store.import_message('conv-1|msg-1', 'hello', payload['created_at'], {})
        second = self.store.import_message('conv-1|msg-1', 'hello', payload['created_at'], {})
        self.assertTrue(first['created'])
        self.assertFalse(second['created'])
        self.assertEqual(first['message']['id'], second['message']['id'])
        self.assertEqual(len(self.store.messages('inbox', limit=50)), 1)

    def test_attachment_is_registered(self):
        path = Path(self.tmp.name) / 'note.txt'
        path.write_text('hello there', encoding='utf-8')
        attachment = self.store.add_attachment('note.txt', path, 'text/plain', path.stat().st_size)
        self.assertEqual(self.store.get_attachment(attachment['id'])['name'], 'note.txt')
        self.assertEqual(len(self.store.list_attachments()), 1)

    def test_attachment_outside_the_data_directory_is_refused(self):
        outside = Path(tempfile.gettempdir()) / 'outside-note.txt'
        outside.write_text('x', encoding='utf-8')
        with self.assertRaises(ValueError):
            self.store.add_attachment('outside.txt', outside, 'text/plain', outside.stat().st_size)


class ImportNormalisationTests(unittest.TestCase):
    CONVERSATION = {'id': 'conv-1'}

    def row(self, **overrides):
        base = {
            'id': 'msg-1',
            'conversation_id': 'conv-1',
            'content': 'hello',
            'created_at': '2026-11-18T10:00:00+08:00',
        }
        base.update(overrides)
        return base

    def test_requires_a_stable_identifier(self):
        with self.assertRaises(ValueError):
            normalize({'conversation_id': 'conv-1', 'content': 'x',
                       'created_at': '2026-11-18T10:00:00+08:00'}, self.CONVERSATION)

    def test_rejects_float_identifiers(self):
        with self.assertRaises(ValueError):
            normalize(self.row(id=1.5), self.CONVERSATION)

    def test_rejects_timestamps_without_a_zone(self):
        with self.assertRaises(ValueError):
            normalize(self.row(created_at='2026-11-18T10:00:00'), self.CONVERSATION)

    def test_normalises_to_utc(self):
        record = normalize(self.row(), self.CONVERSATION)
        self.assertTrue(record['created_at'].endswith('+00:00'))
        self.assertEqual(record['content'], 'hello')

    def test_marks_the_users_own_messages(self):
        mine = normalize(self.row(id='msg-2', is_self=True), self.CONVERSATION)
        theirs = normalize(self.row(id='msg-3'), self.CONVERSATION)
        self.assertTrue(mine['meta']['provenance']['is_self'])
        self.assertFalse(theirs['meta']['provenance']['is_self'])

    def test_media_without_text_keeps_a_placeholder(self):
        record = normalize(self.row(content='', source_type='3'), self.CONVERSATION)
        self.assertEqual(record['content'], '[图片]')


class EngineHelperTests(unittest.TestCase):
    def test_reference_title_strips_platform_branding(self):
        self.assertEqual(reference_title('Camera review _ 哔哩哔哩'), 'camerareview')
        self.assertEqual(reference_title('Sample | YouTube'), 'sample')

    def test_json_result_parses_plain_and_wrapped_json(self):
        self.assertEqual(json_result('{"a": 1}'), {'a': 1})
        self.assertEqual(json_result('```json\n{"a": 2}\n```'), {'a': 2})

    def test_compact_json_keeps_unicode_readable(self):
        self.assertEqual(compact_json({'标题': '测试'}), '{"标题":"测试"}')


if __name__ == '__main__':
    unittest.main()
