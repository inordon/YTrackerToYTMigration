#!/usr/bin/env python3
"""
Этап 1: Миграция пользователей - Улучшенная версия
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
        logging.FileHandler('step1_users_v2.log'),
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

        # ВРЕМЕННОЕ ОГРАНИЧЕНИЕ ДЛЯ ТЕСТА
        if len(all_users) > 5:
            logger.info("🧪 ТЕСТ: Ограничиваем до 5 пользователей")
            all_users = all_users[:5]

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

    def create_user_forced(self, user_data: Dict) -> Optional[str]:
        """Принудительное создание пользователя без проверки существования"""
        try:
            login = user_data.get('login', user_data.get('id'))
            email = user_data.get('email')
            display_name = user_data.get('display', login)

            logger.info(f"🔨 ПРИНУДИТЕЛЬНОЕ создание пользователя: {login}")

            yt_user = {
                'login': login,
                'name': display_name,
                'isActive': True
            }

            if email:
                yt_user['email'] = email

            hub_url = f"{self.base_url}/hub/api/rest/users"

            response = self.session.post(
                hub_url,
                json=yt_user,
                params={'fields': 'id,login,name,email'}
            )

            logger.info(f"    Ответ сервера: {response.status_code}")
            logger.info(f"    Тело ответа: {response.text}")

            if response.status_code in [200, 201]:
                created_user = response.json()
                logger.info(f"✅ УСПЕШНО создан: {login} -> ID: {created_user.get('id')}")
                return created_user.get('id')
            elif response.status_code == 409:
                logger.warning(f"⚠️ Пользователь {login} УЖЕ СУЩЕСТВУЕТ")
                # Пытаемся найти существующего пользователя
                existing_id = self.find_existing_user_brute_force(login)
                if existing_id:
                    logger.info(f"✅ Найден существующий: {login} -> ID: {existing_id}")
                    return existing_id
                else:
                    logger.error(f"❌ Существует, но ID не найден: {login}")
                    return None
            else:
                logger.error(f"❌ Ошибка создания {login}: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"❌ Исключение при создании пользователя: {e}")
            return None

    def find_existing_user_brute_force(self, login: str) -> Optional[str]:
        """Поиск существующего пользователя всеми возможными способами"""
        logger.info(f"    🔍 Ищем существующего пользователя: {login}")

        # Способ 1: Обычный API с разными параметрами
        search_params = [
            {'query': login, 'fields': 'id,login', '$top': 1000},
            {'$filter': f'login eq {login}', 'fields': 'id,login'},
            {'fields': 'id,login', '$top': 1000}  # Получить всех и найти среди них
        ]

        for i, params in enumerate(search_params, 1):
            try:
                response = self.session.get(f"{self.base_url}/api/users", params=params)
                if response.status_code == 200:
                    users = response.json()
                    logger.info(f"      Способ {i}: найдено {len(users)} пользователей")
                    for user in users:
                        if user.get('login') == login:
                            logger.info(f"      ✅ Найден способом {i}: {login} -> {user.get('id')}")
                            return user.get('id')
            except Exception as e:
                logger.debug(f"      Способ {i} не сработал: {e}")

        # Способ 2: Hub API
        try:
            response = self.session.get(
                f"{self.base_url}/hub/api/rest/users",
                params={'query': login, 'fields': 'id,login', '$top': 1000}
            )
            if response.status_code == 200:
                users = response.json()
                logger.info(f"      Hub API: найдено {len(users)} пользователей")
                for user in users:
                    if user.get('login') == login:
                        logger.info(f"      ✅ Найден через Hub: {login} -> {user.get('id')}")
                        return user.get('id')
        except Exception as e:
            logger.debug(f"      Hub API не сработал: {e}")

        logger.warning(f"      ❌ Пользователь {login} не найден ни одним способом")
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

    logger.info(f"Маппинг пользователей сохранен в user_mapping.json")

def load_existing_mapping() -> Dict:
    try:
        with open('user_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('users', {})
    except FileNotFoundError:
        return {}

def main():
    logger.info("=" * 50)
    logger.info("ЭТАП 1: МИГРАЦИЯ ПОЛЬЗОВАТЕЛЕЙ - УЛУЧШЕННАЯ ВЕРСИЯ")
    logger.info("=" * 50)

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

    logger.info(f"Начинаем ПРИНУДИТЕЛЬНУЮ миграцию {len(yandex_users)} пользователей...")

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, user in enumerate(yandex_users, 1):
        yandex_id = user.get('id')
        login = user.get('login', yandex_id)

        logger.info(f"\n[{i}/{len(yandex_users)}] ==========================================")
        logger.info(f"Обрабатываем пользователя: {login} (ID: {yandex_id})")

        if yandex_id in user_mapping:
            logger.info(f"⏭ Пользователь {login} уже в маппинге, пропускаем")
            skip_count += 1
            continue

        # ПРИНУДИТЕЛЬНО пытаемся создать пользователя
        youtrack_id = youtrack_client.create_user_forced(user)
        if youtrack_id:
            user_mapping[yandex_id] = youtrack_id
            success_count += 1
        else:
            error_count += 1

        time.sleep(1)  # Увеличиваем паузу для диагностики

        if i % 2 == 0:
            save_user_mapping(user_mapping)

    save_user_mapping(user_mapping)

    logger.info("\n" + "=" * 50)
    logger.info("РЕЗУЛЬТАТЫ ЭТАПА 1 - УЛУЧШЕННАЯ ВЕРСИЯ:")
    logger.info(f"✓ Успешно создано: {success_count}")
    logger.info(f"⏭ Пропущено (уже в маппинге): {skip_count}")
    logger.info(f"✗ Ошибок: {error_count}")
    logger.info(f"📊 Всего в маппинге: {len(user_mapping)}")
    logger.info("=" * 50)

if __name__ == "__main__":
    main()