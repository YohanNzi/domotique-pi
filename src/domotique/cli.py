"""Point d'entrée : `domotique collect --config config.toml` (lancé chaque minute par systemd)."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from domotique import config
from domotique.collector import collect_once
from domotique.storage import Storage

DAY = 86_400


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="domotique")
    sub = parser.add_subparsers(dest="command", required=True)
    collect = sub.add_parser("collect", help="une passe de collecte de toutes les sources activées")
    collect.add_argument("--config", type=Path, required=True)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    cfg = config.load(args.config)
    now = int(time.time())

    storage = Storage(cfg.database)
    try:
        report = collect_once(cfg.sources, storage, now)
        storage.prune(now - cfg.retention_days * DAY)
    finally:
        storage.close()

    logging.info("collecte : %d mesures, sources OK=%s, en échec=%s",
                 report.measurements, report.ok, list(report.failed))
    # Code de sortie non nul seulement si TOUTES les sources échouent (visible dans systemd).
    return 1 if cfg.sources and not report.ok else 0


if __name__ == "__main__":
    sys.exit(main())
