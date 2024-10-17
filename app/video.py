import cv2
import subprocess

cap = cv2.VideoCapture(0)

# Настройка команды ffmpeg для отправки потока
ffmpeg_cmd = [
    'ffmpeg',
    '-y',
    '-f', 'rawvideo',
    '-vcodec', 'rawvideo',
    '-pix_fmt', 'bgr24',
    '-s', f"{int(cap.get(3))}x{int(cap.get(4))}",
    '-r', '30',
    '-i', '-',
    '-c:v', 'libx264',
    '-preset', 'ultrafast',
    '-f', 'mpegts',
    'udp://192.168.37.10:1234'
]

proc = subprocess.Popen(ffmpeg_cmd, stdin=subprocess.PIPE)

while True:
    ret, frame = cap.read()
    if not ret:
        break

    # Отправка кадра в ffmpeg
    proc.stdin.write(frame.tobytes())

    # Дополнительная обработка (если требуется)
    # ...

    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cap.release()
proc.stdin.close()
proc.wait()
