from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json

app = FastAPI(title="Emission-Eye IoT Server")


# Store latest received packet in memory
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
        "timestamp": data.timestamp
    }

    # Save latest packet in memory
    latest_data = record

    # Append packet to local log file
    with open("data_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")

    print("Saved sensor data:", record)

    return {
        "status": "ok",
        "message": "data saved",
        "data": record
    }


@app.get("/api/data/latest")
async def get_latest_data(gateway_id: int, node_id: int):

    global latest_data

    return latest_data
