# domotique-pi

Collecteur de mesures pour un Raspberry Pi 2 : **sources enfichables → SQLite → Grafana**.
Fait maison volontairement (pas de Home Assistant : trop lourd pour 1 Go de RAM, et l'intérêt
du projet est de l'implémenter). Contrainte locataire : tout est réversible, rien n'est câblé.

## Sources disponibles (aucun matériel à acheter)

| Source | Mesures | Origine |
|---|---|---|
| `system` | `cpu_temperature`, `load_1m`, `memory_used`, `disk_used` | le Pi lui-même (`/sys`, `/proc`) |
| `weather` | `outdoor_temperature`, `outdoor_humidity`, `outdoor_pressure` | [Open-Meteo](https://open-meteo.com) (gratuit, sans clé), Toulouse par défaut |
| `network` | `<cible>_latency`, `<cible>_packet_loss` | `ping` vers la box et vers internet |

La température du SoC **n'est pas** celle de la pièce : elle sert à vérifier que le Pi tient
la charge. Un capteur intérieur (ex. BME280/DHT22) s'ajoutera plus tard comme une source de plus.

## Architecture

```
systemd timer (chaque minute)
  └─ python3 -m domotique collect --config /etc/domotique/config.toml
       ├─ chaque source → [Measurement(ts, source, metric, value, unit)]
       │    (une source en panne est isolée et journalisée, les autres continuent)
       └─ SQLite /var/lib/domotique/domotique.db  (WAL)
            ├─ measurement      format long, index (metric, ts)
            └─ collection_run   ok/error par source et par passe
Grafana ── plugin frser-sqlite-datasource ──> lit la même base
```

- **Zéro dépendance d'exécution** (stdlib Python ≥ 3.11) : rien à compiler sur ARMv7.
- **Ajouter une source** : une classe avec `name` et `collect(now) -> list[Measurement]`
  (cf. `src/domotique/model.py`), puis l'activer dans `config.py` / le TOML.
- **Rétention** : `retention_days` (365 par défaut) purge l'historique à chaque passe, pour
  ménager la carte SD.

## Développement (Mac / Linux)

```bash
uv run --python 3.11 --group dev pytest -q           # tests (sans réseau ni matériel)
cp config.example.toml config.toml                     # puis database = "domotique.db"
PYTHONPATH=src python3 -m domotique collect --config config.toml
```

## Installation sur le Raspberry Pi 2

> Pas encore testé sur le Pi lui-même (Pi pas encore installé au 30/09/2026) : les étapes
> ci-dessous sont le plan, à valider/corriger à la première installation.

1. **Système** : Raspberry Pi Imager → *Raspberry Pi OS Lite (32-bit)* (le Pi 2 est ARMv7),
   dans les réglages avancés : nom d'hôte `domotique`, SSH activé, ton utilisateur. Ethernet
   branché sur la box (le Pi 2 n'a pas de Wi-Fi).
2. **Accès** : `ssh <utilisateur>@domotique.local`, puis `sudo apt update && sudo apt full-upgrade -y`
   et `sudo apt install -y git rsync`.
3. **Collecteur** :
   ```bash
   git clone git@github.com:YohanNzi/domotique-pi.git && cd domotique-pi
   sudo ./deploy/install.sh
   ip route | grep default          # IP de la box → à reporter dans /etc/domotique/config.toml
   sudo systemctl start domotique-collect.service && journalctl -u domotique-collect -n 20
   ```
4. **Grafana** (dépôt APT officiel `apt.grafana.com`, paquet `grafana`, build ARMv7) :
   `sudo grafana-cli plugins install frser-sqlite-datasource`, puis relancer
   `sudo ./deploy/install.sh` (ajoute Grafana au groupe `domotique` et provisionne la datasource).
   Interface : `http://domotique.local:3000`. ⚠️ À vérifier à l'installation : disponibilité
   ARMv7 du plugin SQLite dans sa version courante.

### Requêtes pour les panneaux Grafana

```sql
-- Température extérieure (série temporelle ; colonne de temps : ts, secondes Unix)
SELECT ts AS time, value FROM measurement
WHERE metric = 'outdoor_temperature' AND ts BETWEEN $__from / 1000 AND $__to / 1000 ORDER BY ts;

-- Coupures internet (perte de paquets vers l'extérieur)
SELECT ts AS time, value FROM measurement
WHERE metric = 'internet_packet_loss' AND ts BETWEEN $__from / 1000 AND $__to / 1000 ORDER BY ts;

-- Santé des sources (dernières erreurs)
SELECT ts AS time, source, error FROM collection_run WHERE status = 'error' ORDER BY ts DESC LIMIT 20;
```
