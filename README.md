# Emission-Eye IoT Server

FastAPI ingestion service for legacy four-channel nodes and Emission-Eye v1
telemetry.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

By default, legacy-compatible records are appended to `data_log.jsonl` and
complete v1 records to `telemetry_log.jsonl`. Override the paths with
`EMISSION_EYE_LEGACY_LOG` and `EMISSION_EYE_TELEMETRY_LOG`.

## Legacy API (unchanged)

`POST /api/data/` continues to accept integer IDs, integer raw sensor channels,
and the original string timestamp:

```json
{
  "gateway_id": 10,
  "node_id": 20,
  "sensor1": 101,
  "sensor2": 202,
  "sensor3": 303,
  "sensor4": 404,
  "timestamp": "2026-08-15T12:00:00Z"
}
```

`GET /api/data/latest?gateway_id=10&node_id=20` retains its existing response
and 404 behavior.

Legacy `sensor1` through `sensor4` are raw device measurements. Any existing
4–20 mA interpretation belongs only to that legacy path.

## V1 telemetry API

`POST /api/v1/telemetry` accepts engineering-unit measurements. Its canonical
payload is:

```json
{
  "gateway_id": "ee-gateway-roger",
  "node_id": "F6E8",
  "legacy_gateway_id": 1,
  "legacy_node_id": 1,
  "sequence": 42,
  "hop": 0,
  "sensor_status_bits": 7,
  "timestamp": "2026-08-15T15:45:43Z",
  "environmental": {
    "temperature_c": 24.77,
    "relative_humidity_percent": 36.9,
    "pressure_hpa": 1020.41
  },
  "air_quality": {
    "aqi": 2,
    "tvoc_ppb": 102,
    "eco2_ppm": 553,
    "mox_ohm": 31849
  },
  "motion": {
    "acceleration_mps2": {"x": 9.29, "y": -0.89, "z": 1.46},
    "gyroscope_rad_s": {"x": 0.47, "y": -0.78, "z": -0.43}
  },
  "lora": {
    "frequency_hz": 868000000,
    "bandwidth_hz": 125000,
    "spreading_factor": 7,
    "rssi_dbm": -31,
    "snr_db": 12.25,
    "packet_bytes": 208
  },
  "gateway_gnss": {
    "fix": false,
    "latitude": null,
    "longitude": null,
    "altitude_m": null,
    "satellites_used": 0,
    "satellites_visible": 6,
    "antenna_status": "ok",
    "fix_age_seconds": null
  }
}
```

Timestamps must contain `Z` or an explicit UTC offset. `gateway_gnss` is
optional; coordinates, altitude, and fix age may be null when `fix` is false.
When `fix` is true, latitude and longitude are required. The node reports
estimated CO₂ as `eco2_ppm`; it does not report direct CO₂ or PM1/PM2.5/PM10.
Unknown fields and invalid physical ranges return HTTP 422.

The complete canonical v1 record, including `schema_version` and `received_at`,
is stored in `telemetry_log.jsonl`. String hardware identifiers are preserved
verbatim. The optional integer `legacy_gateway_id` and `legacy_node_id` must be
provided together. When present, a compatibility record is appended to the
legacy log, returned as `compatibility`, and made available through the existing
integer-ID latest endpoint:

| Legacy channel | V1 engineering-unit value |
| --- | --- |
| `sensor1` | `environmental.temperature_c` |
| `sensor2` | `environmental.relative_humidity_percent` |
| `sensor3` | `environmental.pressure_hpa` |
| `sensor4` | `air_quality.aqi` |

The projection is marked `measurement_format: "engineering_units"` and
`source_api: "v1"`. The current sync worker discards these metadata fields, so
the marker alone does **not** prevent downstream 4–20 mA conversion.

For the demo gateway, configure the Supabase channels as direct engineering
values:

- `sensor1`: temperature, direct °C
- `sensor2`: humidity, direct %
- `sensor3`: pressure, direct hPa
- `sensor4`: AQI, direct index

The original legacy node remains independently configured for its raw 4–20 mA
temperature conversion. Changing that platform behavior is outside this server
change.

The representative hardware capture used above is checked in at
`tests/fixtures/f6e8_telemetry.json`.

## Tests

```bash
pytest
```
