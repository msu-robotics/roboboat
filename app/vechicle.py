from app.services.controller_service import VehicleController
from app.config import VehicleSettings


settings = VehicleSettings()
vehicle = VehicleController(host=settings.vehicle_host, port=settings.vehicle_port)
