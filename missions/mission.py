import time
from boat_controller import BoatController


class Mission:
    def __init__(self, boat_controller: BoatController, mission_running, log_mission_output):
        self.boat_controller = boat_controller  # Объект аппарата
        self.mission_running = mission_running
        self.log_mission_output = log_mission_output

    def run(self):

        try:
            self._run()
        except Exception as e:
            self.log_mission_output(str(e))
            self.boat_controller.send_movement_command(0.0, 0.0, 0.0)


    def _run(self):
        # Пример выполнения миссии
        for i in range(5):
            # Проверяем, не была ли миссия остановлена
            if not self.mission_running:
                self.log_mission_output("Миссия не запущена")
                break
            # Выполняем действие
            self.boat_controller.send_movement_command(10.0, 0.0, 0.0)
            self.log_mission_output(f"Шаг {i+1}: Движение вперед.")
            time.sleep(1)
        # Останавливаем аппарата после завершения миссии
        self.boat_controller.send_movement_command(0.0, 0.0, 0.0)
        self.log_mission_output("Миссия завершена.")
