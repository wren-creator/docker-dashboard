# docker-dashboard

One page that shows every Docker container on this Mac, its image, and its ports. Refreshes every 5 seconds.

```
./start.sh     # then open http://localhost:9077
./stop.sh
```

On a new machine: `git clone` the repo, make sure `docker` works from your shell, and run `./start.sh`. If your docker binary isn't at `/usr/local/bin/docker`, set `DOCKER_BIN` (see Config). Needs Python 3, nothing else to install.

- Published ports (`:8081 → 8081/tcp`) are clickable links to `http://localhost:<port>`.
- Ports that are exposed but not published to the host show dimmed.
- "show stopped" toggles exited containers.
- The page is a horizontal split, containers on top and "Other listening ports" below, each pane with its own scroll bar and a sticky header, and a draggable divider between them (the position is remembered in the browser). The bottom pane lists every other TCP port something on this Mac is listening on (process, pid, and whether it's loopback-only or on all interfaces), each with an **open** button to `http://localhost:<port>`. Docker's own published ports are left out since they're already above. Plenty of these aren't web servers (3270, SSH, databases), so open will only work for the HTTP ones. A **Traffic** column flags **RX** (receiving) and **TX** (transmitting) when an established connection to that port moved bytes between 5 second refreshes. A flag holds until later traffic changes it (so a port that last received stays on RX until it transmits), and ports with no traffic seen since the server started show idle. It reads per-connection byte counters from `netstat -anb`, so it is macOS-specific and the first refresh after startup has no baseline.
- Each row has buttons: running containers get **stop** and **restart**, stopped ones get **start**.

## How it works

`server.py` is stdlib-only Python. It runs `docker ps -a` and serves JSON at `/api/containers`, `/api/ports` (from `lsof`), and the page at `/`. It binds to 127.0.0.1 only.

Start/stop/restart go through `POST /api/containers/<id>/<action>`. Because any web page can fire requests at localhost, the server only accepts POSTs that carry an `X-Dashboard: 1` header (which forces a CORS preflight it never approves) and a localhost `Host` header (blocks DNS rebinding). It also only acts on container IDs it just listed from docker.

`start.sh` runs it in the background with a PID file (`dashboard.pid`) and logs to `dashboard.log`. It refuses to start if it's already running or if the port is taken. `stop.sh` kills it by PID and cleans up.

## Config

Environment variables: `DASH_HOST` (default 127.0.0.1), `DASH_PORT` (default 9077), `DOCKER_BIN` (default /usr/local/bin/docker).

**Don't set `DASH_HOST=0.0.0.0`.** There's no login. The dashboard can stop and restart containers, so anyone who can reach the port can too. The localhost-only bind is the security model. The `Host` header check also rejects any address except localhost, so exposing it to the network wouldn't work cleanly anyway. If you need remote access, put it behind an SSH tunnel (`ssh -L 9077:localhost:9077 yourhost`).
