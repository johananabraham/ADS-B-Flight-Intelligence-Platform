from types import SimpleNamespace

import pytest

from app.services.station_mqtt import StationMessageError
from services.edge_telemetry import consumer


class FakeDatabase:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakeClient:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.subscriptions = []
        self.acks = []
        self.disconnected = False
        self.tls_insecure = None
        self.context = None
        self.credentials = None

    def username_pw_set(self, username, password) -> None:
        self.credentials = (username, password)

    def tls_set_context(self, context) -> None:
        self.context = context

    def tls_insecure_set(self, value) -> None:
        self.tls_insecure = value

    def reconnect_delay_set(self, **_kwargs) -> None:
        pass

    def enable_logger(self, _logger) -> None:
        pass

    def subscribe(self, topic, qos):
        self.subscriptions.append((topic, qos))
        return consumer.mqtt.MQTT_ERR_SUCCESS, len(self.subscriptions)

    def ack(self, message_id, qos) -> None:
        self.acks.append((message_id, qos))

    def disconnect(self) -> None:
        self.disconnected = True


class FakeTlsContext:
    def __init__(self) -> None:
        self.minimum_version = None
        self.check_hostname = None
        self.verify_mode = None
        self.cert_chain = None

    def load_cert_chain(self, cert, key) -> None:
        self.cert_chain = (cert, key)


def settings(**updates) -> consumer.ConsumerSettings:
    values = {
        "host": "mqtt.internal",
        "port": 8883,
        "username": "station-consumer",
        "password": "secret-from-runtime",
        "ca_cert": "/run/secrets/ca.crt",
    }
    values.update(updates)
    return consumer.ConsumerSettings(**values)


def test_settings_require_valid_port_and_certificate_pair():
    with pytest.raises(ValueError, match="MQTT_PORT"):
        settings(port=70_000)
    with pytest.raises(ValueError, match="configured together"):
        settings(client_cert="/client.crt")


def test_client_requires_tls_verification_and_callback_v2(monkeypatch):
    fake_context = FakeTlsContext()
    monkeypatch.setattr(
        consumer.ssl, "create_default_context", lambda **_kwargs: fake_context
    )
    monkeypatch.setattr(consumer.mqtt, "Client", FakeClient)

    client = consumer.build_client(
        settings(client_cert="/client.crt", client_key="/client.key")
    )

    assert (
        client.kwargs["callback_api_version"]
        is consumer.mqtt.CallbackAPIVersion.VERSION2
    )
    assert client.kwargs["manual_ack"] is True
    assert client.credentials == ("station-consumer", "secret-from-runtime")
    assert client.tls_insecure is False
    assert fake_context.verify_mode == consumer.ssl.CERT_REQUIRED
    assert fake_context.cert_chain == ("/client.crt", "/client.key")


def test_connect_subscribes_only_to_versioned_station_topics():
    client = FakeClient()

    consumer._on_connect(client, None, None, SimpleNamespace(is_failure=False), None)

    assert client.subscriptions == list(consumer.SUBSCRIPTIONS)


def test_valid_message_commits_before_manual_ack(monkeypatch):
    database = FakeDatabase()
    client = FakeClient()
    monkeypatch.setattr(consumer, "SessionLocal", lambda: database)
    monkeypatch.setattr(
        consumer,
        "process_station_message",
        lambda *_args, **_kwargs: SimpleNamespace(
            kind="telemetry", node_id="roof-node-1", inserted=True
        ),
    )

    consumer._on_message(
        client,
        None,
        SimpleNamespace(topic="topic", payload=b"{}", mid=4, qos=1),
    )

    assert database.committed is True
    assert database.closed is True
    assert client.acks == [(4, 1)]


def test_invalid_message_is_discarded_without_poison_redelivery(monkeypatch):
    database = FakeDatabase()
    client = FakeClient()
    monkeypatch.setattr(consumer, "SessionLocal", lambda: database)

    def reject(*_args, **_kwargs):
        raise StationMessageError("invalid station message")

    monkeypatch.setattr(consumer, "process_station_message", reject)
    consumer._on_message(
        client,
        None,
        SimpleNamespace(topic="topic", payload=b"{}", mid=5, qos=1),
    )

    assert database.rolled_back is True
    assert client.acks == [(5, 1)]
    assert client.disconnected is False


def test_database_failure_is_not_acknowledged(monkeypatch):
    database = FakeDatabase()
    client = FakeClient()
    monkeypatch.setattr(consumer, "SessionLocal", lambda: database)

    def fail(*_args, **_kwargs):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(consumer, "process_station_message", fail)
    consumer._on_message(
        client,
        None,
        SimpleNamespace(topic="topic", payload=b"{}", mid=6, qos=1),
    )

    assert database.rolled_back is True
    assert client.acks == []
    assert client.disconnected is True
