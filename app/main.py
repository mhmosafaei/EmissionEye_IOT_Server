from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


app = FastAPI(title="Emission-Eye IoT Server")

latest_data: dict[str, Any] = {}


def _legacy_log_path() -> Path:
    return Path(os.getenv("EMISSION_EYE_LEGACY_LOG", "data_log.jsonl"))


def _telemetry_log_path() -> Path:
    return Path(os.getenv("EMISSION_EYE_TELEMETRY_LOG", "telemetry_log.jsonl"))


def _append_jsonl(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, separators=(",", ":")) + "\n")


class SensorData(BaseModel):
    """The original payload contract. Do not widen or rename these fields."""

    gateway_id: int
    node_id: int
    sensor1: int
    sensor2: int
    sensor3: int
    sensor4: int
    timestamp: str


class EnvironmentalMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    temperature_c: float = Field(ge=-100, le=150)
    relative_humidity_percent: float = Field(ge=0, le=100)
    pressure_hpa: float = Field(gt=0, le=2000)


class AirQualityMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    aqi: int = Field(ge=0)
    tvoc_ppb: int = Field(ge=0)
    eco2_ppm: int = Field(ge=0)
    mox_ohm: int = Field(ge=0)


class Vector3(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x: float
    y: float
    z: float


class MotionMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid")

    acceleration_mps2: Vector3
    gyroscope_rad_s: Vector3


class LoRaMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    frequency_hz: int = Field(gt=0)
    bandwidth_hz: int = Field(gt=0)
    spreading_factor: int = Field(ge=5, le=12)
    rssi_dbm: float = Field(le=0)
    snr_db: float
    packet_bytes: int = Field(ge=0)


class GatewayGnss(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fix: bool
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    altitude_m: float | None = None
    satellites_used: int = Field(ge=0)
    satellites_visible: int = Field(ge=0)
    antenna_status: str = Field(min_length=1, max_length=64)
    fix_age_seconds: float | None = Field(default=None, ge=0)

    @model_validator(mode="after")
    def coordinates_required_for_valid_fix(self) -> "GatewayGnss":
        if self.fix and (self.latitude is None or self.longitude is None):
            raise ValueError("latitude and longitude are required when fix is true")
        return self


class TelemetryV1(BaseModel):
    """Canonical sampling-node v1 wire format."""

    model_config = ConfigDict(extra="forbid")

    gateway_id: str = Field(min_length=1, max_length=128)
    node_id: str = Field(min_length=1, max_length=128)
    legacy_gateway_id: int | None = Field(default=None, ge=0)
    legacy_node_id: int | None = Field(default=None, ge=0)
    sequence: int = Field(ge=0)
    hop: int = Field(ge=0)
    sensor_status_bits: int = Field(ge=0, le=4_294_967_295)
    timestamp: datetime
    environmental: EnvironmentalMeasurements
    air_quality: AirQualityMeasurements
    motion: MotionMeasurements
    lora: LoRaMetadata
    gateway_gnss: GatewayGnss | None = None

    @field_validator("timestamp")
    @classmethod
    def timestamp_must_include_timezone(cls, value: datetime) -> datetime:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a timezone offset")
        return value

    @model_validator(mode="after")
    def compatibility_ids_must_be_paired(self) -> "TelemetryV1":
        if (self.legacy_gateway_id is None) != (self.legacy_node_id is None):
            raise ValueError(
                "legacy_gateway_id and legacy_node_id must be supplied together"
            )
        return self


def _received_at() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _compatibility_projection(telemetry: TelemetryV1) -> dict[str, Any]:
    """Map v1 readings to the current four-channel sync contract."""

    return {
        "gateway_id": telemetry.legacy_gateway_id,
        "node_id": telemetry.legacy_node_id,
        "sensor1": telemetry.environmental.temperature_c,
        "sensor2": telemetry.environmental.relative_humidity_percent,
        "sensor3": telemetry.environmental.pressure_hpa,
        "sensor4": telemetry.air_quality.aqi,
        "timestamp": telemetry.model_dump(mode="json")["timestamp"],
        "measurement_format": "engineering_units",
        "source_api": "v1",
    }


@app.get("/")
async def root():
    return {"status": "Emission-Eye IoT Server is running"}


@app.head("/")
async def root_head():
    return


@app.get("/health")
async def health_get():
    return {"status": "ok"}


@app.post("/health")
async def health_post():
    return {"status": "ok"}


@app.post("/api/data/")
async def receive_data(data: SensorData):
    global latest_data

    # This is intentionally kept in the original shape for existing devices.
    record = {
        "received_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "sensor1": data.sensor1,
        "sensor2": data.sensor2,
        "sensor3": data.sensor3,
        "sensor4": data.sensor4,
        "timestamp": data.timestamp,
    }
    latest_data = record
    _append_jsonl(_legacy_log_path(), record)

    return {"status": "ok", "message": "data saved", "data": record}


@app.post("/api/v1/telemetry")
async def receive_telemetry_v1(data: TelemetryV1):
    global latest_data

    received_at = _received_at()
    canonical = {
        "schema_version": "1.0",
        "received_at": received_at,
        **data.model_dump(mode="json"),
    }
    compatibility = None
    if data.legacy_gateway_id is not None and data.legacy_node_id is not None:
        compatibility = _compatibility_projection(data)

    _append_jsonl(_telemetry_log_path(), canonical)
    if compatibility is not None:
        _append_jsonl(_legacy_log_path(), compatibility)
        latest_data = compatibility

    return {
        "status": "ok",
        "message": "telemetry saved",
        "data": canonical,
        "compatibility": compatibility,
    }


@app.get("/api/data/latest")
async def get_latest_data(gateway_id: int, node_id: int):
    global latest_data

    if latest_data:
        if (
            latest_data.get("gateway_id") == gateway_id
            and latest_data.get("node_id") == node_id
        ):
            return latest_data

    path = _legacy_log_path()
    if path.exists():
        with path.open("r", encoding="utf-8") as log:
            lines = log.readlines()

        for line in reversed(lines):
            try:
                record = json.loads(line)
                if (
                    record.get("gateway_id") == gateway_id
                    and record.get("node_id") == node_id
                ):
                    latest_data = record
                    return record
            except json.JSONDecodeError:
                continue

    raise HTTPException(status_code=404, detail="No telemetry received yet")
