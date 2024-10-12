import asyncio
from fastapi import WebSocket


class TelemetryService:
    def __init__(self):
        # Инициализация необходимых переменных
        self._telemetry_data = {}

    def get_current_data(self):
        """
        Получение текущих телеметрических данных.
        """
        return self._telemetry_data

    async def websocket_endpoint(self, websocket: WebSocket):
        """
        Обработка веб-сокета для передачи данных в реальном времени.
        """
        await websocket.accept()
        try:
            while True:
                # Отправка данных через веб-сокет
                await websocket.send_json(self._telemetry_data)
                await asyncio.sleep(1)  # Задержка между сообщениями
        except Exception as e:
            print(f"WebSocket error: {e}")
        finally:
            await websocket.close()
