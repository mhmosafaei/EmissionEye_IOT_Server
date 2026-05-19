import json
import os
import time
from urllib.parse import parse_qs, urlparse

import requests

DEFAULT_PROJECT_REF = "jvsmabozwhtyqxdjnoiz"
DEFAULT_FASTAPI_URL = "https://emissioneye-iot-server.onrender.com/api/data/latest?gateway_id=1&node_id=1"
DEFAULT_SUPABASE_URL = f"https://{DEFAULT_PROJECT_REF}.supabase.co"
DEFAULT_EDGE_FUNCTION_URL = f"https://{DEFAULT_PROJECT_REF}.functions.supabase.co/ingest-telemetry"

# Safer: set this from environment variable if possible
DEFAULT_SUPABASE_ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imp2c21hYm96d2h0eXF4ZGpub2l6Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzYxMDc2NDUsImV4cCI6MjA5MTY4MzY0NX0.BaXDro_ziX_zyKXvpTKZXbEN1T97-Iih0zcfsygXgas"

DEFAULT_POLL_INTERVAL_SECONDS = 5
DEFAULT_REQUEST_TIMEOUT_SECONDS = 10

FASTAPI_URL = os.getenv("FASTAPI_URL", DEFAULT_FASTAPI_URL)
SUPABASE_URL = os.getenv("SUPABASE_URL", DEFAULT_SUPABASE_URL).rstrip("/")
EDGE_FUNCTION_URL = os.getenv("EDGE_FUNCTION_URL", DEFAULT_EDGE_FUNCTION_URL)
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", DEFAULT_SUPABASE_ANON_KEY)

POLL_INTERVAL_SECONDS = int(os.getenv("POLL_INTERVAL_SECONDS", DEFAULT_POLL_INTERVAL_SECONDS))
REQUEST_TIMEOUT_SECONDS = int(os.getenv("REQUEST_TIMEOUT_SECONDS", DEFAULT_REQUEST_TIMEOUT_SECONDS))

MONITORED_GATEWAY_ID = int(parse_qs(urlparse(FASTAPI_URL).query).get("gateway_id", ["1"])[0])
MONITORED_NODE_ID = int(parse_qs(urlparse(FASTAPI_URL).query).get("node_id", ["1"])[0])

last_signature = None


def is_valid_payload(data: dict) -> bool:
    return (
        isinstance(data, dict)
        and data.get("gateway_id") is not None
        and data.get("node_id") is not None
        and data.get("timestamp") is not None
    )


while True:
    try:
        res = requests.get(FASTAPI_URL, timeout=REQUEST_TIMEOUT_SECONDS)

        if res.status_code == 404:
            print("No telemetry available yet. Waiting for gateway data.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        if res.status_code != 200:
            print("FastAPI returned:", res.status_code, res.text)
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        data = res.json()
        print("Latest payload:", json.dumps(data, indent=2))

        if not is_valid_payload(data):
            print("Invalid or empty payload. Skipping.")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        signature = (
            data.get("received_at"),
            data.get("timestamp"),
            data.get("gateway_id"),
            data.get("node_id"),
            data.get("sensor1"),
            data.get("sensor2"),
            data.get("sensor3"),
            data.get("sensor4"),
            data.get("status", 1),
        )

        if signature == last_signature:
            print("No new data")
            time.sleep(POLL_INTERVAL_SECONDS)
            continue

        print("New data found")

        edge_payload = {
            "gateway_id": data.get("gateway_id"),
            "node_id": data.get("node_id"),
            "sensor1": data.get("sensor1"),
            "sensor2": data.get("sensor2"),
            "sensor3": data.get("sensor3"),
            "sensor4": data.get("sensor4"),
            "status": data.get("status", 1),
            "reading_timestamp": data.get("timestamp"),
        }

        response = requests.post(
            EDGE_FUNCTION_URL,
            json=edge_payload,
            headers={
                "Authorization": f"Bearer {SUPABASE_ANON_KEY}",
                "Content-Type": "application/json",
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )

        print("Sent to Edge:", response.status_code, response.text)
        response.raise_for_status()

        last_signature = signature

    except Exception as e:
        print("Error:", str(e))
        print("Skipping alert creation for now.")

    time.sleep(POLL_INTERVAL_SECONDS)
