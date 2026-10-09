#!/usr/bin/env bash
set -euo pipefail
umask 077
cd "$(dirname "$0")"
if [ "$(id -u)" != 0 ]; then
  echo 'Run as root.' >&2
  exit 1
fi
if systemctl is-active --quiet wxread.service || systemctl is-active --quiet wxread-test.service; then
  echo 'Existing reading service is active; stop it before installation.' >&2
  exit 1
fi
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq python3-venv ca-certificates
if ! id wxread >/dev/null 2>&1; then
  useradd --system --home /var/lib/wxread --shell /usr/sbin/nologin wxread
fi
install -d -o root -g wxread -m 0750 /opt/wxread /etc/wxread
install -d -o wxread -g wxread -m 0700 /var/lib/wxread /var/lib/wxread/logs
for source in main.py push.py config.py log_utils.py recovery.py run_until.py official_stats.py server_run.py source-revision.txt; do
  install -o root -g wxread -m 0640 "$source" "/opt/wxread/$source"
done
install -o root -g wxread -m 0640 credentials.json /etc/wxread/credentials.json
python3 -m venv /opt/wxread/venv
/opt/wxread/venv/bin/python -m pip install -q 'requests==2.32.3'
chmod -R o-rwx /opt/wxread
chgrp -R wxread /opt/wxread
chmod -R g+rX /opt/wxread
if [ ! -e /opt/wxread/logs ]; then
  ln -s /var/lib/wxread/logs /opt/wxread/logs
fi
/opt/wxread/venv/bin/python -m unittest discover -s tests -v
cat > /etc/systemd/system/wxread.service <<'EOF'
[Unit]
Description=WeRead daily reading and official statistics report
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=wxread
Group=wxread
WorkingDirectory=/opt/wxread
Environment=PYTHONUNBUFFERED=1
Environment=TZ=Asia/Shanghai
ExecStart=/opt/wxread/venv/bin/python /opt/wxread/server_run.py --daily --requests 360
TimeoutStartSec=4h30min
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/wxread
UMask=0077
EOF
cat > /etc/systemd/system/wxread-test.service <<'EOF'
[Unit]
Description=WeRead five minute server verification
Wants=network-online.target
After=network-online.target

[Service]
Type=oneshot
User=wxread
Group=wxread
WorkingDirectory=/opt/wxread
Environment=PYTHONUNBUFFERED=1
Environment=TZ=Asia/Shanghai
ExecStart=/opt/wxread/venv/bin/python /opt/wxread/server_run.py --requests 10
TimeoutStartSec=30min
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/lib/wxread
UMask=0077
EOF
cat > /etc/systemd/system/wxread.timer <<'EOF'
[Unit]
Description=WeRead daily at 03:23 Beijing time

[Timer]
OnCalendar=*-*-* 03:23:00 Asia/Shanghai
AccuracySec=1s
RandomizedDelaySec=0
Persistent=true
Unit=wxread.service

[Install]
WantedBy=timers.target
EOF
systemctl daemon-reload
systemd-analyze verify /etc/systemd/system/wxread.service /etc/systemd/system/wxread-test.service /etc/systemd/system/wxread.timer
systemd-analyze calendar '*-*-* 03:23:00 Asia/Shanghai'
echo 'Installed. Timer remains disabled until real verification succeeds.'
