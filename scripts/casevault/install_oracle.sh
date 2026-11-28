#!/usr/bin/env bash
# Case Vault server setup on an Oracle Cloud Ubuntu VM (idempotent). Run from a checkout:
#   sudo bash scripts/casevault/install_oracle.sh [--deploy-user deploy] [--ghcr-user <github-user>]
# Does: Docker + compose plugin, user "deploy" (docker group, your SSH keys), host firewall
# (Oracle images REJECT everything but SSH in iptables: opens 80/443 and saves the rules),
# fail2ban for SSH, unattended security upgrades, GHCR login (read:packages token), the
# `casevault` command, /opt/casevault/{deploy,prod,staging}. Then: casevault init / up.
set -euo pipefail
DEPLOY_USER=deploy; GHCR_USER=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --deploy-user) DEPLOY_USER="$2"; shift 2 ;;
    --ghcr-user) GHCR_USER="$2"; shift 2 ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
done
say() { printf '\n\033[1;34m==> %s\033[0m\n' "$*"; }
ok()  { printf '    \033[32m✓\033[0m %s\n' "$*"; }
[[ "$(id -u)" -eq 0 ]] || { echo "run with sudo" >&2; exit 1; }
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASE=/opt/casevault

say "1/7 Packages (Docker, fail2ban, unattended-upgrades, iptables-persistent)"
export DEBIAN_FRONTEND=noninteractive
apt-get update -y -q
apt-get install -y -q --no-install-recommends ca-certificates curl openssl fail2ban \
  unattended-upgrades iptables-persistent netfilter-persistent
if ! command -v docker >/dev/null 2>&1; then curl -fsSL https://get.docker.com | sh; fi
systemctl enable --now docker >/dev/null
ok "$(docker --version)"; ok "$(docker compose version)"

say "2/7 User $DEPLOY_USER"
if ! id "$DEPLOY_USER" >/dev/null 2>&1; then
  adduser --disabled-password --gecos "" "$DEPLOY_USER" >/dev/null
fi
usermod -aG docker "$DEPLOY_USER"
install -d -m 700 -o "$DEPLOY_USER" -g "$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh"
for src in /home/ubuntu/.ssh/authorized_keys "${SUDO_USER:+/home/$SUDO_USER/.ssh/authorized_keys}"; do
  if [[ -n "$src" && -f "$src" ]]; then
    cat "$src" >> "/home/$DEPLOY_USER/.ssh/authorized_keys"
  fi
done
if [[ -f "/home/$DEPLOY_USER/.ssh/authorized_keys" ]]; then
  sort -u -o "/home/$DEPLOY_USER/.ssh/authorized_keys" "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chown "$DEPLOY_USER:$DEPLOY_USER" "/home/$DEPLOY_USER/.ssh/authorized_keys"
  chmod 600 "/home/$DEPLOY_USER/.ssh/authorized_keys"
fi
ok "$DEPLOY_USER (docker group, SSH keys copied)"

say "3/7 Host firewall: open 80/443 (Oracle Ubuntu rejects them by default)"
for port in 80 443; do
  for proto in tcp udp; do
    [[ "$port" == 80 && "$proto" == udp ]] && continue
    iptables -C INPUT -p "$proto" -m state --state NEW --dport "$port" -j ACCEPT 2>/dev/null \
      || iptables -I INPUT 5 -p "$proto" -m state --state NEW --dport "$port" -j ACCEPT
  done
done
netfilter-persistent save >/dev/null
ok "iptables: 22, 80, 443 open (saved). Also open 80/443 in the VCN Security List / NSG."
# ufw is NOT enabled: on Oracle images it fights the provider's iptables rules (see docs).

say "4/7 fail2ban (SSH) + automatic security updates"
cat > /etc/fail2ban/jail.d/casevault.local <<'JAIL'
[sshd]
enabled = true
maxretry = 5
findtime = 10m
bantime = 1h
JAIL
systemctl enable --now fail2ban >/dev/null && systemctl restart fail2ban
dpkg-reconfigure -f noninteractive unattended-upgrades >/dev/null 2>&1 || true
ok "fail2ban sshd jail, unattended-upgrades"

say "5/7 Deploy files -> $BASE/deploy"
install -d -m 755 "$BASE" "$BASE/deploy"
install -m 644 "$SRC"/deploy/casevault/{docker-compose.yml,Caddyfile,Caddyfile.cloudflare-origin,env.example,backup-loop.sh} "$BASE/deploy/"
install -m 644 "$SRC/apps/casevault/config/casevault.yaml" "$BASE/deploy/casevault.yaml"
install -m 755 "$SRC/deploy/casevault/casevault.sh" /usr/local/bin/casevault
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$BASE"
ok "casevault command installed"

say "6/7 GHCR login (private image)"
if [[ -n "$GHCR_USER" ]]; then
  echo "Paste a GitHub token with read:packages (input hidden):"
  read -r -s TOKEN
  echo "$TOKEN" | sudo -u "$DEPLOY_USER" docker login ghcr.io -u "$GHCR_USER" --password-stdin
  unset TOKEN
  ok "logged in to ghcr.io as $GHCR_USER (credentials in ~$DEPLOY_USER/.docker)"
else
  echo "    skipped: re-run with --ghcr-user <github-user> (needs a read:packages token)"
fi

say "7/7 Next steps (as $DEPLOY_USER)"
cat <<NEXT
  sudo -iu $DEPLOY_USER
  casevault init                     # creates prod + staging .env with random secrets
  nano /opt/casevault/prod/.env      # DOMAIN, ACME_EMAIL, Klaviyo, Shopify, Etsy, Turnstile, Telegram
  casevault up --staging && casevault up
  casevault admin create owner       # admin + 2FA
  curl -I https://casevault.halosparkinc.com/healthz
NEXT
