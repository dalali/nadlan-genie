#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── helpers ────────────────────────────────────────────────────────────────────

usage() {
  cat <<EOF
Usage: ./run.sh <command>

Commands:
  start         Build and start all services (foreground, with logs)
  up            Build and start all services in the background
  stop          Stop all running services
  restart       Stop, rebuild, and start in the background
  logs          Follow logs from all services (or: logs backend / logs frontend)
  build         Rebuild all Docker images without starting
  status        Show running container status
  test          Run the backend test suite inside a one-off container
  psql          Open a psql shell on the Postgres container
  shell         Open a bash shell on the backend container
  scan          Run a scan: ./run.sh scan [city] [rooms_min] [rooms_max] [price_max] [threshold]
  import        Import a transaction CSV: ./run.sh import /path/to/file.csv
  clean         Stop services and delete all volumes (wipes DB)
  help          Show this message

Examples:
  ./run.sh start               # first-time setup: builds & starts everything
  ./run.sh up                  # start in background
  ./run.sh logs backend        # tail backend logs only
  ./run.sh scan                          # default: Ramat Gan, 3-4 rooms, <=3M, 20%
  ./run.sh scan "Tel Aviv"               # Tel Aviv with defaults
  ./run.sh scan "Jerusalem" 2 3 2500000  # Jerusalem, 2-3 rooms, <=2.5M
  ./run.sh scan "Haifa" 3 4 2000000 0.15 # Haifa, custom threshold
  ./run.sh import ./data.csv   # load real transaction data
EOF
}

ensure_env() {
  if [ ! -f .env ]; then
    if [ -f .env.example ]; then
      cp .env.example .env
      echo "✓ Created .env from .env.example (edit it to customise)"
    else
      echo "✗ Neither .env nor .env.example found" >&2
      exit 1
    fi
  fi
}

require_running() {
  if ! docker compose ps --services --filter status=running 2>/dev/null | grep -q backend; then
    echo "✗ Backend is not running. Start it first: ./run.sh up" >&2
    exit 1
  fi
}

backend_url() {
  local port
  port=$(grep -E '^BACKEND_PORT=' .env 2>/dev/null | cut -d= -f2 | tr -d ' ')
  echo "http://localhost:${port:-8000}"
}

# ── commands ───────────────────────────────────────────────────────────────────

cmd_start() {
  ensure_env
  echo "→ Building and starting nadlan-genie (Ctrl-C to stop)…"
  docker compose up --build
}

cmd_up() {
  ensure_env
  echo "→ Building and starting nadlan-genie in the background…"
  docker compose up --build -d
  echo ""
  echo "  Frontend : http://localhost:$(grep FRONTEND_PORT .env | cut -d= -f2)"
  echo "  Backend  : $(backend_url)"
  echo "  Health   : $(backend_url)/health"
  echo ""
  echo "  ./run.sh logs     — follow all logs"
  echo "  ./run.sh scan     — run a test scan"
  echo "  ./run.sh stop     — shut down"
}

cmd_stop() {
  echo "→ Stopping services…"
  docker compose down
}

cmd_restart() {
  ensure_env
  echo "→ Restarting…"
  docker compose down
  docker compose up --build -d
  echo "✓ Restarted"
}

cmd_logs() {
  local service="${1:-}"
  if [ -n "$service" ]; then
    docker compose logs -f "$service"
  else
    docker compose logs -f
  fi
}

cmd_build() {
  ensure_env
  echo "→ Building images…"
  docker compose build
  echo "✓ Build complete"
}

cmd_status() {
  docker compose ps
}

cmd_test() {
  ensure_env
  echo "→ Running backend tests…"
  docker compose run --rm backend pytest -q
}

cmd_psql() {
  local user
  user=$(grep -E '^POSTGRES_USER=' .env | cut -d= -f2)
  local db
  db=$(grep -E '^POSTGRES_DB=' .env | cut -d= -f2)
  docker compose exec postgres psql -U "$user" -d "$db"
}

cmd_shell() {
  docker compose exec backend bash
}

cmd_scan() {
  local city="${1:-Ramat Gan}"
  local rooms_min="${2:-3}"
  local rooms_max="${3:-4}"
  local price_max="${4:-3000000}"
  local threshold="${5:-0.2}"

  require_running
  local url
  url="$(backend_url)/scan"
  echo "→ Scanning: $city | rooms ${rooms_min}-${rooms_max} | max ₪$(printf '%,.0f' "$price_max") | ${threshold} discount threshold…"
  echo ""

  local body
  body=$(python3 -c "import json; print(json.dumps({'city':'$city','rooms_min':$rooms_min,'rooms_max':$rooms_max,'price_max':$price_max,'max_pages':3,'discount_threshold':$threshold}))")

  local scan_id
  scan_id=$(curl -sf -X POST "$url" \
    -H "Content-Type: application/json" \
    -d "$body" \
    | python3 -c "import sys,json; print(json.load(sys.stdin)['scan_id'])")

  echo "  Scan ID: $scan_id"
  echo "  Polling for results…"

  local status="queued"
  local attempts=0
  while [ "$status" = "queued" ] || [ "$status" = "running" ]; do
    sleep 2
    local resp
    resp=$(curl -sf "$(backend_url)/scan/$scan_id")
    status=$(echo "$resp" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")
    attempts=$((attempts + 1))
    printf "  [%ds] status: %s\r" "$((attempts * 2))" "$status"
    if [ $attempts -ge 30 ]; then
      echo ""
      echo "✗ Timed out waiting for scan to complete" >&2
      exit 1
    fi
  done

  echo ""
  echo ""
  curl -sf "$(backend_url)/results?scan_id=$scan_id" | python3 -c "
import sys, json

data = json.load(sys.stdin)
results = data if isinstance(data, list) else data.get('results', [])

if not results:
    print('No qualifying listings found.')
    sys.exit(0)

print(f'Found {len(results)} qualifying deal(s):')
print()
for r in results:
    print(f'  Address  : {r.get(\"address\") or r.get(\"listing\", {}).get(\"address\", \"N/A\")}')
    print(f'  Asking   : ₪{r.get(\"asking_price\", r.get(\"price\", 0)):,.0f}  ({r.get(\"sqm\", \"?\")} m²  {r.get(\"rooms\", \"?\")} rooms)')
    ppsqm = r.get(\"asking_price_per_sqm\") or r.get(\"price_per_sqm\", 0)
    est_ppsqm = r.get(\"estimated_price_per_sqm\", 0)
    print(f'  ₪/m²     : asking {ppsqm:,.0f}  vs  market {est_ppsqm:,.0f}')
    print(f'  Est value: ₪{r.get(\"estimated_value\", 0):,.0f}')
    print(f'  Discount : {r.get(\"discount_percent\", 0) * 100:.1f}%')
    print(f'  Confidence: {r.get(\"confidence\", \"?\")}  ({r.get(\"comparable_count\", \"?\")} comparables)')
    print(f'  URL      : {r.get(\"url\", \"N/A\")}')
    print()
"
}

cmd_import() {
  local file="${1:-}"
  if [ -z "$file" ]; then
    echo "Usage: ./run.sh import /path/to/transactions.csv" >&2
    exit 1
  fi
  if [ ! -f "$file" ]; then
    echo "✗ File not found: $file" >&2
    exit 1
  fi
  require_running
  echo "→ Importing $file…"
  curl -sf -X POST "$(backend_url)/import-transactions" \
    -F "file=@$file" \
    | python3 -m json.tool
}

cmd_clean() {
  echo "⚠ This will delete all data (Postgres volume included)."
  read -r -p "  Are you sure? [y/N] " confirm
  if [[ "$confirm" =~ ^[Yy]$ ]]; then
    docker compose down -v
    echo "✓ Cleaned"
  else
    echo "Aborted"
  fi
}

# ── dispatch ───────────────────────────────────────────────────────────────────

COMMAND="${1:-help}"
shift || true

case "$COMMAND" in
  start)    cmd_start ;;
  up)       cmd_up ;;
  stop)     cmd_stop ;;
  restart)  cmd_restart ;;
  logs)     cmd_logs "$@" ;;
  build)    cmd_build ;;
  status)   cmd_status ;;
  test)     cmd_test ;;
  psql)     cmd_psql ;;
  shell)    cmd_shell ;;
  scan)     cmd_scan "$@" ;;
  import)   cmd_import "$@" ;;
  clean)    cmd_clean ;;
  help|--help|-h) usage ;;
  *)
    echo "✗ Unknown command: $COMMAND" >&2
    echo ""
    usage
    exit 1
    ;;
esac
