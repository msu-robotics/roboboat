import asyncio
import json
from threading import Lock
from websockets.asyncio.client import connect
from enum import Enum
from loguru import logger
import aiohttp


class VehicleModes(Enum):
    MANUAL = "manual"
    STABILIZE = "stabilize"


class VehicleController:
    """
    Класс для управления роболодкой.

    Использует паттерн Singleton для обеспечения единственного экземпляра.
    """

    _instance = None
    _lock: Lock = Lock()

    def __new__(cls, host: str = None, port: int = None):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(VehicleController, cls).__new__(cls)
                cls._instance._initialize(host, port)
        return cls._instance

    def _initialize(self, host: str, port: int):
        """
        Инициализация контроллера роболодки с заданным хостом и портом.
        """
        self._host = host
        self._port = port
        self._mode = VehicleModes.MANUAL  # Режим по умолчанию

        self._speed_multiplier = 100
        self._forward_speed = 0.0
        self._lateral_speed = 0.0
        self._yaw_speed = 0.0
        self._yaw_target_position = 0.0

        # переменные для значений pid регулятора по yaw
        self._yaw_pid_p = 0
        self._yaw_pid_i = 0
        self._yaw_pid_d = 0

        # переменные под телеметрию
        self._magnetometer = {
            "pitch": 0.0,
            "roll": 0.0,
            "yaw": 0.0,
        }
        self._thrusters: list[int] = [0, 0, 0, 0]

        # Инициализация WebSocket соединения с контроллером лодки
        self._telemetry_connection = None
        self._control_connection = None
        self._http_session = None
        if self._host and self._port:
            loop = asyncio.get_event_loop()
            loop.create_task(self.connect_to_vehicle())
            loop.create_task(self.send_data_loop())
            loop.create_task(self.telemetry_loop())
            loop.create_task(self.refresh_pid_settings())

    def get_magnetometer_telemetry(self) -> dict:
        return self._magnetometer

    def get_pwm_telemetry(self) -> dict:
        return self._thrusters

    async def refresh_pid_settings(self) -> dict:
        while not self._http_session:
            await asyncio.sleep(0.1)

        async with self._http_session.get(
            f"http://{self._host}:{self._port}/pid_settings"
        ) as resp:
            pid_settings = await resp.json()
            logger.debug(f"Получены настройки pid регулятора {pid_settings}")
            self._yaw_pid_p = pid_settings.get("pGain")
            self._yaw_pid_i = pid_settings.get("iGain")
            self._yaw_pid_d = pid_settings.get("dGain")
        return {
            "p_gain": self._yaw_pid_p,
            "i_gain": self._yaw_pid_i,
            "d_gain": self._yaw_pid_d,
        }

    def get_pid_settings(self) -> dict:
        return {
            "p_gain": self._yaw_pid_p,
            "i_gain": self._yaw_pid_i,
            "d_gain": self._yaw_pid_d,
        }

    async def connect_to_vehicle(self):
        """
        Устанавливает соединение с лодкой через WebSocket.
        """
        base_url = f"ws://{self._host}:{self._port}"
        telemetry_url = f"{base_url}/telemetry"
        try:
            self._telemetry_connection = await connect(telemetry_url)
            logger.info(f"Подключено к телеметрии лодки по адресу {telemetry_url}")
        except Exception as e:
            logger.exception(f"Ошибка при подключении к сокету телеметрии: {e}")
            self._telemetry_connection = None

        control_url = f"{base_url}/ws"
        try:
            self._control_connection = await connect(control_url)
            logger.info(
                f"Подключено к сокету управления лодкой по адресу {control_url}"
            )
        except Exception as e:
            logger.exception(
                f"Ошибка при подключении к сокету управления: {control_url}"
            )
            self._control_connection = None

        self._http_session = aiohttp.ClientSession()

    async def send_data_loop(self):
        """
        Отправляет управляющий пакет на лодку через WebSocket
        """
        while True:
            if self._control_connection:
                await self._control_connection.send(
                    json.dumps(
                        {
                            "speedMultiplier": self._speed_multiplier,
                            "forward": self._forward_speed,
                            "lateral": self._lateral_speed,
                            "yaw": self._yaw_speed
                            if self._mode == VehicleModes.MANUAL
                            else self._yaw_target_position,
                            "mode": self._mode.value,
                        }
                    )
                )
            await asyncio.sleep(0.1)

    async def telemetry_loop(self):
        """
        Обновляет состояние телеметрии аппарата
        """
        logger.debug("Запуск цикла обновления телеметрии")
        while True:
            if self._telemetry_connection:
                actual_telemetry = json.loads(await self._telemetry_connection.recv())
                self._magnetometer = actual_telemetry.get(
                    "magnetometer", {"pitch": 0.0, "roll": 0.0, "yaw": 0.0}
                )
                self._pwm = actual_telemetry.get(
                    "pwm",
                    [
                        0,
                        0,
                        0,
                        0,
                    ],
                )
            await asyncio.sleep(0.1)

    async def set_mode(self, mode: VehicleModes):
        """
        Устанавливает режим работы лодки.

        :param mode: Строка, обозначающая режим ('manual', 'auto', и т.д.)
        """
        self._mode = mode

    async def set_motors(
        self, forward: float, lateral: float, yaw: float, speed: float
    ):
        """
        Устанавливает скорости движения.

        :param forward: Скорость движения вперед/назад (-1.0 до 1.0)
        :param lateral: Скорость движения влево/вправо (-1.0 до 1.0)
        :param yaw: Скорость поворота вокруг вертикальной оси (-1.0 до 1.0)
        :param speed: Множитель скорости (0 до 100)
        """
        self._forward_speed = self._clamp_speed(forward)
        self._lateral_speed = self._clamp_speed(lateral)
        self._yaw_speed = self._clamp_speed(yaw)
        self._speed_multiplier = max(min(speed, 100), 0)

    def _clamp_speed(self, speed: float) -> float:
        """
        Ограничивает скорость в диапазоне от -1.0 до 1.0.

        :param speed: Входная скорость
        :return: Ограниченная скорость
        """
        return max(min(speed, 1.0), -1.0)

    async def disconnect(self):
        """
        Отключение от лодки.
        """
        if self._connection:
            await self._connection.close()
            logger.info(f"Соединение закрыто")
