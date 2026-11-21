#!/usr/bin/env bash
# QuickPick backend in one command (Git Bash on Windows, macOS, Linux).
#   ./run.sh           local: http://localhost:8000, calls ring in the browser
#   ./run.sh phone     plus a public HTTPS tunnel (cloudflared): Twilio/Exotel phone calls and the app on your phone
#   PORT=9000 ./run.sh       BUILD=1 ./run.sh  (rebuild the web UI)
# Ctrl+C stops everything (server, tunnel and the Swiggy/Zepto bridges).
set -euo pipefail
cd "$(dirname "$0")"
PORT="${PORT:-8000}"
MODE="${1:-local}"
LOG=".server-$PORT.log"

if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe
elif [ -x .venv/bin/python ]; then PY=.venv/bin/python
else
  echo "Creating .venv and installing requirements ..."
  if command -v python3 >/dev/null 2>&1; then python3 -m venv .venv; else python -m venv .venv; fi
  if [ -x .venv/Scripts/python.exe ]; then PY=.venv/Scripts/python.exe; else PY=.venv/bin/python; fi
  "$PY" -m pip install -q -r requirements.txt
fi

[ -f .env ] || { echo "No .env. Run: cp .env.example .env  and add OPENAI_API_KEY"; exit 1; }
[ -f household.yaml ] || { echo "No household.yaml. Run: cp household.example.yaml household.yaml  and fill it in"; exit 1; }

if [ ! -f web/dist/index.html ] || [ "${BUILD:-0}" = 1 ]; then
  echo "Building the web UI ..."
  (cd web && { [ -d node_modules ] || npm install; } && npm run build)
fi

export PYTHONIOENCODING=utf-8 PYTHONUNBUFFERED=1
PIDS=()

stop_all() {
  trap - EXIT INT TERM
  for p in "${PIDS[@]:-}"; do
    [ -n "$p" ] || continue
    if [ -r "/proc/$p/winpid" ] && command -v taskkill >/dev/null 2>&1; then
      taskkill //PID "$(cat "/proc/$p/winpid")" //T //F >/dev/null 2>&1 || true   # Windows: the whole tree
    else
      pkill -TERM -P "$p" 2>/dev/null || true
      kill "$p" 2>/dev/null || true
    fi
  done
  if [ "$MODE" = phone ]; then                                                  # back to browser calls
    "$PY" -c "import sys; sys.path.insert(0, 'scripts'); import phone; phone.set_env({'CALL_MODE': 'browser'})" || true
  fi
  echo "Stopped."
}
trap stop_all EXIT INT TERM

if [ "$MODE" = phone ]; then
  : > .phone.log
  "$PY" scripts/phone.py "$PORT" > .phone.log 2>&1 &
  PIDS+=($!)
  echo "Opening the tunnel ..."
  for _ in $(seq 60); do grep -q "Now (re)start" .phone.log && break; sleep 1; done
  grep -q "Now (re)start" .phone.log || { echo "The tunnel did not start:"; tail -20 .phone.log; exit 1; }
  grep -v -E " (INF|WRN|ERR) |^Now \(re\)start|^Ctrl\+C" .phone.log || true
else
  export CALL_MODE=browser                                                       # overrides a stale value in .env
fi

echo "Starting QuickPick on http://localhost:$PORT (logs in $LOG) ..."
"$PY" -m uvicorn app.main:app --port "$PORT" > "$LOG" 2>&1 &
PIDS+=($!)
for _ in $(seq 90); do
  code=$(curl -s -o /dev/null -w "%{http_code}" "http://localhost:$PORT/api/state" || true)
  [ "$code" = 200 ] || [ "$code" = 401 ] && break
  sleep 1
done
echo "QuickPick is up: http://localhost:$PORT$([ "$MODE" = phone ] && echo ' (on your phone: the link above)')"
echo "Logs: tail -f $LOG    Ctrl+C stops everything."
wait -n "${PIDS[@]}" || true                                                     # one stopped: stop the rest
