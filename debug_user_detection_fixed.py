#!/usr/bin/env python3
"""
Исправленная диагностика проблемы с пользователями
"""

import requests
import json
import logging

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def test_user_detection():
    config = load_config()

    base_url = config['youtrack']['url'].rstrip('/')
    token = config['youtrack']['token']

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
        'Content-Type': 'application/json'
    }

    # Получаем первых пользователей из Yandex
    response = requests.get(
        'https://api.tracker.yandex.net/v2/users?page=1&perPage=3',
        headers=yandex_headers
    )

    yandex_users = response.json()

    print("🔍 ДИАГНОСТИКА API ОТВЕТОВ")
    print("=" * 50)

    for i, user in enumerate(yandex_users, 1):
        login = user.get('login')
        print(f"\n{i}. 👤 Пользователь: {login}")

        # Тест 1: Что возвращает обычный API
        try:
            response = requests.get(
                f"{base_url}/api/users",
                headers=headers,
                params={'query': login, 'fields': 'id,login', '$top': 10}
            )

            print(f"   📋 API users: {response.status_code}")
            if response.status_code == 200:
                api_data = response.json()
                print(f"   📄 Тип ответа API: {type(api_data)}")
                print(f"   📊 Длина ответа: {len(api_data) if isinstance(api_data, list) else 'не список'}")

                if isinstance(api_data, list):
                    found = any(u.get('login') == login for u in api_data if isinstance(u, dict))
                    print(f"   ✅ Найден через API: {found}")
                    if found:
                        for u in api_data:
                            if isinstance(u, dict) and u.get('login') == login:
                                print(f"   🆔 ID: {u.get('id')}")
                else:
                    print(f"   📝 Ответ: {str(api_data)[:200]}...")
        except Exception as e:
            print(f"   ❌ Ошибка API: {e}")

        # Тест 2: Что возвращает Hub API
        try:
            response = requests.get(
                f"{base_url}/hub/api/rest/users",
                headers=headers,
                params={'query': login, 'fields': 'id,login', '$top': 10}
            )

            print(f"   🏢 Hub API: {response.status_code}")
            if response.status_code == 200:
                hub_data = response.json()
                print(f"   📄 Тип ответа Hub: {type(hub_data)}")
                print(f"   📊 Длина ответа: {len(hub_data) if isinstance(hub_data, (list, dict)) else 'не коллекция'}")

                if isinstance(hub_data, list):
                    found = any(u.get('login') == login for u in hub_data if isinstance(u, dict))
                    print(f"   ✅ Найден через Hub: {found}")
                elif isinstance(hub_data, dict):
                    print(f"   📝 Hub возвращает объект, а не список")
                    print(f"   🔑 Ключи: {list(hub_data.keys())}")
                else:
                    print(f"   📝 Ответ Hub: {str(hub_data)[:200]}...")
        except Exception as e:
            print(f"   ❌ Ошибка Hub: {e}")

        # Тест 3: Попытка создания с подробным логом
        print(f"   🔨 Попытка создания пользователя {login}...")

        yt_user = {
            'login': login,
            'name': user.get('display', login),
            'isActive': True
        }

        if user.get('email'):
            yt_user['email'] = user.get('email')

        print(f"   📦 Данные для создания: {json.dumps(yt_user, ensure_ascii=False)}")

        try:
            response = requests.post(
                f"{base_url}/hub/api/rest/users",
                headers=headers,
                json=yt_user,
                params={'fields': 'id,login,name'}
            )

            print(f"   📊 Статус создания: {response.status_code}")
            print(f"   📄 Заголовки ответа: {dict(response.headers)}")
            print(f"   📝 Тело ответа: {response.text}")

            if response.status_code in [200, 201]:
                created = response.json()
                print(f"   ✅ СОЗДАН! ID: {created.get('id')}")
            elif response.status_code == 409:
                print(f"   ⚠️ УЖЕ СУЩЕСТВУЕТ")
            else:
                print(f"   ❌ ОШИБКА СОЗДАНИЯ")
        except Exception as e:
            print(f"   💥 Исключение при создании: {e}")

        print(f"   " + "-" * 40)

if __name__ == "__main__":
    test_user_detection()