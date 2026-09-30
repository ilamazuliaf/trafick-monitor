"""
REST API Unit Tests (prd.md Section 45)
"""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_config():
    response = client.get("/api/config")
    assert response.status_code == 200
    data = response.json()
    assert "interfaces" in data
    assert "graph_periods" in data
    assert "default_period" in data
    assert "realtime_max" in data


def test_api_status():
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "mikrotik" in data


def test_api_interfaces():
    response = client.get("/api/interfaces")
    assert response.status_code == 200
    data = response.json()
    assert "interfaces" in data
    assert isinstance(data["interfaces"], list)


def test_api_traffic_valid():
    # Use default interface from settings
    config_res = client.get("/api/config").json()
    iface = config_res["interfaces"][0]
    period = config_res["default_period"]

    response = client.get(f"/api/traffic?interface={iface}&period={period}")
    assert response.status_code == 200
    data = response.json()
    assert data["interface"] == iface
    assert data["period"] == period
    assert "data" in data


def test_api_traffic_all_interfaces():
    config_res = client.get("/api/config").json()
    period = config_res["default_period"]

    response = client.get(f"/api/traffic?interface=all&period={period}")
    assert response.status_code == 200
    data = response.json()
    assert data["interface"] == "all"
    assert data["period"] == period
    assert "data" in data


def test_api_traffic_invalid_interface():
    response = client.get("/api/traffic?interface=invalid_iface_xyz&period=15m")
    assert response.status_code == 400


def test_api_traffic_invalid_period():
    config_res = client.get("/api/config").json()
    iface = config_res["interfaces"][0]

    response = client.get(f"/api/traffic?interface={iface}&period=invalid_period_99x")
    assert response.status_code == 400
