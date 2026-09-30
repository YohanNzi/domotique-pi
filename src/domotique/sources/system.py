"""Mesures du Raspberry Pi lui-même : température SoC, charge, mémoire, disque.

Aucun matériel requis. La température du SoC n'est PAS la température de la pièce (elle
suit la charge), mais elle sert à surveiller que le Pi 2 tient sa charge (Grafana compris).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from domotique.model import Measurement


class SystemSource:
    name = "system"

    def __init__(self, root: Path = Path("/"), disk_path: str = "/") -> None:
        # `root` injectable : les tests pointent vers une arborescence /sys, /proc factice.
        self._root = root
        self._disk_path = disk_path

    def collect(self, now: int) -> list[Measurement]:
        out: list[Measurement] = []

        temp = self._cpu_temperature()
        if temp is not None:
            out.append(Measurement(now, self.name, "cpu_temperature", temp, "°C"))

        load1, _, _ = os.getloadavg()
        out.append(Measurement(now, self.name, "load_1m", round(load1, 2), ""))

        mem = self._memory_used_percent()
        if mem is not None:
            out.append(Measurement(now, self.name, "memory_used", mem, "%"))

        usage = shutil.disk_usage(self._disk_path)
        out.append(Measurement(now, self.name, "disk_used", round(usage.used / usage.total * 100, 1), "%"))
        return out

    def _cpu_temperature(self) -> float | None:
        # Linux / Raspberry Pi OS : millidegrés dans thermal_zone0. Absent sur macOS → ignoré.
        path = self._root / "sys/class/thermal/thermal_zone0/temp"
        try:
            return round(int(path.read_text().strip()) / 1000, 1)
        except (FileNotFoundError, ValueError):
            return None

    def _memory_used_percent(self) -> float | None:
        path = self._root / "proc/meminfo"
        try:
            fields = {}
            for line in path.read_text().splitlines():
                key, _, rest = line.partition(":")
                fields[key] = int(rest.split()[0])
            total, available = fields["MemTotal"], fields["MemAvailable"]
        except (FileNotFoundError, KeyError, ValueError, IndexError):
            return None
        return round((total - available) / total * 100, 1)
