"""A host fake device (firmware/test/host/fake_device.cpp) on a pseudo-terminal, reachable by the app as a serial port.

The device runs on one pseudo-terminal; the app opens the slave side of a second one by its path (/dev/pts/N) with
pyserial, like a real port. Two pump threads copy bytes between the two masters. inject() sends a line to the device
as if it came from the host (the fake device's test-only '!' commands); unplug() closes the app's side, which the app
sees as a vanished device.
"""
import os
import pty
import select
import signal
import subprocess
import threading
import tty


class PtyDevice:
    def __init__(self, binary, devdir):
        self.m_dev, s_dev = pty.openpty()
        tty.setraw(s_dev)
        self.proc = subprocess.Popen([binary, str(devdir)], stdin=s_dev, stdout=s_dev, stderr=subprocess.DEVNULL)
        os.close(s_dev)
        self.m_app, self.s_app = pty.openpty()
        tty.setraw(self.s_app)
        self.port = os.ttyname(self.s_app)
        self.alive = True
        self.to_app = bytearray()        # every byte the device sent (for checks)
        self.lock = threading.Lock()
        self.threads = [threading.Thread(target=self._pump, args=(self.m_dev, self.m_app, True), daemon=True),
                        threading.Thread(target=self._pump, args=(self.m_app, self.m_dev, False), daemon=True)]
        for th in self.threads:
            th.start()

    def _pump(self, a, b, record):
        while self.alive:
            try:
                r, _, _ = select.select([a], [], [], 0.05)
                if not r:
                    continue
                d = os.read(a, 65536)
            except OSError:
                return
            if not d:
                return
            if record:
                with self.lock:
                    self.to_app += d
            try:
                os.write(b, d)
            except OSError:
                return

    def inject(self, line):
        os.write(self.m_dev, (line + "\n").encode("ascii"))

    def lines(self):
        with self.lock:
            return bytes(self.to_app).decode("utf-8", "replace").replace("\r", "").split("\n")

    def pause(self):
        self.proc.send_signal(signal.SIGSTOP)     # the device stops answering

    def resume(self):
        self.proc.send_signal(signal.SIGCONT)

    def unplug(self):
        """The cable is pulled: the app's side of the port goes away."""
        self.alive = False
        for fd in (self.m_app, self.s_app):
            try:
                os.close(fd)
            except OSError:
                pass

    def close(self):
        if self.proc.poll() is None:
            self.resume()
            self.proc.kill()
            self.proc.wait(5)
        self.alive = False
        for fd in (self.m_dev, self.m_app, self.s_app):
            try:
                os.close(fd)
            except OSError:
                pass
