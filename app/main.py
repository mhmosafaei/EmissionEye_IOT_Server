from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
import json

app = FastAPI(title="Emission-Eye IoT Server")


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

    with open("data_log.jsonl", "a") as f:
        f.write(json.dumps(record) + "\n")

    print("Saved sensor data:", record)

    return {
        "status": "ok",
        "message": "data saved",
        "data": record
    }
