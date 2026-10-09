"""Verify real statistics before reading and report their measured difference."""
import os
from pathlib import Path
import subprocess
import sys
import time
import official_stats as stats
import run_until


def report(message, success):
    print(message, flush=True)
    return run_until.notify(message, success)


def stage(name, target):
    env = os.environ.copy()
    env['READ_NUM'] = str(target)
    env['WXREAD_REPORT_BY_PARENT'] = '1'
    env['WXREAD_PROGRESS_PATH'] = str(Path('logs') / (
        f"{os.getenv('GITHUB_RUN_ID', os.getpid())}-{os.getenv('GITHUB_RUN_ATTEMPT', '1')}-{name}.json"))
    # Reader subprocess owns the checkpoint and bounded recovery logic.
    return subprocess.run([sys.executable, '-u', 'run_until.py'], env=env, timeout=6 * 3600).returncode


def measure(before, expected):
    after = stats.capture()
    # Permit delayed statistic synchronization without counting it as reading.
    for _ in range(6):
        if stats.delta(before, after) >= expected:
            break
        time.sleep(30)
        after = stats.capture()
    return after, stats.delta(before, after)


def main():
    target = int(os.getenv('READ_NUM') or 360)
    if not 0 < target <= 600:
        raise ValueError('Verified reading requires 1..600 requests')
    if not os.getenv('WEREAD_API_KEY', '').strip():
        report('未配置官方统计密钥，未启动阅读；请配置 WEREAD_API_KEY。', False)
        return 1
    try:
        # Pause after the preceding task to reduce carry-over synchronization.
        before = stats.capture()
        for _ in range(6):
            time.sleep(30)
            latest = stats.capture()
            if stats.delta(before, latest) == 0:
                before = latest
                break
            before = latest
        else:
            raise stats.StatisticsUnavailable('统计持续变化，无法建立稳定基线；请暂停其他设备的阅读和听书。')
        report(f"测试前官方累计时长：{stats.duration(before['total_seconds'])}\n"
               f"查询时间：{before['captured_at']}\n开始约5分钟验证。", True)
        code = stage('preflight', 10)
        after, added = measure(before, 300)
        report(f"短时测试结果：官方累计从{stats.duration(before['total_seconds'])}"
               f"变为{stats.duration(after['total_seconds'])}；实际增加{stats.duration(added)}。\n"
               '统计口径包含阅读与听书。', code == 0 and added > 0)
        if code != 0 or added <= 0:
            report('短时验证未通过，未启动正式任务。阅读接口成功不等于实际计入时长。', False)
            return code or 1
        # A separate baseline excludes the preflight from the formal run.
        baseline = stats.capture()
        report(f"开始《三体》正式任务，目标约{target * 0.5:g}分钟。\n"
               f"正式任务前官方累计：{stats.duration(baseline['total_seconds'])}", True)
        code = stage('formal', target)
        final, added = measure(baseline, target * 30)
        report(f"《三体》正式任务{'已完成' if code == 0 else '异常结束'}\n"
               f"任务前累计：{stats.duration(baseline['total_seconds'])}\n"
               f"任务后累计：{stats.duration(final['total_seconds'])}\n"
               f"官方统计实际增加：{stats.duration(added)}\n"
               f"结束查询时间：{final['captured_at']}\n"
               '上述增量包含本账户同期阅读与听书，不代表挑战赛计入时长。', code == 0 and added > 0)
        return code if code else (0 if added > 0 else 1)
    except stats.StatisticsUnavailable as error:
        report(f'官方时长核对失败：{error}\n未确认的增量不会当作阅读成功；请检查运行日志。', False)
        return 1
    except (subprocess.TimeoutExpired, OSError, ValueError):
        report('验证任务异常，已停止；未能确认最终官方时长，请查看运行日志。', False)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
