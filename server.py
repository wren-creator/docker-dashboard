#!/usr/bin/env python3
"""Docker dashboard: one page showing every container, its image, and its ports.

Stdlib only. Shells out to the docker CLI, serves JSON at /api/containers and
the page at /. Binds to localhost so it is not exposed to the network.
"""
import json
import os
import re
import subprocess
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HOST = os.environ.get("DASH_HOST", "127.0.0.1")
PORT = int(os.environ.get("DASH_PORT", "9077"))
DOCKER = os.environ.get("DOCKER_BIN", "/usr/local/bin/docker")
LSOF = os.environ.get("LSOF_BIN", "/usr/sbin/lsof")
NETSTAT = os.environ.get("NETSTAT_BIN", "/usr/sbin/netstat")
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


_prev_bytes, _port_state, _prev_lock = {}, {}, threading.Lock()


def port_activity():
    """{listening port: (receiving, transmitting)}, held until new activity.

    macOS netstat -b reports cumulative rx/tx bytes per connection. When any
    established connection to a port moved bytes since the previous call, that
    port's state is replaced with what moved (rx, tx, or both). Quiet calls
    leave it alone, so a flag stays lit until later traffic changes it. The
    first call has no baseline and reports nothing.
    """
    global _prev_bytes
    out = subprocess.run([NETSTAT, "-anb", "-p", "tcp"], capture_output=True, text=True, timeout=10).stdout
    now, moved = {}, {}
    for line in out.splitlines():
        f = line.split()
        if len(f) < 8 or f[5] != "ESTABLISHED" or not (f[-2].isdigit() and f[-1].isdigit()):
            continue
        port = f[3].rpartition(".")[2]
        if not port.isdigit():
            continue
        key, rx, tx = (f[3], f[4]), int(f[-2]), int(f[-1])
        now[key] = (rx, tx)
        with _prev_lock:
            old = _prev_bytes.get(key)
        if old:
            r, t = moved.get(int(port), (False, False))
            moved[int(port)] = (r or rx > old[0], t or tx > old[1])
    with _prev_lock:
        _prev_bytes = now
        _port_state.update({p: rt for p, rt in moved.items() if rt[0] or rt[1]})
        return dict(_port_state)


def list_listeners():
    """TCP ports something on this Mac is listening on, one row per port."""
    out = subprocess.run(
        [LSOF, "-nP", "-iTCP", "-sTCP:LISTEN", "-F", "pcn"],
        capture_output=True, text=True, timeout=10,
    ).stdout  # lsof exits 1 when nothing matches, so no check=True
    ports, pid, cmd = {}, None, None
    for line in out.splitlines():
        tag, val = line[0], line[1:]
        if tag == "p":
            pid = val
        elif tag == "c":  # lsof escapes odd bytes, e.g. "Code\\x20Helper"
            cmd = re.sub(r"\\x([0-9a-f]{2})", lambda m: chr(int(m[1], 16)), val)
        elif tag == "n":
            addr, _, port = val.rpartition(":")
            if not port.isdigit():
                continue
            local = addr in ("127.0.0.1", "[::1]", "localhost")
            row = ports.setdefault(int(port), {"port": int(port), "process": cmd, "pid": pid, "local": local})
            row["local"] = row["local"] and local  # reachable from the network on any non-loopback bind
    try:
        act = port_activity()
    except (OSError, subprocess.SubprocessError):
        act = {}
    for p, row in ports.items():
        row["rx"], row["tx"] = act.get(p, (False, False))
    return sorted(ports.values(), key=lambda r: r["port"])


ACTIONS = {"start", "stop", "restart"}
ID_RE = re.compile(r"^[0-9a-f]{12}$")


def run_action(action, cid):
    """Run docker start/stop/restart on a container the dashboard itself listed."""
    if cid not in {c["id"] for c in list_containers()}:
        return False, "unknown container"
    p = subprocess.run([DOCKER, action, cid], capture_output=True, text=True, timeout=60)
    return p.returncode == 0, (p.stderr or p.stdout).strip()


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
        elif self.path == "/api/ports":
            try:
                body = json.dumps({"ok": True, "ports": list_listeners()})
            except Exception as e:
                body = json.dumps({"ok": False, "error": str(e), "ports": []})
            self._send(200, body.encode(), "application/json")
        elif self.path in ("/", "/index.html"):
            self._send(200, (HERE / "index.html").read_bytes(), "text/html; charset=utf-8")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):
        # Localhost-only, but any web page can still fire requests at localhost.
        # Require our custom header (forces a CORS preflight we never grant) and
        # a Host we recognise (blocks DNS rebinding).
        host = self.headers.get("Host", "").rsplit(":", 1)[0]
        if self.headers.get("X-Dashboard") != "1" or host not in ("127.0.0.1", "localhost", "[::1]"):
            return self._send(403, b'{"ok": false, "error": "forbidden"}', "application/json")
        m = re.fullmatch(r"/api/containers/([0-9a-f]{12})/(\w+)", self.path)
        if not m or m[2] not in ACTIONS:
            return self._send(404, b'{"ok": false, "error": "not found"}', "application/json")
        try:
            ok, msg = run_action(m[2], m[1])
        except Exception as e:
            ok, msg = False, str(e)
        self._send(200, json.dumps({"ok": ok, "error": None if ok else msg}).encode(), "application/json")

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    print(f"docker-dashboard on http://{HOST}:{PORT}", flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
