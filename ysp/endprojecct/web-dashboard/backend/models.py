from typing import Optional
from pydantic import BaseModel


class SensorReading(BaseModel):
    temperature: float
    humidity: float
    time: Optional[str] = None


class AlertConfigUpdate(BaseModel):
    metric: str
    min_val: float
    max_val: float
    enabled: int
