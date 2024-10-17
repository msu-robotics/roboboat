import asyncio
import json
import time
import threading
import os
import uvicorn
from websockets.asyncio.async_timeout import timeout

from boat_controller import BoatController
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from enum import Enum


app = FastAPI()

# Создаем экземпляр BoatController
ESP32_IP = '192.168.43.222'
boat_controller = BoatController(esp32_ip=ESP32_IP)
boat_controller.start()


# Маршрут для получения телеметрии
@app.websocket("/telemetry")
async def telemetry_websocket(websocket: WebSocket):
    """
    Веб-сокет для передачи телеметрии в реальном времени.
    """
    await websocket.accept()
    try:
        while True:
            telemetry = boat_controller.get_telemetry()
            await websocket.send_json(telemetry)
            await asyncio.sleep(0.1)  # Задержка между сообщениями
    except Exception as e:
        print("Connection closed")
    finally:
        await websocket.close()


# Маршрут для управления уппаратом
@app.websocket("/control")
async def telemetry_websocket(websocket: WebSocket):
    """
    Веб-сокет для управления аппаратом в реальном времени.
    """
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            if message:
                data = json.loads(message)
                speed_multiplier = int(data.get("speedMultiplier", 100))
                forward = float(data.get("forward", 0)) * speed_multiplier
                lateral = float(data.get("lateral", 0)) * speed_multiplier
                yaw = float(data.get("yaw", 0)) * speed_multiplier
                boat_controller.send_movement_command(forward, lateral, yaw)
    except Exception as e:
        print("Connection closed")
    finally:
        await websocket.close()


class ModeRequest(BaseModel):
    mode: str


class ProbeAction(BaseModel):
    action: str
    timeout: int = 0


@app.post('/probe_control')
def probe_control(action_data: ProbeAction):
    action = action_data.action
    timeout = action_data.timeout  # Значение по умолчанию 10 секунд

    # Проверяем действие и отправляем соответствующую команду на ESP32
    if action == 'up':
        boat_controller.send_probe_command(1, timeout)
    elif action == 'down':
        boat_controller.send_probe_command(2, timeout)
    elif action == 'stop':
        boat_controller.send_probe_command(3)
    else:
        return JSONResponse({'status': 'error', 'message': 'Invalid action'}), 400

    return JSONResponse({'status': 'success'}), 200

@app.post('/mode')
async def telemetry_websocket(mode_request: ModeRequest):
    """
    Конечная точка для переключения режима работы лодки
    """
    if mode_request.mode == 'manual':
        boat_controller.send_mode_command(0)
    else:
        boat_controller.send_mode_command(1)


class PidSettings(BaseModel):
    p: float
    i: float
    d: float


@app.post('/pid_settings')
async def telemetry_websocket(pid_settings: PidSettings):
    """
    Конечная точка установки значений пид регулятора
    """
    boat_controller.send_pid_command(pid_settings.p, pid_settings.i, pid_settings.d)


@app.get('/pid_settings', response_model=PidSettings)
async def get_pid_settings(request: Request):
    """
    Конечная точка для получения значений пид регулятора
    """
    return PidSettings(
        p = boat_controller.telemetry_data['pid']['p'],
        i = boat_controller.telemetry_data['pid']['i'],
        d = boat_controller.telemetry_data['pid']['d']
    )


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse(os.path.join("app", "static", "index.html"))


# Функция для запуска FastAPI приложения в отдельном потоке
def start_api():
    uvicorn.run(app, host="0.0.0.0", port=8000)

# Запуск FastAPI приложения в отдельном потоке
api_thread = threading.Thread(target=start_api)
api_thread.daemon = True
api_thread.start()

# Основной цикл программы (если требуется)
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    pass
finally:
    # Остановка работы
    boat_controller.close()
    print("Программа завершена")