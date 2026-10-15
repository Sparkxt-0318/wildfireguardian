"""Offline stdlib fallback for Mac systems with Python but no Node."""
from functools import partial
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from socketserver import TCPServer
from pathlib import Path
import webbrowser
import threading
import os
class Handler(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, '.mjs':'text/javascript', '.js':'text/javascript', '.woff2':'font/woff2'}
    def log_message(self, *_): pass
class LocalServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer normally reverse-resolves the address; offline DNS can stall.
        TCPServer.server_bind(self)
        self.server_name = 'localhost'
        self.server_port = self.server_address[1]
root = Path(__file__).resolve().parent
for port in range(int(os.environ.get('PORT','4173')), int(os.environ.get('PORT','4173'))+11):
    try:
        server=LocalServer(('127.0.0.1',port),partial(Handler,directory=str(root)))
        break
    except OSError: continue
else: raise SystemExit('No available exhibition port (4173–4183).')
url=f'http://127.0.0.1:{port}'
print(f'WildfireGuardian Showcase · {url}\nPress Ctrl+C to stop.',flush=True)
threading.Timer(.4,lambda:webbrowser.open(url)).start()
try: server.serve_forever()
except KeyboardInterrupt: server.server_close()
