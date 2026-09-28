#!/usr/bin/env bash
# ALSE VPS bootstrap — Ubuntu 24.04 x86_64 (GCP e2-micro, Doc 3 v1.3). Run as the default 'ubuntu' user:
#   curl -fsSL https://raw.githubusercontent.com/MARKDISPLAYNONE/ALSE/arena/01a0e7cc-alse/ops/setup/bootstrap_ubuntu.sh | bash
# Idempotent: safe to re-run.
set -euo pipefail
[[ "$(uname -m)" == "x86_64" ]] || { echo "x86_64 required (MT5 is x86 Windows) — see Doc 3 v1.2"; exit 1; }

echo "== 1/6 memory: 3 GB swap + zram (e2-micro has 1 GB RAM) =="
if ! swapon --show | grep -q /swapfile; then
  sudo fallocate -l 3G /swapfile && sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
fi
echo 'vm.swappiness=60' | sudo tee /etc/sysctl.d/99-alse.conf >/dev/null && sudo sysctl -q --system

echo "== 2/6 base packages + timezone UTC =="
sudo timedatectl set-timezone UTC
sudo dpkg --add-architecture i386
sudo apt-get update -y
sudo apt-get install -y software-properties-common curl wget git xvfb cabextract unzip \
  python3 python3-venv python3-pip fail2ban unattended-upgrades vnstat zram-tools
sudo systemctl enable --now vnstat
printf 'ALGO=zstd\nPERCENT=50\n' | sudo tee /etc/default/zramswap >/dev/null && sudo systemctl restart zramswap || true

echo "== 3/6 WineHQ stable =="
if ! command -v wine >/dev/null; then
  sudo mkdir -pm755 /etc/apt/keyrings
  sudo wget -qO /etc/apt/keyrings/winehq-archive.key https://dl.winehq.org/wine-builds/winehq.key
  . /etc/os-release
  sudo wget -qNP /etc/apt/sources.list.d/ "https://dl.winehq.org/wine-builds/ubuntu/dists/${VERSION_CODENAME}/winehq-${VERSION_CODENAME}.sources"
  sudo apt-get update -y && sudo apt-get install -y --install-recommends winehq-stable
fi

echo "== 4/6 service user 'alse' + repo =="
id alse >/dev/null 2>&1 || sudo useradd -m -s /bin/bash alse
sudo mkdir -p /opt/alse && sudo chown alse:alse /opt/alse
if [[ ! -d /opt/alse/.git ]]; then
  sudo -u alse git clone -b arena/01a0e7cc-alse https://github.com/MARKDISPLAYNONE/ALSE.git /opt/alse
fi
sudo -u alse bash -c 'cd /opt/alse && python3 -m venv .venv && .venv/bin/pip install -q -e ".[mt5-bridge]"'

echo "== 5/6 Wine prefix + Windows Python 3.11 + MetaTrader5/mt5linux (as alse) =="
sudo -u alse bash <<'INNER'
set -euo pipefail
export WINEPREFIX=/home/alse/.wine WINEARCH=win64 WINEDEBUG=-all DISPLAY=:99
pgrep -f "Xvfb :99" >/dev/null || (Xvfb :99 -screen 0 1024x768x16 >/dev/null 2>&1 &) ; sleep 2
[[ -d "$WINEPREFIX" ]] || wineboot --init
PY="$WINEPREFIX/drive_c/Python311/python.exe"
if [[ ! -f "$PY" ]]; then
  cd /tmp && wget -q https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe
  wine python-3.11.9-amd64.exe /quiet InstallAllUsers=1 TargetDir='C:\Python311' PrependPath=1 Include_test=0
fi
wine "C:\\Python311\\python.exe" -m pip install -q --upgrade pip
wine "C:\\Python311\\python.exe" -m pip install -q MetaTrader5 mt5linux
INNER

echo "== 6/6 done =="
cat <<'MSG'
NEXT (manual, see docs/runbooks/01_gcp_vps_setup.md):
  a) Install the FX Pesa MT5 terminal under Wine (step 6 of runbook) and log in to the DEMO account once.
  b) sudo -u alse cp /path/to/.env /opt/alse/.env && sudo chmod 600 /opt/alse/.env
  c) sudo cp /opt/alse/ops/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload
     sudo systemctl enable --now alse-mt5 && sleep 20 && sudo systemctl enable --now alse-engine
  d) cd /opt/alse && sudo -u alse .venv/bin/python -m scripts.phase1_smoke_test
MSG
