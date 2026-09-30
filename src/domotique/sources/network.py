"""Santé de la connexion de l'appartement : latence et perte de paquets par cible (ping).

Cibles typiques : la box (réseau local) et une IP publique (accès internet). Une coupure
internet se voit donc comme `packet_loss = 100` sur la cible publique avec une box qui répond.
"""

from __future__ import annotations

import platform
import re
import subprocess
from typing import Callable

from domotique.model import Measurement

# Linux : "rtt min/avg/max/mdev = 1.1/2.2/3.3/0.4 ms" ; macOS : "round-trip min/avg/max/stddev = ..."
_RTT = re.compile(r"= [\d.]+/([\d.]+)/[\d.]+/[\d.]+ ms")
_LOSS = re.compile(r"([\d.]+)% packet loss")

Runner = Callable[[list[str]], str]


def _run(cmd: list[str]) -> str:
    # ping renvoie un code non nul quand tout est perdu : on lit quand même la sortie.
    return subprocess.run(cmd, capture_output=True, text=True, timeout=30).stdout


def ping_command(target: str, count: int, system: str | None = None) -> list[str]:
    system = system or platform.system()
    # Délai d'attente par paquet : secondes sous Linux, millisecondes sous macOS.
    wait = ["-W", "2"] if system == "Linux" else ["-W", "2000"]
    return ["ping", "-c", str(count), *wait, target]


def parse_ping(output: str) -> tuple[float | None, float]:
    """Retourne (latence moyenne en ms ou None si aucune réponse, perte en %)."""
    loss_match = _LOSS.search(output)
    if loss_match is None:
        raise ValueError("sortie de ping illisible (pas de ligne 'packet loss')")
    rtt_match = _RTT.search(output)
    return (float(rtt_match.group(1)) if rtt_match else None, float(loss_match.group(1)))


class NetworkSource:
    name = "network"

    def __init__(self, targets: dict[str, str], count: int = 3, run: Runner = _run) -> None:
        self._targets = targets  # libellé → hôte, ex. {"box": "192.168.1.1", "internet": "1.1.1.1"}
        self._count = count
        self._run = run  # injectable pour les tests

    def collect(self, now: int) -> list[Measurement]:
        out = []
        for label, host in self._targets.items():
            latency, loss = parse_ping(self._run(ping_command(host, self._count)))
            out.append(Measurement(now, self.name, f"{label}_packet_loss", loss, "%"))
            if latency is not None:
                out.append(Measurement(now, self.name, f"{label}_latency", latency, "ms"))
        return out
