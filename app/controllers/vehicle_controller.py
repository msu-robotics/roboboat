from app.services.controller_service import VehicleController
import json
from app.main import app


vehicle = VehicleController(host='mcu.boat.local', port=5000)


@app.websocket("/ws")
async def websocket_handler(websocket):
    await websocket.accept()
    try:
        while True:
            message = await websocket.receive_text()
            if message:
                data = json.loads(message)
                speed_multiplier = int(data.get('speedMultiplier', 100)) / 100
                forward = float(data.get('forward', 0)) * speed_multiplier
                lateral = float(data.get('lateral', 0)) * speed_multiplier
                yaw = float(data.get('yaw', 0)) * speed_multiplier
                mode = data.get('mode', None)
                # Обновление режима, если он передан
                if mode:
                    await vehicle.set_mode(mode)
                await vehicle.set_motors(forward, lateral, yaw)
    except Exception as e:
        print('WebSocket error:', e)
    finally:
        await vehicle.disconnect()
        await websocket.close()
