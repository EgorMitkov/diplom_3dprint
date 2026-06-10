#!/bin/bash

# Выход при любой ошибке
set -o errexit

# Установка зависимостей из requirements.txt
pip install -r requirements.txt

# Сбор статических файлов
python manage.py collectstatic --no-input

# Применение миграций базы данных
python manage.py migrate

# После миграций (в конце build.sh)
python manage.py shell <<EOF
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(username='admin').exists():
    User.objects.create_superuser('admin', 'admin@example.com', 'admin123')
    print("✅ Администратор создан")
else:
    print("ℹ️ Администратор уже существует")
EOF