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

EDGE_SECRET_DIR="$scratch_dir" \
  "${project_root}/scripts/provision_edge_mqtt.sh" "$broker_name"
docker network create "$network_name" >/dev/null
node_password="$(docker run --rm --user 0:0 -v "${scratch_dir}:/work:ro" \
  --entrypoint /bin/cat "$image" /work/roof-node-1.password | tr -d '\r\n')"
bridge_password="$(docker run --rm --user 0:0 -v "${scratch_dir}:/work:ro" \
  --entrypoint /bin/cat "$image" /work/roof-node-1-bridge.password | tr -d '\r\n')"
consumer_password="$(docker run --rm --user 0:0 -v "${scratch_dir}:/work:ro" \
  --entrypoint /bin/cat "$image" /work/station-consumer.password | tr -d '\r\n')"
client=(docker run --rm --network "$network_name" -v "${scratch_dir}/ca.crt:/ca.crt:ro" "$image")

broker_ready() {
  "${client[@]}" mosquitto_sub -V 5 --cafile /ca.crt \
    -h "$broker_name" -p 8883 -u station-consumer -P "$consumer_password" \
    -t '$SYS/broker/uptime' -C 1 -W 1 >/dev/null 2>&1
}

publish_is_visible() {
  local username="$1"
  local password="$2"
  local topic="$3"
  local subscriber_pid
  local subscriber_status
  local publisher_auth=()
  if [[ -n "$username" ]]; then
    publisher_auth=(-u "$username" -P "$password")
  fi

  "${client[@]}" mosquitto_sub -V 5 --cafile /ca.crt \
    -h "$broker_name" -p 8883 -u station-consumer -P "$consumer_password" \
    -t "$topic" -C 1 -W 2 >/dev/null 2>&1 &
  subscriber_pid=$!
  sleep 0.25
  "${client[@]}" mosquitto_pub -V 5 --cafile /ca.crt \
    -h "$broker_name" -p 8883 "${publisher_auth[@]}" \
    -t "$topic" -q 1 -m '{}' >/dev/null 2>&1 || true
  if wait "$subscriber_pid"; then
    subscriber_status=0
  else
    subscriber_status=$?
  fi
  [[ "$subscriber_status" -eq 0 ]]
}

docker run -d --name "$broker_name" --network "$network_name" \
  --entrypoint mosquitto \
  -v "${project_root}/edge/mosquitto/config:/mosquitto/config:ro" \
  -v "${scratch_dir}:/mosquitto/secrets:ro" "$image" \
  -c /mosquitto/config/mosquitto.conf >/dev/null

for _attempt in $(seq 1 30); do
  if broker_ready; then
    break
  fi
  sleep 1
done
if ! broker_ready; then
  docker logs "$broker_name" >&2
  exit 1
fi

# Authenticated station can write its own telemetry topic over verified TLS.
if ! publish_is_visible roof-node-1 "$node_password" \
  adsb/stations/v1/roof-node-1/telemetry; then
  echo "authorized station publish was not delivered" >&2
  exit 1
fi

# The host bridge can publish only privacy-safe aggregate pipeline health.
if ! publish_is_visible roof-node-1-bridge "$bridge_password" \
  adsb/stations/v1/roof-node-1/pipeline; then
  echo "authorized receiver bridge publish was not delivered" >&2
  exit 1
fi
if publish_is_visible roof-node-1-bridge "$bridge_password" \
  adsb/stations/v1/roof-node-1/telemetry; then
  echo "receiver bridge unexpectedly published firmware telemetry" >&2
  exit 1
fi
if publish_is_visible roof-node-1 "$node_password" \
  adsb/stations/v1/roof-node-1/pipeline; then
  echo "firmware station unexpectedly published receiver pipeline health" >&2
  exit 1
fi

# Anonymous TLS connections are rejected.
if publish_is_visible "" "" adsb/stations/v1/roof-node-1/telemetry; then
  echo "anonymous publish unexpectedly succeeded" >&2
  exit 1
fi

# The same station cannot impersonate another node's topic.
if publish_is_visible roof-node-1 "$node_password" \
  adsb/stations/v1/other-node/telemetry; then
  echo "cross-node publish unexpectedly succeeded" >&2
  exit 1
fi

# The fleet consumer cannot publish station messages.
if publish_is_visible station-consumer "$consumer_password" \
  adsb/stations/v1/roof-node-1/telemetry; then
  echo "read-only consumer publish unexpectedly succeeded" >&2
  exit 1
fi

echo "MQTT TLS, authentication, cross-node ACL, and read-only consumer checks passed."
