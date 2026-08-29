# ESP32 edge-station firmware

This generic ESP-IDF 6.0 firmware turns an ESP32 into a secure health sidecar
for an ADS-B receiver station. It reports station uptime, Wi-Fi RSSI, free heap,
bounded queue depth, reconnect count, boot identity, sequence, and prior
watchdog-reset status. It does **not** receive or decode 1090 MHz ADS-B radio
signals without suitable RF hardware and receiver software.

## Safety and reliability behavior

- MQTT is TLS-only and verifies the broker against the provisioned CA.
- The node ID must match its MQTT username and broker ACL.
- QoS 1 telemetry is held in a bounded 16-message queue; the oldest sample is
  dropped under sustained backpressure instead of exhausting memory.
- A retained online message and MQTT Last Will provide presence evidence.
- UTC is synchronized before any schema-valid event is published.
- Wi-Fi reconnect uses bounded exponential backoff; MQTT reconnect is handled
  by ESP-MQTT.
- The telemetry task feeds the ESP-IDF task watchdog.

## Build and flash

1. Choose the host's exact private LAN address. Do not expose the MQTT port on a
   public address or use `0.0.0.0`. Generate a certificate for the same address:

   ```bash
   scripts/provision_edge_mqtt.sh <broker-hostname-or-lan-ip>
   ```

2. Run the physical-deployment preflight. It verifies the private bind, certificate
   SAN and expiry, credential permissions, and least-privilege station ACL without
   printing any secrets:

   ```bash
   MQTT_BIND_ADDRESS=<exact-private-lan-ip> \
     scripts/check_edge_hardware_readiness.py \
     --broker-host <same-lan-ip-or-certificate-hostname>
   ```

   A numeric broker host must equal `MQTT_BIND_ADDRESS`. If using a hostname, it
   must resolve to that interface for the ESP32 and appear in the certificate SAN.
   Restrict TCP 8883 to the trusted LAN in the host firewall.

3. Copy the generated public CA into the firmware project:

   ```bash
   cp edge/mosquitto/secrets/ca.crt firmware/esp32-station/certs/broker_ca.pem
   ```

4. Start the broker on only that interface:

   ```bash
   MQTT_BIND_ADDRESS=<exact-private-lan-ip> \
     docker compose -f docker-compose.yml -f docker-compose.edge.yml up --build -d
   ```

5. With ESP-IDF 6.0.2 installed, configure secrets locally and build:

   ```bash
   cd firmware/esp32-station
   idf.py set-target esp32
   idf.py menuconfig
   idf.py build
   idf.py -p <serial-port> flash monitor
   ```

Under `ADS-B edge station`, set the Wi-Fi credentials, `mqtts://` broker URI,
node ID, username, and generated node password. The node ID must be 1–63
lowercase letters, digits, or hyphens, begin with a letter or digit, and exactly
match the MQTT username. `sdkconfig` and the provisioned
CA are ignored by Git because they contain deployment-specific material.

The broker's compose default remains `127.0.0.1` for simulator-only use. A physical
station therefore requires the explicit private `MQTT_BIND_ADDRESS` above. Never
forward port 8883 from an internet router and never commit `sdkconfig`, passwords,
private keys, or the provisioned CA.

## Correlate the receiver pipeline

The ESP32 cannot directly observe the USB SDR, dump1090, or the feeder sidecar. Run
the host bridge on the same computer as the sidecar to publish only aggregate
connection, freshness, queue, drop, and reconnect metrics. Its HTTP input is
fail-closed to loopback and its separate MQTT account can write only the station's
`pipeline` topic:

```bash
STATION_NODE_ID=roof-node-1 \
PIPELINE_MQTT_PASSWORD_FILE=edge/mosquitto/secrets/roof-node-1-bridge.password \
MQTT_CA_CERT=edge/mosquitto/secrets/ca.crt \
MQTT_HOST=<exact-private-lan-ip> \
PYTHONPATH=backend:. python3 -m services.edge_telemetry.receiver_bridge
```

The bridge never publishes SBS frames, aircraft identifiers, callsigns, coordinates,
receiver labels, or receiver location. If the local sidecar cannot be reached or its
health response is invalid, it publishes `DISCONNECTED` rather than inventing a
healthy result.

Physical RF coexistence, power stability, long-duration reconnect behavior,
and watchdog recovery still require testing on the user's exact ESP32 board.
