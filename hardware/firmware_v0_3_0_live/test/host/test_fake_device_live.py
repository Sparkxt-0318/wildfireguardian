#!/usr/bin/env python3
"""HOST/SIMULATED test of the LIVE lines through the host fake device (no hardware).

Runs test/host/fake_device (the real wfg_core logging, protocol and LIVE code) on a Linux pseudo-terminal and drives
it the way a desktop app would: nothing is sent by default, LIVE ON, GNSS epochs with !NMEA, LIVE NMEA ON, a
recording started, marked and stopped with !START, !MARK and !STOP. Every LIVE line is checked for its format, and
the "rec" lines are checked against the session file the logging code wrote.
Python standard library only. Run: python3 -B test_fake_device_live.py path/to/fake_device
"""
import json
import os
import pty
import select
import shutil
import subprocess
import sys
import tempfile
import time
import tty
import zlib

passed = failed = 0
EP_KEYS = ["v", "t", "ms", "utc", "fix", "q", "ft", "su", "hd", "la", "lo", "al", "sp", "co", "nr", "rs", "ss", "md"]
REC_KEYS = ["v", "t", "seq", "ty", "b", "crc", "hx"]


def check(cond, msg):
    global passed, failed
    if cond:
        passed += 1
    else:
        failed += 1
        print("FAIL:", msg)


def ck(body):
    c = 0
    for ch in body:
        c ^= ord(ch)
    return "$%s*%02X" % (body, c)


def epoch(hms, fix=True):
    if fix:
        return [ck("GNGGA,%s,3112.5559,N,12126.3372,E,1,11,0.9,12.4,M,8.9,M,," % hms),
                ck("GNRMC,%s,A,3112.5559,N,12126.3372,E,0.155,343.0,141026,,,A,V" % hms),
                ck("GNGSA,A,3,01,02,03,04,05,06,,,,,,,1.8,0.9,1.4,1")]
    return [ck("GNGGA,%s,,,,,0,03,,,M,,M,," % hms), ck("GNRMC,%s,V,,,,,,,141026,,,N,V" % hms),
            ck("GNGSA,A,1,,,,,,,,,,,,,99.99,99.99,99.99,1")]


class Dev:
    def __init__(self, binary, devdir):
        self.m, s = pty.openpty()
        tty.setraw(s)
        self.p = subprocess.Popen([binary, devdir], stdin=s, stdout=s, stderr=subprocess.PIPE)
        os.close(s)
        self.buf = b""
        self.lines = []      # every line received, in order (str)
        self.raw = []        # the same lines as bytes

    def pump(self, t):
        end = time.time() + t
        while True:
            left = end - time.time()
            r, _, _ = select.select([self.m], [], [], max(0.0, min(0.02, left)))
            if r:
                try:
                    d = os.read(self.m, 65536)
                except OSError:
                    return
                if not d:
                    return
                self.buf += d
                while b"\n" in self.buf:
                    ln, self.buf = self.buf.split(b"\n", 1)
                    self.raw.append(ln)
                    self.lines.append(ln.decode("ascii", "replace"))
            if time.time() >= end:
                return

    def send(self, line):
        os.write(self.m, (line + "\n").encode())

    def cmd(self, line, wait=0.25):
        n0 = len(self.lines)
        self.send(line)
        self.pump(wait)
        return self.lines[n0:]

    def wait_for(self, pred, timeout):
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            self.pump(0.05)
        return pred()

    def nmea(self, sentences):
        for s in sentences:
            self.send("!NMEA " + s)


def jl(lines, t=None):
    out = []
    for ln in lines:
        if ln.startswith("#J "):
            o = json.loads(ln[3:])
            if t is None or o.get("t") == t:
                out.append(o)
    return out


def keys(line):
    return [k for k, _ in json.loads(line[3:], object_pairs_hook=list)]


def raw_field(line, key):
    k = '"%s":' % key
    p = line.find(k)
    if p < 0:
        return None
    p += len(k)
    e = min(x for x in (line.find(",", p), line.find("}", p), len(line)) if x >= 0)
    return line[p:e]


def main(binary):
    work = tempfile.mkdtemp(prefix="wfg_live_")
    devdir = os.path.join(work, "device_fs")
    os.makedirs(devdir)
    d = Dev(binary, devdir)
    try:
        d.wait_for(lambda: d.lines, 3)
        check(d.lines[:1] == ["# fake device ready"], "ready line first")
        out = d.cmd("HELLO")
        check('OK HELLO fw=0.1.0-host board="HOST-FAKE-DEVICE" device=1A2B3C4D fmt=2 recsize=48 state=IDLE' in out,
              "HELLO keeps the fake device's strings: %r" % out)

        # 1. Default off: epochs and sentences give no LIVE lines at all
        n0 = len(d.lines)
        d.nmea(epoch("081640.000"))
        d.pump(0.6)
        out = d.cmd("STATUS")
        check(not any(x.startswith("#J") or x.startswith("#N") for x in d.lines[n0:]), "default off: no LIVE lines")
        check(any(x.startswith("OK STATUS state=IDLE mode=WALK session=- seq=0 ") for x in out), "STATUS %r" % out)

        # 2. LIVE ON: one ep per epoch, fields as specified, no #N yet
        check(d.cmd("LIVE ON") == ["OK LIVE ON"], "LIVE ON reply")
        n0 = len(d.lines)
        d.nmea(epoch("081641.000"))
        d.wait_for(lambda: jl(d.lines[n0:], "ep"), 2)
        d.pump(0.2)
        new = d.lines[n0:]
        eps = [x for x in new if x.startswith("#J ") and '"t":"ep"' in x]
        check(len(eps) == 1, "one ep per epoch: %r" % new)
        check(not any(x.startswith("#N") for x in new), "no #N while LIVE NMEA is off")
        if eps:
            e = json.loads(eps[0][3:])
            check(keys(eps[0]) == EP_KEYS, "ep keys in order: %r" % keys(eps[0]))
            check(e["v"] == 1 and e["utc"] == "2026-10-14T08:16:41.000Z" and e["fix"] == 1 and e["q"] == 1 and
                  e["ft"] == "3D" and e["su"] == 11 and e["nr"] is None and e["rs"] == "IDLE" and e["ss"] is None and
                  e["md"] == "WALK", "ep values %r" % e)
            check(raw_field(eps[0], "la") == "31.2092650" and raw_field(eps[0], "lo") == "121.4389533" and
                  raw_field(eps[0], "hd") == "0.9" and raw_field(eps[0], "al") == "12.4" and
                  raw_field(eps[0], "sp") == "0.08" and raw_field(eps[0], "co") == "343.0", "ep numbers %s" % eps[0])

        # 3. LIVE NMEA ON: the sentences come back exactly as sent, before the epoch's ep line
        check(d.cmd("LIVE NMEA ON") == ["OK LIVE NMEA ON"], "LIVE NMEA ON reply")
        n0 = len(d.lines)
        sent = epoch("081642.000", fix=False)
        d.nmea(sent)
        d.wait_for(lambda: jl(d.lines[n0:], "ep"), 2)
        new = d.lines[n0:]
        check([x[3:] for x in new if x.startswith("#N ")] == sent, "#N lines are the raw sentences: %r" % new)
        e = jl(new, "ep")
        check(len(e) == 1 and e[0]["fix"] == 0 and e[0]["nr"] == "RECEIVER_NO_FIX" and e[0]["la"] is None and
              e[0]["ft"] == "NONE" and e[0]["q"] == 0, "no-fix ep %r" % e)
        live_new = [x for x in new if x.startswith("#N ") or '"t":"ep"' in x]
        check(live_new and live_new[-1].startswith('#J {"v":1,"t":"ep"'), "ep after the epoch's #N lines")

        # 4. !START: rec lines for START, CLOCK and STATUS, st, ss, then the banner main.cpp prints
        n0 = len(d.lines)
        d.send("!START VEHICLE")
        d.wait_for(lambda: "# REC S000001.wfg VEHICLE" in d.lines[n0:], 2)
        new = d.lines[n0:]
        check(new[-1:] == ["# REC S000001.wfg VEHICLE"], "REC banner last: %r" % new)
        recs = jl(new, "rec")
        check([r["ty"] for r in recs] == [1, 5, 7], "START, CLOCK (UTC known), STATUS: %r" % [r["ty"] for r in recs])
        i7 = [i for i, x in enumerate(new) if '"t":"rec"' in x and '"ty":7,' in x]
        st = json.loads(new[i7[0] + 1][3:]) if i7 and i7[0] + 1 < len(new) else {}
        check(st.get("t") == "st" and st.get("vb", 0) is None and isinstance(st.get("ff"), int),
              "st right after the STATUS record %r" % st)
        ss = [x for x in new if '"t":"ss"' in x]
        check(ss == ['#J {"v":1,"t":"ss","ss":1,"md":"VEHICLE","sr":"OWNER_BUTTON"}'], "ss line %r" % ss)

        # 5. Two epochs while recording, about 1 s apart (the logger keeps at most one row per second)
        for k, hms in enumerate(("081643.000", "081644.000")):
            n0 = len(d.lines)
            d.nmea(epoch(hms))
            d.wait_for(lambda: jl(d.lines[n0:], "ep") and jl(d.lines[n0:], "rec"), 2)
            new = d.lines[n0:]
            e = jl(new, "ep")
            check(len(e) == 1 and e[0]["rs"] == "RECORDING" and e[0]["ss"] == 1 and e[0]["md"] == "VEHICLE",
                  "ep while recording %r" % e)
            check([r["ty"] for r in jl(new, "rec") if r["ty"] != 3] == [2], "FIX row %r" % new)
            ep_i = [i for i, x in enumerate(new) if '"t":"ep"' in x]
            rec_i = [i for i, x in enumerate(new) if '"t":"rec"' in x and '"ty":2,' in x]
            check(ep_i and rec_i and ep_i[0] < rec_i[0], "ep before the row it produces")
            if k == 0:
                d.pump(0.8)

        # 6. !MARK: EVENT record, ev, banner (a gap-filler row may come in between and is ignored here)
        out = d.cmd("!MARK")
        check([r["ty"] for r in jl(out, "rec") if r["ty"] != 3] == [4], "EVENT record %r" % out)
        check('#J {"v":1,"t":"ev","n":1,"loc":1}' in out and "# EVENT 1 marked" in out, "ev and banner %r" % out)

        # 7. Protocol while recording: as main.cpp, byte for byte ("%.5s" of "DUMP S..." keeps the space after DUMP)
        out = d.cmd("LIST") + d.cmd("DUMP S000001.wfg") + d.cmd("CHECK S000001.wfg")
        check([x for x in out if x.startswith("ERR")] ==
              ["ERR LIST recording-active (stop recording first)", "ERR DUMP  recording-active (stop recording first)",
               "ERR CHECK recording-active (stop recording first)"], "heavy commands refused %r" % out)
        out = d.cmd("STATUS")
        check(any(x.startswith("OK STATUS state=RECORDING mode=VEHICLE session=S000001.wfg seq=") for x in out),
              "STATUS while recording %r" % out)
        check(d.cmd("LIVE MAYBE") == ["ERR LIVE bad-argument"], "bad LIVE argument while recording")
        check(d.cmd("LIVE NMEA OFF") == ["OK LIVE NMEA OFF"], "LIVE NMEA OFF while recording")

        # 8. No GNSS data: the gap filler writes NOFIX rows (NO_NMEA_DATA), seen as rec lines
        n0 = len(d.lines)
        d.wait_for(lambda: any(r["ty"] == 3 for r in jl(d.lines[n0:], "rec")), 4)
        fill = [r for r in jl(d.lines[n0:], "rec") if r["ty"] == 3]
        check(fill and bytes.fromhex(fill[0]["hx"])[41] == 2, "gap filler row NO_NMEA_DATA")

        # 9. !STOP: END record, se with the record count, banner
        n0 = len(d.lines)
        d.send("!STOP")
        d.wait_for(lambda: "# STOPPED - saved" in d.lines[n0:], 2)
        new = [x for x in d.lines[n0:] if '"t":"st"' not in x]  # an idle st may follow the stop at any moment
        check([r["ty"] for r in jl(new, "rec")][-1:] == [6], "END record %r" % new)
        check(new[-2:] == ['#J {"v":1,"t":"se","ss":1,"er":"USER_STOP","n":%d}'
                           % (os.path.getsize(os.path.join(devdir, "S000001.wfg")) // 48), "# STOPPED - saved"],
              "se, then the STOPPED banner %r" % new)

        # The rec lines rebuild the session file exactly; b, seq and crc agree with the bytes
        data = open(os.path.join(devdir, "S000001.wfg"), "rb").read()
        rec_lines = [x for x in d.lines if x.startswith('#J {"v":1,"t":"rec"')]
        recs = [json.loads(x[3:]) for x in rec_lines]
        check(b"".join(bytes.fromhex(r["hx"]) for r in recs) == data, "rec lines == session file bytes")
        check([r["seq"] for r in recs] == list(range(len(recs))), "seq 0..n-1 without gaps")
        check(all(r["b"] == (r["seq"] + 1) * 48 for r in recs), "b = file size after each record")
        check(all(r["crc"] == "%08x" % zlib.crc32(bytes.fromhex(r["hx"])[:44]) and
                  r["crc"] == "%08x" % int.from_bytes(bytes.fromhex(r["hx"])[44:48], "little") for r in recs),
              "crc = CRC-32 of bytes 0..43 = u32 at 44..47")
        check(all(r["ty"] == bytes.fromhex(r["hx"])[2] for r in recs), "ty = byte 2")
        check(all(keys(x) == REC_KEYS for x in rec_lines), "rec keys in order")
        se = [x for x in new if '"t":"se"' in x]
        check(se == ['#J {"v":1,"t":"se","ss":1,"er":"USER_STOP","n":%d}' % (len(data) // 48)], "se line %r" % se)
        out = d.cmd("CHECK S000001.wfg")
        check(any(x.startswith("OK CHECK S000001.wfg OK ") for x in out), "session file intact %r" % out)

        # 10. Idle: st every 10 s (no battery on the host: vb null)
        n0 = len(d.lines)
        check(d.wait_for(lambda: jl(d.lines[n0:], "st"), 11.5), "st every 10 s while idle")
        st = jl(d.lines[n0:], "st")
        check(st and st[0]["vb"] is None and isinstance(st[0]["ff"], int), "idle st %r" % st)

        # 11. LIVE OFF: silence again
        check(d.cmd("LIVE OFF") == ["OK LIVE OFF"], "LIVE OFF reply")
        n0 = len(d.lines)
        d.nmea(epoch("081700.000"))
        d.pump(0.6)
        check(not any(x.startswith("#J") or x.startswith("#N") for x in d.lines[n0:]), "LIVE OFF: no LIVE lines")

        # Every line seen: ASCII, no CR, LIVE lines at most 320 bytes with the '\n', #J lines are JSON with v=1
        check(all(all(b < 0x80 for b in r) and b"\r" not in r for r in d.raw), "ASCII, LF line endings")
        live = [r for r in d.raw if r.startswith(b"#J ") or r.startswith(b"#N ")]
        check(all(len(r) + 1 <= 320 for r in live), "LIVE lines <= 320 bytes")
        check(all(json.loads(x[3:]).get("v") == 1 for x in d.lines if x.startswith("#J ")), "#J lines parse, v=1")
        d.send("!QUIT")
        try:
            rc = d.p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            rc = None
        check(rc == 0, "exits on !QUIT")
        err = d.p.stderr.read().decode("utf-8", "replace") if rc is not None else ""
        check(err == "", "nothing on stderr: %r" % err)
    finally:
        if d.p.poll() is None:
            d.p.kill()
        os.close(d.m)
        shutil.rmtree(work, ignore_errors=True)


if __name__ == "__main__":
    if len(sys.argv) < 2 or not os.path.exists(sys.argv[1]):
        print("usage: test_fake_device_live.py path/to/fake_device")
        sys.exit(2)
    main(sys.argv[1])
    print("LIVE FAKE DEVICE TESTS (simulated, no hardware): %d passed, %d failed" % (passed, failed))
    sys.exit(1 if failed else 0)
