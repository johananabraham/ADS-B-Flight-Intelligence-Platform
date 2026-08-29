import asyncio
import contextlib
import hashlib
import json
import stat
from pathlib import Path

import pytest

from evaluation.field.capture import (
    allocate_output_path,
    atomic_private_json,
    capture,
    load_manifest,
    preflight_source,
    usable_captures_by_day,
    validate_loopback_source,
)


def test_allocate_output_path_never_replaces_previous_attempt(tmp_path: Path) -> None:
    first = allocate_output_path(tmp_path, 1)
    assert first.name == "day-01.sbs"
    first.touch()
    second = allocate_output_path(tmp_path, 1)
    assert second.name == "day-01-attempt-02.sbs"
    second.touch()
    assert allocate_output_path(tmp_path, 1).name == "day-01-attempt-03.sbs"


def test_atomic_private_json_is_owner_only_and_complete(tmp_path: Path) -> None:
    target = tmp_path / "private.json"
    atomic_private_json(target, {"state": "CAPTURING", "lines": 10})
    assert json.loads(target.read_text(encoding="utf-8"))["lines"] == 10
    assert stat.S_IMODE(target.stat().st_mode) == 0o600
    assert stat.S_IMODE(tmp_path.stat().st_mode) == 0o700
    assert not list(tmp_path.glob("*.tmp"))


def test_existing_manifest_rejects_receiver_configuration_change(tmp_path: Path) -> None:
    manifest = tmp_path / "capture-manifest.private.json"
    manifest.write_text(
        json.dumps(
            {
                "schema_version": "1.0",
                "receiver_configuration": "receiver-v1",
                "captures": [],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="configuration changed"):
        load_manifest(manifest, "receiver-v2")


def test_new_manifest_has_no_network_or_location_fields(tmp_path: Path) -> None:
    manifest = load_manifest(tmp_path / "missing.json", "receiver-v1")
    assert manifest["receiver_configuration"] == "receiver-v1"
    assert "host" not in manifest
    assert "port" not in manifest
    assert "location" not in manifest


def test_usable_capture_selection_rejects_duplicates_and_interruptions() -> None:
    with pytest.raises(ValueError, match="multiple usable"):
        usable_captures_by_day(
            {
                "captures": [
                    {"day": 1, "usable": True, "capture_state": "COMPLETED"},
                    {"day": 1, "usable": True, "capture_state": "COMPLETED"},
                ]
            }
        )
    with pytest.raises(ValueError, match="not completed"):
        usable_captures_by_day(
            {"captures": [{"day": 1, "usable": True, "capture_state": "INTERRUPTED"}]}
        )


@pytest.mark.parametrize("host", ["192.168.1.10", "8.8.8.8", "localhost", "dump1090"])
def test_capture_source_must_be_numeric_loopback(host: str) -> None:
    with pytest.raises(ValueError, match="loopback"):
        validate_loopback_source(host)


def test_capture_source_accepts_ipv4_and_ipv6_loopback() -> None:
    assert validate_loopback_source("127.0.0.1") == "127.0.0.1"
    assert validate_loopback_source("::1") == "::1"


def test_preflight_requires_real_sbs_message() -> None:
    async def exercise() -> None:
        async def handler(
            _reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            writer.write(b"not-sbs\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = int(server.sockets[0].getsockname()[1])
        try:
            with pytest.raises(RuntimeError, match="SBS MSG"):
                await preflight_source("127.0.0.1", port, 1)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(exercise())


def test_preflight_accepts_bounded_sbs_message() -> None:
    async def exercise() -> None:
        async def handler(
            _reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            writer.write(b"MSG,1,fixture\n")
            await writer.drain()
            writer.close()

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = int(server.sockets[0].getsockname()[1])
        try:
            await preflight_source("127.0.0.1", port, 1)
        finally:
            server.close()
            await server.wait_closed()

    asyncio.run(exercise())


def test_short_capture_writes_verifiable_private_artifacts(tmp_path: Path) -> None:
    async def exercise() -> None:
        async def handler(
            _reader: asyncio.StreamReader, writer: asyncio.StreamWriter
        ) -> None:
            with contextlib.suppress(ConnectionError):
                while True:
                    writer.write(b"MSG,1,fixture\n")
                    await writer.drain()
                    await asyncio.sleep(0.005)

        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = int(server.sockets[0].getsockname()[1])
        output = tmp_path / "day-01.sbs"
        status = tmp_path / "capture-status.private.json"
        try:
            result = await capture(
                "127.0.0.1", port, 0.00003, output, status_path=status
            )
        finally:
            server.close()
            await server.wait_closed()

        assert result["capture_state"] == "COMPLETED"
        assert result["lines"] > 0
        assert result["sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
        assert stat.S_IMODE(output.stat().st_mode) == 0o600
        assert json.loads(status.read_text(encoding="utf-8"))["state"] == "COMPLETED"

    asyncio.run(exercise())
