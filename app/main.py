import asyncio
import json
import time
import threading
import os
import uvicorn
from boat_controller import BoatController
from fastapi import FastAPI, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse


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
                print(data)
                speed_multiplier = int(data.get("speedMultiplier", 100)) / 100
                forward = float(data.get("forward", 0)) * speed_multiplier
                lateral = float(data.get("lateral", 0)) * speed_multiplier
                yaw = float(data.get("yaw", 0)) * speed_multiplier
                boat_controller.send_movement_command(forward, lateral, yaw)
    except Exception as e:
        print("Connection closed")
    finally:
        await websocket.close()


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