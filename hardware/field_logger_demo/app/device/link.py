"""One link owns the open port (spec section 3C). A reader thread reads every line; lines that start with '#' and
anything that does not belong to the command in flight go to the listener; replies complete the command in flight.
Every line sent and received is appended to logs/device_<YYYYMMDD>.log (git-ignored: DUMP lines contain positions).
"""
import datetime as dt
import threading
import time

from .. import config


class LinkLost(Exception):
    pass


def default_factory(port, method):
    """Open a real port. 'default' is pyserial's default open; 'lines_low' sets DTR and RTS False before open()."""
    import serial
    s = serial.Serial()
    s.port = port
    s.baudrate = 115200
    s.timeout = 0.05
    s.write_timeout = 2
    try:
        s.exclusive = True
    except (ValueError, AttributeError):
        pass
    if method == "lines_low":
        s.dtr = False
        s.rts = False
    s.open()
    return s


def belongs(kw, line):
    if line.startswith("OK " + kw) or line.startswith("ERR " + kw) or line.startswith("ERR FS "):
        return True
    if kw == "LIST" and line.startswith("SESS "):
        return True
    if kw == "DUMP" and (line.startswith("BEGIN ") or line.startswith("R ") or line.startswith("T ")):
        return True
    return False


def completes(kw, line):
    if line.startswith("ERR"):
        return True
    return line.startswith("OK " + kw)


class Pending:
    def __init__(self, cmd):
        self.cmd = cmd
        self.kw = cmd.split()[0].upper()
        self.lines = []
        self.done = threading.Event()
        self.last = time.monotonic()


class Link:
    def __init__(self, port, method="default", listener=None, factory=None, log_dir=None):
        self.port = port
        self.method = method
        self.listener = listener
        self.factory = factory or default_factory
        self.log_dir = log_dir or config.LOGS
        self.ser = None
        self.alive = False
        self.pending = None
        self.cmd_lock = threading.Lock()
        self.log_lock = threading.Lock()
        self.on_lost = None
        self.dump_lines = 0
        self.thread = None

    # ------------------------------------------------------------------ open / close
    def open(self):
        self.ser = self.factory(self.port, self.method)
        self.alive = True
        self.thread = threading.Thread(target=self._reader, name="link-reader", daemon=True)
        self.thread.start()
        self._log("·", "open %s method=%s" % (self.port, self.method))

    def close(self):
        self.alive = False
        try:
            if self.ser is not None:
                self.ser.close()
        except Exception:
            pass
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=1.0)
        self._log("·", "close %s" % self.port)

    # ------------------------------------------------------------------ logging
    def _log(self, direction, text):
        now = dt.datetime.now()
        try:
            self.log_dir.mkdir(parents=True, exist_ok=True)
            with self.log_lock, open(self.log_dir / ("device_%s.log" % now.strftime("%Y%m%d")), "a",
                                     encoding="utf-8") as f:
                f.write("%s  %s  %s\n" % (now.isoformat(timespec="milliseconds"), direction, text))
        except OSError:
            pass

    # ------------------------------------------------------------------ reading
    def _reader(self):
        buf = bytearray()
        while self.alive:
            try:
                chunk = self.ser.read(4096)
            except Exception as ex:   # unplugged, closed under us, or the driver went away
                if self.alive:
                    self._lost(ex)
                return
            if not chunk:
                continue
            buf += chunk
            while b"\n" in buf:
                i = buf.index(b"\n")
                raw = bytes(buf[:i])
                del buf[:i + 1]
                text = raw.rstrip(b"\r").decode("utf-8", "replace")
                if text.strip():
                    self._dispatch(text)
            if len(buf) > 8192:          # a line this long is noise; keep it visible, do not grow forever
                self._dispatch(bytes(buf).decode("utf-8", "replace"))
                buf.clear()

    def _lost(self, ex):
        self.alive = False
        self._log("·", "lost: %s" % ex)
        p = self.pending
        if p:
            p.done.set()
        if self.on_lost:
            self.on_lost(ex)

    def _dispatch(self, text):
        self._log("<", text)
        p = self.pending
        if not text.startswith("#") and p is not None and belongs(p.kw, text):
            p.lines.append(text)
            p.last = time.monotonic()
            if completes(p.kw, text):
                p.done.set()
            if self.listener:
                self.listener("reply", text, p)
            return
        if self.listener:
            self.listener("line", text, None)

    # ------------------------------------------------------------------ commands
    def write_line(self, text):
        self._log(">", text)
        try:
            self.ser.write((text + "\n").encode("ascii"))
            self.ser.flush()
        except Exception as ex:
            self._lost(ex)
            raise LinkLost(str(ex))

    def command(self, cmd, timeout=2.0, inactivity=None, blocking=True, quiet=False, first_timeout=None):
        """Send one command and return its reply lines. quiet: a poll (the sent line is not shown on the page).
        inactivity: the longest silence between reply lines (DUMP); first_timeout: the longest wait for the first
        reply line when it differs (the firmware hashes the whole file before DUMP's BEGIN line).
        Returns None if blocking is False and another command is in flight."""
        if not self.alive:
            raise LinkLost("not connected")
        if not self.cmd_lock.acquire(blocking=blocking):
            return None
        try:
            p = Pending(cmd)
            p.quiet = quiet
            self.pending = p
            if self.listener:
                self.listener("sent", cmd, p)
            self.write_line(cmd)
            start = time.monotonic()
            while not p.done.wait(0.02):
                if not self.alive:
                    raise LinkLost("connection lost")
                now = time.monotonic()
                if inactivity is not None:
                    limit = first_timeout if (first_timeout is not None and not p.lines) else inactivity
                    if now - p.last > limit:
                        raise TimeoutError("no reply to %s" % cmd.split()[0])
                elif now - start > timeout:
                    raise TimeoutError("no reply to %s" % cmd.split()[0])
            if not self.alive and not p.lines:
                raise LinkLost("connection lost")
            return p.lines
        finally:
            self.pending = None
            self.cmd_lock.release()


def parse_kv(line):
    """'OK HELLO fw=0.2.0 board="FireBeetle2 ESP32-E + TEL0157 (fallback)" device=1A2B3C4D ...' -> dict."""
    out = {}
    i = 0
    n = len(line)
    while i < n:
        j = line.find("=", i)
        if j < 0:
            break
        k0 = line.rfind(" ", 0, j) + 1
        key = line[k0:j]
        if j + 1 < n and line[j + 1] == '"':
            e = line.find('"', j + 2)
            e = n if e < 0 else e
            out[key] = line[j + 2:e]
            i = e + 1
        else:
            e = line.find(" ", j + 1)
            e = n if e < 0 else e
            out[key] = line[j + 1:e]
            i = e
    return out


def parse_dump(lines, name):
    """BEGIN/R/T/OK DUMP lines -> (bytes, size, sha) with the same checks as usb_export.Device.dump()."""
    if not lines or lines[0].startswith("ERR"):
        raise RuntimeError(lines[0] if lines else "no reply to DUMP")
    p = lines[0].split()
    if p[0] != "BEGIN" or p[1] != name:
        raise RuntimeError("unexpected reply: " + lines[0])
    size, sha = int(p[2]), p[3]
    buf = bytearray()
    expect = 0
    for ln in lines[1:]:
        if ln.startswith("R "):
            _, idx, hx = ln.split()
            if int(idx) != expect:
                raise RuntimeError("record index gap at %d (got %s)" % (expect, idx))
            buf += bytes.fromhex(hx)
            expect += 1
        elif ln.startswith("T "):
            buf += bytes.fromhex(ln.split()[1])
        elif ln.startswith("OK DUMP"):
            break
        elif ln.startswith("ERR"):
            raise RuntimeError(ln)
    return bytes(buf), size, sha
