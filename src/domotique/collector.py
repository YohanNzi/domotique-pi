"""Une passe de collecte : interroge chaque source, isole les pannes, persiste, journalise."""

from __future__ import annotations

import logging
from dataclasses import dataclass

from domotique.model import Source
from domotique.storage import Storage

log = logging.getLogger(__name__)


@dataclass
class RunReport:
    ok: list[str]
    failed: dict[str, str]
    measurements: int


def collect_once(sources: list[Source], storage: Storage, now: int) -> RunReport:
    report = RunReport(ok=[], failed={}, measurements=0)
    for source in sources:
        try:
            measurements = source.collect(now)
        except Exception as exc:  # une source en panne ne doit jamais bloquer les autres
            message = f"{type(exc).__name__}: {exc}"
            log.warning("source %s en échec : %s", source.name, message)
            storage.log_run(now, source.name, 0, message)
            report.failed[source.name] = message
            continue
        storage.save(measurements)
        storage.log_run(now, source.name, len(measurements))
        report.ok.append(source.name)
        report.measurements += len(measurements)
    return report
