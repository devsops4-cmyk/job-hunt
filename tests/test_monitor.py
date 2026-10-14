import json
import argparse
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from monitor import (validate_brief, brief_text, connect, add_projects,
                     deliver, daily_count, check_telegram, source_urls, cycle)

URL = 'https://x.com/project/status/123'


def example():
    return {
        'project': 'Example project', 'purpose': 'An on-chain game',
        'purpose_sources': [URL], 'contact_url': 'https://x.com/project',
        'contact_identity_evidence': [URL], 'launch_date': '2026-10-14',
        'launch_evidence': [URL], 'posts_read': [{'url': URL, 'date': '2026-10-14', 'finding': 'Launch announcement'}],
        'opportunities': [{'observation': 'A tutorial could explain the launch mechanic',
            'kind': 'possible_improvement', 'evidence_urls': [URL],
            'possible_deliverable': 'An interactive tutorial',
            'draft_pitch': 'Would an interactive tutorial help explain this mechanic?',
            'what_to_confirm': 'Whether a tutorial already exists'}], 'unknowns': ['DM availability'],
    }


class EvidenceTests(unittest.TestCase):
    def test_candidate_cannot_pass_with_invented_source(self):
        brief = example()
        brief['opportunities'][0]['evidence_urls'] = ['https://invented.test']
        self.assertTrue(validate_brief(brief, {URL}, date(2026, 10, 14)))

    def test_missing_launch_and_unread_posts_fail(self):
        brief = example()
        brief['launch_date'] = ''
        brief['posts_read'] = []
        errors = validate_brief(brief, {URL}, date(2026, 10, 14))
        self.assertIn('No verified launch date', errors)
        self.assertIn('No substantive project post read', errors)

    def test_proposal_allowed_without_manufactured_defect(self):
        self.assertEqual(validate_brief(example(), {URL}, date(2026, 10, 14)), [])
        text = brief_text(example(), 'id')
        self.assertIn('Possible improvement (confirm first)', text)
        self.assertIn('choose your own role', text)
        self.assertIn(URL, text)

    def test_old_launch_rejected(self):
        self.assertIn('Launch outside configured new-project window', validate_brief(example(), {URL}, date(2026, 11, 1)))

    def test_long_unicode_brief_stays_in_telegram_limit(self):
        brief = example()
        for field in ('purpose', 'project'):
            brief[field] = '🐱' * 5000
        for field in ('observation', 'possible_deliverable', 'draft_pitch', 'what_to_confirm'):
            brief['opportunities'][0][field] = '🐱' * 5000
        # Length protection must fail closed, never submit an oversized message.
        try:
            text = brief_text(brief, 'id')
        except ValueError:
            return
        self.assertLessEqual(len(text.encode('utf-16-le')) // 2, 4096)

    def test_response_urls_only_from_actual_tool_sources(self):
        response = {'output': [{'type': 'web_search_call', 'action': {'sources': [{'url': URL}]}},
                     {'type': 'message', 'content': [{'type': 'output_text', 'text': 'https://invented.test', 'annotations': []}]}]}
        self.assertEqual(source_urls(response), {URL})


class DeliveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / 'state.sqlite3'
        self.db = connect(self.path)
        add_projects(self.db, [{'id': 'test', 'name': 'Example'}])
        self.db.execute("UPDATE projects SET status='ready',brief=?", (json.dumps(example()),))
        self.db.commit()

    def tearDown(self):
        self.db.close()
        self.temp.cleanup()

    def row(self):
        return self.db.execute('SELECT * FROM projects').fetchone()

    @patch('monitor.telegram', return_value={'message_id': 10})
    def test_success_records_delivery(self, send):
        self.assertTrue(deliver(self.db, self.row(), 'fake', '123', '2026-10-14'))
        self.assertEqual(self.row()['status'], 'sent')
        self.assertEqual(daily_count(self.db, '2026-10-14'), 1)
        self.assertEqual(daily_count(self.db, '2026-10-15'), 0)
        self.assertEqual(send.call_count, 1)
        self.assertFalse(deliver(self.db, self.row(), 'fake', '123', '2026-10-14'))
        self.assertEqual(send.call_count, 1)

    @patch('monitor.telegram', side_effect=RuntimeError('timeout'))
    def test_ambiguous_delivery_not_ready_for_resend(self, send):
        self.assertFalse(deliver(self.db, self.row(), 'fake', '123', '2026-10-14'))
        self.assertEqual(self.row()['status'], 'delivery_uncertain')
        self.assertEqual(daily_count(self.db, '2026-10-14'), 1)

    def test_crash_during_send_recovers_as_uncertain(self):
        self.db.execute("UPDATE projects SET status='sending'")
        self.db.commit()
        self.db.close()
        self.db = connect(self.path)
        self.assertEqual(self.row()['status'], 'delivery_uncertain')

    @patch('monitor.telegram', side_effect=[{'username': 'mybot'}, {'id': -123, 'type': 'group'}])
    def test_initial_setup_rejects_group_target(self, send):
        with self.assertRaises(RuntimeError):
            check_telegram('fake', '-123')

    def test_dry_research_cycle_persists_brief_without_sending(self):
        self.db.execute('DELETE FROM projects')
        self.db.commit()
        args = argparse.Namespace(data=Path(self.temp.name), gecko_pages=0,
            max_age_days=7, x_query='', seed_json=None, discover_only=False,
            target=50, max_research_daily=100, batch=1, send_telegram=False)
        brief = example()
        from datetime import datetime
        from monitor import LAGOS
        brief['launch_date'] = datetime.now(LAGOS).date().isoformat()
        with patch('monitor.discover', return_value={}), patch('monitor.enrich', return_value=[{'id':'new','name':'Example'}]), patch('monitor.research', return_value=(brief, {URL}, {}, [])), patch('monitor.telegram') as send, patch('builtins.print'):
            cycle(args, self.db)
        self.assertEqual(self.row()['status'], 'ready')
        self.assertTrue((Path(self.temp.name)/'briefs.json').exists())
        self.assertEqual(self.db.execute('SELECT SUM(research_calls) FROM usage').fetchone()[0], 1)
        send.assert_not_called()


if __name__ == '__main__':
    unittest.main()
