#!/bin/sh
set -eu

export PORT="${PORT:-80}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"

envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

/opt/venv/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID="$!"

PORT=3000 HOSTNAME=127.0.0.1 node /app/frontend/server.js &
FRONTEND_PID="$!"

wait_for_port() {
    host="$1"
    port="$2"
    name="$3"
    attempts=0

    until /opt/venv/bin/python - "$host" "$port" <<'PY'
import socket
import sys

sock = socket.socket()
sock.settimeout(0.2)
try:
    sock.connect((sys.argv[1], int(sys.argv[2])))
except OSError:
    sys.exit(1)
finally:
    sock.close()
PY
    do
        attempts=$((attempts + 1))
        if [ "$attempts" -ge 100 ]; then
            echo "$name did not start in time"
            exit 1
        fi
        sleep 0.1
    done
}

wait_for_port 127.0.0.1 8000 FastAPI
wait_for_port 127.0.0.1 3000 Next.js

shutdown() {
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap shutdown INT TERM

nginx -g "daemon off;" &
NGINX_PID="$!"

wait "$NGINX_PID"
