# MQTT runtime secrets

This directory intentionally contains no credentials. Before starting the edge
stack, provide files readable by container UID `1883`:

- `ca.crt`: CA certificate trusted by stations and the consumer
- `server.crt`: broker certificate whose SAN matches `MQTT_HOST`
- `server.key`: broker private key
- `passwords`: `mosquitto_passwd` database containing station users and
  `station-consumer`
- `station-consumer.password`: the consumer's plaintext runtime password
- `<node_id>.password`: the corresponding station's provisioning password

Never commit generated files. Production deployments should inject equivalent
files from a secrets manager and use a private network or firewall around port
8883.

For a local deployment, run `scripts/provision_edge_mqtt.sh <broker-hostname>`.
The hostname must be exactly what clients use for TLS verification. Re-run with
`--force` only when intentionally rotating every generated credential.
