"""``python3 -m wfgvu.tccheck`` exit codes with the simulated bench (no hardware) and injected failures."""
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from wfgvu import tccheck
from wfgvu.drivers import max31855 as mx

ROOT = Path(__file__).resolve().parents[1]
FAST = dict(sleep=lambda s: None)


def run(argv, **kw):
    out = io.StringIO()
    code = tccheck.run(argv, out=out, **{**FAST, **kw})
    return code, out.getvalue()


def test_fake_ok_exit_0():
    code, out = run(["--fake", "--seconds", "2"])
    assert code == 0, out
    assert out.count("tc_plate   hot") == 4 and "VERDICT: PASS" in out and "SIMULATED" in out
    assert "no_cs + software CS GPIO5" in out


def test_fake_disc_over_70_stops_at_once_exit_2():
    bench = mx.FakeBench()
    code, out = run(["--fake", "--seconds", "10", "--fake-disc-c", "71"], bench=bench)
    assert code == 2
    assert "STOP: flux disc at 71.00 C >= 70 C (PETG tabs)" in out
    assert len(bench.log) == 4                       # three open() probes + ONE plate read, nothing after
    assert bench.log[-1] == ("tc_plate",)
    assert "VERDICT" not in out


def test_fake_disc_exactly_70_stops():
    code, out = run(["--fake", "--fake-disc-c", "70"])
    assert code == 2 and "STOP: flux disc at 70.00 C >= 70 C" in out


def test_fake_disc_69_is_an_implausible_bench_reading_not_a_stop():
    code, out = run(["--fake", "--seconds", "1", "--fake-disc-c", "69"])
    assert code == 1 and "STOP" not in out and "outside the bench range" in out


def test_disc_limit_from_config_capped_at_70(tmp_path):
    cfg = tmp_path / "u.yaml"
    cfg.write_text((ROOT / "config" / "unit.yaml").read_text().replace("disc_max_c: 70", "disc_max_c: 50"))
    code, out = run(["--config", str(cfg), "--fake", "--fake-disc-c", "55"])
    assert code == 2 and ">= 50 C" in out
    cfg.write_text((ROOT / "config" / "unit.yaml").read_text().replace("disc_max_c: 70", "disc_max_c: 95"))
    code, out = run(["--config", str(cfg), "--fake", "--fake-disc-c", "71"])
    assert code == 2 and ">= 70 C" in out


def test_missing_config_file_is_exit_1_not_a_pass(tmp_path):
    """A typo in --config must not fall back to DEFAULTS (all three channels on spidev0.0 kernel CS) and PASS."""
    code, out = run(["--fake", "--seconds", "1", "--config", str(tmp_path / "nonexistent.yaml")])
    assert code == 1 and "config file not found" in out and "PASS" not in out


@pytest.mark.parametrize("edit,why", [
    (("cs_gpio: 5", "cs_gpio: null"), "share the same chip select"),          # tc_air on CE0 with tc_plate
    (("cs_gpio: 5", "cs_gpio: 8"), "kernel chip-select line"),                # software CS on CE0's pin
])
def test_chip_selects_must_be_distinct(tmp_path, edit, why):
    text = (ROOT / "config" / "unit.yaml").read_text()
    assert text.count(edit[0]) == 1
    cfg = tmp_path / "u.yaml"
    cfg.write_text(text.replace(*edit))
    code, out = run(["--fake", "--seconds", "1", "--config", str(cfg)])
    assert code == 1 and why in out and "PASS" not in out


def test_open_thermocouple_exit_1():
    bench = mx.FakeBench()
    orig = bench.word_for
    bench.word_for = lambda chip: (orig(chip) | 0x1 | (1 << 16)) if chip == "tc_housing" else orig(chip)
    code, out = run(["--fake", "--seconds", "1"], bench=bench)
    assert code == 1 and "tc_housing: faults: open" in out


def test_no_cs_unsupported_exit_1():
    code, out = run(["--fake", "--seconds", "1"], bench=mx.FakeBench(no_cs_supported=False))
    assert code == 1 and "tc_air: not open" in out and "no_cs unsupported" in out


def test_cj_spread_exit_1():
    bench = mx.FakeBench()
    orig = bench.word_for

    def word_for(chip):
        if chip == "tc_air":
            return mx.encode_max31855(21.0, 31.0)            # air chip die 7 C warmer than the others
        return orig(chip)

    bench.word_for = word_for
    code, out = run(["--fake", "--seconds", "1"], bench=bench)
    assert code == 1 and "cold-junction spread" in out and "FAIL" in out


def test_missing_chip_exit_1():
    bench = mx.FakeBench()
    bench.gpio_chips = {}                                   # nothing answers on GPIO5: MISO reads all zeros
    code, out = run(["--fake", "--seconds", "1"], bench=bench)
    assert code == 1 and "tc_air: not open" in out and "no chip answering" in out


def test_spi_busy_service_running_exit_3(tmp_path):
    """Another process (the service) holds the SPI0 bus lock: exit 3 with the systemctl hint."""
    (tmp_path / "spidev0.0").write_text("")                  # stands in for the /dev/spidev0.0 node
    holder = mx.SpiBus(0, lock_dir=str(tmp_path))
    holder.attach()
    try:
        bench = mx.FakeBench()
        bus = mx.SpiBus(0, gpio_factory=bench.gpio_factory, lock_dir=str(tmp_path))
        ds = {}
        for name, c in (("tc_plate", {"spi_dev": 0}), ("tc_housing", {"spi_dev": 1}),
                        ("tc_air", {"spi_dev": 0, "cs_gpio": 5})):
            ds[name] = mx.Max31855Driver(name, c, lambda m: None, bus=bus,
                                         spi_factory=lambda c=c: bench.spi_factory(0, c["spi_dev"]))
        code, out = run(["--seconds", "1"], drivers=ds)
    finally:
        holder.detach()
    assert code == 3
    assert "in use by another process" in out and "sudo systemctl stop wfgvu" in out
    assert bench.log == []


def test_gpio_busy_exit_3():
    def busy(n):
        raise mx.SpiAccessError("cannot claim GPIO%d on gpiochip0 (pinctrl-bcm2711): GPIO busy" % n)

    bench = mx.FakeBench()
    bus = mx.SpiBus(0, gpio_factory=busy, lock_dir=None)
    ds = {}
    for name, c in (("tc_plate", {"spi_dev": 0}), ("tc_housing", {"spi_dev": 1}),
                    ("tc_air", {"spi_dev": 0, "cs_gpio": 5})):
        ds[name] = mx.Max31855Driver(name, c, lambda m: None, bus=bus,
                                     spi_factory=lambda c=c: bench.spi_factory(0, c["spi_dev"]))
    code, out = run(["--seconds", "1"], drivers=ds)
    assert code == 3 and "GPIO busy" in out and "systemctl stop wfgvu" in out


def test_usage_errors_exit_64_not_2():
    with pytest.raises(SystemExit) as e:
        run(["--fake-disc-c", "71"])                         # needs --fake
    assert e.value.code == 64
    with pytest.raises(SystemExit) as e:
        run(["--fake", "--hz", "0"])
    assert e.value.code == 64


def test_cli_subprocess_fake_and_help():
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run([sys.executable, "-m", "wfgvu.tccheck", "--help"], cwd=ROOT, env=env,
                       capture_output=True, text=True, timeout=60)
    assert r.returncode == 0 and "--fake-disc-c" in r.stdout and "exit codes" in r.stdout
    r = subprocess.run([sys.executable, "-m", "wfgvu.tccheck", "--fake", "--seconds", "1", "--hz", "4",
                        "--fake-disc-c", "71"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=60)
    assert r.returncode == 2 and "STOP: flux disc at 71.00 C >= 70 C (PETG tabs)" in r.stdout
