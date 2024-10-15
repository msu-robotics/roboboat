from pydantic import BaseModel


class PidSettings(BaseModel):
    p_gain: float
    i_gain: float
    d_gain: float


class MagnetometerTelemetry(BaseModel):
    pitch: float
    yaw: float
    roll: float


class PowerTelemetry(BaseModel):
    voltage: float
    current: float


class Telemetry(BaseModel):
    magnetometer: MagnetometerTelemetry
    power: PowerTelemetry
    thrusters: list[float]


class PIDSettings(BaseModel):
    kp: float
    ki: float
    kd: float
