import importlib.util
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import recovery
import run_until


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = patch.dict(os.environ, {'WXREAD_PROGRESS_PATH': str(Path(self.temp.name) / 'progress.json'),
                                          'WXREAD_SUPERVISED': '1', 'READ_UNTIL': ''})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_network_failure_then_resume(self):
        def run(*args, **kwargs):
            if recovery.completed() == 0:
                recovery.record(1)
                return types.SimpleNamespace(returncode=75)
            self.assertEqual(recovery.completed(), 1)
            recovery.record(2)
            return types.SimpleNamespace(returncode=0)
        with patch('run_until.subprocess.run', side_effect=run) as process, patch('run_until.time.sleep') as sleep, patch('run_until.notify') as notify:
            self.assertEqual(run_until.supervise(2), 0)
        self.assertEqual(process.call_count, 2)
        sleep.assert_called_once_with(30)
        self.assertTrue(notify.call_args.args[1])

    def test_recovery_is_bounded(self):
        with patch('run_until.subprocess.run', return_value=types.SimpleNamespace(returncode=75)) as process, patch('run_until.time.sleep') as sleep, patch('run_until.notify') as notify:
            self.assertEqual(run_until.supervise(2), 75)
        self.assertEqual(process.call_count, 4)
        self.assertEqual([c.args[0] for c in sleep.call_args_list], [30, 60, 120])
        self.assertFalse(notify.call_args.args[1])

    def test_auth_failure_does_not_restart(self):
        with patch('run_until.subprocess.run', return_value=types.SimpleNamespace(returncode=77)) as process, patch('run_until.time.sleep') as sleep, patch('run_until.notify') as notify:
            self.assertEqual(run_until.supervise(2), 77)
        process.assert_called_once()
        sleep.assert_not_called()
        self.assertIn('登录状态失效', notify.call_args.args[0])

    def test_cutoff_stops_hung_process(self):
        with patch('run_until.subprocess.run', side_effect=subprocess.TimeoutExpired('main', 1)), patch('run_until.notify') as notify:
            self.assertEqual(run_until.supervise(2, run_until.time.time() + 1), 0)
        self.assertIn('截止时间', notify.call_args.args[0])

    def test_corrupt_progress_fails_closed(self):
        Path(os.environ['WXREAD_PROGRESS_PATH']).write_text('broken')
        with patch('run_until.subprocess.run') as process, patch('run_until.notify') as notify:
            self.assertEqual(run_until.main(), 1)
        process.assert_not_called()
        self.assertFalse(notify.call_args.args[1])

    def test_reader_records_and_resumes_after_timeout(self):
        config = types.SimpleNamespace(data={'s': 'old'}, headers={}, cookies={}, READ_NUM=2,
                                       PUSH_METHOD='', book=['three-body'], chapter=['matching-chapter'])
        successful = lambda: types.SimpleNamespace(status_code=200, json=lambda: {'succ': 1, 'synckey': 1})
        calls = []
        def first_post(url, **kwargs):
            if 'renewal' in url:
                return types.SimpleNamespace(cookies={'wr_skey': 'new-key'})
            calls.append(url)
            if len(calls) == 2:
                import requests
                raise requests.exceptions.ReadTimeout('simulated network timeout')
            return successful()
        push = types.SimpleNamespace(push=Mock())
        with patch.dict(sys.modules, {'config': config, 'push': push}), patch('requests.post', side_effect=first_post), patch('time.sleep'):
            with self.assertRaises(SystemExit) as result:
                runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
        self.assertEqual(result.exception.code, 75)
        self.assertEqual(recovery.completed(), 1)
        config.data['s'] = 'old'
        def next_post(url, **kwargs):
            if 'renewal' in url:
                return types.SimpleNamespace(cookies={'wr_skey': 'new-key'})
            calls.append(url)
            return successful()
        with patch.dict(sys.modules, {'config': config, 'push': push}), patch('requests.post', side_effect=next_post), patch('time.sleep'):
            runpy.run_path(str(ROOT / 'main.py'), run_name='__main__')
        self.assertEqual(recovery.completed(), 2)
        self.assertEqual(len(calls), 3)  # first success, timeout, remaining success
        push.push.assert_not_called()

    def test_pushplus_rejection_is_not_success(self):
        config = types.SimpleNamespace(**{name: '' for name in ['PUSHPLUS_TOKEN','SERVERCHAN_SPT','TELEGRAM_BOT_TOKEN','TELEGRAM_CHAT_ID','WXPUSHER_SPT']})
        with patch.dict(sys.modules, {'config': config}):
            spec = importlib.util.spec_from_file_location('push_under_test', ROOT / 'push.py')
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
        response = Mock()
        response.json.return_value = {'code': 600}
        with patch('requests.post', return_value=response):
            self.assertFalse(module.PushNotification().push_pushplus('test', 'test', True))


if __name__ == '__main__':
    unittest.main()
