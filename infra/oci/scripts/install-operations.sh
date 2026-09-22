#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="${ROOT_DIR:-/opt/stock-analysis}"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Run with sudo: sudo $0" >&2
  exit 1
fi

install -m 0644 "$ROOT_DIR/infra/oci/systemd/stock-analysis-backup.service" /etc/systemd/system/
install -m 0644 "$ROOT_DIR/infra/oci/systemd/stock-analysis-backup.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now stock-analysis-backup.timer
systemctl list-timers stock-analysis-backup.timer --no-pager
