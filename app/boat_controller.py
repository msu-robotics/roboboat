import socket
import struct
import threading
import queue
import time

# Заголовки команд
CMD_MOVE = 0x01       # Команда для установки скоростей движения
CMD_PID = 0x02        # Команда для установки параметров PID-регулятора
CMD_TELEMETRY = 0x03  # Заголовок для телеметрии (используется при получении данных)
CMD_LED = 0x04        # Команда для управления LED-лентой
CMD_GPIO = 0x05       # Команда для управления GPIO пином
CMD_MODE = 0x06       # Команда для переключения режима работы
CMD_PROBE_CONTROL = 0x07  # Команда для управления пробоотборником

# Форматы пакетов
# Команда движения: заголовок (1 байт) + forward (float) + lateral (float) + yaw (float)
MOVE_CMD_STRUCT = 'Bfff'  # B: unsigned char, f: float

# Команда PID: заголовок (1 байт) + P (float) + I (float) + D (float)
PID_CMD_STRUCT = 'Bfff'

# Данные телеметрии: заголовок (1 байт) + roll (float) + pitch (float) + yaw (float) + adc_value (float)
# + pwm двигателей (float * 4)
TELEMETRY_STRUCT = 'Bfffffffffff'  # B: unsigned char, f: float

# Команда LED: заголовок (1 байт) + режим (1 байт) + R (1 байт) + G (1 байт) + B (1 байт)
LED_CMD_STRUCT = 'BBBBB'  # B: unsigned char

# Команда GPIO: заголовок (1 байт) + состояние (1 байт)
GPIO_CMD_STRUCT = 'BB'    # B: unsigned char

# Команда режима: заголовок (1 байт) + режим (1 байт)
MODE_CMD_STRUCT = 'BB'    # B: unsigned char

# Команда управления пробоотборником: заголовок (1 байт) + действие (1 байт) + таймаут (2 байта, unsigned short)
PROBE_CONTROL_STRUCT = 'BBH'  # B: unsigned char, H: unsigned short (для таймаута в секундах)


class BoatController:
    def __init__(self, esp32_ip, esp32_port=5005, local_port=5006):
        """
        Класс для взаимодействия с лодкой по UDP.

        :param esp32_ip: IP-адрес ESP32 (лодки)
        :param esp32_port: Порт ESP32 для приема команд (по умолчанию 5005)
        :param local_port: Локальный порт для приема телеметрии (по умолчанию 5006)
        """
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.local_port = local_port

        # Создаем UDP сокет для отправки команд
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

        # Создаем UDP сокет для приема телеметрии
        self.telemetry_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.telemetry_socket.bind(('', self.local_port))
        self.telemetry_socket.settimeout(1.0)

        self.telemetry_thread = None
        self.telemetry_running = False

        # Хранение состояния телеметрии
        self.telemetry_data = {
            'roll': 0.0,
            'pitch': 0.0,
            'yaw': 0.0,
            'adc_value': 0.0,
            'motor_pwms': [0.0, 0.0, 0.0, 0.0],
            'pid': {'p': 0, 'i': 0, 'd': 0}
        }

        # Хранение текущих скоростей движения
        self.current_forward_speed = 0.0
        self.current_lateral_speed = 0.0
        self.current_yaw_speed = 0.0

        self.lock = threading.Lock()
        self.mode = 0

        # Очередь команд
        self.command_queue = queue.Queue()

        # Поток для отправки команд
        self.command_thread = None
        self.command_running = False

    def start(self):
        """
        Запустить фоновые потоки для отправки команд и получения телеметрии.
        """
        self.telemetry_running = True
        self.command_running = True

        # Запуск потока телеметрии
        self.telemetry_thread = threading.Thread(target=self._receive_telemetry_thread)
        self.telemetry_thread.daemon = True
        self.telemetry_thread.start()

        # Запуск потока отправки команд
        self.command_thread = threading.Thread(target=self._send_commands_thread)
        self.command_thread.daemon = True
        self.command_thread.start()

        # Отправляем начальный пакет, чтобы лодка знала адрес и порт для телеметрии
        self._send_initial_packet()

    def stop(self):
        """
        Остановить фоновые потоки.
        """
        self.telemetry_running = False
        self.command_running = False

        if self.telemetry_thread is not None:
            self.telemetry_thread.join()
            self.telemetry_thread = None

        if self.command_thread is not None:
            self.command_thread.join()
            self.command_thread = None

    def _send_initial_packet(self):
        """
        Отправить начальный пакет для уведомления лодки об адресе и порте для телеметрии.
        """
        # Отправляем команду движения с текущими скоростями
        packet = struct.pack(MOVE_CMD_STRUCT, CMD_MOVE, self.current_forward_speed, self.current_lateral_speed, self.current_yaw_speed)
        self.command_socket.sendto(packet, (self.esp32_ip, self.esp32_port))

    def _send_commands_thread(self):
        """
        Фоновый поток для отправки команд лодке.
        """
        while self.command_running:
            try:
                # Проверяем, есть ли команды в очереди
                try:
                    # Ожидаем команду из очереди в течение определенного времени
                    command_packet = self.command_queue.get(timeout=0.1)
                    # Отправляем команду
                    self.command_socket.sendto(command_packet, (self.esp32_ip, self.esp32_port))
                except queue.Empty:
                    # Если очередь пуста, отправляем текущую команду движения
                    with self.lock:
                        packet = struct.pack(MOVE_CMD_STRUCT, CMD_MOVE, self.current_forward_speed, self.current_lateral_speed, self.current_yaw_speed)
                    self.command_socket.sendto(packet, (self.esp32_ip, self.esp32_port))
                # Задержка перед следующей отправкой
                time.sleep(0.1)  # Отправляем команды каждые 100 мс
            except Exception as e:
                print("Ошибка в потоке отправки команд:", e)
                time.sleep(0.1)

    def _receive_telemetry_thread(self):
        """
        Фоновый поток для приема телеметрии от лодки.
        """
        while self.telemetry_running:
            try:
                data, addr = self.telemetry_socket.recvfrom(1024)
                if data[0] == CMD_TELEMETRY:
                    telemetry = self._parse_telemetry_packet(data)
                    if telemetry:
                        with self.lock:
                            self.telemetry_data = telemetry
            except socket.timeout:
                pass  # Таймаут приема данных
            except Exception as e:
                print("Ошибка при получении телеметрии:", e)

    def _parse_telemetry_packet(self, packet):
        """
        Разбор пакета телеметрии.
        """
        try:
            unpacked = struct.unpack(TELEMETRY_STRUCT, packet)
            _, roll, pitch, yaw, adc_value, motor1_pwm, motor2_pwm, motor3_pwm, motor4_pwm, kp, ki, kd = unpacked
            telemetry = {
                'roll': roll,
                'pitch': pitch,
                'yaw': yaw,
                'adc_value': adc_value,
                'motor_pwms': [motor1_pwm, motor2_pwm, motor3_pwm, motor4_pwm],
                'pid': {'p': kp, 'i': ki, 'd': kd}
            }
            return telemetry
        except Exception as e:
            print("Ошибка при разборе пакета телеметрии:", e)
            return None

    def get_telemetry(self):
        """
        Получить последнюю полученную телеметрию.

        :return: Словарь с телеметрией
        """
        with self.lock:
            return self.telemetry_data.copy()

    def send_movement_command(self, forward_speed, lateral_speed, yaw_speed):
        """
        Установить текущие скорости движения лодки.

        :param forward_speed: Скорость вперед (float)
        :param lateral_speed: Скорость вбок (float)
        :param yaw_speed: Скорость поворота (float)
        """
        with self.lock:
            self.current_forward_speed = forward_speed
            self.current_lateral_speed = lateral_speed
            self.current_yaw_speed = yaw_speed

    def send_pid_command(self, p_gain, i_gain, d_gain):
        """
        Отправить параметры PID-регулятора лодке.

        :param p_gain: Пропорциональный коэффициент (float)
        :param i_gain: Интегральный коэффициент (float)
        :param d_gain: Дифференциальный коэффициент (float)
        """
        packet = struct.pack(PID_CMD_STRUCT, CMD_PID, p_gain, i_gain, d_gain)
        self.command_queue.put(packet)

    def send_probe_command(self, direction, timeout=0):
        """
        Отправить команду на пробоотборник

        :param direction: Направление движения (int) 1-up 2-down 3-stop
        :param timeout: Время в секундах до остановки(int)
        """
        packet = struct.pack(PROBE_CONTROL_STRUCT, CMD_PROBE_CONTROL, direction, timeout)
        self.command_queue.put(packet)

    def send_led_command(self, mode, r, g, b):
        """
        Отправить команду управления LED-лентой лодке.

        :param mode: Режим LED (0: выкл, 1: статичный, 2: мигание, 3: радуга)
        :param r: Красный компонент (0-255)
        :param g: Зеленый компонент (0-255)
        :param b: Синий компонент (0-255)
        """
        packet = struct.pack(LED_CMD_STRUCT, CMD_LED, mode, r, g, b)
        self.command_queue.put(packet)

    def send_gpio_command(self, state):
        """
        Отправить команду управления GPIO пином лодке.

        :param state: Состояние GPIO (0: низкий уровень, 1: высокий уровень)
        """
        packet = struct.pack(GPIO_CMD_STRUCT, CMD_GPIO, state)
        self.command_queue.put(packet)

    def send_mode_command(self, mode):
        """
        Отправить команду переключения режима работы лодке.

        :param mode: Режим работы (0: ручной, 1: стабилизация)
        """
        packet = struct.pack(MODE_CMD_STRUCT, CMD_MODE, mode)
        self.mode = mode
        self.command_queue.put(packet)

    def close(self):
        """
        Закрыть соединение и остановить все фоновые процессы.
        """
        self.stop()
        self.command_socket.close()
        self.telemetry_socket.close()
