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


class ThrustersTelemetry(BaseModel):
    forward_left: float
    forward_right: float
    backward_left: float
    backward_right: float


class Telemetry(BaseModel):
    magnetometer: MagnetometerTelemetry
    power: PowerTelemetry
    thrusters: ThrustersTelemetry
