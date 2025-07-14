#!/usr/bin/env python3
"""
Этап 2: Миграция проектов из Yandex Tracker в YouTrack
Создает проекты со статусами через state bundles и сохраняет маппинг
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
        logging.FileHandler('step2_projects.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class YandexTrackerClient:
    """Клиент для работы с Yandex Tracker API"""

    def __init__(self, token: str, org_id: str, is_cloud_org: bool = False):
        self.token = token
        self.org_id = org_id
        self.base_url = "https://api.tracker.yandex.net/v2"
        self.session = requests.Session()
        # Выбираем правильный заголовок для организации
        org_header = 'X-Cloud-Org-Id' if is_cloud_org else 'X-Org-ID'
        self.session.headers.update({
            'Authorization': f'OAuth {token}',
            org_header: org_id,
            'Content-Type': 'application/json'
        })

    def get_queues(self) -> List[Dict]:
        """Получение всех очередей"""
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
        """Получение статусов очереди"""
        try:
            response = self.session.get(f"{self.base_url}/queues/{queue_key}/statuses")
            response.raise_for_status()
            statuses = response.json()
            logger.debug(f"Получено {len(statuses)} статусов для очереди {queue_key}")
            return statuses
        except requests.RequestException as e:
            logger.warning(f"Ошибка получения статусов для очереди {queue_key}: {e}")
            # Возвращаем базовые статусы в случае ошибки
            return [
                {'name': 'Open', 'key': 'open', 'color': '#6B73FF'},
                {'name': 'In Progress', 'key': 'inprogress', 'color': '#FFA500'},
                {'name': 'Resolved', 'key': 'resolved', 'color': '#00AA00'},
                {'name': 'Closed', 'key': 'closed', 'color': '#808080'}
            ]

class YouTrackClient:
    """Клиент для работы с YouTrack API"""

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
                logger.debug(f"Текущий пользователь YouTrack ID: {youtrack_id}")
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

            logger.debug(f"Создаем проект: {yt_project['shortName']} с лидером ID: {leader_id}")

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
        """Получение ID проекта по короткому имени"""
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

    def create_state_bundle(self, bundle_name: str, statuses: List[Dict]) -> Optional[str]:
        """Создание state bundle в YouTrack"""
        try:
            # Подготавливаем состояния для bundle
            bundle_states = []
            for status in statuses:
                state_data = {
                    'name': status.get('name', status.get('key')),
                    'description': status.get('description', ''),
                    'color': {'id': status.get('color', '#6B73FF').replace('#', '')}
                }
                bundle_states.append(state_data)

            bundle_data = {
                'name': bundle_name,
                'states': bundle_states
            }

            response = self.session.post(
                f"{self.base_url}/api/admin/customFieldSettings/bundles/state",
                json=bundle_data,
                params={'fields': 'id,name,states(id,name)'}
            )

            if response.status_code in [200, 201]:
                created_bundle = response.json()
                logger.debug(f"  ✓ Создан state bundle: {bundle_name}")
                return created_bundle.get('id')
            else:
                logger.warning(f"  ⚠ Не удалось создать bundle {bundle_name}: {response.status_code}")
                return None

        except Exception as e:
            logger.error(f"  ✗ Ошибка создания state bundle: {e}")
            return None

    def assign_state_bundle_to_project(self, project_id: str, bundle_id: str) -> bool:
        """Назначение state bundle проекту"""
        try:
            # Находим State field
            response = self.session.get(
                f"{self.base_url}/api/admin/customFieldSettings/customFields",
                params={'fields': 'id,name,fieldType', '$top': 100}
            )

            state_field_id = None
            if response.status_code == 200:
                fields = response.json()
                for field in fields:
                    if field.get('name') == 'State' and 'state' in field.get('fieldType', '').lower():
                        state_field_id = field.get('id')
                        break

            if not state_field_id:
                logger.warning(f"  ⚠ Не найдено поле State")
                return False

            # Назначаем bundle проекту
            custom_field_data = {
                'field': {'id': state_field_id},
                'bundle': {'id': bundle_id}
            }

            response = self.session.post(
                f"{self.base_url}/api/admin/projects/{project_id}/customFields",
                json=custom_field_data,
                params={'fields': 'id,field(name),bundle(name)'}
            )

            if response.status_code in [200, 201]:
                logger.debug(f"  ✓ State bundle назначен проекту")
                return True
            elif response.status_code == 409:
                logger.debug(f"  ⚠ State bundle уже назначен проекту")
                return True
            else:
                logger.warning(f"  ⚠ Не удалось назначить bundle: {response.status_code}")
                return False

        except Exception as e:
            logger.error(f"  ✗ Ошибка назначения state bundle: {e}")
            return False

    def create_project_statuses(self, project_id: str, queue_key: str, statuses: List[Dict]) -> bool:
        """Создание статусов для проекта через state bundle"""
        if not statuses:
            logger.warning(f"  ⚠ Нет статусов для создания")
            return False

        # Создаем уникальное имя для bundle
        bundle_name = f"{queue_key} States"

        # Создаем state bundle
        bundle_id = self.create_state_bundle(bundle_name, statuses)
        if not bundle_id:
            return False

        # Назначаем bundle проекту
        return self.assign_state_bundle_to_project(project_id, bundle_id)

def load_config() -> Dict:
    """Загрузка конфигурации"""
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        exit(1)

def load_user_mapping() -> Dict:
    """Загрузка маппинга пользователей"""
    try:
        with open('user_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('users', {})
    except FileNotFoundError:
        logger.error("Файл user_mapping.json не найден")
        logger.error("Сначала запустите step1_users_migration.py")
        exit(1)

def save_project_mapping(project_mapping: Dict):
    """Сохранение маппинга проектов"""
    mapping_data = {
        'projects': project_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'projects_completed'
    }

    with open('project_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

    logger.debug(f"Маппинг проектов сохранен в project_mapping.json")

def load_existing_project_mapping() -> Dict:
    """Загрузка существующего маппинга проектов"""
    try:
        with open('project_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('projects', {})
    except FileNotFoundError:
        return {}

def main():
    """Главная функция этапа 2"""
    logger.info("=" * 50)
    logger.info("ЭТАП 2: МИГРАЦИЯ ПРОЕКТОВ")
    logger.info("=" * 50)

    # Загружаем конфигурацию
    config = load_config()

    # Загружаем маппинг пользователей
    user_mapping = load_user_mapping()
    if not user_mapping:
        logger.error("Маппинг пользователей пуст")
        logger.error("Сначала успешно завершите step1_users_migration.py")
        exit(1)

    logger.info(f"Загружен маппинг пользователей: {len(user_mapping)} пользователей")

    # Создаем клиентов
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

    # Загружаем существующий маппинг проектов
    project_mapping = load_existing_project_mapping()
    logger.info(f"Загружен существующий маппинг проектов: {len(project_mapping)} проектов")

    # Получаем очереди из Yandex Tracker
    yandex_queues = yandex_client.get_queues()
    if not yandex_queues:
        logger.error("Не удалось получить очереди из Yandex Tracker")
        exit(1)

    logger.info(f"Начинаем миграцию {len(yandex_queues)} проектов...")

    # Мигрируем проекты
    success_count = 0
    skip_count = 0
    error_count = 0
    status_success_count = 0
    status_error_count = 0

    for i, queue in enumerate(yandex_queues, 1):
        queue_key = queue.get('key')
        queue_name = queue.get('name', queue_key)

        logger.info(f"[{i}/{len(yandex_queues)}] Обрабатываем проект: {queue_key} - {queue_name}")

        # Пропускаем если уже мигрирован
        if queue_key in project_mapping:
            logger.info(f"⏭ Проект {queue_key} уже мигрирован, пропускаем")
            skip_count += 1
            continue

        # Создаем проект
        project_id = youtrack_client.create_project(queue)
        if project_id:
            project_mapping[queue_key] = project_id
            success_count += 1

            # Создаем статусы для проекта через state bundle
            logger.info(f"  🔧 Настраиваем статусы для проекта {queue_key}")
            statuses = yandex_client.get_queue_statuses(queue_key)

            if youtrack_client.create_project_statuses(project_id, queue_key, statuses):
                status_success_count += 1
                logger.info(f"  ✓ Статусы настроены для проекта {queue_key}")
            else:
                status_error_count += 1
                logger.warning(f"  ⚠ Не удалось настроить статусы для проекта {queue_key}")
        else:
            error_count += 1

        # Пауза между запросами
        time.sleep(1.0)

        # Сохраняем промежуточный результат каждые 5 проектов
        if i % 5 == 0:
            save_project_mapping(project_mapping)
            logger.info(f"Промежуточное сохранение: {i} проектов обработано")

    # Сохраняем финальный результат
    save_project_mapping(project_mapping)

    # Выводим статистику
    logger.info("=" * 50)
    logger.info("РЕЗУЛЬТАТЫ ЭТАПА 2:")
    logger.info(f"✓ Успешно создано проектов: {success_count}")
    logger.info(f"⏭ Пропущено (уже существуют): {skip_count}")
    logger.info(f"✗ Ошибок создания проектов: {error_count}")
    logger.info(f"✓ Статусы настроены: {status_success_count}")
    logger.info(f"⚠ Ошибок настройки статусов: {status_error_count}")
    logger.info(f"📊 Всего в маппинге: {len(project_mapping)}")
    logger.info("=" * 50)

    if error_count == 0:
        logger.info("🎉 ЭТАП 2 ЗАВЕРШЕН УСПЕШНО!")
        logger.info("Теперь можно запустить step3_issues_migration.py")
    else:
        logger.warning(f"⚠ Этап завершен с {error_count} ошибками")
        logger.info("Проверьте логи и повторите запуск для исправления ошибок")

if __name__ == "__main__":
    main()