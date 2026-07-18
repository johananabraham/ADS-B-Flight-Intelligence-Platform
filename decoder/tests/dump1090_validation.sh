#!/usr/bin/env bash
set -euo pipefail

for command in dump1090 jq nc; do
    command -v "$command" >/dev/null || {
        echo "Required command not found: $command" >&2
        exit 1
    }
done

raw_port="${DUMP1090_RAW_PORT:-31001}"
json_dir=$(mktemp -d)
dump_pid=""

cleanup() {
    test -z "$dump_pid" || kill "$dump_pid" >/dev/null 2>&1 || true
    rm -rf "$json_dir"
}
trap cleanup EXIT

make modes_decode >/dev/null

dump1090 --net-only --net-bind-address 127.0.0.1 \
    --net-ri-port "$raw_port" --net-ro-port "$((raw_port + 1))" \
    --net-sbs-port "$((raw_port + 2))" --net-bi-port "$((raw_port + 3))" \
    --net-bo-port "$((raw_port + 4))" --write-json "$json_dir" \
    --write-json-every 0.5 >"$json_dir/dump1090.log" 2>&1 &
dump_pid=$!

sleep 1
for _ in {1..4}; do
    printf '%s\n' \
        '*8D4840D6202CC371C32CE0576098;' \
        '*8D40621D58C382D690C8AC2863A7;' \
        '*8D40621D58C386435CC412692AD6;' \
        '*8D485020994409940838175B284F;' | nc 127.0.0.1 "$raw_port"
done

for _ in {1..20}; do
    test -f "$json_dir/aircraft.json" && break
    sleep 0.25
done
test -f "$json_dir/aircraft.json"

ours_id=$(./modes_decode 8D4840D6202CC371C32CE0576098)
ours_pos=$(./modes_decode 8D40621D58C382D690C8AC2863A7)
ours_vel=$(./modes_decode 8D485020994409940838175B284F)

ours_callsign=$(awk -F ': ' '/Callsign:/ {print $2}' <<<"$ours_id")
ours_altitude=$(awk '/Altitude:/ {print $2}' <<<"$ours_pos")
ours_speed=$(awk '/Ground Speed:/ {print $3}' <<<"$ours_vel")
ours_heading=$(awk '/Heading:/ {gsub(/°/, "", $2); print $2}' <<<"$ours_vel")
ours_rate=$(awk '/Vertical Rate:/ {print $3}' <<<"$ours_vel")

dump_callsign=$(jq -r '.aircraft[] | select(.hex == "4840d6") | .flight | sub(" +$"; "")' "$json_dir/aircraft.json")
dump_altitude=$(jq -r '.aircraft[] | select(.hex == "40621d") | .alt_baro' "$json_dir/aircraft.json")
dump_speed=$(jq -r '.aircraft[] | select(.hex == "485020") | .gs' "$json_dir/aircraft.json")
dump_heading=$(jq -r '.aircraft[] | select(.hex == "485020") | .track' "$json_dir/aircraft.json")
dump_rate=$(jq -r '.aircraft[] | select(.hex == "485020") | .geom_rate' "$json_dir/aircraft.json")

test "$ours_callsign" = "$dump_callsign"
test "$ours_altitude" = "$dump_altitude"
test "$ours_rate" = "$dump_rate"
awk -v ours="$ours_speed" -v reference="$dump_speed" \
    'BEGIN { difference = ours-reference; if (difference < 0) difference = -difference; exit !(difference <= 0.1) }'
awk -v ours="$ours_heading" -v reference="$dump_heading" \
    'BEGIN { difference = ours-reference; if (difference < 0) difference = -difference; exit !(difference <= 0.1) }'

printf 'dump1090 comparison passed\n'
printf '  callsign:      %s\n' "$ours_callsign"
printf '  altitude:      %s ft\n' "$ours_altitude"
printf '  ground speed:  %s kt (dump1090: %s)\n' "$ours_speed" "$dump_speed"
printf '  heading:       %s degrees (dump1090: %s)\n' "$ours_heading" "$dump_heading"
printf '  vertical rate: %s ft/min\n' "$ours_rate"
