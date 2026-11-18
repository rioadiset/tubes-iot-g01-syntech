#!/usr/bin/env python3
"""Server HTTP lokal untuk Bagian B: POST /status/200 -> 200 tanpa body, keep-alive (HTTP/1.1)."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


class H(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"          # koneksi dipakai ulang (keep-alive)

    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        self.rfile.read(n)
        self.send_response(200)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, *a):           # jangan banjiri terminal
        pass


print("Server HTTP lokal di port 8080 (Ctrl+C untuk berhenti)")
ThreadingHTTPServer(("0.0.0.0", 8080), H).serve_forever()
