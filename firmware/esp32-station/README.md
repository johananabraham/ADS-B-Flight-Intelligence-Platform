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

1. Generate broker credentials from the repository root:

   ```bash
   scripts/provision_edge_mqtt.sh <broker-hostname-or-lan-ip>
   ```

2. Copy the generated public CA into the firmware project:

   ```bash
   cp edge/mosquitto/secrets/ca.crt firmware/esp32-station/certs/broker_ca.pem
   ```

3. With ESP-IDF 6.0.2 installed, configure secrets locally and build:

   ```bash
   cd firmware/esp32-station
   idf.py set-target esp32
   idf.py menuconfig
   idf.py build
   idf.py -p <serial-port> flash monitor
   ```

Under `ADS-B edge station`, set the Wi-Fi credentials, `mqtts://` broker URI,
node ID, username, and generated node password. `sdkconfig` and the provisioned
CA are ignored by Git because they contain deployment-specific material.

Physical RF coexistence, power stability, long-duration reconnect behavior,
and watchdog recovery still require testing on the user's exact ESP32 board.
