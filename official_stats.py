"""Read official account statistics; never log API keys or raw account data."""
import datetime
import os
import time
import requests

URL = 'https://i.weread.qq.com/api/agent/gateway'
VERSION = '1.0.4'
TZ = datetime.timezone(datetime.timedelta(hours=8))


class StatisticsUnavailable(RuntimeError):
    pass


def capture():
    key = os.getenv('WEREAD_API_KEY', '').strip()
    if not key:
        raise StatisticsUnavailable('未配置微信读书官方 API Key。')
    for attempt in range(3):
        try:
            response = requests.post(
                URL, headers={'Authorization': f'Bearer {key}'},
                json={'api_name': '/readdata/detail', 'skill_version': VERSION, 'mode': 'overall'},
                timeout=(10, 20),
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError):
            if attempt < 2:
                time.sleep(2)
                continue
            raise StatisticsUnavailable('官方统计网络请求失败，未能核对实际时长。') from None
        if not isinstance(payload, dict):
            raise StatisticsUnavailable('官方统计返回格式不符合预期。')
        if 'upgrade_info' in payload:
            raise StatisticsUnavailable('官方接口要求更新版本，停止统计核对。')
        if payload.get('errcode'):
            raise StatisticsUnavailable('官方统计接口拒绝请求，请检查 API Key。')
        seconds = payload.get('totalReadTime')
        if type(seconds) is not int or seconds < 0:
            raise StatisticsUnavailable('官方接口未返回有效累计秒数，不能视为零时长。')
        return {'captured_at': datetime.datetime.now(TZ).isoformat(),
                'mode': 'overall', 'total_seconds': seconds,
                'scope': 'account_reading_and_listening'}


def delta(before, after):
    if before.get('mode') != 'overall' or after.get('mode') != 'overall':
        raise StatisticsUnavailable('统计口径不同，不能相减。')
    difference = after['total_seconds'] - before['total_seconds']
    if difference < 0:
        raise StatisticsUnavailable('累计统计出现倒退，不能确认本次增量。')
    return difference


def duration(seconds):
    seconds = int(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f'{hours}小时{minutes}分钟{seconds}秒'
