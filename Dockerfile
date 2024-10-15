# Используем официальный образ Python
FROM python:3.12-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Устанавливаем зависимости для сборки фронтенда
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/* \
    && curl -LsSf https://astral.sh/uv/install.sh | sh

# Устанавливаем Node.js (для сборки фронтенда)
RUN curl -fsSL https://deb.nodesource.com/setup_16.x | bash - && \
    apt-get install -y nodejs && \
    rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей Python
COPY pyproject.toml .
COPY uv.lock .

# Устанавливаем зависимости Python
RUN /root/.cargo/bin/uv sync

# Копируем бэкенд
COPY ./app ./app

## Копируем фронтенд
#COPY ./frontend ./frontend
#
## Сборка фронтенда
#RUN cd ./frontend && \
#    npm install && \
#    npm run build

## Удаляем исходники фронтенда и node_modules для уменьшения размера образа
#RUN rm -rf ./frontend/node_modules && \
#    rm -rf ./frontend/src && \
#    rm -rf ./frontend/public

# Переносим сборку фронтенда в директорию, откуда FastAPI будет обслуживать статические файлы
# (Если вы уже указали правильный путь в app.mount, этот шаг можно пропустить)
# В данном случае файлы уже находятся в нужной директории

# Открываем порт для доступа
EXPOSE 5000

ENV vehicle_host "192.168.43.8"
ENV vehicle_port 5000

# Запускаем приложение
CMD ["/root/.cargo/bin/uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "5000"]
