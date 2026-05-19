from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from datetime import datetime
import json
import os

app = FastAPI(title="Emission-Eye IoT Server")


latest_data = {}


class SensorData(BaseModel):
    gateway_id: int
    node_id: int
    sensor1: int
    sensor2: int
    sensor3: int
    sensor4: int
    timestamp: str


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

    record = {
        "received_at": datetime.utcnow().isoformat(),
        "gateway_id": data.gateway_id,
        "node_id": data.node_id,
        "sensor1": data.sensor1,
        "sensor2": data.sensor2,
        "sensor3": data.sensor3,
        "sensor4": data.sensor4,
        "timestamp": data.timestamp,
    }

    latest_data = record

    with open("data_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")

    print("Saved sensor data:", record)

    return {
        "status": "ok",
        "message": "data saved",
        "data": record,
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

    if os.path.exists("data_log.jsonl"):
        with open("data_log.jsonl", "r") as f:
            lines = f.readlines()

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
