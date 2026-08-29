#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 [--force] <broker-hostname-or-ip>" >&2
}

force=false
if [[ "${1:-}" == "--force" ]]; then
  force=true
  shift
fi
if [[ $# -ne 1 || ! "$1" =~ ^[A-Za-z0-9.-]+$ ]]; then
  usage
  exit 2
fi

broker_host="$1"
project_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
secret_dir="${EDGE_SECRET_DIR:-${project_root}/edge/mosquitto/secrets}"
image="eclipse-mosquitto:2.0.22-openssl"
runtime_uid="${EDGE_RUNTIME_UID:-1883}"
runtime_gid="${EDGE_RUNTIME_GID:-1883}"
generated=(ca.key ca.crt ca.srl server.key server.csr server.crt server.ext passwords station-consumer.password roof-node-1.password)

mkdir -p "$secret_dir"
umask 077
for filename in "${generated[@]}"; do
  if [[ -e "${secret_dir}/${filename}" && "$force" != true ]]; then
    echo "refusing to overwrite ${secret_dir}/${filename}; use --force to rotate" >&2
    exit 1
  fi
done
if [[ "$force" == true ]]; then
  for filename in "${generated[@]}"; do
    rm -f "${secret_dir:?}/${filename}"
  done
fi

openssl req -x509 -newkey rsa:3072 -sha256 -nodes -days 365 \
  -subj "/CN=ADS-B Edge Development CA" \
  -keyout "${secret_dir}/ca.key" -out "${secret_dir}/ca.crt"
openssl req -newkey rsa:3072 -sha256 -nodes \
  -subj "/CN=${broker_host}" \
  -keyout "${secret_dir}/server.key" -out "${secret_dir}/server.csr"

if [[ "$broker_host" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  san="DNS:mqtt,DNS:localhost,IP:${broker_host}"
else
  san="DNS:mqtt,DNS:localhost,DNS:${broker_host}"
fi
printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth\n' "$san" > "${secret_dir}/server.ext"
openssl x509 -req -sha256 -days 365 \
  -in "${secret_dir}/server.csr" -CA "${secret_dir}/ca.crt" \
  -CAkey "${secret_dir}/ca.key" -CAcreateserial \
  -extfile "${secret_dir}/server.ext" -out "${secret_dir}/server.crt"

openssl rand -base64 32 > "${secret_dir}/station-consumer.password"
openssl rand -base64 32 > "${secret_dir}/roof-node-1.password"
consumer_password="$(tr -d '\r\n' < "${secret_dir}/station-consumer.password")"
node_password="$(tr -d '\r\n' < "${secret_dir}/roof-node-1.password")"

docker run --rm --user "$(id -u):$(id -g)" \
  -v "${secret_dir}:/work" --entrypoint mosquitto_passwd "$image" \
  -b -c /work/passwords station-consumer "$consumer_password"
docker run --rm --user "$(id -u):$(id -g)" \
  -v "${secret_dir}:/work" --entrypoint mosquitto_passwd "$image" \
  -b /work/passwords roof-node-1 "$node_password"
chmod 0600 "${secret_dir}"/*.key "${secret_dir}"/*.password "${secret_dir}/passwords"
chmod 0755 "${secret_dir}"
chmod 0644 "${secret_dir}/ca.crt" "${secret_dir}/server.crt"
docker run --rm --user 0:0 -v "${secret_dir}:/work" \
  --entrypoint /bin/chown "$image" \
  "${runtime_uid}:${runtime_gid}" \
  /work/server.key /work/passwords /work/station-consumer.password

echo "Generated local MQTT credentials in ${secret_dir}"
echo "Copy ca.crt and roof-node-1.password to the station through a secure channel."
echo "Before physical use, provision for the broker's exact private IPv4 LAN address, then run:"
echo "  MQTT_BIND_ADDRESS=<private-ip> scripts/check_edge_hardware_readiness.py --broker-host <private-ip>"
