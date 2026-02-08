# -*- coding: utf-8 -*-
"""
Менеджер токенов с поддержкой времени жизни и статуса.
Токены хранятся в JSON формате: tokens.json
"""
import json
import os
import secrets
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Dict, List, Tuple

APP_DIR = Path(__file__).resolve().parent
# На Render.com файлы могут не сохраняться, используем переменную окружения
# или /tmp (но лучше использовать переменные окружения для токенов)
TOKENS_FILE = Path(os.getenv("TOKENS_FILE", str(APP_DIR / "tokens.json")))


class TokenManager:
    def __init__(self):
        self.tokens_file = TOKENS_FILE
        self.tokens = self._load_tokens()

    def _load_tokens(self) -> Dict[str, Dict]:
        """Загружает токены из файла или переменной окружения."""
        # Сначала пробуем загрузить из переменной окружения (для Render.com)
        env_tokens = os.getenv("TOKENS_JSON")
        print(f"DEBUG: TOKENS_JSON env var exists: {bool(env_tokens)}")
        if env_tokens:
            try:
                data = json.loads(env_tokens)
                print(f"DEBUG: Loaded {len(data)} tokens from TOKENS_JSON")
                # Конвертируем строки дат обратно в datetime для проверки
                for token, info in data.items():
                    if "created_at" in info and isinstance(info["created_at"], str):
                        try:
                            info["created_at"] = datetime.fromisoformat(info["created_at"])
                        except:
                            pass
                    if "expires_at" in info and info["expires_at"] and isinstance(info["expires_at"], str):
                        try:
                            info["expires_at"] = datetime.fromisoformat(info["expires_at"])
                        except:
                            pass
                return data
            except (json.JSONDecodeError, ValueError) as e:
                print(f"DEBUG: Error parsing TOKENS_JSON: {e}")
                pass
        
        # Если нет в переменной окружения, загружаем из файла
        if not self.tokens_file.exists():
            print(f"DEBUG: tokens.json file does not exist: {self.tokens_file}")
            return {}
        try:
            with open(self.tokens_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                print(f"DEBUG: Loaded {len(data)} tokens from file")
                # Конвертируем строки дат обратно в datetime для проверки
                for token, info in data.items():
                    if "created_at" in info and isinstance(info["created_at"], str):
                        try:
                            info["created_at"] = datetime.fromisoformat(info["created_at"])
                        except:
                            pass
                    if "expires_at" in info and info["expires_at"] and isinstance(info["expires_at"], str):
                        try:
                            info["expires_at"] = datetime.fromisoformat(info["expires_at"])
                        except:
                            pass
                return data
        except (json.JSONDecodeError, ValueError) as e:
            print(f"DEBUG: Error loading tokens from file: {e}")
            return {}

    def _save_tokens(self):
        """Сохраняет токены в файл и обновляет переменную окружения (если нужно)."""
        # Конвертируем datetime в строки для JSON
        data = {}
        for token, info in self.tokens.items():
            data[token] = info.copy()
            if isinstance(data[token].get("created_at"), datetime):
                data[token]["created_at"] = data[token]["created_at"].isoformat()
            if isinstance(data[token].get("expires_at"), datetime):
                if data[token]["expires_at"]:
                    data[token]["expires_at"] = data[token]["expires_at"].isoformat()
        
        # Сохраняем в файл (если возможно)
        try:
            # Создаём директорию если нужно
            self.tokens_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tokens_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            # На Render.com файлы могут не сохраняться - это нормально
            print(f"Warning: Could not save tokens to file: {e}")
        
        # Также обновляем переменную окружения (для Render.com)
        # Но это не будет работать автоматически - нужно обновлять вручную в Render
        # Или использовать внешнее хранилище

    def create_token(
        self,
        custom_token: Optional[str] = None,
        days_valid: Optional[int] = None,
        hours_valid: Optional[int] = None,
        description: str = ""
    ) -> str:
        """
        Создаёт новый токен.
        
        Args:
            custom_token: Кастомный токен (если None - генерируется случайный)
            days_valid: Количество дней действия (None = бессрочный)
            hours_valid: Количество часов действия (None = бессрочный)
            description: Описание токена
        
        Returns:
            Созданный токен
        """
        if custom_token:
            token = custom_token.strip()
        else:
            token = secrets.token_hex(16)
        
        if token in self.tokens:
            raise ValueError(f"Токен уже существует: {token}")
        
        now = datetime.now()
        expires_at = None
        
        if days_valid:
            expires_at = now + timedelta(days=days_valid)
        elif hours_valid:
            expires_at = now + timedelta(hours=hours_valid)
        
        self.tokens[token] = {
            "created_at": now,
            "expires_at": expires_at,
            "active": True,
            "description": description,
            "used_count": 0,
            "last_used": None
        }
        self._save_tokens()
        return token

    def is_valid(self, token: str) -> Tuple[bool, Optional[str]]:
        """
        Проверяет валидность токена.
        
        Returns:
            (is_valid, error_message)
        """
        if token not in self.tokens:
            return False, "Токен не найден"
        
        info = self.tokens[token]
        
        if not info.get("active", True):
            return False, "Токен деактивирован"
        
        expires_at = info.get("expires_at")
        if expires_at:
            if isinstance(expires_at, str):
                expires_at = datetime.fromisoformat(expires_at)
            if datetime.now() > expires_at:
                return False, "Токен истёк"
        
        # Обновляем статистику использования
        info["used_count"] = info.get("used_count", 0) + 1
        info["last_used"] = datetime.now()
        self._save_tokens()
        
        return True, None

    def deactivate_token(self, token: str) -> bool:
        """Деактивирует токен."""
        if token not in self.tokens:
            return False
        self.tokens[token]["active"] = False
        self._save_tokens()
        return True

    def activate_token(self, token: str) -> bool:
        """Активирует токен."""
        if token not in self.tokens:
            return False
        self.tokens[token]["active"] = True
        self._save_tokens()
        return True

    def delete_token(self, token: str) -> bool:
        """Удаляет токен."""
        if token not in self.tokens:
            return False
        del self.tokens[token]
        self._save_tokens()
        return True

    def get_token_info(self, token: str) -> Optional[Dict]:
        """Получает информацию о токене."""
        if token not in self.tokens:
            return None
        info = self.tokens[token].copy()
        # Конвертируем datetime в строки для удобства
        if isinstance(info.get("created_at"), datetime):
            info["created_at"] = info["created_at"].isoformat()
        if isinstance(info.get("expires_at"), datetime):
            if info["expires_at"]:
                info["expires_at"] = info["expires_at"].isoformat()
        if isinstance(info.get("last_used"), datetime):
            info["last_used"] = info["last_used"].isoformat()
        return info

    def list_tokens(self, active_only: bool = False) -> List[Dict]:
        """Список всех токенов с информацией."""
        result = []
        for token, info in self.tokens.items():
            if active_only and not info.get("active", True):
                continue
            
            expires_at = info.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    expires_at = datetime.fromisoformat(expires_at)
                if datetime.now() > expires_at:
                    if active_only:
                        continue
            
            token_info = {
                "token": token,
                "created_at": info.get("created_at"),
                "expires_at": expires_at,
                "active": info.get("active", True),
                "description": info.get("description", ""),
                "used_count": info.get("used_count", 0),
                "last_used": info.get("last_used")
            }
            
            # Конвертируем datetime в строки
            if isinstance(token_info["created_at"], datetime):
                token_info["created_at"] = token_info["created_at"].isoformat()
            if isinstance(token_info["expires_at"], datetime):
                if token_info["expires_at"]:
                    token_info["expires_at"] = token_info["expires_at"].isoformat()
            if isinstance(token_info["last_used"], datetime):
                token_info["last_used"] = token_info["last_used"].isoformat()
            
            result.append(token_info)
        
        return result

    def get_time_remaining(self, token: str) -> Optional[str]:
        """Возвращает оставшееся время действия токена в читаемом формате."""
        if token not in self.tokens:
            return None
        
        info = self.tokens[token]
        expires_at = info.get("expires_at")
        
        if not expires_at:
            return "Бессрочный"
        
        if isinstance(expires_at, str):
            expires_at = datetime.fromisoformat(expires_at)
        
        now = datetime.now()
        if now > expires_at:
            return "Истёк"
        
        delta = expires_at - now
        days = delta.days
        hours, remainder = divmod(delta.seconds, 3600)
        minutes, _ = divmod(remainder, 60)
        
        parts = []
        if days > 0:
            parts.append(f"{days} дн.")
        if hours > 0:
            parts.append(f"{hours} ч.")
        if minutes > 0 and days == 0:
            parts.append(f"{minutes} мин.")
        
        return ", ".join(parts) if parts else "Меньше минуты"
