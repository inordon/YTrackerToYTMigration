#!/usr/bin/env python3
"""
Подробная диагностика процесса миграции
"""

import requests
import json
import logging

# Включаем максимальное логирование
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def test_detailed_process():
    config = load_config()

    # Настройки YouTrack
    base_url = config['youtrack']['url'].rstrip('/')
    token = config['youtrack']['token']

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # Получаем первых 10 пользователей из Yandex
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
        'Content-Type': 'application/json'
    }

    response = requests.get(
        'https://api.tracker.yandex.net/v2/users?page=1&perPage=10',
        headers=yandex_headers
    )

    yandex_users = response.json()

    print("🔍 ПОДРОБНАЯ ДИАГНОСТИКА ПЕРВЫХ 10 ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 60)

    for i, user in enumerate(yandex_users, 1):
        login = user.get('login')
        yandex_id = user.get('id')
        email = user.get('email')

        print(f"\n{i}. 👤 Пользователь: {login} (ID: {yandex_id})")
        print(f"   📧 Email: {email}")

        # Проверка существования через API
        try:
            response = requests.get(
                f"{base_url}/api/users",
                headers=headers,
                params={'query': login, 'fields': 'id,login', '$top': 100}
            )

            if response.status_code == 200:
                api_users = response.json()
                found_in_api = any(u.get('login') == login for u in api_users if isinstance(u, dict))
                print(f"   🔍 Найден через API: {found_in_api}")

                if found_in_api:
                    for u in api_users:
                        if isinstance(u, dict) and u.get('login') == login:
                            print(f"   🆔 ID в YouTrack: {u.get('id')}")
                            print(f"   ⏭️  РЕЗУЛЬТАТ: Пропускаем (уже существует)")
                            break
                else:
                    print(f"   🆕 НЕ НАЙДЕН в YouTrack - НУЖНО СОЗДАТЬ")

                    # Пытаемся создать
                    yt_user = {
                        'login': login,
                        'name': user.get('display', login),
                        'isActive': True
                    }

                    if email:
                        yt_user['email'] = email

                    print(f"   🔨 Попытка создания...")
                    create_response = requests.post(
                        f"{base_url}/hub/api/rest/users",
                        headers=headers,
                        json=yt_user,
                        params={'fields': 'id,login,name'}
                    )

                    print(f"   📊 Результат создания: {create_response.status_code}")
                    if create_response.status_code in [200, 201]:
                        created = create_response.json()
                        print(f"   ✅ СОЗДАН! ID: {created.get('id')}")
                    elif create_response.status_code == 409:
                        print(f"   ⚠️  УЖЕ СУЩЕСТВУЕТ (409)")
                    else:
                        print(f"   ❌ ОШИБКА: {create_response.text}")
            else:
                print(f"   ❌ Ошибка API: {response.status_code}")

        except Exception as e:
            print(f"   💥 Исключение: {e}")

        print(f"   " + "-" * 50)

if __name__ == "__main__":
    test_detailed_process()