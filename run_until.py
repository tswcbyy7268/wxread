"""Restart transient reader failures with confirmed progress and a hard deadline."""
import os
from pathlib import Path
import subprocess
import sys
import time
import recovery

RESTART_DELAYS = (30, 60, 120)


def notify(message, success):
    from config import PUSH_METHOD
    from push import push
    return push(message, PUSH_METHOD, is_success=success)


def supervise(target, deadline=0):
    # Leave time for a final report before GitHub's six-hour job limit.
    hard_stop = min(deadline or float('inf'), time.time() + 5 * 3600 + 50 * 60)
    restarted = 0
    code = 1
    reason = '阅读未完成'
    while True:
        if time.time() >= hard_stop:
            code = 0 if deadline else 1
            reason = '已到截止时间，按计划停止' if deadline else '达到运行安全时限，已停止'
            break
        try:
            result = subprocess.run(
                [sys.executable, '-u', 'main.py'], timeout=hard_stop - time.time(),
            )
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 0 if deadline else 1
            reason = '已到截止时间，阅读进程已停止' if deadline else '达到运行安全时限，已停止'
            break
        count = recovery.completed()
        if code == 0:
            if count >= target:
                reason = '目标请求已完成'
            elif deadline and time.time() >= deadline:
                reason = '已到截止时间，按计划停止'
            else:
                code = 1
                reason = '阅读进程退出，但未确认完成目标'
            break
        if code == recovery.AUTH_EXIT:
            reason = '登录状态失效，自动恢复已停止；请重新扫码更新登录请求'
            break
        if code != recovery.TRANSIENT_EXIT or restarted >= len(RESTART_DELAYS):
            reason = ('网络异常连续恢复失败，已停止' if code == recovery.TRANSIENT_EXIT
                      else '阅读发生不可恢复错误，请查看运行日志')
            break
        delay = min(RESTART_DELAYS[restarted], max(0, hard_stop - time.time()))
        restarted += 1
        print(f'网络异常，{delay:g}秒后第{restarted}次自动重启；保留{count}次已确认请求。', flush=True)
        time.sleep(delay)
    count = recovery.completed()
    print(f'运行结果：{reason}；已确认{count}次请求；自动重启{restarted}次。', flush=True)
    notify(f'《三体》运行结果：{reason}\n已确认请求：{count}/{target}\n'
           f'估算提交时长：{count * 0.5:g} 分钟\n自动重启：{restarted} 次\n'
           '实际计入阅读和挑战赛的时长，请以微信读书 App 为准。', code == 0)
    return code


def main():
    target = int(os.getenv('READ_NUM') or 40)
    deadline = float(os.getenv('READ_UNTIL') or 0)
    if target <= 0:
        raise ValueError('READ_NUM must be positive')
    if deadline and deadline <= time.time():
        print('截止时间已过，未启动阅读。', flush=True)
        return 0
    if deadline and deadline - time.time() > 6 * 3600:
        raise ValueError('单次截止时间不能超过六小时。')
    os.environ['WXREAD_SUPERVISED'] = '1'
    run_id = os.getenv('GITHUB_RUN_ID', str(os.getpid()))
    attempt = os.getenv('GITHUB_RUN_ATTEMPT', '1')
    os.environ.setdefault('WXREAD_PROGRESS_PATH', str(Path('logs') / f'{run_id}-{attempt}-progress.json'))
    try:
        recovery.completed()
        return supervise(target, deadline)
    except (ValueError, OSError):
        print('进度状态或运行环境异常，已停止，避免重复阅读。', flush=True)
        notify('《三体》运行失败：进度状态或运行环境异常，请查看运行日志。', False)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
