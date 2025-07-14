#!/usr/bin/env python3
"""
Этап 1: Миграция пользователей из Yandex Tracker в YouTrack
Создает всех пользователей в YouTrack и сохраняет маппинг
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('step1_users.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YandexTrackerClient:
    """Клиент для работы с Yandex Tracker API"""

    def __init__(self, token: str, org_id: str):
        self.token = token
        self.org_id = org_id
        self.base_url = "https://api.tracker.yandex.net/v2"
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'OAuth {token}',
            'X-Org-ID': org_id,
            'Content-Type': 'application/json'
        })

    def get_users(self) -> List[Dict]:
        """Получение всех пользователей"""
        try:
            response = self.session.get(f"{self.base_url}/users")
            response.raise_for_status()
            users = response.json()
            logger.info(f"Получено {len(users)} пользователей из Yandex Tracker")
            return users
        except requests.RequestException as e:
            logger.error(f"Ошибка получения пользователей: {e}")
            return []

class YouTrackClient:
    """Клиент для работы с YouTrack Hub API"""

    def __init__(self, base_url: str, token: str):
        self.base_url = base_url.rstrip('/')
        self.token = token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def test_connection(self) -> bool:
        """Тестирование подключения к YouTrack"""
        try:
            response = self.session.get(f"{self.base_url}/api/users/me")
            if response.status_code == 200:
                user = response.json()
                logger.info(f"✓ YouTrack: подключение успешно, пользователь {user.get('login')}")
                return True
            else:
                logger.error(f"✗ YouTrack: ошибка авторизации - {response.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ YouTrack: ошибка подключения - {e}")
            return False

    def create_user(self, user_data: Dict) -> Optional[str]:
        """Создание пользователя в YouTrack через Hub API"""
        try:
            hub_url = f"{self.base_url}/hub/api/rest/users"

            # Подготавливаем данные пользователя
            yt_user = {
                'login': user_data.get('login', user_data.get('id')),
                'name': user_data.get('display', user_data.get('login')),
                'email': user_data.get('email'),
                'isActive': True
            }

            # Удаляем None значения
            yt_user = {k: v for k, v in yt_user.items() if v is not None}

            response = self.session.post(
                hub_url,
                json=yt_user,
                params={'fields': 'id,login,name'}
            )

            if response.status_code == 201:
                created_user = response.json()
                logger.info(f"✓ Создан пользователь: {created_user.get('login')}")
                return created_user.get('id')
            elif response.status_code == 409:
                logger.warning(f"⚠ Пользователь {yt_user['login']} уже существует")
                return self.get_user_by_login(yt_user['login'])
            else:
                logger.error(f"✗ Ошибка создания пользователя {yt_user['login']}: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"✗ Ошибка создания пользователя: {e}")
            return None

    def get_user_by_login(self, login: str) -> Optional[str]:
        """Получение ID пользователя по логину"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/users",
                params={
                    'query': login,
                    'fields': 'id,login'
                }
            )
            response.raise_for_status()
            users = response.json()

            for user in users:
                if user.get('login') == login:
                    return user.get('id')

            return None

        except requests.RequestException as e:
            logger.error(f"Ошибка поиска пользователя {login}: {e}")
            return None

def load_config() -> Dict:
    """Загрузка конфигурации"""
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        logger.info("Создайте конфигурацию согласно документации")
        exit(1)

def save_user_mapping(user_mapping: Dict):
    """Сохранение маппинга пользователей"""
    mapping_data = {
        'users': user_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'users_completed'
    }

    with open('user_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Маппинг пользователей сохранен в user_mapping.json")

def load_existing_mapping() -> Dict:
    """Загрузка существующего маппинга"""
    try:
        with open('user_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('users', {})
    except FileNotFoundError:
        return {}

def main():
    """Главная функция этапа 1"""
    logger.info("=" * 50)
    logger.info("ЭТАП 1: МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ")
    logger.info("=" * 50)

    # Загружаем конфигурацию
    config = load_config()

    # Создаем клиентов
    yandex_client = YandexTrackerClient(
        config['yandex_tracker']['token'],
        config['yandex_tracker']['org_id']
    )

    youtrack_client = YouTrackClient(
        config['youtrack']['url'],
        config['youtrack']['token']
    )

    # Тестируем подключение к YouTrack
    if not youtrack_client.test_connection():
        logger.error("Не удалось подключиться к YouTrack")
        exit(1)

    # Загружаем существующий маппинг (если есть)
    user_mapping = load_existing_mapping()
    logger.info(f"Загружен существующий маппинг: {len(user_mapping)} пользователей")

    # Получаем пользователей из Yandex Tracker
    yandex_users = yandex_client.get_users()
    if not yandex_users:
        logger.error("Не удалось получить пользователей из Yandex Tracker")
        exit(1)

    logger.info(f"Начинаем миграцию {len(yandex_users)} пользователей...")

    # Мигрируем пользователей
    success_count = 0
    skip_count = 0
    error_count = 0

    for i, user in enumerate(yandex_users, 1):
        yandex_id = user.get('id')
        login = user.get('login', yandex_id)

        logger.info(f"[{i}/{len(yandex_users)}] Обрабатываем пользователя: {login}")

        # Пропускаем если уже мигрирован
        if yandex_id in user_mapping:
            logger.info(f"⏭ Пользователь {login} уже мигрирован, пропускаем")
            skip_count += 1
            continue

        # Создаем пользователя
        youtrack_id = youtrack_client.create_user(user)
        if youtrack_id:
            user_mapping[yandex_id] = youtrack_id
            success_count += 1
        else:
            error_count += 1

        # Пауза между запросами
        time.sleep(0.5)

        # Сохраняем промежуточный результат каждые 10 пользователей
        if i % 10 == 0:
            save_user_mapping(user_mapping)
            logger.info(f"Промежуточное сохранение: {i} пользователей обработано")

    # Сохраняем финальный результат
    save_user_mapping(user_mapping)

    # Выводим статистику
    logger.info("=" * 50)
    logger.info("РЕЗУЛЬТАТЫ ЭТАПА 1:")
    logger.info(f"✓ Успешно создано: {success_count}")
    logger.info(f"⏭ Пропущено (уже существуют): {skip_count}")
    logger.info(f"✗ Ошибок: {error_count}")
    logger.info(f"📊 Всего в маппинге: {len(user_mapping)}")
    logger.info("=" * 50)

    if error_count == 0:
        logger.info("🎉 ЭТАП 1 ЗАВЕРШЕН УСПЕШНО!")
        logger.info("Теперь можно запустить step2_projects_migration.py")
    else:
        logger.warning(f"⚠ Этап завершен с {error_count} ошибками")
        logger.info("Проверьте логи и повторите запуск для исправления ошибок")

if __name__ == "__main__":
    main()