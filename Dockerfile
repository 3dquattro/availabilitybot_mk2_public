# Основа - официальный образ python 3
FROM python:3.9

# Зададим рабочую директорию
WORKDIR /app

# Установим зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Скопируем всё что есть в контейнер
COPY . .

# Запускаем приложение
CMD ["python", "main.py"]