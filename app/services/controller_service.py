import asyncio
from threading import Lock
import websockets


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
        self._mode = 'manual'  # Режим по умолчанию
        self._forward_speed = 0.0
        self._lateral_speed = 0.0
        self._yaw_speed = 0.0

        # Инициализация WebSocket соединения с контроллером лодки
        self._connection = None
        if self._host and self._port:
            asyncio.get_event_loop().run_until_complete(self.connect_to_vehicle())

    async def connect_to_vehicle(self):
        """
        Устанавливает соединение с лодкой через WebSocket.
        """
        uri = f"ws://{self._host}:{self._port}"
        try:
            self._connection = await websockets.connect(uri)
            print(f"[VehicleController] Подключено к лодке по адресу {uri}")
        except Exception as e:
            print(f"[VehicleController] Ошибка при подключении: {e}")
            self._connection = None

    async def set_mode(self, mode: str):
        """
        Устанавливает режим работы лодки.

        :param mode: Строка, обозначающая режим ('manual', 'auto', и т.д.)
        """
        self._mode = mode
        if self._connection:
            await self._connection.send(f"SET_MODE {mode}")
        print(f"[VehicleController] Режим установлен: {mode}")

    async def set_motors(self, forward: float, lateral: float, yaw: float):
        """
        Устанавливает скорости двигателей на основе входных параметров.

        :param forward: Скорость движения вперед/назад (-1.0 до 1.0)
        :param lateral: Скорость движения влево/вправо (-1.0 до 1.0)
        :param yaw: Скорость поворота вокруг вертикальной оси (-1.0 до 1.0)
        """
        self._forward_speed = self._clamp_speed(forward)
        self._lateral_speed = self._clamp_speed(lateral)
        self._yaw_speed = self._clamp_speed(yaw)

        # Преобразование скоростей в команды для двигателей
        motor_commands = self._compute_motor_commands(
            self._forward_speed, self._lateral_speed, self._yaw_speed
        )
        if self._connection:
            await self._connection.send(f"SET_MOTORS {motor_commands}")
        print(f"[VehicleController] Двигатели установлены: forward={self._forward_speed}, "
              f"lateral={self._lateral_speed}, yaw={self._yaw_speed}")

    def _clamp_speed(self, speed: float) -> float:
        """
        Ограничивает скорость в диапазоне от -1.0 до 1.0.

        :param speed: Входная скорость
        :return: Ограниченная скорость
        """
        return max(min(speed, 1.0), -1.0)

    def _compute_motor_commands(self, forward: float, lateral: float, yaw: float):
        """
        Вычисляет команды для двигателей на основе входных скоростей.

        :param forward: Скорость движения вперед/назад
        :param lateral: Скорость движения влево/вправо
        :param yaw: Скорость поворота
        :return: Словарь с командами для двигателей
        """
        motor_left = forward - yaw
        motor_right = forward + yaw
        motor_strafe = lateral

        motor_left = self._clamp_speed(motor_left)
        motor_right = self._clamp_speed(motor_right)

        commands = {
            'motor_left': motor_left,
            'motor_right': motor_right,
            'motor_strafe': motor_strafe
        }

        print(f"[VehicleController] Вычисленные команды двигателей: {commands}")
        return commands

    async def disconnect(self):
        """
        Отключение от лодки.
        """
        if self._connection:
            await self._connection.close()
            print(f"[VehicleController] Соединение закрыто")
