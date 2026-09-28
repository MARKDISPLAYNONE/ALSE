# Runbook 01 — Google Cloud e2-micro VPS (Phase 1, Doc 3 v1.3) — $0 permanently

Time: ~60–90 min. Result: MT5 under Wine, engine under systemd, `/health` monitored by UptimeRobot.
**Stay free:** e2-micro only · region **us-east1** · **Standard** persistent disk ≤ 30 GB · **Standard** network tier.

## 1. Account safety (10 min)
1. https://console.cloud.google.com → create project **`alse`**. A billing account with a card is required, but Always Free usage costs $0.
2. **Billing → Budgets & alerts → Create budget** of **$1** with alerts at 50/90/100%, emailed to you.
3. Turn on 2-Step Verification on the Google account.

## 2. Create the VM (10 min)
Compute Engine → VM instances → **Create instance**:
| Field | Value |
|---|---|
| Name | `alse-vps` |
| Region / Zone | **us-east1** / us-east1-b |
| Machine | **E2 → e2-micro** (the price panel should show the free-tier note) |
| Boot disk → Change | **Ubuntu 24.04 LTS (x86/64, amd64)**, type **Standard persistent disk**, **30 GB** |
| Networking → External IPv4 | **Reserve static address** `alse-ip` (free while attached to a running VM) |
| Networking → Network Service Tier | **Standard** |
| Security → Manage access → Add SSH key | contents of your public key (step 3) |

## 3. SSH key (Git Bash on your PC)
```bash
ssh-keygen -t ed25519 -f ~/.ssh/alse -C alse      # paste ~/.ssh/alse.pub into step 2
ssh -i ~/.ssh/alse <your-username>@<STATIC_IP>
```

## 4. Firewall (VPC network → Firewall), Doc 4 §1.3
- Create `alse-ssh`: ingress, TCP 22, source = **your IP/32 only**. Then **delete or disable** `default-allow-ssh` (0.0.0.0/0), `default-allow-rdp` and `default-allow-icmp`.
- Create `alse-health`: ingress, TCP 8080, source 0.0.0.0/0 (returns only ok/stale — needed by UptimeRobot).
Your home IP changed? Update `alse-ssh`, or use the console's browser SSH button.

## 5. Bootstrap (20–30 min, unattended — slow on e2-micro, that's normal)
```bash
curl -fsSL https://raw.githubusercontent.com/MARKDISPLAYNONE/ALSE/arena/01a0e7cc-alse/ops/setup/bootstrap_ubuntu.sh | bash
sudo sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' /etc/ssh/sshd_config && sudo systemctl restart ssh
```

## 6. FX Pesa MT5 terminal under Wine
```bash
sudo -u alse bash
export WINEPREFIX=/home/alse/.wine DISPLAY=:99 WINEDEBUG=-all
cd /tmp && wget -O mt5setup.exe "<FXPESA_MT5_WINDOWS_INSTALLER_URL>"   # FX Pesa portal → Platforms → MT5 Windows
wine mt5setup.exe /auto
ls "/home/alse/.wine/drive_c/Program Files/"        # note the terminal folder name
exit
```
If the folder isn't `FXPesa MT5 Terminal`, fix the path in `/opt/alse/ops/systemd/alse-mt5.service`.
**RAM tuning (important on 1 GB):** Max bars in chart = 5000, News disabled, only `UT100xx` in Market Watch, no charts open.

## 7. Secrets
From your PC:
```bash
scp -i ~/.ssh/alse .env <user>@<STATIC_IP>:/tmp/.env
```
On the VM:
```bash
sudo mv /tmp/.env /opt/alse/.env && sudo chown alse:alse /opt/alse/.env && sudo chmod 600 /opt/alse/.env
```
`.env` needs `SUPABASE_URL` (not NEXT_PUBLIC_), `MT5_MODE=bridge`, the demo `MT5_LOGIN/PASSWORD/SERVER` (exact server name from FX Pesa's demo email), and `ALSE_ENV=demo`.

## 8. Start + smoke test
```bash
sudo cp /opt/alse/ops/systemd/*.service /etc/systemd/system/ && sudo systemctl daemon-reload
sudo systemctl enable --now alse-mt5 && sleep 45
sudo systemctl enable --now alse-engine
cd /opt/alse && sudo -u alse .venv/bin/python -m scripts.phase1_smoke_test
curl -s localhost:8080/health ; free -m ; vnstat -m
```
Logs: `journalctl -u alse-mt5 -f` · `journalctl -u alse-engine -f`

## 9. External uptime monitor (hard Phase 1 exit criterion)
UptimeRobot (free) → HTTP monitor `http://<STATIC_IP>:8080/health`, 5-minute interval, alerts by email + the **alse-critical** Discord webhook. Test: `sudo systemctl stop alse-engine`; you should get an alert within ~10 minutes. Then start it again.

## 10. Phase 1 sign-off
- [ ] Smoke test all PASS on the VM, including the MT5 read
- [ ] UptimeRobot UP, and the stop test fired an alert
- [ ] `free -m` shows headroom with everything running
- [ ] Heartbeat rows arriving in `heartbeats`
- [ ] Broker contract-spec PDF saved to `docs/evidence/` (Doc 6 item 1)
