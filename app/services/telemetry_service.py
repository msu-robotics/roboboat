import asyncio
from fastapi import WebSocket
from app.models.schema import (
    Telemetry,
    PowerTelemetry,
    MagnetometerTelemetry,
)
from loguru import logger
from app.vechicle import VehicleController


class TelemetryService:
    def __init__(self, vehicle: VehicleController):
        # Инициализация необходимых переменных
        self._telemetry_data = Telemetry(
            magnetometer=MagnetometerTelemetry(pitch=0, yaw=0, roll=0),
            thrusters=[0, 0, 0, 0],
            power=PowerTelemetry(voltage=0, current=0),
        )
        self._vehicle = vehicle
        self._pid_settings = {"p_gain": 0, "i_gain": 0, "d_gain": 0}

    def update_telemetry(self):
        """
        Получение текущих телеметрических данных.
        """
        self._telemetry_data = Telemetry(
            magnetometer=MagnetometerTelemetry(
                **self._vehicle.get_magnetometer_telemetry()
            ),
            thrusters=self._vehicle.get_pwm_telemetry(),
            power=PowerTelemetry(voltage=0, current=0),
        )
        return self._telemetry_data

    async def refresh_pid_settings(self):
        self._pid_settings = await self._vehicle.refresh_pid_settings()

    def get_pid_settings(self):
        return self._vehicle.get_pid_settings()

    async def websocket_endpoint(self, websocket: WebSocket):
        """
        Обработка веб-сокета для передачи данных в реальном времени.
        """
        logger.info("Connection try to accept")
        await websocket.accept()
        logger.info("Connection accepted")
        try:
            while True:
                # Отправка данных через веб-сокет
                telemetry = self.update_telemetry()
                await websocket.send_json(telemetry.dict())
                await asyncio.sleep(0.1)  # Задержка между сообщениями
        except Exception:
            logger.exception(f"Connection closed")
        finally:
            await websocket.close()
