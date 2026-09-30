"""Météo extérieure via Open-Meteo (gratuit, sans clé ni compte).

Sert de référence « dehors » : une fois un capteur intérieur branché, on pourra comparer
intérieur/extérieur (le vrai cas d'usage confort).
"""

from __future__ import annotations

import json
import urllib.parse
import urllib.request
from typing import Callable

from domotique.model import Measurement

API_URL = "https://api.open-meteo.com/v1/forecast"

# Variables Open-Meteo → (nom de métrique, unité).
_VARIABLES = {
    "temperature_2m": ("outdoor_temperature", "°C"),
    "relative_humidity_2m": ("outdoor_humidity", "%"),
    "surface_pressure": ("outdoor_pressure", "hPa"),
}

Fetcher = Callable[[str, float], bytes]


def _http_get(url: str, timeout: float) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "domotique-pi/0.1"})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read()


class WeatherSource:
    name = "weather"

    def __init__(self, latitude: float, longitude: float, timeout: float = 10.0,
                 fetch: Fetcher = _http_get) -> None:
        self._latitude = latitude
        self._longitude = longitude
        self._timeout = timeout
        self._fetch = fetch  # injectable pour les tests (pas d'appel réseau)

    def url(self) -> str:
        query = urllib.parse.urlencode({
            "latitude": self._latitude,
            "longitude": self._longitude,
            "current": ",".join(_VARIABLES),
            "timezone": "UTC",
        })
        return f"{API_URL}?{query}"

    def collect(self, now: int) -> list[Measurement]:
        payload = json.loads(self._fetch(self.url(), self._timeout))
        current = payload["current"]
        out = []
        for variable, (metric, unit) in _VARIABLES.items():
            value = current.get(variable)
            if value is not None:  # jamais de valeur inventée pour une variable absente
                out.append(Measurement(now, self.name, metric, float(value), unit))
        return out
