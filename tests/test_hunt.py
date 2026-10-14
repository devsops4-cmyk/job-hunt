import unittest
from hunt import contacts, key, qualify, safe_url, csv_safe


class IntegrityTests(unittest.TestCase):
    def test_posts_are_not_team_profiles(self):
        links = [{'url': u} for u in ['https://x.com/team/status/123', 'https://x.com/i/communities/42', 'https://instagram.com/p/123', 'https://x.com/search?q=coin']]
        self.assertEqual(contacts(links), [])

    def test_contact_hosts_and_schemes(self):
        self.assertEqual(contacts([{'url': 'https://x.com/RealTeam'}, {'url': 'https://x.com.evil.test/fake'}, {'url': 'javascript:alert(1)'}, {'url': 'https://t.me/teamchannel'}]), ['https://t.me/teamchannel', 'https://x.com/RealTeam'])

    def test_identity_respects_solana_case(self):
        self.assertNotEqual(key('solana', 'Abc'), key('solana', 'abc'))
        self.assertEqual(key('base', '0xAbC'), key('base', '0xabc'))

    def test_unknown_stale_future_and_duplicate_not_qualified(self):
        def p(id, ts): return {'id': id, 'pool_timestamp': ts, 'contact_links': ['https://x.com/team']}
        rows = [p('old', 1), p('unknown', None), p('future', 9999999), p('seen', 199999), p('fresh', 199999)]
        self.assertEqual([p['id'] for p in qualify(rows, {'seen'}, 200000, 1)], ['fresh'])

    def test_unsafe_links_and_csv_cells(self):
        self.assertEqual(safe_url('javascript:alert(1)'), '')
        self.assertEqual(safe_url('https://user:pass@host.test'), '')
        self.assertTrue(csv_safe(' =HYPERLINK("bad")').startswith("'"))


if __name__ == '__main__':
    unittest.main()
