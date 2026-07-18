#!/usr/bin/env bash
set -euo pipefail

compose=(docker compose)
duration="${DURATION_SECONDS:-15}"
rate="${RATE_PER_SECOND:-200}"
victim="${VICTIM_SERVICE:-decoder2}"
output="${OUTPUT_FILE:-fault-tolerance-results.txt}"

cleanup() {
    "${compose[@]}" start "$victim" >/dev/null 2>&1 || true
}
trap cleanup EXIT

if ! docker info >/dev/null 2>&1; then
    echo "Docker is not running; start Docker Desktop and retry." >&2
    exit 1
fi

"${compose[@]}" up -d --build nginx decoder1 decoder2 decoder3

for _ in {1..30}; do
    if curl --fail --silent http://localhost:8080/health >/dev/null; then
        break
    fi
    sleep 1
done
curl --fail --silent http://localhost:8080/health >/dev/null

make tools
./load_generator --host localhost --port 8080 --rate "$rate" --duration "$duration" >"$output" 2>&1 &
load_pid=$!

sleep 3
"${compose[@]}" stop "$victim"

set +e
wait "$load_pid"
load_status=$?
set -e

success_line=$(grep -E 'Success Rate:' "$output" | tail -1 || true)
failed_line=$(grep -E 'Failed:' "$output" | tail -1 || true)

{
    echo
    echo "Fault injection: stopped $victim while load was active"
    echo "Load generator exit status: $load_status"
    echo "${success_line:-Success Rate: unavailable}"
    echo "${failed_line:-Failed: unavailable}"
} | tee -a "$output"

test "$load_status" -eq 0
test -n "$success_line"
test -n "$failed_line"
failed_count=$(printf '%s\n' "$failed_line" | awk '{print $2}')
test "$failed_count" -eq 0
