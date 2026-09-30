import json
from pathlib import Path

import pytest

from domotique.sources.network import NetworkSource, parse_ping, ping_command
from domotique.sources.system import SystemSource
from domotique.sources.weather import WeatherSource

NOW = 1_790_000_000

LINUX_PING = """PING 1.1.1.1 (1.1.1.1) 56(84) bytes of data.
--- 1.1.1.1 ping statistics ---
3 packets transmitted, 3 received, 0% packet loss, time 2003ms
rtt min/avg/max/mdev = 11.204/12.530/14.117/1.204 ms
"""
MACOS_PING = """--- 1.1.1.1 ping statistics ---
2 packets transmitted, 2 packets received, 0.0% packet loss
round-trip min/avg/max/stddev = 16.688/19.682/22.677/2.995 ms
"""
LINUX_PING_DOWN = """--- 1.1.1.1 ping statistics ---
3 packets transmitted, 0 received, 100% packet loss, time 2040ms
"""


# --- réseau -----------------------------------------------------------------------------

@pytest.mark.parametrize("output, latency, loss", [
    (LINUX_PING, 12.53, 0.0),
    (MACOS_PING, 19.682, 0.0),
    (LINUX_PING_DOWN, None, 100.0),
])
def test_parse_ping_linux_macos_and_outage(output, latency, loss):
    assert parse_ping(output) == (latency, loss)


def test_parse_ping_rejects_unreadable_output():
    with pytest.raises(ValueError):
        parse_ping("ping: unknown host")


def test_ping_command_uses_platform_specific_timeout_unit():
    assert ping_command("1.1.1.1", 3, system="Linux") == ["ping", "-c", "3", "-W", "2", "1.1.1.1"]
    assert ping_command("1.1.1.1", 3, system="Darwin") == ["ping", "-c", "3", "-W", "2000", "1.1.1.1"]


def test_network_outage_reports_full_loss_without_latency():
    outputs = {"192.168.1.1": LINUX_PING, "1.1.1.1": LINUX_PING_DOWN}
    source = NetworkSource({"box": "192.168.1.1", "internet": "1.1.1.1"}, run=lambda cmd: outputs[cmd[-1]])

    metrics = {m.metric: m.value for m in source.collect(NOW)}

    assert metrics == {"box_packet_loss": 0.0, "box_latency": 12.53, "internet_packet_loss": 100.0}


# --- météo ------------------------------------------------------------------------------

def _payload(**current):
    return json.dumps({"current": {"time": "2026-09-30T12:00", **current}}).encode()


def test_weather_maps_open_meteo_fields():
    source = WeatherSource(43.6047, 1.4442, fetch=lambda url, timeout: _payload(
        temperature_2m=28.9, relative_humidity_2m=50, surface_pressure=999.9))

    got = {(m.metric, m.unit): m.value for m in source.collect(NOW)}

    assert got == {("outdoor_temperature", "°C"): 28.9, ("outdoor_humidity", "%"): 50.0,
                   ("outdoor_pressure", "hPa"): 999.9}


def test_weather_never_invents_missing_values():
    source = WeatherSource(43.6, 1.44, fetch=lambda url, timeout: _payload(temperature_2m=12.0))

    assert [m.metric for m in source.collect(NOW)] == ["outdoor_temperature"]


def test_weather_url_targets_requested_coordinates():
    url = WeatherSource(43.6047, 1.4442).url()
    assert "latitude=43.6047" in url and "longitude=1.4442" in url and "timezone=UTC" in url


# --- système ----------------------------------------------------------------------------

def test_system_reads_pi_temperature_and_memory(tmp_path: Path):
    (tmp_path / "sys/class/thermal/thermal_zone0").mkdir(parents=True)
    (tmp_path / "sys/class/thermal/thermal_zone0/temp").write_text("48312\n")
    (tmp_path / "proc").mkdir()
    (tmp_path / "proc/meminfo").write_text("MemTotal: 948304 kB\nMemFree: 100000 kB\nMemAvailable: 474152 kB\n")

    metrics = {m.metric: m.value for m in SystemSource(root=tmp_path, disk_path=str(tmp_path)).collect(NOW)}

    assert metrics["cpu_temperature"] == 48.3
    assert metrics["memory_used"] == 50.0
    assert {"load_1m", "disk_used"} <= metrics.keys()


def test_system_skips_linux_only_metrics_when_absent(tmp_path: Path):
    metrics = {m.metric for m in SystemSource(root=tmp_path, disk_path=str(tmp_path)).collect(NOW)}

    assert metrics == {"load_1m", "disk_used"}
