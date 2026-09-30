"""Lecture de la configuration TOML et construction des sources activées."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from domotique.model import Source
from domotique.sources.network import NetworkSource
from domotique.sources.system import SystemSource
from domotique.sources.weather import WeatherSource


@dataclass
class Config:
    database: Path
    retention_days: int
    sources: list[Source]


def load(path: Path) -> Config:
    raw = tomllib.loads(path.read_text())
    sources: list[Source] = []
    src = raw.get("sources", {})

    if src.get("system", {}).get("enabled", True):
        sources.append(SystemSource())

    weather = src.get("weather", {})
    if weather.get("enabled", False):
        sources.append(WeatherSource(latitude=float(weather["latitude"]), longitude=float(weather["longitude"])))

    network = src.get("network", {})
    if network.get("enabled", False):
        sources.append(NetworkSource(targets=dict(network["targets"]), count=int(network.get("count", 3))))

    return Config(
        database=Path(raw.get("database", "domotique.db")),
        retention_days=int(raw.get("retention_days", 365)),
        sources=sources,
    )
