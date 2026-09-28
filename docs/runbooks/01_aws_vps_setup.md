# Runbook 01 — AWS EC2 VPS setup (Phase 1, Doc 3 v1.2)

Time: ~60–90 minutes. Result: MT5 running under Wine, engine under systemd, `/health` reachable by UptimeRobot.

## 1. AWS account safety first (5 min)
1. Sign in at https://console.aws.amazon.com. **Enable MFA on the root user** (IAM → Security credentials).
2. **Billing → Budgets → Create budget → "Zero spend budget"**, emailing you. This warns you before credits or charges are used.
3. Note your **account creation date**. On the new free plan, credits expire after **6 months**. Add a calendar reminder for **month 5** (Doc 6 risk register).

## 2. Launch the instance (10 min)
EC2 → pick region **US East (N. Virginia) us-east-1** (closest to the broker's NY4 servers, Doc 3 §5) → **Launch instance**:
| Field | Value |
|---|---|
| Name | `alse-vps` |
| AMI | **Ubuntu Server 24.04 LTS (x86_64)** ⚠️ not Arm |
| Instance type | **t3.small** if labelled "Free tier eligible", else **t3.micro** |
| Key pair | Create new → `alse-key` → type ED25519 → `.pem` → save it somewhere safe **outside the repo** |
| Network → Security group | Create `alse-sg`: **SSH 22 from "My IP" only**. Add **Custom TCP 8080 from 0.0.0.0/0** (health endpoint, returns only ok/stale) |
| Storage | 20 GiB gp3 (free plan allows up to 30) |

Launch, then **Elastic IPs → Allocate → Associate** with `alse-vps`, so the IP never changes (it's free while attached to a running instance).

## 3. Connect (Git Bash on your PC)
```bash
chmod 400 ~/Downloads/alse-key.pem
ssh -i ~/Downloads/alse-key.pem ubuntu@<ELASTIC_IP>
```
Your home IP changes (common with Safaricom and other ISPs)? Update the SSH rule in `alse-sg` to "My IP" again.

## 4. Bootstrap (15–25 min, unattended)
```bash
curl -fsSL https://raw.githubusercontent.com/MARKDISPLAYNONE/ALSE/arena/01a0e7cc-alse/ops/setup/bootstrap_ubuntu.sh | bash
```

## 5. Harden SSH (Doc 4 §1.3)
```bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config
sudo systemctl restart ssh
```

## 6. Install the FX Pesa MT5 terminal under Wine
1. Get the Windows MT5 installer link from FX Pesa (client portal → Platforms → MT5 for Windows). The file is usually `fxpesa5setup.exe`.
2. On the VPS:
```bash
sudo -u alse bash
export WINEPREFIX=/home/alse/.wine DISPLAY=:99
cd /tmp && wget -O mt5setup.exe "<FXPESA_MT5_INSTALLER_URL>"
wine mt5setup.exe /auto
ls "/home/alse/.wine/drive_c/Program Files/"      # note the exact terminal folder name
exit
```
3. If the folder isn't `FXPesa MT5 Terminal`, edit the path in `/opt/alse/ops/systemd/alse-mt5.service` to match.
4. The first login is done by the engine: `mt5.initialize(login, password, server)` uses the credentials in `.env`. `MT5_SERVER` must match the broker's server name exactly (e.g. `EGMSecurities-Demo`); FX Pesa's demo account email shows it.

## 7. Secrets
From your PC:
```bash
scp -i ~/Downloads/alse-key.pem .env ubuntu@<ELASTIC_IP>:/tmp/.env
```
On the VPS:
```bash
sudo mv /tmp/.env /opt/alse/.env && sudo chown alse:alse /opt/alse/.env && sudo chmod 600 /opt/alse/.env
```
Make sure `.env` has `MT5_MODE=bridge`, the `MT5_LOGIN/PASSWORD/SERVER` for the **demo** account, and `ALSE_ENV=demo`.

## 8. Start services + smoke test
```bash
sudo cp /opt/alse/ops/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now alse-mt5 && sleep 30
sudo systemctl enable --now alse-engine
cd /opt/alse && sudo -u alse .venv/bin/python -m scripts.phase1_smoke_test
curl -s localhost:8080/health
```
Logs: `journalctl -u alse-mt5 -f` / `journalctl -u alse-engine -f`

## 9. External uptime monitor (hard Phase 1 exit criterion, Doc 3 §6)
UptimeRobot (free) → **New monitor** → HTTP(s) → URL `http://<ELASTIC_IP>:8080/health` → interval 5 min → alert contacts: your **email** + a webhook to the **alse-critical** Discord channel. Test it by running `sudo systemctl stop alse-engine`. You should get an alert within about 5–10 minutes. Then start the engine again.

## 10. Phase 1 sign-off checklist
- [ ] Smoke test all PASS on the VPS, including the MT5 read
- [ ] `/health` UP in UptimeRobot, and the stop test fired an alert
- [ ] Heartbeat rows appearing in `heartbeats` (09:00 NY daily; every 5 min from 20:00 NY)
- [ ] Broker contract spec PDF/screenshot saved to `docs/evidence/` (Doc 6 item 1)
