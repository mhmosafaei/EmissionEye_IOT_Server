from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime

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

    print("Received sensor data:", data)

    return {
        "status": "ok",
        "message": "data received",
        "received_at": datetime.utcnow().isoformat(),
        "data": data
    }
