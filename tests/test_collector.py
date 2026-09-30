from pathlib import Path

from domotique import cli
from domotique.collector import collect_once
from domotique.model import Measurement
from domotique.storage import Storage

NOW = 1_790_000_000


class FakeSource:
    def __init__(self, name, measurements=None, error=None):
        self.name, self._measurements, self._error = name, measurements or [], error

    def collect(self, now):
        if self._error:
            raise self._error
        return self._measurements


def test_failing_source_is_isolated_and_logged(tmp_path: Path):
    storage = Storage(tmp_path / "t.db")
    ok = FakeSource("ok", [Measurement(NOW, "ok", "m", 1.0, "u")])
    broken = FakeSource("broken", error=TimeoutError("api muette"))

    report = collect_once([broken, ok], storage, NOW)

    assert report.ok == ["ok"] and "broken" in report.failed
    assert storage.query("SELECT metric, value FROM measurement") == [("m", 1.0)]
    assert storage.query("SELECT source, status, error FROM collection_run ORDER BY source") == [
        ("broken", "error", "TimeoutError: api muette"), ("ok", "ok", None)]


def test_prune_removes_only_old_history(tmp_path: Path):
    storage = Storage(tmp_path / "t.db")
    storage.save([Measurement(NOW - 400 * 86_400, "s", "old", 1.0, ""), Measurement(NOW, "s", "new", 2.0, "")])

    assert storage.prune(NOW - 365 * 86_400) == 1
    assert storage.query("SELECT metric FROM measurement") == [("new",)]


def test_cli_end_to_end_with_system_source_only(tmp_path: Path):
    db = tmp_path / "e2e.db"
    config = tmp_path / "config.toml"
    config.write_text(f'database = "{db}"\n[sources.system]\nenabled = true\n')

    assert cli.main(["collect", "--config", str(config)]) == 0

    storage = Storage(db)
    assert storage.query("SELECT COUNT(*) FROM measurement")[0][0] >= 2
    assert storage.query("SELECT source, status FROM collection_run") == [("system", "ok")]
