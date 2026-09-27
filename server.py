#!/usr/bin/env python3
"""Docker dashboard: one page showing every container, its image, and its ports.

Stdlib only. Shells out to the docker CLI, serves JSON at /api/containers and
the page at /. Binds to localhost so it is not exposed to the network.
"""
import json
import os
import re
import subprocess
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("DASH_HOST", "127.0.0.1")
PORT = int(os.environ.get("DASH_PORT", "9077"))
DOCKER = os.environ.get("DOCKER_BIN", "/usr/local/bin/docker")
HERE = Path(__file__).parent

# "0.0.0.0:8081->8081/tcp", "[::]:8081->8081/tcp", "3272/tcp", "0.0.0.0:80-81->80-81/tcp"
PORT_RE = re.compile(r"^(?:(?P<ip>\[?[^\]]*\]?):(?P<host>[\d-]+)->)?(?P<cont>[\d-]+)/(?P<proto>\w+)$")


def parse_ports(raw):
    ports, seen = [], set()
    for chunk in filter(None, (p.strip() for p in raw.split(","))):
        m = PORT_RE.match(chunk)
        if not m:
            continue
        host, cont, proto = m["host"], m["cont"], m["proto"]
        key = (host, cont, proto)
        if key in seen:  # docker lists IPv4 and IPv6 bindings separately
            continue
        seen.add(key)
        ports.append({"host": host, "container": cont, "proto": proto,
                      "published": host is not None})
    return ports


def list_containers():
    out = subprocess.run(
        [DOCKER, "ps", "-a", "--no-trunc", "--format", "{{json .}}"],
        capture_output=True, text=True, timeout=10, check=True,
    ).stdout
    rows = []
    for line in out.splitlines():
        c = json.loads(line)
        rows.append({
            "name": c["Names"],
            "image": c["Image"],
            "id": c["ID"][:12],
            "state": c["State"],
            "status": c["Status"],
            "ports": parse_ports(c["Ports"]),
        })
    rows.sort(key=lambda r: (r["state"] != "running", r["name"]))
    return rows


class Handler(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/api/containers":
            try:
                body = json.dumps({"ok": True, "containers": list_containers()})
            except Exception as e:  # docker stopped, CLI missing, timeout
                body = json.dumps({"ok": False, "error": str(e), "containers": []})
            self._send(200, body.encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"docker-dashboard on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
