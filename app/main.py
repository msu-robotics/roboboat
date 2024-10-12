from fastapi import FastAPI
from app.routers import telemetry, video, mcu, ml_model

app = FastAPI()

# Подключение роутеров
app.include_router(telemetry.router)
app.include_router(video.router)
app.include_router(controller.router)
app.include_router(ml_model.router)
