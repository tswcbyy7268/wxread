import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import session_state


class SessionStateTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'session.json'
        self.environment = patch.dict(os.environ, {'WXREAD_SESSION_PATH': str(self.path), 'WXREAD_CURL_BASH': 'first-login'})
        self.environment.start()
        self.addCleanup(self.environment.stop)

    def test_rotated_cookies_survive_next_process(self):
        session_state.save({'wr_vid': 'same-user', 'wr_skey': 'new-key', 'wr_rt': 'rotated-token'})
        cookies = {'wr_vid': 'same-user', 'wr_skey': 'old-key'}
        self.assertTrue(session_state.restore(cookies))
        self.assertEqual(cookies['wr_rt'], 'rotated-token')
        self.assertEqual(cookies['wr_skey'], 'new-key')
        self.assertFalse(list(self.path.parent.glob('.session-*')))
        if os.name != 'nt':
            self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)

    def test_new_qr_login_discards_old_saved_session(self):
        session_state.save({'wr_vid': 'same-user', 'wr_skey': 'cached-key'})
        with patch.dict(os.environ, {'WXREAD_CURL_BASH': 'new-qr-login'}):
            cookies = {'wr_vid': 'same-user', 'wr_skey': 'fresh-key'}
            self.assertFalse(session_state.restore(cookies))
            self.assertEqual(cookies['wr_skey'], 'fresh-key')

    def test_account_mismatch_stops(self):
        session_state.save({'wr_vid': 'other-user', 'wr_skey': 'cached-key'})
        with self.assertRaises(ValueError):
            session_state.restore({'wr_vid': 'expected-user'})

    def test_corrupt_state_does_not_become_empty_session(self):
        self.path.write_text('broken', encoding='utf-8')
        with self.assertRaises(ValueError):
            session_state.restore({'wr_vid': 'same-user'})
