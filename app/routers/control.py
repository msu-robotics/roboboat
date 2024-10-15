from http.client import HTTPException
from fastapi.responses import HTMLResponse
from fastapi import APIRouter, WebSocket, Request
from app.services.telemetry_service import TelemetryService
from app.models.schema import PidSettings
from app.models.schema import PIDSettings
from app.vechicle import vehicle
from loguru import logger

router = APIRouter(prefix="/control", tags=["Control"])


@router.websocket("/")
async def telemetry_websocket(websocket: WebSocket):
    """
    Веб-сокет для передачи телеметрии в реальном времени.
    """
    logger.info("Connection try to accept")
    await websocket.accept()
    logger.info("Connection accepted")
    while True:
        data = await websocket.receive_json()
        await vehicle.set_motors(data.get("forward"), data.get("lateral"), data.get("yaw"), data.get("speedMultiplier"))


@router.post("/pid_settings")
async def pid_settings(settings: PIDSettings):
    try:
        await vehicle.set_pid_settings(settings.kp, settings.ki, settings.kd)
    except Exception as e:
        logger.exception(e)
        return HTMLResponse(str(e), status_code=400)
