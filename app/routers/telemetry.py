from fastapi import APIRouter, WebSocket
from app.services.telemetry_service import TelemetryService

router = APIRouter(prefix="/telemetry", tags=["Telemetry"])

telemetry_service = TelemetryService()


@router.get("/")
async def get_telemetry():
    """
    Эндпоинт для получения текущей телеметрии.
    """
    data = telemetry_service.get_current_data()
    return data


@router.websocket("/ws")
async def telemetry_websocket(websocket: WebSocket):
    """
    Веб-сокет для передачи телеметрии в реальном времени.
    """
    await telemetry_service.websocket_endpoint(websocket)
