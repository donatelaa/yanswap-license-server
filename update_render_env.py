# -*- coding: utf-8 -*-
"""
Скрипт для обновления переменной окружения TOKENS_JSON на Render.com
Использование: python update_render_env.py

ВНИМАНИЕ: Это требует API ключ Render.com или ручного обновления через веб-интерфейс.
"""
import json
import os
from pathlib import Path
from token_manager import TokenManager

def main():
    token_manager = TokenManager()
    tokens = token_manager.list_tokens()
    
    # Конвертируем в JSON строку
    data = {}
    for token_info in tokens:
        token = token_info.get("token")
        if token:
            data[token] = {
                "created_at": token_info.get("created_at"),
                "expires_at": token_info.get("expires_at"),
                "active": token_info.get("active", True),
                "description": token_info.get("description", ""),
                "used_count": token_info.get("used_count", 0),
                "last_used": token_info.get("last_used")
            }
    
    tokens_json = json.dumps(data, indent=2, ensure_ascii=False)
    
    print("=" * 60)
    print("Обновите переменную окружения TOKENS_JSON на Render.com:")
    print("=" * 60)
    print()
    print("1. Перейдите на https://dashboard.render.com")
    print("2. Выберите ваш сервис: yanswap-license-server")
    print("3. Перейдите в 'Environment'")
    print("4. Добавьте/обновите переменную:")
    print("   Key: TOKENS_JSON")
    print("   Value: (скопируйте из файла tokens_json_output.txt)")
    print()
    print("Или используйте Render API (нужен API ключ)")
    print()
    
    # Сохраняем в файл для удобства
    output_file = Path(__file__).parent / "tokens_json_output.txt"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(tokens_json)
    
    print(f"JSON сохранён в: {output_file}")
    print()
    print("Количество токенов:", len(data))
    print("Активных токенов:", sum(1 for t in data.values() if t.get("active", True)))


if __name__ == "__main__":
    main()
