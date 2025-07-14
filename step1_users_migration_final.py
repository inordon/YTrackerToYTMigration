#!/usr/bin/env python3
"""
Этап 1: Финальная версия миграции пользователей
"""

import requests
import json
import time
import logging
from typing import Dict, List, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('step1_users_final.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YandexTrackerClient:
    def __init__(self, token: str, org_id: str, is_cloud_org: bool = False):
        self.token = token
        self.org_id = org_id
        self.base_url = "https://api.tracker.yandex.net/v2"
        self.session = requests.Session()

        org_header = 'X-Cloud-Org-Id' if is_cloud_org else 'X-Org-ID'
        self.session.headers.update({
            'Authorization': f'OAuth {token}',
            org_header: org_id,
            'Content-Type': 'application/json'
        })

    def get_users(self) -> List[Dict]:
        all_users = []
        page = 1
        per_page = 50

        logger.info("Получение пользователей с пагинацией...")

        while True:
            try:
                params = {'page': page, 'perPage': per_page}
                response = self.session.get(f"{self.base_url}/users", params=params)
                response.raise_for_status()
                users = response.json()

                if not users:
                    break

                all_users.extend(users)
                logger.info(f"  Страница {page}: получено {len(users)} пользователей")

                if len(users) < per_page:
                    break

                page += 1
                time.sleep(0.3)

            except requests.RequestException as e:
                logger.error(f"Ошибка получения пользователей, страница {page}: {e}")
                break

        logger.info(f"Всего получено {len(all_users)} пользователей из Yandex Tracker")
        return all_users

class YouTrackClient:
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

    def user_exists_in_youtrack(self, login: str) -> Optional[str]:
        """Проверка существования пользователя в YouTrack"""
        try:
            # Проверяем через обычный API
            response = self.session.get(
                f"{self.base_url}/api/users",
                params={'query': login, 'fields': 'id,login', '$top': 100}
            )

            if response.status_code == 200:
                users = response.json()
                for user in users:
                    if isinstance(user, dict) and user.get('login') == login:
                        logger.debug(f"    Найден через API: {login} -> {user.get('id')}")
                        return user.get('id')

            return None

        except Exception as e:
            logger.debug(f"Ошибка проверки пользователя {login}: {e}")
            return None

    def create_user(self, user_data: Dict) -> Optional[str]:
        """Создание пользователя в YouTrack"""
        try:
            login = user_data.get('login', user_data.get('id'))
            email = user_data.get('email')
            display_name = user_data.get('display', login)

            # Сначала проверяем, существует ли пользователь
            existing_id = self.user_exists_in_youtrack(login)
            if existing_id:
                logger.info(f"⏭ Пользователь {login} уже существует (ID: {existing_id})")
                return existing_id

            # Создаем нового пользователя
            logger.info(f"🔨 Создаем пользователя: {login}")

            yt_user = {
                'login': login,
                'name': display_name,
                'isActive': True
            }

            if email:
                yt_user['email'] = email

            response = self.session.post(
                f"{self.base_url}/hub/api/rest/users",
                json=yt_user,
                params={'fields': 'id,login,name'}
            )

            if response.status_code in [200, 201]:
                created_user = response.json()
                logger.info(f"✅ Создан пользователь: {login} -> ID: {created_user.get('id')}")
                return created_user.get('id')
            elif response.status_code == 409:
                logger.warning(f"⚠️ Пользователь {login} уже существует (409)")
                # Пытаемся найти его ID
                existing_id = self.user_exists_in_youtrack(login)
                return existing_id
            else:
                logger.error(f"❌ Ошибка создания {login}: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Исключение при создании пользователя {login}: {e}")
            return None

def load_config() -> Dict:
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        exit(1)

def save_user_mapping(user_mapping: Dict):
    mapping_data = {
        'users': user_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'users_completed'
    }

    with open('user_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Маппинг пользователей сохранен: {len(user_mapping)} записей")

def load_existing_mapping() -> Dict:
    try:
        with open('user_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('users', {})
    except FileNotFoundError:
        return {}

def main():
    logger.info("=" * 60)
    logger.info("ЭТАП 1: ФИНАЛЬНАЯ МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ")
    logger.info("🎯 Цель: создать 94 пользователя в YouTrack")
    logger.info("=" * 60)

    config = load_config()
    is_cloud_org = config['yandex_tracker'].get('is_cloud_org', False)

    yandex_client = YandexTrackerClient(
        config['yandex_tracker']['token'],
        config['yandex_tracker']['org_id'],
        is_cloud_org
    )

    youtrack_client = YouTrackClient(
        config['youtrack']['url'],
        config['youtrack']['token']
    )

    if not youtrack_client.test_connection():
        logger.error("Не удалось подключиться к YouTrack")
        exit(1)

    user_mapping = load_existing_mapping()
    logger.info(f"Загружен существующий маппинг: {len(user_mapping)} пользователей")

    yandex_users = yandex_client.get_users()
    if not yandex_users:
        logger.error("Не удалось получить пользователей из Yandex Tracker")
        exit(1)

    logger.info(f"Начинаем обработку {len(yandex_users)} пользователей...")

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, user in enumerate(yandex_users, 1):
        yandex_id = user.get('id')
        login = user.get('login', yandex_id)

        if i % 20 == 0:
            logger.info(f"📊 Прогресс: {i}/{len(yandex_users)} пользователей обработано")

        # Пропускаем если уже в маппинге
        if yandex_id in user_mapping:
            skip_count += 1
            continue

        logger.debug(f"[{i}/{len(yandex_users)}] Обрабатываем: {login}")

        # Создаем/находим пользователя
        youtrack_id = youtrack_client.create_user(user)
        if youtrack_id:
            user_mapping[yandex_id] = youtrack_id
            success_count += 1
        else:
            error_count += 1

        # Увеличенная пауза для стабильности
        time.sleep(1.0)

        # Сохраняем промежуточный результат каждые 20 пользователей
        if i % 20 == 0:
            save_user_mapping(user_mapping)
            logger.info(f"💾 Промежуточное сохранение")

    save_user_mapping(user_mapping)

    logger.info("\n" + "=" * 60)
    logger.info("ФИНАЛЬНЫЕ РЕЗУЛЬТАТЫ ЭТАПА 1:")
    logger.info(f"✅ Успешно создано/найдено: {success_count}")
    logger.info(f"⏭️ Пропущено (уже в маппинге): {skip_count}")
    logger.info(f"❌ Ошибок: {error_count}")
    logger.info(f"📊 Всего в маппинге: {len(user_mapping)}")
    logger.info(f"🎯 Ожидалось новых: ~94")
    logger.info("=" * 60)

    if error_count == 0:
        logger.info("🎉 ЭТАП 1 ЗАВЕРШЕН УСПЕШНО!")
        logger.info("➡️  Теперь можно запустить step2_projects_migration.py")
    else:
        logger.warning(f"⚠️  Этап завершен с {error_count} ошибками")

if __name__ == "__main__":
    main()