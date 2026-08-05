from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_mqtt_broker_has_only_tls_authenticated_listener():
    config = (ROOT / "edge/mosquitto/config/mosquitto.conf").read_text()

    assert "listener 8883" in config
    assert "listener 1883" not in config
    assert "tls_version tlsv1.2" in config
    assert "allow_anonymous false" in config
    assert "password_file " in config
    assert "acl_file " in config


def test_acl_is_explicit_and_consumer_has_no_write_grant():
    acl = (ROOT / "edge/mosquitto/config/acl").read_text()
    consumer_block = acl.split("user station-consumer", maxsplit=1)[1]

    assert "user roof-node-1" in acl
    assert "topic write adsb/stations/v1/roof-node-1/telemetry" in acl
    assert "pattern write" not in acl
    assert "topic write" not in consumer_block
    assert "topic read adsb/stations/v1/+/telemetry" in consumer_block


def test_compose_uses_pinned_broker_and_runtime_secrets():
    compose = (ROOT / "docker-compose.edge.yml").read_text()

    assert "eclipse-mosquitto:2.0.22-openssl" in compose
    assert "MQTT_CONSUMER_PASSWORD_FILE" in compose
    assert "MQTT_CONSUMER_PASSWORD:" not in compose
    assert "${MQTT_BIND_ADDRESS:-127.0.0.1}:8883:8883" in compose


def test_firmware_emits_exact_backend_contract_names_and_enum_values():
    source = (ROOT / "firmware/esp32-station/main/main.c").read_text()

    assert '\\"watchdog_reset_count\\"' in source
    assert "watchdog_reset_detected" not in source
    assert '"ONLINE", "connected"' in source
    assert '"OFFLINE",' in source
