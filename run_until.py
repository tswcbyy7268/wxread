"""Run the reader normally, or enforce an absolute cutoff for a one-off run."""
import os
import subprocess
import sys
import time

deadline_text = os.getenv("READ_UNTIL", "").strip()
if not deadline_text:
    raise SystemExit(subprocess.run([sys.executable, "-u", "main.py"]).returncode)

deadline = float(deadline_text)
remaining = deadline - time.time()
if remaining <= 0:
    print("截止时间已过，未启动阅读。", flush=True)
    raise SystemExit(0)
if remaining > 6 * 3600:
    raise ValueError("单次截止时间不能超过六小时。")
print("已启用截止时间，届时自动停止阅读。", flush=True)
try:
    result = subprocess.run([sys.executable, "-u", "main.py"], timeout=remaining)
    raise SystemExit(result.returncode)
except subprocess.TimeoutExpired:
    print("已到北京时间截止时间，阅读进程已停止。", flush=True)
    from config import PUSH_METHOD
    from push import push
    push("《三体》今晚阅读已按截止时间停止。实际计入时长请在微信读书 App 核对。",
         PUSH_METHOD, is_success=True)
