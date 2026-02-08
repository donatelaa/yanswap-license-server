# -*- coding: utf-8 -*-
"""
Flask приложение для деплоя на бесплатный хостинг (Render, Railway, Heroku и т.д.)
Работает без SSL (хостинг предоставляет HTTPS автоматически)
"""
from server import app, token_manager

# Для деплоя на хостинг (gunicorn запускает через app:app)
# Для локального запуска используйте server.py
