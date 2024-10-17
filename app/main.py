import asyncio
import json
import time
import threading
import os
import uvicorn
from websockets.asyncio.async_timeout import timeout

from boat_controller import BoatController
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, UploadFile, File, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from enum import Enum


app = FastAPI()

# Создаем экземпляр BoatController
ESP32_IP = '192.168.43.222'
boat_controller = BoatController(esp32_ip=ESP32_IP)
boat_controller.start()

# Путь для сохранения файлов миссий
MISSION_FOLDER = 'missions'
os.makedirs(MISSION_FOLDER, exist_ok=True)

# Глобальные переменные для управления миссией
mission_thread = None
mission_running = False
mission_output = []


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

# Функция для логирования вывода миссии
def log_mission_output(message):
    global mission_output
    mission_output.append(message)
    # Ограничиваем размер лога, чтобы не переполнить память
    if len(mission_output) > 1000:
        mission_output = mission_output[-1000:]

# Конечная точка для загрузки файла миссии
@app.post("/upload_mission")
async def upload_mission(mission_file: UploadFile = File(...)):
    if mission_file.filename.endswith('.py'):
        contents = await mission_file.read()
        filepath = os.path.join(MISSION_FOLDER, 'mission.py')
        with open(filepath, 'wb') as f:
            f.write(contents)
        return JSONResponse(content={"status": "success"}, status_code=200)
    else:
        return JSONResponse(content={"status": "error", "message": "Invalid file type"}, status_code=400)

# Конечная точка для запуска миссии
@app.post("/start_mission")
async def start_mission():
    global mission_thread, mission_running, mission_output
    if mission_running:
        return JSONResponse(content={"status": "error", "message": "Mission is already running"}, status_code=400)
    mission_output = []  # Очищаем предыдущий вывод
    try:
        mission_running = True
        # Динамическая загрузка файла миссии
        import importlib.util
        spec = importlib.util.spec_from_file_location("mission_module", os.path.join(MISSION_FOLDER, 'mission.py'))
        mission_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mission_module)
        mission_instance = mission_module.Mission(boat_controller, mission_running, log_mission_output)
        mission_thread = threading.Thread(target=mission_instance.run)
        mission_thread.start()
        return JSONResponse(content={"status": "success"}, status_code=200)
    except Exception as e:

        return JSONResponse(content={"status": "error", "message": str(e)}, status_code=500)

# Конечная точка для остановки миссии
@app.post("/stop_mission")
async def stop_mission():
    global mission_running
    if mission_running:
        mission_running = False
        return JSONResponse(content={"status": "success"}, status_code=200)
    else:
        return JSONResponse(content={"status": "error", "message": "No mission is running"}, status_code=400)

# WebSocket для передачи вывода миссии на клиент
from fastapi import WebSocket

@app.websocket("/mission_output")
async def mission_output_ws(websocket: WebSocket):
    await websocket.accept()
    last_index = 0
    try:
        while True:
            if mission_output:
                new_output = mission_output[last_index:]
                for line in new_output:
                    await websocket.send_text(line)
                last_index = len(mission_output)
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        print("Клиент отключился от mission_output_ws")


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