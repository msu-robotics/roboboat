import time

from paramiko.py3compat import is_callable


# from boat_controller import BoatController


class VehicleProxy:

    def __init__(self, vehicle, mission_queue, log_mission_output):
        self.vehicle = vehicle
        self.mission_queue = mission_queue
        self.log_mission_output = log_mission_output

    def __getattribute__(self, name):
        if name in ['mission_queue', 'log_mission_output', 'vehicle']:
            return super(VehicleProxy, self).__getattribute__(name)

        attr = getattr(self.vehicle, name)

        try:
            is_mission_stop = self.mission_queue.get(None)
        except Exception as e:
            is_mission_stop = None

        if is_mission_stop is not None and is_mission_stop:
            self.log_mission_output('Миссия была завершена или не запущена')
            raise ValueError('Миссия была завершена или не запущена')

        return attr


class Mission:
    def __init__(self, boat_controller, mission_running, log_mission_output):
        self.boat_controller = VehicleProxy(boat_controller, mission_running, log_mission_output)  # Объект аппарата
        self.mission_running = mission_running
        self.log_mission_output = log_mission_output

    def run(self):

        try:
            self.log_mission_output("Запуск миссии")
            self._run()
        except Exception as e:
            self.log_mission_output(str(e))
            self.boat_controller.send_movement_command(0.0, 0.0, 0.0)

    def _run(self):
        # Пример выполнения миссии
        for i in range(50):
            # Выполняем действие
            self.boat_controller.send_movement_command(10.0, 0.0, 0.0)
            self.log_mission_output(f"Шаг {i+1}: Движение вперед.")
            time.sleep(1)
        # Останавливаем аппарата после завершения миссии
        self.boat_controller.send_movement_command(0.0, 0.0, 0.0)
        self.log_mission_output("Миссия завершена.")
