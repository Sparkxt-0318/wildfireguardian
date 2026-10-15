#!/usr/bin/env python3
"""HOST/SIMULATED tests for phone_export/usb_export.py (no hardware).

1. Byte-identity: Python CSV/GPX/GeoJSON converters == C++ firmware exporter output (samples written by the C++ host
   tests in phone_export/samples/).
2. Integrity checker: detects torn tail, flipped bit, missing END.
3. End-to-end USB protocol: runs the real wfg_core protocol in firmware/test/host/fake_device (built by
   run_all_host_tests.sh) behind a Linux pseudo-terminal and drives it with usb_export.py through pyserial:
   list -> dump --confirm -> delete (refused until button) -> simulated button hold -> deleted.
Run: python3 phone_export/tests/test_usb_export.py [path-to-fake_device-binary]
"""
import hashlib
import os
import pty
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tty

HERE = os.path.dirname(os.path.abspath(__file__))
PE = os.path.dirname(HERE)
sys.path.insert(0, PE)
import usb_export as ue  # noqa: E402

SAMPLES = os.path.join(PE, "samples")
passed = failed = 0


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL:", msg)


def test_byte_identity():
    data = open(os.path.join(SAMPLES, "S000001_WALK.wfg"), "rb").read()
    for ext, fn in ((".csv", ue.to_csv), (".gpx", ue.to_gpx), (".geojson", ue.to_geojson)):
        ref = open(os.path.join(SAMPLES, "S000001_WALK" + ext), encoding="utf-8").read()
        got = fn(data, "S000001.wfg")
        check(got == ref, "python %s differs from firmware output" % ext)
    rep = ue.integrity(data)
    check(rep["ok"] and rep["status"] == "OK", "sample integrity %r" % rep)
    check(rep["status_records"] == 2, "sample has 2 STATUS records")
    # auto-resumed session sample (format v2 attribution)
    d2 = open(os.path.join(SAMPLES, "S000002_WALK_autoresumed.wfg"), "rb").read()
    for ext, fn in ((".csv", ue.to_csv), (".gpx", ue.to_gpx), (".geojson", ue.to_geojson)):
        ref = open(os.path.join(SAMPLES, "S000002_WALK_autoresumed" + ext), encoding="utf-8").read()
        check(fn(d2, "S000002.wfg") == ref, "python %s differs for auto-resumed sample" % ext)
    check(",AUTO_RESUMED_AFTER_RESET,WFG-1A2B3C4D-000001," in ue.to_csv(d2), "resume attribution in CSV")
    # format v1 file (firmware 0.1.0) still decodes
    d1 = open(os.path.join(SAMPLES, "format_v1", "S000001_WALK_v1.wfg"), "rb").read()
    r1 = ue.integrity(d1)
    check(r1["status"] == "OK" and r1["fix"] == 60 and r1["status_records"] == 0, "v1 integrity %r" % r1["status"])
    c1 = ue.to_csv(d1)
    check(c1.startswith(ue.CSV_HEADER) and ",OWNER_BUTTON,,\n" in c1, "v1 CSV converts with OWNER_BUTTON")
    sha_line = open(os.path.join(SAMPLES, "S000001_WALK.wfg.sha256")).read().split()[0]
    check(hashlib.sha256(data).hexdigest() == sha_line, "sha256 file")


def test_integrity_detects_damage():
    data = open(os.path.join(SAMPLES, "S000001_WALK.wfg"), "rb").read()
    torn = data[:-48] + data[-48:-20]
    r = ue.integrity(torn)
    check(r["status"] == "TORN_TAIL" and r["trailing_bytes"] == 28, "torn tail %r" % r["status"])
    flip = bytearray(data)
    flip[48 * 10 + 21] ^= 0x04
    r = ue.integrity(bytes(flip))
    check(r["status"] == "CORRUPT" and r["crc_errors"] == 1, "bit flip")
    check(",CORRUPT," in ue.to_csv(bytes(flip)), "corrupt row visible in CSV")
    r = ue.integrity(data[:-48])
    check(r["status"] == "OPEN" and not r["has_end"], "missing END -> OPEN")
    rec = open(os.path.join(SAMPLES, "S000001_WALK_recovered.csv")).read()
    check(",RECOVERED_ON_BOOT," in rec, "recovered sample has RECOVERED_ON_BOOT end")


def test_usb_end_to_end(fake_bin):
    if not fake_bin or not os.path.exists(fake_bin):
        print("SKIP usb end-to-end: fake_device binary not found")
        return
    work = tempfile.mkdtemp(prefix="wfg_usb_")
    devdir = os.path.join(work, "device_fs")
    os.makedirs(devdir)
    shutil.copy(os.path.join(SAMPLES, "S000001_WALK.wfg"), os.path.join(devdir, "S000001.wfg"))
    master, slave = pty.openpty()
    tty.setraw(slave)
    proc = subprocess.Popen([fake_bin, devdir], stdin=slave, stdout=slave, stderr=subprocess.DEVNULL)
    port = os.ttyname(slave)
    # Bridge: our test talks to the master side via pyserial on a second pty pair? Simpler: open master with
    # pyserial through its file descriptor path is not possible, so use a second pty and pump bytes.
    m2, s2 = pty.openpty()
    tty.setraw(s2)
    stop = False

    def pump(a, b):
        while not stop:
            try:
                d = os.read(a, 4096)
            except OSError:
                return
            if not d:
                return
            os.write(b, d)
    threading.Thread(target=pump, args=(master, m2), daemon=True).start()
    threading.Thread(target=pump, args=(m2, master), daemon=True).start()
    host_port = os.ttyname(s2)
    try:
        dev = ue.Device(host_port, timeout=2)
        check(dev.hello().startswith("OK HELLO"), "hello")
        sess = dev.list()
        check(len(sess) == 1 and sess[0]["name"] == "S000001.wfg" and sess[0]["closed"], "list %r" % sess)
        check(not sess[0]["exported"], "not exported yet")
        out = os.path.join(work, "exports")
        fails = ue.cmd_dump(dev, ["S000001.wfg"], out, confirm=True)
        check(fails == 0, "dump+confirm")
        files = sorted(os.listdir(out))
        check(any(f.endswith(".csv") for f in files) and any(f.endswith(".gpx") for f in files), "files %r" % files)
        ref = open(os.path.join(SAMPLES, "S000001_WALK.csv")).read()
        got = open(os.path.join(out, "WFG-1A2B3C4D-000001_WALK.csv")).read()
        check(ref == got, "USB-exported CSV equals firmware CSV")
        sess = dev.list()
        check(sess[0]["exported"], "export confirmed on device")
        # Delete requires the physical button
        ln = dev.simple("DELETE S000001.wfg " + sess[0]["sha256"], "OK DELETE")
        check(ln.startswith("PENDING DELETE"), "pending delete " + ln)
        check(os.path.exists(os.path.join(devdir, "S000001.wfg")), "not deleted before button")
        dev.cmd("!BUTTON_LONG")
        ln = dev.readline(5)
        check(ln.startswith("OK DELETE"), "deleted after button: " + ln)
        check(not os.path.exists(os.path.join(devdir, "S000001.wfg")), "file gone")
        check(len(dev.list()) == 0, "list empty")
        # Wrong-hash confirm is refused
        shutil.copy(os.path.join(SAMPLES, "S000001_WALK.wfg"), os.path.join(devdir, "S000002.wfg"))
        ln = dev.simple("CONFIRM S000002.wfg " + "0" * 64, "OK CONFIRM")
        check(ln.startswith("ERR CONFIRM"), "bad hash refused")
        ln = dev.simple("DELETE S000002.wfg " + "0" * 64, "OK DELETE")
        check(ln.startswith("ERR DELETE"), "unconfirmed delete refused")
        dev.cmd("!QUIT")
    finally:
        stop = True
        time.sleep(0.2)
        proc.kill()
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    test_byte_identity()
    test_integrity_detects_damage()
    test_usb_end_to_end(sys.argv[1] if len(sys.argv) > 1 else None)
    print("PYTHON HOST TESTS (simulated, no hardware): %d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)
