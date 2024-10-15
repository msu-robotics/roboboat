from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from aiortc import RTCPeerConnection, VideoStreamTrack
from aiortc.contrib.media import MediaRecorder
from aiortc.mediastreams import VideoFrame
from pydantic import BaseModel
from loguru import logger
import cv2
import asyncio


router = APIRouter(prefix="/video", tags=["Control"])


# Видео источник (например, камера через OpenCV)
class CameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.cap = cv2.VideoCapture(0)  # Захват с камеры

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        ret, frame = self.cap.read()
        if not ret:
            raise Exception("Unable to capture video frame")

        # Преобразуем OpenCV BGR изображение в нужный формат
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Возвращаем видео фрейм
        return VideoFrame.from_ndarray(frame, format="rgb24")


# Модель данных для SDP информации
class Offer(BaseModel):
    sdp: str
    type: str

# Хранилище для WebRTC соединений
pcs = set()


@router.post("/offer")
async def offer(offer: Offer):
    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("iceconnectionstatechange")
    async def on_iceconnectionstatechange():
        logger.info("ICE connection state is %s" % pc.iceConnectionState)
        if pc.iceConnectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # Захватываем видео с камеры
    video_track = CameraVideoTrack()
    pc.addTrack(video_track)

    # Обрабатываем offer
    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}


@router.on_event("shutdown")
async def on_shutdown():
    # Закрываем все WebRTC соединения при завершении работы
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
