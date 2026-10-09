import os
import unittest
from unittest.mock import patch
import official_stats as stats
import verified_run as verify


def snapshot(seconds):
    return {'mode': 'overall', 'total_seconds': seconds, 'captured_at': 'test-time'}


class VerifiedRunTests(unittest.TestCase):
    def test_no_increment_blocks_formal_run(self):
        with patch.dict(os.environ, {'WEREAD_API_KEY': 'test', 'READ_NUM': '360'}), patch.object(stats, 'capture', return_value=snapshot(100)), patch.object(verify, 'stage', return_value=0) as stage, patch.object(verify, 'report'), patch.object(verify.time, 'sleep'):
            self.assertEqual(verify.main(), 1)
        stage.assert_called_once_with('preflight', 10)

    def test_verified_increment_starts_formal_and_reports_actual_delta(self):
        with patch.dict(os.environ, {'WEREAD_API_KEY': 'test', 'READ_NUM': '360'}), patch.object(stats, 'capture', side_effect=[snapshot(100), snapshot(100), snapshot(400), snapshot(400), snapshot(11200)]), patch.object(verify, 'stage', return_value=0) as stage, patch.object(verify, 'report') as report, patch.object(verify.time, 'sleep'):
            self.assertEqual(verify.main(), 0)
        self.assertEqual([call.args for call in stage.call_args_list], [('preflight', 10), ('formal', 360)])
        self.assertIn('实际增加：3小时0分钟0秒', report.call_args.args[0])

    def test_stats_failure_blocks_reading(self):
        with patch.dict(os.environ, {'WEREAD_API_KEY': 'test'}), patch.object(stats, 'capture', side_effect=stats.StatisticsUnavailable('test')), patch.object(verify, 'stage') as stage, patch.object(verify, 'report'):
            self.assertEqual(verify.main(), 1)
        stage.assert_not_called()

    def test_reader_failure_blocks_formal_even_with_increment(self):
        with patch.dict(os.environ, {'WEREAD_API_KEY': 'test', 'READ_NUM': '360'}), patch.object(stats, 'capture', side_effect=[snapshot(100), snapshot(100), snapshot(400)]), patch.object(verify, 'stage', return_value=77) as stage, patch.object(verify, 'report'), patch.object(verify.time, 'sleep'):
            self.assertEqual(verify.main(), 77)
        stage.assert_called_once_with('preflight', 10)
