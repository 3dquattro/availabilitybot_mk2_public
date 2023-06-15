"""
Модуль, содержащий основные элементы конфигурации приложения
"""
import os

# Параметры подключения к БД

db_params = {
    "engine": os.environ["DB_ENGINE"],
    "host": os.environ["DB_HOST"],
    "port": os.environ["DB_PORT"],
    "user": os.environ["DB_USER"],
    "password": os.environ["DB_PASSWORD"],
    "db_name": os.environ["DB_NAME"],
}

# Параметры соединения с телеграмом
token = os.environ["API_TOKEN"]

# Число попыток пинга
max_tries = os.environ["MAX_TRIES"]

# Время между сессиями пингов, в секундах
period = os.environ["PING_PERIOD"]

# Время между попытками пинга в случае неудачи, с.
retry_period = os.environ["RETRY_PERIOD"]
