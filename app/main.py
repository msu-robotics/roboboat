from fastapi import FastAPI
import os
from app.routers import telemetry, video, mcu, ml_model, control
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

app = FastAPI()

# Подключение роутеров
app.include_router(telemetry.router)
app.include_router(control.router)
app.include_router(video.router)
# app.include_router(controller.router)
# app.include_router(ml_model.router)


app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/")
async def read_index():
    return FileResponse(os.path.join("app", "static", "index.html"))
