#!/usr/bin/env python3
"""
Добавление email аутентификации для уже созданных пользователей
"""

import requests
import json
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_mappings():
    """Загрузка маппингов пользователей"""
    with open('user_mapping.json', 'r') as f:
        data = json.load(f)
    return data.get('users', {})

def load_config():
    """Загрузка конфигурации"""
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def get_yandex_users():
    """Получение пользователей из Yandex Tracker"""
    config = load_config()

    headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
        'Content-Type': 'application/json'
    }

    response = requests.get('https://api.tracker.yandex.net/v2/users', headers=headers)
    return response.json() if response.status_code == 200 else []

def add_email_to_user(youtrack_url, token, user_id, email, login):
    """Добавление email аутентификации пользователю"""
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Генерируем временный пароль
    temp_password = f"ChangeMe123_{login[-4:]}"

    # Добавляем email credential
    credentials_url = f"{youtrack_url}/hub/api/rest/users/{user_id}/credentials"

    credential_data = {
        'email': email,
        'password': temp_password,
        'changeOnLogin': True
    }

    response = requests.post(credentials_url, headers=headers, json=credential_data)

    if response.status_code in [200, 201]:
        logger.info(f"✅ Email добавлен для {login}: {email}")
        logger.info(f"🔑 Временный пароль: {temp_password}")
        return True
    else:
        logger.error(f"❌ Ошибка добавления email для {login}: {response.status_code}")
        return False

def main():
    """Главная функция"""
    logger.info("📧 Добавление email аутентификации для пользователей")

    config = load_config()
    user_mappings = load_mappings()
    yandex_users = get_yandex_users()

    # Создаем словарь yandex_id -> email
    email_map = {user['id']: user for user in yandex_users if user.get('email')}

    success_count = 0

    for yandex_id, youtrack_id in user_mappings.items():
        if yandex_id in email_map:
            yandex_user = email_map[yandex_id]
            email = yandex_user.get('email')
            login = yandex_user.get('login', yandex_id)

            if email:
                if add_email_to_user(
                        config['youtrack']['url'],
                        config['youtrack']['token'],
                        youtrack_id,
                        email,
                        login
                ):
                    success_count += 1

    logger.info(f"🎉 Email добавлен для {success_count} пользователей")
    logger.info("📝 Сохраните временные пароли и отправьте пользователям")

if __name__ == "__main__":
    main()