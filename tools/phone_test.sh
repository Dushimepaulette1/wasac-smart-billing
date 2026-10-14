#!/usr/bin/env bash
# Test on a phone: run the backend, the household app and the staff portal on this laptop and
# publish both sites over HTTPS with free Cloudflare quick tunnels (no account). Works only while
# this script runs; the links change every time. Stop with Ctrl+C.
#
#   tools/phone_test.sh
#
# Needs: backend/.venv, backend/.env (DATABASE_URL), the model weights in backend/ml
# (scripts/download_models.py), frontend/node_modules, and cloudflared on PATH or in ~/.local/bin.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOGS="$(mktemp -d)"
CLOUDFLARED="$(command -v cloudflared || echo "$HOME/.local/bin/cloudflared")"
pids=()
cleanup() { kill "${pids[@]}" 2>/dev/null || true; echo; echo "Stopped. Logs were in $LOGS"; }
trap cleanup EXIT INT TERM

wait_for() {  # wait_for URL SECONDS NAME
  for _ in $(seq 1 "$2"); do curl -fs -o /dev/null "$1" && return 0; sleep 2; done
  echo "$3 did not start; see $LOGS"; exit 1
}

start_tunnel() {  # start_tunnel PORT NAME (in this shell, so cleanup can stop it)
  "$CLOUDFLARED" tunnel --no-autoupdate --url "http://127.0.0.1:$1" >"$LOGS/tunnel-$2.log" 2>&1 &
  pids+=($!)
}

tunnel_link() {  # tunnel_link NAME -> prints the https link
  local url=""
  for _ in $(seq 1 30); do
    url="$(grep -oE 'https://[a-z0-9-]+\.trycloudflare\.com' "$LOGS/tunnel-$1.log" | head -1 || true)"
    [ -n "$url" ] && break
    sleep 1
  done
  [ -n "$url" ] || { echo "No tunnel link for $1; see $LOGS/tunnel-$1.log" >&2; exit 1; }
  echo "$url"
}

echo "Starting the backend (loading the models can take a minute or two)..."
cd "$ROOT/backend"
# Never create the sample customers in the shared database; it holds DEMO- households only.
SEED_SAMPLE_DATA=0 .venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000 >"$LOGS/backend.log" 2>&1 &
pids+=($!)
wait_for http://127.0.0.1:8000/health 150 "The backend"

echo "Building the household app (demo household) and the staff portal..."
cd "$ROOT/frontend"
VITE_CUSTOMER_ID=DEMO-CUST-001 VITE_METER_ID=DEMO-MTR-001 npm run -s build >"$LOGS/build.log" 2>&1
npm run -s build:staff >"$LOGS/build-staff.log" 2>&1
npx vite preview --host 127.0.0.1 >"$LOGS/frontend.log" 2>&1 &
pids+=($!)
VITE_APP=staff npx vite preview --host 127.0.0.1 >"$LOGS/staff.log" 2>&1 &
pids+=($!)
wait_for http://127.0.0.1:3000/ 30 "The household app"
wait_for http://127.0.0.1:3001/ 30 "The staff portal"

echo "Opening the tunnels..."
start_tunnel 3000 household
start_tunnel 3001 staff
household="$(tunnel_link household)"
staff="$(tunnel_link staff)"

echo
echo "  Household app (phone):  $household"
echo "  Staff portal:           $staff"
echo "  Health:                 $household/health"
echo
echo "Keep this window open. Ctrl+C stops everything."
wait
