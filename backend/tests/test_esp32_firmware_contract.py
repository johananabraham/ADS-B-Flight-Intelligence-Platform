"""Static wire-contract guard between physical ESP32 firmware and the backend."""

import re
from pathlib import Path

from app.schemas.edge import StationTelemetry


ROOT = Path(__file__).parents[2]
FIRMWARE_SOURCE = ROOT / "firmware/esp32-station/main/main.c"


def test_firmware_telemetry_keys_match_strict_backend_schema() -> None:
    source = FIRMWARE_SOURCE.read_text(encoding="utf-8")
    start = source.index("static bool build_telemetry")
    end = source.index("static void wifi_reconnect_callback", start)
    function = source[start:end]
    emitted_keys = set(re.findall(r'\\"([a-z_]+)\\":', function))

    required_keys = {
        name
        for name, field in StationTelemetry.model_fields.items()
        if field.is_required()
    }
    optional_keys = set(StationTelemetry.model_fields) - required_keys

    assert required_keys <= emitted_keys
    assert emitted_keys <= required_keys | optional_keys


def test_firmware_node_id_guard_matches_backend_constraints() -> None:
    source = FIRMWARE_SOURCE.read_text(encoding="utf-8")
    start = source.index("static bool node_id_is_safe")
    end = source.index("static bool format_utc_now", start)
    function = source[start:end]

    assert "length > 63" in function
    assert "index > 0 && value == '-'" in function
    assert "value >= 'A'" not in function
    assert "value == '_'" not in function
