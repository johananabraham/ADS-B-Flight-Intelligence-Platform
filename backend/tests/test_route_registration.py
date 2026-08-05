"""Full-application API registration contract."""

from app.main import app


def test_all_product_routers_are_present_in_openapi():
    paths = set(app.openapi()["paths"])

    expected = {
        "/api/v1/aircraft/",
        "/api/v1/anomalies/",
        "/api/v1/safety/query",
        "/api/v1/replay/status",
        "/api/v1/kinematics/evaluations",
        "/api/v1/corroboration/{icao_hex}",
        "/api/v1/stations/",
        "/api/v1/trust/{icao_hex}",
        "/api/v1/trust/{icao_hex}/assessments",
        "/api/v1/trust-events/",
    }
    assert expected <= paths


def test_websocket_route_is_registered_outside_openapi():
    assert str(app.url_path_for("websocket_endpoint")) == "/api/v1/ws/aircraft"
