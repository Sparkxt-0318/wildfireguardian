#!/usr/bin/env python3
"""Serve the ember page (booth/ember/index.html) to phones on the same Wi-Fi.

For use before the page is on GitHub Pages. Prints the address and a QR code in the
terminal; open it on the phone (Safari or Chrome), tap once for fullscreen. Ctrl-C stops.

Usage: python scripts/serve_page.py [--port 8000]
"""
from __future__ import annotations

import argparse
import functools
import http.server
import socket
import sys
from pathlib import Path

PAGE_DIR = Path(__file__).resolve().parents[1] / "booth" / "ember"


def lan_address() -> str:
    """This Mac's address on the local network (the route a packet to the internet would take)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("192.168.0.1", 9))      # no packet is sent; this only picks the interface
        return s.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        s.close()


def print_qr(text: str) -> None:
    try:
        import cv2
        import numpy as np

        qr = cv2.QRCodeEncoder.create().encode(text)
        m = (np.asarray(qr) > 0)          # True = white
        m = np.pad(m, 2, constant_values=True)
        if m.shape[0] % 2:
            m = np.vstack([m, np.ones((1, m.shape[1]), bool)])
        for r in range(0, m.shape[0], 2):  # two rows per line with half blocks
            top, bot = m[r], m[r + 1]
            print("".join("█" if t and b else "▀" if t else "▄" if b else " " for t, b in zip(top, bot)))
    except Exception as exc:  # the address is enough
        print(f"(no QR code: {exc})")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    url = f"http://{lan_address()}:{a.port}/"
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(PAGE_DIR))
    with http.server.ThreadingHTTPServer(("0.0.0.0", a.port), handler) as srv:
        print(f"Ember page: {url}\nOpen it on the phone (same Wi-Fi), or scan:\n")
        print_qr(url)
        print("\nCtrl-C to stop.")
        try:
            srv.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
