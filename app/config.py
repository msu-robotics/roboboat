from pydantic_settings import BaseSettings


class VehicleSettings(BaseSettings):
    vehicle_host: str
    vehicle_port: int
