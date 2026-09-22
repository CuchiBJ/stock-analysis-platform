#!/usr/bin/env bash
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

DATA_VOLUME="${DATA_VOLUME:-/srv/stock-platform}"
APP_ROOT="${APP_ROOT:-/opt/stock-analysis}"

if ! mountpoint -q "$DATA_VOLUME"; then
  echo "$DATA_VOLUME is not a mounted data volume; refusing to place Docker data there." >&2
  exit 1
fi

export DEBIAN_FRONTEND=noninteractive
apt-get update
apt-get install -y --no-install-recommends \
  ca-certificates \
  curl \
  docker-compose-v2 \
  docker.io \
  fail2ban \
  git \
  jq \
  netfilter-persistent \
  rsync \
  unattended-upgrades

systemctl stop docker.service docker.socket 2>/dev/null || true
install -d -m 0711 "$DATA_VOLUME/docker"
install -d -o ubuntu -g ubuntu -m 0750 "$DATA_VOLUME/backups"
install -d -o ubuntu -g ubuntu -m 0755 "$APP_ROOT"

install -D -m 0644 /dev/stdin /etc/docker/daemon.json <<EOF
{
  "data-root": "$DATA_VOLUME/docker",
  "log-driver": "local",
  "log-opts": {
    "max-size": "20m",
    "max-file": "5"
  }
}
EOF

install -D -m 0644 /dev/stdin /etc/ssh/sshd_config.d/99-stock-analysis-hardening.conf <<'EOF'
PasswordAuthentication no
PermitRootLogin no
KbdInteractiveAuthentication no
EOF

install -D -m 0644 /dev/stdin /etc/fail2ban/jail.d/sshd.local <<'EOF'
[sshd]
enabled = true
maxretry = 5
bantime = 1h
EOF

for protocol_port in tcp:80 tcp:443 udp:443; do
  protocol="${protocol_port%%:*}"
  port="${protocol_port##*:}"
  iptables -C INPUT -p "$protocol" --dport "$port" -j ACCEPT 2>/dev/null \
    || iptables -I INPUT 5 -p "$protocol" --dport "$port" -j ACCEPT
done
netfilter-persistent save

usermod -aG docker ubuntu
systemctl daemon-reload
systemctl enable --now docker fail2ban
systemctl restart ssh

docker info --format 'Docker {{.ServerVersion}} · {{.Architecture}} · data-root={{.DockerRootDir}}'
docker compose version
sshd -T | awk '/^(passwordauthentication|permitrootlogin|kbdinteractiveauthentication) /'
