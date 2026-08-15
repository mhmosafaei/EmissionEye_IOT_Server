import json
from copy import deepcopy
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app import main


FIXTURE_PATH = Path(__file__).parent / "fixtures" / "f6e8_telemetry.json"


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("EMISSION_EYE_LEGACY_LOG", str(tmp_path / "data_log.jsonl"))
    monkeypatch.setenv(
        "EMISSION_EYE_TELEMETRY_LOG", str(tmp_path / "telemetry_log.jsonl")
    )
    main.latest_data = {}
    return TestClient(main.app)


@pytest.fixture()
def captured_f6e8():
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_legacy_post_and_latest_are_unchanged(client):
    payload = {
        "gateway_id": 10,
        "node_id": 20,
        "sensor1": 101,
        "sensor2": 202,
        "sensor3": 303,
        "sensor4": 404,
        "timestamp": "2026-08-15T12:00:00Z",
    }

    posted = client.post("/api/data/", json=payload)
    assert posted.status_code == 200
    posted_data = posted.json()["data"]
    assert {key: posted_data[key] for key in payload} == payload
    assert "received_at" in posted_data

    latest = client.get("/api/data/latest", params={"gateway_id": 10, "node_id": 20})
    assert latest.status_code == 200
    assert latest.json() == posted_data


def test_captured_f6e8_record_is_preserved_and_projected(
    client, tmp_path, captured_f6e8
):
    response = client.post("/api/v1/telemetry", json=captured_f6e8)

    assert response.status_code == 200
    body = response.json()
    canonical = body["data"]
    assert canonical["schema_version"] == "1.0"
    assert "received_at" in canonical
    assert {key: canonical[key] for key in captured_f6e8} == captured_f6e8
    assert canonical["node_id"] == "F6E8"
    assert canonical["gateway_gnss"]["fix"] is False
    assert canonical["gateway_gnss"]["latitude"] is None
    assert canonical["gateway_gnss"]["longitude"] is None

    persisted = json.loads(
        (tmp_path / "telemetry_log.jsonl").read_text(encoding="utf-8")
    )
    assert persisted == canonical

    expected_projection = {
        "gateway_id": 1,
        "node_id": 1,
        "sensor1": 24.77,
        "sensor2": 36.9,
        "sensor3": 1020.41,
        "sensor4": 2,
        "timestamp": "2026-08-15T15:45:43Z",
        "measurement_format": "engineering_units",
        "source_api": "v1",
    }
    assert body["compatibility"] == expected_projection

    latest = client.get("/api/data/latest", params={"gateway_id": 1, "node_id": 1})
    assert latest.status_code == 200
    assert latest.json() == expected_projection


def test_nonnumeric_hardware_ids_do_not_require_compatibility_ids(
    client, tmp_path, captured_f6e8
):
    payload = deepcopy(captured_f6e8)
    payload.pop("legacy_gateway_id")
    payload.pop("legacy_node_id")

    response = client.post("/api/v1/telemetry", json=payload)

    assert response.status_code == 200
    assert response.json()["data"]["node_id"] == "F6E8"
    assert response.json()["compatibility"] is None
    assert not (tmp_path / "data_log.jsonl").exists()


def test_compatibility_ids_must_be_supplied_as_a_pair(client, captured_f6e8):
    payload = deepcopy(captured_f6e8)
    payload.pop("legacy_node_id")

    response = client.post("/api/v1/telemetry", json=payload)

    assert response.status_code == 422


def test_timestamp_must_be_timezone_aware(client, captured_f6e8):
    payload = deepcopy(captured_f6e8)
    payload["timestamp"] = "2026-08-15T15:45:43"

    response = client.post("/api/v1/telemetry", json=payload)

    assert response.status_code == 422


@pytest.mark.parametrize("invented_field", ["co2_ppm", "pm1_0_ug_m3", "pm2_5_ug_m3", "pm10_ug_m3"])
def test_unmeasured_or_misnamed_air_quality_fields_are_rejected(
    client, captured_f6e8, invented_field
):
    payload = deepcopy(captured_f6e8)
    payload["air_quality"][invented_field] = 1

    response = client.post("/api/v1/telemetry", json=payload)

    assert response.status_code == 422


def test_valid_gnss_fix_requires_coordinates(client, captured_f6e8):
    payload = deepcopy(captured_f6e8)
    payload["gateway_gnss"]["fix"] = True

    response = client.post("/api/v1/telemetry", json=payload)

    assert response.status_code == 422
