#!/usr/bin/env python3
"""
Проверка, есть ли пользователи, которых нет в YouTrack
"""

import requests
import json

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def main():
    config = load_config()

    # Получаем всех пользователей из Yandex Tracker
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
        'Content-Type': 'application/json'
    }

    youtrack_headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    print("🔍 Получение всех пользователей из обеих систем...")

    # Получаем пользователей Yandex Tracker
    yandex_users = []
    page = 1
    while True:
        response = requests.get(
            f'https://api.tracker.yandex.net/v2/users?page={page}&perPage=50',
            headers=yandex_headers
        )
        users = response.json()
        if not users:
            break
        yandex_users.extend(users)
        page += 1
        if page > 10:  # Ограничение для безопасности
            break

    # Получаем пользователей YouTrack
    response = requests.get(
        f"{config['youtrack']['url']}/api/users",
        headers=youtrack_headers,
        params={'fields': 'id,login', '$top': 1000}
    )
    youtrack_users = response.json() if response.status_code == 200 else []

    # Создаем множества логинов
    yandex_logins = {user.get('login') for user in yandex_users if user.get('login')}
    youtrack_logins = {user.get('login') for user in youtrack_users if user.get('login')}

    # Находим различия
    only_in_yandex = yandex_logins - youtrack_logins
    only_in_youtrack = youtrack_logins - yandex_logins
    common = yandex_logins & youtrack_logins

    print(f"\n📊 СТАТИСТИКА ПОЛЬЗОВАТЕЛЕЙ:")
    print(f"👥 Всего в Yandex Tracker: {len(yandex_logins)}")
    print(f"👥 Всего в YouTrack: {len(youtrack_logins)}")
    print(f"🤝 Общие пользователи: {len(common)}")
    print(f"🆕 Только в Yandex (нужно создать): {len(only_in_yandex)}")
    print(f"🏠 Только в YouTrack: {len(only_in_youtrack)}")

    if only_in_yandex:
        print(f"\n🆕 ПОЛЬЗОВАТЕЛИ ДЛЯ СОЗДАНИЯ:")
        for i, login in enumerate(sorted(only_in_yandex), 1):
            print(f"  {i}. {login}")
            if i >= 10:
                print(f"  ... и еще {len(only_in_yandex) - 10}")
                break
    else:
        print(f"\n✅ ВСЕ ПОЛЬЗОВАТЕЛИ ИЗ YANDEX TRACKER УЖЕ ЕСТЬ В YOUTRACK!")

if __name__ == "__main__":
    main()