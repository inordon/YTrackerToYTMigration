#!/usr/bin/env python3
"""
Этап 2: Миграция проектов - Исправленная версия
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
        logging.FileHandler('step2_projects.log'),
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

    def get_queues(self) -> List[Dict]:
        try:
            response = self.session.get(f"{self.base_url}/queues")
            response.raise_for_status()
            queues = response.json()
            logger.info(f"Получено {len(queues)} очередей из Yandex Tracker")
            return queues
        except requests.RequestException as e:
            logger.error(f"Ошибка получения очередей: {e}")
            return []

    def get_queue_statuses(self, queue_key: str) -> List[Dict]:
        try:
            response = self.session.get(f"{self.base_url}/queues/{queue_key}/statuses")
            response.raise_for_status()
            statuses = response.json()
            logger.debug(f"Получено {len(statuses)} статусов для очереди {queue_key}")
            return statuses
        except requests.RequestException as e:
            logger.error(f"Ошибка получения статусов для очереди {queue_key}: {e}")
            return []

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

    def get_current_user_youtrack_id(self) -> Optional[str]:
        """Получение YouTrack ID текущего пользователя"""
        try:
            response = self.session.get(f"{self.base_url}/api/users/me")
            if response.status_code == 200:
                user = response.json()
                youtrack_id = user.get('id')
                logger.info(f"Текущий пользователь YouTrack ID: {youtrack_id}")
                return youtrack_id
            return None
        except Exception as e:
            logger.error(f"Ошибка получения текущего пользователя: {e}")
            return None

    def create_project(self, project_data: Dict, leader_id: str = None) -> Optional[str]:
        """Создание проекта в YouTrack"""
        try:
            # Используем текущего пользователя как лидера проекта
            if not leader_id:
                leader_id = self.get_current_user_youtrack_id()

            if not leader_id:
                logger.error("Не удалось определить ID лидера проекта")
                return None

            yt_project = {
                'name': project_data.get('name'),
                'shortName': project_data.get('key'),
                'description': project_data.get('description', ''),
                'leader': {'id': leader_id}
            }

            logger.info(f"Создаем проект: {yt_project['shortName']} с лидером ID: {leader_id}")

            response = self.session.post(
                f"{self.base_url}/api/admin/projects",
                json=yt_project,
                params={'fields': 'id,shortName,name'}
            )

            if response.status_code in [200, 201]:
                created_project = response.json()
                logger.info(f"✓ Создан проект: {created_project.get('shortName')} - {created_project.get('name')}")
                return created_project.get('id')
            elif response.status_code == 409:
                logger.warning(f"⚠ Проект {yt_project['shortName']} уже существует")
                return self.get_project_by_shortname(yt_project['shortName'])
            else:
                logger.error(f"✗ Ошибка создания проекта {yt_project['shortName']}: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"✗ Ошибка создания проекта: {e}")
            return None

    def get_project_by_shortname(self, shortname: str) -> Optional[str]:
        try:
            response = self.session.get(
                f"{self.base_url}/api/admin/projects",
                params={'query': shortname, 'fields': 'id,shortName'}
            )
            response.raise_for_status()
            projects = response.json()

            for project in projects:
                if project.get('shortName') == shortname:
                    return project.get('id')
            return None
        except requests.RequestException as e:
            logger.error(f"Ошибка поиска проекта {shortname}: {e}")
            return None

    def create_project_statuses(self, project_id: str, statuses: List[Dict]) -> bool:
        try:
            response = self.session.get(
                f"{self.base_url}/api/admin/projects/{project_id}/statuses",
                params={'fields': 'id,name'}
            )

            if response.status_code != 200:
                logger.error(f"Не удалось получить статусы проекта {project_id}")
                return False

            existing_statuses = {status['name']: status['id'] for status in response.json()}

            created_count = 0
            for status in statuses:
                status_name = status.get('name', status.get('key'))
                if status_name not in existing_statuses:
                    status_data = {
                        'name': status_name,
                        'description': status.get('description', ''),
                        'color': status.get('color', '#6B73FF')
                    }

                    create_response = self.session.post(
                        f"{self.base_url}/api/admin/projects/{project_id}/statuses",
                        json=status_data,
                        params={'fields': 'id,name'}
                    )

                    if create_response.status_code in [200, 201]:
                        created_count += 1
                        logger.debug(f"  ✓ Создан статус: {status_name}")
                    else:
                        logger.warning(f"  ⚠ Не удалось создать статус {status_name}: {create_response.status_code}")

            logger.info(f"  📋 Создано {created_count} новых статусов для проекта")
            return True

        except requests.RequestException as e:
            logger.error(f"Ошибка создания статусов: {e}")
            return False

def load_config() -> Dict:
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        exit(1)

def load_user_mapping() -> Dict:
    try:
        with open('user_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('users', {})
    except FileNotFoundError:
        logger.error("Файл user_mapping.json не найден")
        logger.error("Сначала запустите step1_users_migration.py")
        exit(1)

def save_project_mapping(project_mapping: Dict):
    mapping_data = {
        'projects': project_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'projects_completed'
    }

    with open('project_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Маппинг проектов сохранен в project_mapping.json")

def load_existing_project_mapping() -> Dict:
    try:
        with open('project_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('projects', {})
    except FileNotFoundError:
        return {}

def main():
    logger.info("=" * 50)
    logger.info("ЭТАП 2: МИГРАЦИЯ ПРОЕКТОВ - ИСПРАВЛЕННАЯ ВЕРСИЯ")
    logger.info("=" * 50)

    config = load_config()
    user_mapping = load_user_mapping()

    if not user_mapping:
        logger.error("Маппинг пользователей пуст")
        logger.error("Сначала успешно завершите step1_users_migration.py")
        exit(1)

    logger.info(f"Загружен маппинг пользователей: {len(user_mapping)} пользователей")

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

    project_mapping = load_existing_project_mapping()
    logger.info(f"Загружен существующий маппинг проектов: {len(project_mapping)} проектов")

    yandex_queues = yandex_client.get_queues()
    if not yandex_queues:
        logger.error("Не удалось получить очереди из Yandex Tracker")
        exit(1)

    logger.info(f"Начинаем миграцию {len(yandex_queues)} проектов...")

    success_count = 0
    skip_count = 0
    error_count = 0

    for i, queue in enumerate(yandex_queues, 1):
        queue_key = queue.get('key')
        queue_name = queue.get('name', queue_key)

        logger.info(f"[{i}/{len(yandex_queues)}] Обрабатываем проект: {queue_key} - {queue_name}")

        if queue_key in project_mapping:
            logger.info(f"⏭ Проект {queue_key} уже мигрирован, пропускаем")
            skip_count += 1
            continue

        # Создаем проект (лидер будет назначен автоматически)
        project_id = youtrack_client.create_project(queue)
        if project_id:
            project_mapping[queue_key] = project_id
            success_count += 1

            # Создаем статусы для проекта
            logger.info(f"  🔧 Настраиваем статусы для проекта {queue_key}")
            statuses = yandex_client.get_queue_statuses(queue_key)
            if statuses:
                youtrack_client.create_project_statuses(project_id, statuses)
            else:
                logger.warning(f"  ⚠ Не удалось получить статусы для проекта {queue_key}")
        else:
            error_count += 1

        time.sleep(1.0)

        if i % 3 == 0:
            save_project_mapping(project_mapping)
            logger.info(f"Промежуточное сохранение: {i} проектов обработано")

    save_project_mapping(project_mapping)

    logger.info("=" * 50)
    logger.info("РЕЗУЛЬТАТЫ ЭТАПА 2:")
    logger.info(f"✓ Успешно создано: {success_count}")
    logger.info(f"⏭ Пропущено (уже существуют): {skip_count}")
    logger.info(f"✗ Ошибок: {error_count}")
    logger.info(f"📊 Всего в маппинге: {len(project_mapping)}")
    logger.info("=" * 50)

    if error_count == 0:
        logger.info("🎉 ЭТАП 2 ЗАВЕРШЕН УСПЕШНО!")
        logger.info("Теперь можно запустить step3_issues_migration.py")
    else:
        logger.warning(f"⚠ Этап завершен с {error_count} ошибками")

if __name__ == "__main__":
    main()