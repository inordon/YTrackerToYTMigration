#!/usr/bin/env python3
"""
Принудительное создание пользователей (игнорируем проверки)
"""

import requests
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def force_create_missing_users():
    config = load_config()

    # Получаем пользователей, которых нужно создать (из предыдущей проверки)
    missing_users = [
        'adm', 'ahhehkob', 'akim.vladimirsky', 'alena.fisenko',
        'alexander.karavaev', 'alexxandr', 'alina.smaznova',
        'andrei.raikov', 'andrey.ivanov', 'andrey.korzhevin'
        # Можно добавить больше из списка
    ]

    headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }

    # Получаем данные пользователей из Yandex
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
    }

    # Получаем всех пользователей Yandex
    yandex_response = requests.get(
        'https://api.tracker.yandex.net/v2/users?page=1&perPage=200',
        headers=yandex_headers
    )
    yandex_users = yandex_response.json()

    # Создаем словарь логин -> данные пользователя
    user_data_map = {user.get('login'): user for user in yandex_users}

    success_count = 0

    print(f"🔨 ПРИНУДИТЕЛЬНОЕ СОЗДАНИЕ {len(missing_users)} ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 50)

    for i, login in enumerate(missing_users, 1):
        if login not in user_data_map:
            print(f"{i}. ❌ {login} - не найден в Yandex Tracker")
            continue

        user_data = user_data_map[login]

        print(f"{i}. 🔨 Создаем: {login}")

        yt_user = {
            'login': login,
            'name': user_data.get('display', login),
            'isActive': True
        }

        if user_data.get('email'):
            yt_user['email'] = user_data.get('email')

        try:
            response = requests.post(
                f"{config['youtrack']['url']}/hub/api/rest/users",
                headers=headers,
                json=yt_user,
                params={'fields': 'id,login,name'}
            )

            if response.status_code in [200, 201]:
                created = response.json()
                print(f"   ✅ СОЗДАН! ID: {created.get('id')}")
                success_count += 1
            elif response.status_code == 409:
                print(f"   ⚠️  УЖЕ СУЩЕСТВУЕТ")
            else:
                print(f"   ❌ Ошибка {response.status_code}: {response.text}")

        except Exception as e:
            print(f"   💥 Исключение: {e}")

        time.sleep(1)  # Пауза между созданиями

    print(f"\n🎉 Создано {success_count} пользователей")

if __name__ == "__main__":
    force_create_missing_users()