"""Server reader with private credentials, persistent progress and actual statistics."""
import argparse
import datetime
import fcntl
import json
import os
from pathlib import Path
import sys
import time

STATE = Path('/var/lib/wxread')


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument('--requests', type=int, default=360)
    parser.add_argument('--daily', action='store_true')
    args = parser.parse_args()
    if not 0 < args.requests <= 600:
        raise ValueError('requests must be in 1..600')
    credentials = json.loads(Path('/etc/wxread/credentials.json').read_text(encoding='utf-8'))
    for name in ['WXREAD_CURL_BASH', 'PUSH_METHOD', 'PUSHPLUS_TOKEN', 'WEREAD_API_KEY']:
        if not isinstance(credentials.get(name), str) or not credentials[name].strip():
            raise ValueError('Missing credential: ' + name)
        os.environ[name] = credentials[name]
    os.environ['READ_NUM'] = str(args.requests)
    os.environ['READ_UNTIL'] = ''
    os.environ['WXREAD_SUPERVISED'] = '1'
    import official_stats as stats
    import recovery
    import run_until
    tz = datetime.timezone(datetime.timedelta(hours=8))
    now = datetime.datetime.now(tz)
    run_id = now.strftime('%Y-%m-%d') if args.daily else now.strftime('test-%Y%m%d-%H%M%S')
    os.environ['WXREAD_PROGRESS_PATH'] = str(STATE / (run_id + '-progress.json'))
    snapshot_path = STATE / (run_id + '-statistics.json')
    os.environ['GITHUB_RUN_ID'] = run_id
    lock = (STATE / 'reader.lock').open('a')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print('已有服务器阅读任务运行，本次跳过。', flush=True)
        return 1
    def report(message, success):
        print(message, flush=True)
        accepted = run_until.notify(message, success)
        print('PushPlus 已接受消息。' if accepted else 'PushPlus 未接受消息。', flush=True)
        return accepted
    try:
        if recovery.completed() >= args.requests:
            print('今天的目标请求已经完成，本次跳过，避免重复阅读。', flush=True)
            return 0
        if snapshot_path.exists():
            baseline = json.loads(snapshot_path.read_text(encoding='utf-8'))['before']
        else:
            baseline = stats.capture()
            snapshot_path.write_text(json.dumps({'before': baseline}, ensure_ascii=False), encoding='utf-8')
        report(f"服务器《三体》任务开始，目标约{args.requests * 0.5:g}分钟。\n"
               f"任务前官方累计：{stats.duration(baseline['total_seconds'])}\n"
               f"查询时间：{baseline['captured_at']}", True)
        os.environ['WXREAD_REPORT_BY_PARENT'] = '1'
        try:
            code = run_until.main()
        finally:
            os.environ.pop('WXREAD_REPORT_BY_PARENT', None)
        count = recovery.completed()
        after = stats.capture()
        for _ in range(6):
            if stats.delta(baseline, after) >= count * 30:
                break
            time.sleep(30)
            after = stats.capture()
        added = stats.delta(baseline, after)
        snapshot_path.write_text(json.dumps({'before': baseline, 'after': after,
                                            'actual_added_seconds': added,
                                            'confirmed_requests': count,
                                            'reader_exit_code': code}, ensure_ascii=False), encoding='utf-8')
        report(f"服务器《三体》任务{'完成' if code == 0 else '异常结束'}\n"
               f"已确认请求：{count}/{args.requests}\n"
               f"任务前官方累计：{stats.duration(baseline['total_seconds'])}\n"
               f"任务后官方累计：{stats.duration(after['total_seconds'])}\n"
               f"官方实际增加：{stats.duration(added)}\n"
               f"结束查询：{after['captured_at']}\n"
               '统计包含本账户同期阅读与听书，不代表挑战赛计入时长。', code == 0 and added > 0)
        return code or (0 if added > 0 else 1)
    except stats.StatisticsUnavailable as error:
        report(f'服务器官方时长核对失败：{error}\n未确认实际增量，请检查任务。', False)
        return 1
    finally:
        fcntl.flock(lock, fcntl.LOCK_UN)
        lock.close()


if __name__ == '__main__':
    raise SystemExit(run())
