# docker-dashboard

One page that shows every Docker container on this Mac, its image, and its ports. Refreshes every 5 seconds.

```
./start.sh     # then open http://localhost:9077
./stop.sh
```

- Published ports (`:8081 → 8081/tcp`) are clickable links to `http://localhost:<port>`.
- Ports that are exposed but not published to the host show dimmed.
- "show stopped" toggles exited containers.

## How it works

`server.py` is stdlib-only Python. It runs `docker ps -a` and serves JSON at `/api/containers` and the page at `/`. It binds to 127.0.0.1 only.

`start.sh` runs it in the background with a PID file (`dashboard.pid`) and logs to `dashboard.log`. It refuses to start if it's already running or if the port is taken. `stop.sh` kills it by PID and cleans up.

## Config

Environment variables: `DASH_HOST` (default 127.0.0.1), `DASH_PORT` (default 9077), `DOCKER_BIN` (default /usr/local/bin/docker).
