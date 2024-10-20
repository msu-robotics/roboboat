import time
import traceback


class VehicleProxy:

    def __init__(self, vehicle, mission_queue, log_mission_output):
        self.vehicle = vehicle
        self.mission_queue = mission_queue
        self.log_mission_output = log_mission_output
        self.vehicle.is_running = False

    def __getattribute__(self, name):
        if name in ['mission_queue', 'log_mission_output', 'vehicle']:
            return super(VehicleProxy, self).__getattribute__(name)

        attr = getattr(self.vehicle, name)

        try:
            is_mission_stop = self.mission_queue.get(None)
        except Exception as e:
            is_mission_stop = None

        if is_mission_stop is not None and is_mission_stop and self.vehicle.is_running:
            self.vehicle.send_movement_command(0.0, 0.0, 0.0)
            self.vehicle.send_mode_command(0)
            raise ValueError(f'Миссия была завершена или не запущена {is_mission_stop}')

        return attr


class Mission:
    def __init__(self, boat_controller, mission_running, log_mission_output):
        self.boat_controller = VehicleProxy(boat_controller, mission_running, log_mission_output)  # Объект аппарата
        self.mission_running = mission_running
        self.log_mission_output = log_mission_output
        self.current_heading = 0.0  # Текущий курс (угол рыскания)

    def run(self):

        try:
            self.log_mission_output("Запуск миссии")
            self.boat_controller.is_running = True
            self._run()
        except Exception as e:
            self.boat_controller.is_running = False
            self.log_mission_output(str(traceback.format_exc()))
            self.boat_controller.send_movement_command(0.0, 0.0, 0.0)

    def _run(self):
        # Переключение в режим стабилизации
        self.log_mission_output("Переключение в режим стабилизации.")
        self.boat_controller.send_mode_command(1)

        self.log_mission_output("Устанавливаем позицию по курсу")
        self.boat_controller.set_target_heading(self.boat_controller.get_current_yaw())

        self.log_mission_output("Движение прямо")
        self.boat_controller.send_movement_command(20.0, 0.0, 0)
        time.sleep(10)

        # Получение текущего курса от IMU аппарата
        # self.current_heading = self.boat_controller.get_current_yaw()
        # self.log_mission_output(f"Текущий курс: {self.current_heading:.2f} градусов")
        #
        # # Поворот на 90 градусов против часовой стрелки
        # self.log_mission_output("Поворот на 90 градусов против часовой стрелки.")
        # self.rotate_relative(-90.0)
        #
        # # Движение по окружности вокруг буя
        # linear_speed = 10.0  # Скорость движения вперед (%)
        # circle_duration = 30.0  # Время выполнения полного оборота (секунды)
        # self.log_mission_output("Начало движения по окружности вокруг буя.")
        # self.circle_around_buoy(linear_speed, circle_duration)
        #
        # # Поворот на 90 градусов по часовой стрелке для возвращения к исходному курсу
        # self.log_mission_output("Поворот на 90 градусов по часовой стрелке для возвращения к исходному курсу.")
        # self.rotate_relative(90.0)

        # Останавливаем аппарата после завершения миссии


        self.log_mission_output("Переключение в ручной режим.")
        self.boat_controller.send_mode_command(0)
        self.boat_controller.send_movement_command(0.0, 0.0, 0.0)

        self.log_mission_output("Миссия завершена.")

    def rotate_relative(self, angle):
        """
        Поворачивает аппарат на относительный угол (в градусах).

        :param angle: Относительный угол поворота (положительный для по часовой стрелке, отрицательный для против часовой)
        """
        target_heading = self.normalize_angle(self.current_heading + angle)
        self.log_mission_output(f"Поворот к целевому курсу: {target_heading:.2f} градусов")
        self.rotate_to_heading(target_heading)

        # Обновление текущего курса
        self.current_heading = target_heading

    def rotate_to_heading(self, target_heading):
        """
        Поворачивает аппарат к целевому курсу, используя режим стабилизации.

        :param target_heading: Целевой курс в градусах (от -180 до 180)
        """
        tolerance = 2.0  # Допустимая погрешность в градусах
        max_duration = 10.0  # Максимальное время для попытки поворота (секунды)
        start_time = time.time()

        self.boat_controller.set_target_heading(target_heading)

        while True:
            current_yaw = self.boat_controller.get_current_yaw()
            error = self.angle_difference(current_yaw, target_heading)
            if abs(error) <= tolerance:
                self.log_mission_output(f"Достигнут целевой курс: {current_yaw:.2f} градусов")
                break
            if time.time() - start_time > max_duration:
                self.log_mission_output("Время поворота истекло.")
                break
            time.sleep(0.1)

    def circle_around_buoy(self, speed, duration):
        """
        Двигает аппарат по окружности вокруг буя.

        :param speed: Скорость движения вперед (%)
        :param duration: Время выполнения полного оборота (секунды)
        """
        # Количество шагов для обновления курса
        steps = int(duration / 0.1)  # Обновление каждые 0.1 секунды
        heading_increment = 360.0 / steps  # Угол для инкрементации целевого курса на каждом шаге

        # Начальный курс
        initial_heading = self.current_heading

        self.log_mission_output(f"Начало движения по окружности с курса: {initial_heading:.2f} градусов")

        for i in range(steps):

            # Вычисление нового целевого курса
            delta_heading = heading_increment * i
            new_heading = self.normalize_angle(initial_heading + delta_heading)

            self.boat_controller.set_target_heading(new_heading)

            # Установка скорости движения вперед
            self.boat_controller.send_movement_command(speed, 0.0, 0.0)  # В режиме стабилизации yaw контролируется целевым курсом

            time.sleep(0.1)

        # Остановка двигателей после завершения движения по окружности
        self.boat_controller.send_movement_command(0.0, 0.0, 0.0)

        # Обновление текущего курса до финального курса
        self.current_heading = initial_heading  # После полного оборота курс вернется к начальному значению
        self.log_mission_output(f"Движение по окружности завершено. Текущий курс: {self.current_heading:.2f} градусов")

    @staticmethod
    def angle_difference(angle1, angle2):
        """
        Вычисляет наименьшую разницу между двумя углами в диапазоне от -180 до 180 градусов.

        :param angle1: Первый угол в градусах
        :param angle2: Второй угол в градусах
        :return: Разница в градусах (-180 до 180)
        """
        diff = angle2 - angle1
        while diff < -180.0:
            diff += 360.0
        while diff > 180.0:
            diff -= 360.0
        return diff

    @staticmethod
    def normalize_angle(angle):
        """
        Нормализует угол в диапазон от -180 до 180 градусов.

        :param angle: Угол в градусах
        :return: Нормализованный угол
        """
        while angle < -180.0:
            angle += 360.0
        while angle > 180.0:
            angle -= 360.0
        return angle