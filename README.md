# docker-dashboard

One page that shows every Docker container on this Mac, its image, and its ports. Refreshes every 5 seconds.

```
./start.sh     # then open http://localhost:9077
./stop.sh
```

On a new machine: `git clone` the repo, make sure `docker` works from your shell, and run `./start.sh`. It runs on macOS and Linux. The docker binary is found on your `PATH` (or set `DOCKER_BIN`, see Config). Needs Python 3, nothing else to install.

- Published ports (`:8081 → 8081/tcp`) are clickable links to `http://localhost:<port>`.
- Ports that are exposed but not published to the host show dimmed.
- "show stopped" toggles exited containers.
- The page is a horizontal split, containers on top and "Other listening ports" below, each pane with its own scroll bar and a sticky header, and a draggable divider between them (the position is remembered in the browser). The bottom pane lists every other TCP port something on this machine is listening on (process, pid, and whether it's loopback-only or on all interfaces), each with an **open** button to `http://localhost:<port>`. Docker's own published ports are left out since they're already above. Plenty of these aren't web servers (3270, SSH, databases), so open will only work for the HTTP ones. A **Traffic** column flags **RX** (receiving) and **TX** (transmitting) when an established connection to that port moved bytes between 5 second refreshes. A flag holds until later traffic changes it (so a port that last received stays on RX until it transmits), and ports with no traffic seen since the server started show idle. It reads per-connection byte counters (`netstat -anb` on macOS, `ss -ti` on Linux), and the first refresh after startup has no baseline.
- Each row has buttons: running containers get **stop** and **restart**, stopped ones get **start**.

## How it works

`server.py` is stdlib-only Python. It runs `docker ps -a` and serves JSON at `/api/containers`, `/api/ports` (from `lsof` on macOS, `ss` on Linux), and the page at `/`. It binds to 127.0.0.1 by default.

Start/stop/restart go through `POST /api/containers/<id>/<action>`. Because any web page can fire requests at localhost, the server only accepts POSTs that carry an `X-Dashboard: 1` header (which forces a CORS preflight it never approves) and a recognized `Host` header (blocks DNS rebinding) — loopback values by default, plus whatever `DASH_ALLOWED_HOSTS` opts in. It also only acts on container IDs it just listed from docker.

`start.sh` runs it in the background with a PID file (`dashboard.pid`) and logs to `dashboard.log`. It refuses to start if it's already running or if the port is taken. `stop.sh` kills it by PID and cleans up.

## Config

Environment variables: `DASH_HOST` (default 127.0.0.1), `DASH_PORT` (default 9077), `DASH_ALLOWED_HOSTS` (comma-separated extra `Host` header values to accept — see below), `DOCKER_BIN` (default: `docker` from `PATH`), plus `LSOF_BIN`, `NETSTAT_BIN` and `SS_BIN` if those tools live somewhere odd.

**Default is loopback-only, on purpose.** There's no login. The dashboard can stop and restart containers, so anyone who can reach the port can too. The `Host` header check also rejects any address except localhost by default, so just setting `DASH_HOST=0.0.0.0` wouldn't even work cleanly on its own. If you need remote access without accepting that tradeoff, put it behind an SSH tunnel instead (`ssh -L 9077:localhost:9077 yourhost`).

**Deliberately exposing it to your LAN:** `./start.sh --lan <ip>` sets `DASH_HOST=0.0.0.0` and adds `<ip>` to the accepted `Host` values, so it's reachable at `http://<ip>:$DASH_PORT`. Only do this on a network you actually trust — anyone who can reach that port gets unauthenticated start/stop/restart control over every container on the box. The flag prints that warning every time, on purpose.

## Running on a headless Linux server

Needs Python 3 and a user that can run `docker ps` (in the `docker` group). `iproute2` (`ss`) ships with Ubuntu. On Linux, process names in the ports pane only show for sockets your user owns, so run it as root if you want every one (otherwise they show `?`). Then, from your desktop:

```bash
ssh -L 9077:localhost:9077 user@server-ip
```

and open `http://localhost:9077`. The port **open** links point at `localhost` on whatever machine your browser is on, so they only work for ports you also forward.

## Running on boot (systemd)

```bash
sudo cp deploy/docker-dashboard.service /etc/systemd/system/docker-dashboard.service
# edit User=, WorkingDirectory=, and the Environment= lines to match your box
sudo systemctl daemon-reload
sudo systemctl enable --now docker-dashboard.service
```

Runs `server.py` directly instead of through `start.sh` — systemd already handles backgrounding and restart-on-crash, so `start.sh`'s own PID-file tracking would just duplicate that. Set `DASH_ALLOWED_HOSTS` in the unit only if you've deliberately decided to expose this past loopback (see the `--lan` note above) — leave it unset to stay loopback-only.
