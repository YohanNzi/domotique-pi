"""Stockage SQLite : une table de mesures (format long) + un journal des collectes."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from domotique.model import Measurement

SCHEMA = """
CREATE TABLE IF NOT EXISTS measurement (
    ts     INTEGER NOT NULL,   -- secondes Unix UTC
    source TEXT    NOT NULL,
    metric TEXT    NOT NULL,
    value  REAL    NOT NULL,
    unit   TEXT    NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_measurement_metric_ts ON measurement (metric, ts);

-- Une ligne par source et par collecte : rend visibles (dans Grafana aussi) les sources en
-- panne, au lieu d'un trou silencieux dans les courbes.
CREATE TABLE IF NOT EXISTS collection_run (
    ts     INTEGER NOT NULL,
    source TEXT    NOT NULL,
    status TEXT    NOT NULL CHECK (status IN ('ok', 'error')),
    count  INTEGER NOT NULL,
    error  TEXT
);
CREATE INDEX IF NOT EXISTS idx_collection_run_ts ON collection_run (ts);
"""


class Storage:
    def __init__(self, path: Path | str) -> None:
        self._conn = sqlite3.connect(str(path))
        # WAL : Grafana peut lire pendant que le collecteur écrit, sans verrou bloquant.
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.executescript(SCHEMA)

    def save(self, measurements: list[Measurement]) -> None:
        with self._conn:
            self._conn.executemany(
                "INSERT INTO measurement (ts, source, metric, value, unit) VALUES (?, ?, ?, ?, ?)",
                [(m.ts, m.source, m.metric, m.value, m.unit) for m in measurements],
            )

    def log_run(self, ts: int, source: str, count: int, error: str | None = None) -> None:
        with self._conn:
            self._conn.execute(
                "INSERT INTO collection_run (ts, source, status, count, error) VALUES (?, ?, ?, ?, ?)",
                (ts, source, "error" if error else "ok", count, error),
            )

    def prune(self, older_than_ts: int) -> int:
        """Supprime l'historique ancien (usure de la carte SD). Retourne le nombre de mesures supprimées."""
        with self._conn:
            deleted = self._conn.execute("DELETE FROM measurement WHERE ts < ?", (older_than_ts,)).rowcount
            self._conn.execute("DELETE FROM collection_run WHERE ts < ?", (older_than_ts,))
        return deleted

    def query(self, sql: str, params: tuple = ()) -> list[tuple]:
        return self._conn.execute(sql, params).fetchall()

    def close(self) -> None:
        self._conn.close()
