#!/bin/bash

# Выход при любой ошибке
set -o errexit

# Установка зависимостей из requirements.txt
pip install -r requirements.txt

# Сбор статических файлов
python manage.py collectstatic --no-input

# Применение миграций базы данных
python manage.py migrate