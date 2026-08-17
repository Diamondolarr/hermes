#!/bin/sh
set -eu

export PORT="${PORT:-80}"
export HOSTNAME="${HOSTNAME:-0.0.0.0}"

envsubst '${PORT}' < /etc/nginx/templates/default.conf.template > /etc/nginx/conf.d/default.conf

uvicorn app.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID="$!"

node /app/frontend/server.js --hostname 127.0.0.1 --port 3000 &
FRONTEND_PID="$!"

shutdown() {
    kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap shutdown INT TERM

nginx -g "daemon off;" &
NGINX_PID="$!"

wait "$NGINX_PID"
