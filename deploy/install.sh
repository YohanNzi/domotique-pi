#!/usr/bin/env bash
# Installation / mise à jour du collecteur sur le Raspberry Pi (idempotent).
# Usage, depuis la racine du repo cloné sur le Pi :  sudo ./deploy/install.sh
set -euo pipefail

if [[ $EUID -ne 0 ]]; then
  echo "À lancer avec sudo." >&2
  exit 1
fi

REPO="$(cd "$(dirname "$0")/.." && pwd)"

id domotique &>/dev/null || useradd --system --no-create-home --shell /usr/sbin/nologin domotique

install -d /opt/domotique
rsync -a --delete "$REPO/src/" /opt/domotique/src/

install -d /etc/domotique
if [[ ! -f /etc/domotique/config.toml ]]; then
  install -m 0644 "$REPO/config.example.toml" /etc/domotique/config.toml
  echo "→ /etc/domotique/config.toml créé depuis l'exemple : vérifier l'IP de la box (ip route)."
fi

install -m 0644 "$REPO/deploy/systemd/domotique-collect.service" /etc/systemd/system/
install -m 0644 "$REPO/deploy/systemd/domotique-collect.timer" /etc/systemd/system/
systemctl daemon-reload
systemctl enable --now domotique-collect.timer

# Grafana (si installé) : lecture de la base + datasource provisionnée.
if id grafana &>/dev/null; then
  usermod -aG domotique grafana
  install -d /etc/grafana/provisioning/datasources
  install -m 0644 "$REPO/deploy/grafana/datasource.yaml" /etc/grafana/provisioning/datasources/domotique.yaml
  systemctl restart grafana-server
fi

echo "OK. Première collecte : sudo systemctl start domotique-collect.service && journalctl -u domotique-collect -n 20"
