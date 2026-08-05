#!/usr/bin/env bash
set -euo pipefail

project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
scratch_dir="$(mktemp -d)"
broker_name="adsb-edge-mqtt-security-test"
network_name="adsb-edge-mqtt-security-test"
image="eclipse-mosquitto:2.0.22-openssl"

cleanup() {
  docker rm -f "$broker_name" >/dev/null 2>&1 || true
  docker network rm "$network_name" >/dev/null 2>&1 || true
  rm -rf "${scratch_dir:?}"
}
trap cleanup EXIT

EDGE_SECRET_DIR="$scratch_dir" EDGE_RUNTIME_UID="$(id -u)" EDGE_RUNTIME_GID="$(id -g)" \
  "${project_root}/scripts/provision_edge_mqtt.sh" "$broker_name"
docker network create "$network_name" >/dev/null
docker run -d --name "$broker_name" --network "$network_name" \
  --user "$(id -u):$(id -g)" \
  -v "${project_root}/edge/mosquitto/config:/mosquitto/config:ro" \
  -v "${scratch_dir}:/mosquitto/secrets:ro" "$image" >/dev/null

for _attempt in $(seq 1 30); do
  if docker logs "$broker_name" 2>&1 | grep -q "mosquitto version .* running"; then
    break
  fi
  sleep 1
done
docker logs "$broker_name" 2>&1 | grep -q "mosquitto version .* running"

node_password="$(tr -d '\r\n' < "${scratch_dir}/roof-node-1.password")"
consumer_password="$(tr -d '\r\n' < "${scratch_dir}/station-consumer.password")"
client=(docker run --rm --network "$network_name" -v "${scratch_dir}/ca.crt:/ca.crt:ro" "$image")

# Authenticated station can write its own telemetry topic over verified TLS.
"${client[@]}" mosquitto_pub -V 5 --cafile /ca.crt -h "$broker_name" -p 8883 \
  -u roof-node-1 -P "$node_password" \
  -t adsb/stations/v1/roof-node-1/telemetry -q 1 -m '{}'

# Anonymous TLS connections are rejected.
if "${client[@]}" mosquitto_pub -V 5 --cafile /ca.crt -h "$broker_name" -p 8883 \
  -t adsb/stations/v1/roof-node-1/telemetry -q 1 -m '{}'; then
  echo "anonymous publish unexpectedly succeeded" >&2
  exit 1
fi

# The same station cannot impersonate another node's topic.
if "${client[@]}" mosquitto_pub -V 5 --cafile /ca.crt -h "$broker_name" -p 8883 \
  -u roof-node-1 -P "$node_password" \
  -t adsb/stations/v1/other-node/telemetry -q 1 -m '{}'; then
  echo "cross-node publish unexpectedly succeeded" >&2
  exit 1
fi

# The fleet consumer cannot publish station messages.
if "${client[@]}" mosquitto_pub -V 5 --cafile /ca.crt -h "$broker_name" -p 8883 \
  -u station-consumer -P "$consumer_password" \
  -t adsb/stations/v1/roof-node-1/telemetry -q 1 -m '{}'; then
  echo "read-only consumer publish unexpectedly succeeded" >&2
  exit 1
fi

echo "MQTT TLS, authentication, cross-node ACL, and read-only consumer checks passed."
