# -*- coding: utf-8 -*-
"""
Сервер лицензий для Yanswap (telegraam addon).
Эндпоинты: activate, heartbeat, hook_config.
Токены управляются через TokenManager (поддержка времени жизни и статуса).
"""
import os
import ssl
import json
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify
from flask_cors import CORS

from token_manager import TokenManager

APP_DIR = Path(__file__).resolve().parent

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для работы с приложением
token_manager = TokenManager()


def get_token_from_request():
    """Токен может быть в JSON body или в form."""
    # Логируем запрос для отладки
    print(f"DEBUG: Request method: {request.method}")
    print(f"DEBUG: Request content-type: {request.content_type}")
    print(f"DEBUG: Request data: {request.get_data(as_text=True)[:200]}")
    
    if request.is_json:
        data = request.get_json(silent=True) or {}
        print(f"DEBUG: JSON data: {data}")
        token = data.get("token") or data.get("Token")
        print(f"DEBUG: Extracted token: {token}")
        return token
    
    # Также пробуем form data
    form_token = request.form.get("token") or request.form.get("Token")
    if form_token:
        print(f"DEBUG: Form token: {form_token}")
        return form_token
    
    # Пробуем получить из query string
    query_token = request.args.get("token") or request.args.get("Token")
    if query_token:
        print(f"DEBUG: Query token: {query_token}")
        return query_token
    
    return None


def check_token():
    """Проверяет токен через TokenManager."""
    token = get_token_from_request()
    print(f"DEBUG: check_token called, token: {token}")
    
    if not token:
        print("DEBUG: No token found in request")
        return None, jsonify({"detail": "Missing token", "ok": False}), 400
    
    # Показываем доступные токены для отладки
    all_tokens = list(token_manager.tokens.keys())
    print(f"DEBUG: Available tokens: {all_tokens[:5]}... (total: {len(all_tokens)})")
    print(f"DEBUG: Checking token: {token[:20]}...")
    
    is_valid, error = token_manager.is_valid(token)
    print(f"DEBUG: Token validation result: valid={is_valid}, error={error}")
    
    if not is_valid:
        return None, jsonify({"detail": error or "Invalid token", "ok": False}), 403
    
    return token, None


# --- Эндпоинты (несколько вариантов путей на случай разного API) ---

@app.route("/activate", methods=["POST", "GET"])
@app.route("/api/activate", methods=["POST", "GET"])
def activate():
    print(f"DEBUG: /activate called, method: {request.method}")
    token, err = check_token()
    if err:
        print(f"DEBUG: Token check failed: {err.get_json() if hasattr(err, 'get_json') else err}")
        return err
    
    print(f"DEBUG: Token validated successfully: {token}")
    # Успешная активация
    return jsonify({"ok": True, "success": True, "token": token})


@app.route("/heartbeat", methods=["POST", "GET"])
@app.route("/api/heartbeat", methods=["POST", "GET"])
def heartbeat():
    token, err = check_token()
    if err:
        return err
    return jsonify({"ok": True})


@app.route("/hook_config", methods=["POST", "GET"])
@app.route("/api/hook_config", methods=["POST", "GET"])
def hook_config():
    token, err = check_token()
    if err:
        return err
    # HookConfigResp(ok=...) — приложение ждёт ok
    return jsonify({"ok": True})


@app.route("/", methods=["GET"])
def root():
    tokens = token_manager.list_tokens()
    active_tokens = [t for t in tokens if t.get("active", True)]
    # Показываем первые несколько токенов для отладки (первые 10 символов)
    token_previews = [t["token"][:10] + "..." for t in tokens[:5]]
    return jsonify({
        "service": "license",
        "endpoints": ["/activate", "/heartbeat", "/hook_config", "/sync_tokens"],
        "tokens_file": str(token_manager.tokens_file),
        "total_tokens": len(tokens),
        "active_tokens": len(active_tokens),
        "token_previews": token_previews,  # Для отладки
        "has_env_tokens": bool(os.getenv("TOKENS_JSON")),
    })


@app.route("/test", methods=["GET", "POST"])
def test():
    """Тестовый эндпоинт для проверки работы сервера"""
    token = get_token_from_request()
    tokens = token_manager.list_tokens()
    return jsonify({
        "status": "ok",
        "received_token": token[:20] + "..." if token else None,
        "total_tokens": len(tokens),
        "token_list": [t["token"][:20] + "..." for t in tokens[:10]],
        "has_env": bool(os.getenv("TOKENS_JSON")),
    })


@app.route("/sync_tokens", methods=["POST"])
def sync_tokens():
    """Синхронизация токенов от бота на сервер"""
    try:
        data = request.get_json()
        if not data or "tokens" not in data:
            return jsonify({"ok": False, "error": "Invalid request"}), 400
        
        tokens_data = data["tokens"]
        
        # Обновляем токены на сервере
        for token_info in tokens_data:
            token = token_info.get("token")
            if not token:
                continue
            
            try:
                # Проверяем, существует ли токен
                if token not in token_manager.tokens:
                    # Создаём новый токен
                    expires_at = None
                    if token_info.get("expires_at"):
                        expires_at = datetime.fromisoformat(token_info["expires_at"])
                    
                    created_at = datetime.now()
                    if token_info.get("created_at"):
                        created_at = datetime.fromisoformat(token_info["created_at"])
                    
                    token_manager.tokens[token] = {
                        "created_at": created_at,
                        "expires_at": expires_at,
                        "active": token_info.get("active", True),
                        "description": token_info.get("description", ""),
                        "used_count": token_info.get("used_count", 0),
                        "last_used": None
                    }
                else:
                    # Обновляем существующий токен
                    if "active" in token_info:
                        token_manager.tokens[token]["active"] = token_info["active"]
                    if "description" in token_info:
                        token_manager.tokens[token]["description"] = token_info["description"]
            except Exception as e:
                print(f"Ошибка при синхронизации токена {token}: {e}")
                continue
        
        token_manager._save_tokens()
        
        return jsonify({"ok": True, "synced": len(tokens_data)})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


# --- Запуск с HTTPS ---

def main():
    # Проверяем, запускаем ли мы локально или на хостинге
    port = int(os.getenv("PORT", 8443))
    
    cert_file = APP_DIR / "server.crt"
    key_file = APP_DIR / "server.key"
    
    if cert_file.exists() and key_file.exists() and port == 8443:
        # Локальный запуск с SSL
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        context.load_cert_chain(str(cert_file), str(key_file))
        app.run(host="0.0.0.0", port=port, ssl_context=context, debug=False)
    else:
        # Запуск без SSL (для хостинга или тестирования)
        # Хостинг предоставляет HTTPS автоматически
        app.run(host="0.0.0.0", port=port, debug=False)


if __name__ == "__main__":
    main()
