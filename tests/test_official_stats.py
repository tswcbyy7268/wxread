import unittest
from unittest.mock import Mock, patch
import official_stats


class OfficialStatisticsTests(unittest.TestCase):
    def response(self, payload):
        result = Mock()
        result.json.return_value = payload
        return result

    def test_seconds_and_request_contract(self):
        with patch.dict('os.environ', {'WEREAD_API_KEY': 'test-only'}), patch('requests.post', return_value=self.response({'totalReadTime': 3661})) as post:
            result = official_stats.capture()
        self.assertEqual(result['total_seconds'], 3661)
        self.assertEqual(official_stats.duration(3661), '1小时1分钟1秒')
        self.assertEqual(post.call_args.kwargs['json']['mode'], 'overall')

    def test_missing_field_is_not_zero(self):
        with patch.dict('os.environ', {'WEREAD_API_KEY': 'test-only'}), patch('requests.post', return_value=self.response({})):
            with self.assertRaises(official_stats.StatisticsUnavailable):
                official_stats.capture()

    def test_upgrade_stops_verification(self):
        with patch.dict('os.environ', {'WEREAD_API_KEY': 'test-only'}), patch('requests.post', return_value=self.response({'totalReadTime': 100, 'upgrade_info': {'message': 'upgrade'}})):
            with self.assertRaises(official_stats.StatisticsUnavailable):
                official_stats.capture()

    def test_overall_delta_across_midnight(self):
        self.assertEqual(official_stats.delta({'mode': 'overall', 'total_seconds': 1000}, {'mode': 'overall', 'total_seconds': 1300}), 300)

    def test_negative_delta_not_reported_as_success(self):
        with self.assertRaises(official_stats.StatisticsUnavailable):
            official_stats.delta({'mode': 'overall', 'total_seconds': 1300}, {'mode': 'overall', 'total_seconds': 1000})
