"""Root-only import of a QR-verified login through SSH stdin; no secret output."""
import datetime
import grp
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

sys.path.insert(0, '/opt/wxread')
from config import convert


def main():
    if os.geteuid() != 0:
        raise RuntimeError('Root required')
    for service in ['wxread.service', 'wxread-now.service', 'wxread-test.service']:
        status = subprocess.run(['systemctl', 'show', service, '-p', 'ActiveState', '--value'], capture_output=True, text=True)
        if status.stdout.strip() in ['active', 'activating', 'deactivating']:
            raise RuntimeError('Reading already active; import deferred')
    credentials_path = Path('/etc/wxread/credentials.json')
    credentials = json.loads(credentials_path.read_text(encoding='utf-8'))
    incoming = json.load(sys.stdin)
    curl = incoming['curl']
    if not isinstance(curl, str) or len(curl) > 100000:
        raise RuntimeError('Invalid login request')
    _, previous = convert(credentials['WXREAD_CURL_BASH'])
    _, updated = convert(curl)
    if not updated.get('wr_skey') or not updated.get('wr_vid'):
        raise RuntimeError('Required login cookies missing')
    if previous.get('wr_vid') and previous['wr_vid'] != updated['wr_vid']:
        raise RuntimeError('Account mismatch')
    credentials['WXREAD_CURL_BASH'] = curl
    descriptor, temporary = tempfile.mkstemp(prefix='.credentials-', dir=credentials_path.parent)
    try:
        os.fchmod(descriptor, 0o640)
        os.fchown(descriptor, 0, grp.getgrnam('wxread').gr_gid)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump(credentials, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, credentials_path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
    # A failed zero-request attempt must not reuse a baseline from hours earlier.
    today = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).strftime('%Y-%m-%d')
    state = Path('/var/lib/wxread')
    progress = state / (today + '-progress.json')
    count = json.loads(progress.read_text())['completed_requests'] if progress.exists() else 0
    if count == 0:
        (state / (today + '-statistics.json')).unlink(missing_ok=True)
    print('LOGIN_IMPORTED: 原账户新登录已安全保存。')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        print('LOGIN_IMPORT_FAILED: 登录导入未完成，请检查账户、任务状态和输入格式。')
        raise SystemExit(1)
