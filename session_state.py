"""Persist renewed cookies privately, tied to the source login credentials."""
import hashlib
import json
import os
from pathlib import Path
import tempfile


def fingerprint():
    return hashlib.sha256(os.getenv('WXREAD_CURL_BASH', '').encode()).hexdigest()


def restore(cookies):
    path = os.getenv('WXREAD_SESSION_PATH')
    if not path or not Path(path).exists():
        return False
    value = json.loads(Path(path).read_text(encoding='utf-8'))
    # New QR login credentials invalidate any previous cached session.
    if value.get('source') != fingerprint():
        return False
    saved = value.get('cookies')
    if not isinstance(saved, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in saved.items()):
        raise ValueError('Invalid saved session')
    if cookies.get('wr_vid') and saved.get('wr_vid') != cookies['wr_vid']:
        raise ValueError('Saved session belongs to a different account')
    cookies.update(saved)
    return True


def save(cookies):
    path = os.getenv('WXREAD_SESSION_PATH')
    if not path:
        return
    destination = Path(path)
    descriptor, temporary = tempfile.mkstemp(prefix='.session-', dir=destination.parent)
    try:
        os.chmod(temporary, 0o600)
        with os.fdopen(descriptor, 'w', encoding='utf-8') as stream:
            json.dump({'source': fingerprint(), 'cookies': cookies}, stream, ensure_ascii=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, destination)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
