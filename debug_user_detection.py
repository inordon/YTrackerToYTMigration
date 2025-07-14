#!/usr/bin/env python3
"""
Диагностика проблемы с определением существующих пользователей
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

    # Настройки YouTrack
    base_url = config['youtrack']['url'].rstrip('/')
    token = config['youtrack']['token']

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    # Получаем первых нескольких пользователей из Yandex Tracker
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
        'Content-Type': 'application/json'
    }

    response = requests.get(
        'https://api.tracker.yandex.net/v2/users?page=1&perPage=5',
        headers=yandex_headers
    )

    yandex_users = response.json()

    print("🔍 ДИАГНОСТИКА ОПРЕДЕЛЕНИЯ ПОЛЬЗОВАТЕЛЕЙ")
    print("=" * 50)

    for i, user in enumerate(yandex_users, 1):
        login = user.get('login')
        print(f"\n{i}. Тестируем пользователя: {login}")

        # Тест 1: Поиск через обычный API
        response = requests.get(
            f"{base_url}/api/users",
            headers=headers,
            params={'query': login, 'fields': 'id,login', '$top': 100}
        )

        print(f"   API users поиск: {response.status_code}")
        if response.status_code == 200:
            api_users = response.json()
            found_api = any(u.get('login') == login for u in api_users)
            print(f"   Найден через API: {found_api}")
            if found_api:
                for u in api_users:
                    if u.get('login') == login:
                        print(f"   ID через API: {u.get('id')}")

        # Тест 2: Поиск через Hub API
        response = requests.get(
            f"{base_url}/hub/api/rest/users",
            headers=headers,
            params={'query': login, 'fields': 'id,login', '$top': 100}
        )

        print(f"   Hub API поиск: {response.status_code}")
        if response.status_code == 200:
            hub_users = response.json()
            found_hub = any(u.get('login') == login for u in hub_users)
            print(f"   Найден через Hub: {found_hub}")
            if found_hub:
                for u in hub_users:
                    if u.get('login') == login:
                        print(f"   ID через Hub: {u.get('id')}")

        # Тест 3: Попытка создания
        yt_user = {
            'login': login,
            'name': user.get('display', login),
            'isActive': True
        }

        if user.get('email'):
            yt_user['email'] = user.get('email')

        response = requests.post(
            f"{base_url}/hub/api/rest/users",
            headers=headers,
            json=yt_user,
            params={'fields': 'id,login,name'}
        )

        print(f"   Попытка создания: {response.status_code}")
        if response.status_code in [200, 201]:
            created = response.json()
            print(f"   ✅ Создан с ID: {created.get('id')}")
        elif response.status_code == 409:
            print(f"   ⚠️ Уже существует (409)")
            print(f"   Ответ: {response.text}")
        else:
            print(f"   ❌ Ошибка: {response.text}")

if __name__ == "__main__":
    test_user_detection()