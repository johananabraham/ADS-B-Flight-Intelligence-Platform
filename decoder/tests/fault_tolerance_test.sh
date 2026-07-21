#!/usr/bin/env bash
set -euo pipefail

compose=(docker compose)
duration="${DURATION_SECONDS:-15}"
rate="${RATE_PER_SECOND:-200}"
victim="${VICTIM_SERVICE:-decoder2}"
output="${OUTPUT_FILE:-fault-tolerance-results.txt}"
minimum_success_rate="${MINIMUM_SUCCESS_RATE:-99.0}"

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
post_failure_health=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    http://localhost:8080/health || true)

set +e
wait "$load_pid"
load_status=$?
set -e

success_line=$(grep -E 'Success Rate:' "$output" | tail -1 || true)
failed_line=$(grep -E 'Failed:' "$output" | tail -1 || true)
success_rate=$(printf '%s\n' "$success_line" | awk '{gsub(/%/, "", $3); print $3}')
final_health=$(curl --silent --output /dev/null --write-out '%{http_code}' \
    http://localhost:8080/health || true)

{
    echo
    echo "Fault injection: stopped $victim while load was active"
    echo "Load generator exit status: $load_status"
    echo "Health immediately after fault: HTTP $post_failure_health"
    echo "Health after load completed: HTTP $final_health"
    echo "${success_line:-Success Rate: unavailable}"
    echo "${failed_line:-Failed: unavailable}"
} | tee -a "$output"

test "$load_status" -eq 0
test -n "$success_line"
test -n "$failed_line"
test "$post_failure_health" = "200"
test "$final_health" = "200"
awk -v actual="$success_rate" -v minimum="$minimum_success_rate" \
    'BEGIN { exit !(actual >= minimum) }'
