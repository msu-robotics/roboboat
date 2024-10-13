from fastapi import APIRouter, WebSocket, Request
from app.services.telemetry_service import TelemetryService
from app.models.schema import PidSettings
from app.vechicle import vehicle
from loguru import logger

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])

telemetry_service = TelemetryService(vehicle)


@router.websocket("/")
async def telemetry_websocket(websocket: WebSocket):
    """
    Веб-сокет для передачи телеметрии в реальном времени.
    """
    logger.info('Telemetry')
    await telemetry_service.websocket_endpoint(websocket)


@router.get("/pid_settings", response_model=PidSettings)
async def pid_settings(request: Request):
    return telemetry_service.get_pid_settings()
