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
- Each row has buttons: running containers get **stop** and **restart**, stopped ones get **start**.

## How it works

`server.py` is stdlib-only Python. It runs `docker ps -a` and serves JSON at `/api/containers` and the page at `/`. It binds to 127.0.0.1 only.

Start/stop/restart go through `POST /api/containers/<id>/<action>`. Because any web page can fire requests at localhost, the server only accepts POSTs that carry an `X-Dashboard: 1` header (which forces a CORS preflight it never approves) and a localhost `Host` header (blocks DNS rebinding). It also only acts on container IDs it just listed from docker.

`start.sh` runs it in the background with a PID file (`dashboard.pid`) and logs to `dashboard.log`. It refuses to start if it's already running or if the port is taken. `stop.sh` kills it by PID and cleans up.

## Config

Environment variables: `DASH_HOST` (default 127.0.0.1), `DASH_PORT` (default 9077), `DOCKER_BIN` (default /usr/local/bin/docker).
