"""Confirmed progress shared by reader processes in one workflow job."""
import json
import os
from pathlib import Path

TRANSIENT_EXIT = 75
AUTH_EXIT = 77


def completed():
    path = os.getenv('WXREAD_PROGRESS_PATH')
    if not path or not Path(path).exists():
        return 0
    count = json.loads(Path(path).read_text(encoding='utf-8'))['completed_requests']
    if type(count) is not int or count < 0:
        raise ValueError('Invalid saved progress')
    return count


def record(count):
    path = os.getenv('WXREAD_PROGRESS_PATH')
    if not path:
        return
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps({'completed_requests': count}), encoding='utf-8')
    os.replace(temporary, target)
