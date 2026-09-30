"""Modèle commun à toutes les sources : une mesure = (instant, source, métrique, valeur, unité)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Measurement:
    """Une valeur mesurée. `ts` en secondes Unix (UTC) : format lu directement par Grafana."""

    ts: int
    source: str
    metric: str
    value: float
    unit: str


class Source(Protocol):
    """Une source de mesures. Ajouter un capteur = écrire une classe qui respecte ce contrat."""

    name: str

    def collect(self, now: int) -> list[Measurement]:
        """Retourne les mesures du moment. Lève une exception si la source est indisponible :
        le collecteur l'isole et la journalise sans bloquer les autres sources."""
        ...
