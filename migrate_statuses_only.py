#!/usr/bin/env python3
"""
Миграция статусов для уже созданных проектов
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
        logging.FileHandler('migrate_statuses.log'),
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

    def get_queue_statuses(self, queue_key: str) -> List[Dict]:
        """Получение статусов очереди"""
        try:
            response = self.session.get(f"{self.base_url}/queues/{queue_key}/statuses")
            response.raise_for_status()
            statuses = response.json()
            logger.info(f"  📋 Получено {len(statuses)} статусов для очереди {queue_key}")
            return statuses
        except requests.RequestException as e:
            logger.warning(f"  ⚠ Ошибка получения статусов для очереди {queue_key}: {e}")
            # Возвращаем базовые статусы
            return [
                {'name': 'Open', 'key': 'open', 'color': '#6B73FF'},
                {'name': 'In Progress', 'key': 'inprogress', 'color': '#FFA500'},
                {'name': 'Resolved', 'key': 'resolved', 'color': '#00AA00'},
                {'name': 'Closed', 'key': 'closed', 'color': '#808080'}
            ]

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

    def project_has_custom_state_bundle(self, project_id: str, queue_key: str) -> bool:
        """Проверка, есть ли у проекта кастомный state bundle для данной очереди"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/admin/projects/{project_id}/customFields",
                params={'fields': 'field(name),bundle(name)'}
            )

            if response.status_code == 200:
                custom_fields = response.json()
                for field in custom_fields:
                    if field.get('field', {}).get('name') == 'State':
                        bundle_name = field.get('bundle', {}).get('name', '')
                        # Проверяем, что это НАШ bundle для данной очереди
                        expected_bundle_name = f"{queue_key} States"
                        if bundle_name == expected_bundle_name:
                            logger.debug(f"    ✓ Проект уже имеет наш state bundle: {bundle_name}")
                            return True
                        elif bundle_name and not bundle_name.startswith('Default'):
                            logger.info(f"    🔄 Проект имеет другой bundle: {bundle_name}, заменим на наш")
                            return False
                        else:
                            logger.info(f"    🔄 Проект имеет дефолтный bundle: {bundle_name}, заменим на наш")
                            return False
            return False
        except Exception as e:
            logger.debug(f"    Ошибка проверки state bundle: {e}")
            return False

    def remove_existing_state_bundle(self, project_id: str, queue_key: str) -> bool:
        """Удаление существующего state bundle у проекта"""
        try:
            # Получаем custom fields проекта
            response = self.session.get(
                f"{self.base_url}/api/admin/projects/{project_id}/customFields",
                params={'fields': 'id,field(id,name),bundle(id,name)'}
            )

            if response.status_code != 200:
                logger.warning(f"    ⚠ Не удалось получить поля проекта")
                return False

            custom_fields = response.json()
            state_field_config = None

            # Находим конфигурацию поля State
            for field in custom_fields:
                if field.get('field', {}).get('name') == 'State':
                    state_field_config = field
                    break

            if not state_field_config:
                logger.debug(f"    ℹ Поле State не найдено в проекте")
                return True

            project_field_id = state_field_config.get('id')
            bundle_info = state_field_config.get('bundle', {})
            bundle_id = bundle_info.get('id')
            bundle_name = bundle_info.get('name', '')

            logger.info(f"    🗑️ Удаляем существующий bundle: {bundle_name}")

            # Удаляем поле State из проекта
            if project_field_id:
                delete_response = self.session.delete(
                    f"{self.base_url}/api/admin/projects/{project_id}/customFields/{project_field_id}"
                )

                if delete_response.status_code in [200, 204]:
                    logger.info(f"    ✓ Поле State удалено из проекта")
                else:
                    logger.warning(f"    ⚠ Не удалось удалить поле State: {delete_response.status_code}")

            # Если bundle был создан нами (содержит имя очереди), удаляем его полностью
            if bundle_id and (queue_key in bundle_name or 'States' in bundle_name):
                try:
                    bundle_delete_response = self.session.delete(
                        f"{self.base_url}/api/admin/customFieldSettings/bundles/state/{bundle_id}"
                    )

                    if bundle_delete_response.status_code in [200, 204]:
                        logger.info(f"    ✓ State bundle '{bundle_name}' удален")
                    else:
                        logger.debug(f"    ℹ Не удалось удалить bundle (возможно используется в других проектах)")
                except Exception as e:
                    logger.debug(f"    ℹ Bundle не удален: {e}")

            return True

        except Exception as e:
            logger.error(f"    ✗ Ошибка удаления state bundle: {e}")
            return False

    def create_unique_state_bundle(self, base_name: str, statuses: List[Dict], attempt: int = 1) -> Optional[str]:
        """Создание уникального state bundle с обработкой дублирования"""
        try:
            # Генерируем уникальное имя
            if attempt == 1:
                bundle_name = base_name
            else:
                bundle_name = f"{base_name} v{attempt}"

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
                logger.info(f"    ✓ Создан state bundle: {bundle_name}")
                return created_bundle.get('id')
            elif response.status_code == 400 and 'не является уникальным' in response.text and attempt < 10:
                logger.debug(f"    🔄 Bundle '{bundle_name}' уже существует, пробуем другое имя")
                return self.create_unique_state_bundle(base_name, statuses, attempt + 1)
            else:
                logger.warning(f"    ⚠ Не удалось создать bundle {bundle_name}: {response.status_code} - {response.text}")
                return None

        except Exception as e:
            logger.error(f"    ✗ Ошибка создания state bundle: {e}")
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
                logger.warning(f"    ⚠ Не найдено поле State")
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
                logger.info(f"    ✓ State bundle назначен проекту")
                return True
            elif response.status_code == 409:
                logger.info(f"    ✓ State bundle уже назначен проекту")
                return True
            else:
                logger.warning(f"    ⚠ Не удалось назначить bundle: {response.status_code} - {response.text}")
                return False

        except Exception as e:
            logger.error(f"    ✗ Ошибка назначения state bundle: {e}")
            return False

def load_config() -> Dict:
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        exit(1)

def load_project_mapping() -> Dict:
    try:
        with open('project_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('projects', {})
    except FileNotFoundError:
        logger.error("Файл project_mapping.json не найден")
        exit(1)

def main():
    logger.info("=" * 60)
    logger.info("МИГРАЦИЯ СТАТУСОВ ДЛЯ СУЩЕСТВУЮЩИХ ПРОЕКТОВ")
    logger.info("=" * 60)

    config = load_config()
    project_mapping = load_project_mapping()

    if not project_mapping:
        logger.error("Маппинг проектов пуст")
        exit(1)

    logger.info(f"Найдено {len(project_mapping)} проектов для обработки")

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

    # Обрабатываем каждый проект
    success_count = 0
    skip_count = 0
    error_count = 0

    for i, (queue_key, project_id) in enumerate(project_mapping.items(), 1):
        logger.info(f"[{i}/{len(project_mapping)}] 📁 Обрабатываем проект: {queue_key}")

        # Проверяем, есть ли уже наш кастомный state bundle
        if youtrack_client.project_has_custom_state_bundle(project_id, queue_key):
            logger.info(f"  ⏭ Проект {queue_key} уже имеет настроенные состояния из Yandex Tracker")
            skip_count += 1
            continue

        # Удаляем существующий state bundle
        logger.info(f"  🗑️ Удаляем существующие состояния для проекта {queue_key}")
        if not youtrack_client.remove_existing_state_bundle(project_id, queue_key):
            logger.error(f"  ✗ Не удалось удалить существующие состояния")
            error_count += 1
            continue

        # Получаем статусы из Yandex Tracker
        statuses = yandex_client.get_queue_statuses(queue_key)

        if not statuses:
            logger.warning(f"  ⚠ Нет статусов для проекта {queue_key}")
            error_count += 1
            continue

        # Создаем уникальное имя для bundle
        bundle_base_name = f"{queue_key} States"

        # Создаем state bundle с уникальным именем
        bundle_id = youtrack_client.create_unique_state_bundle(bundle_base_name, statuses)
        if not bundle_id:
            error_count += 1
            continue

        # Назначаем bundle проекту
        if youtrack_client.assign_state_bundle_to_project(project_id, bundle_id):
            success_count += 1
            logger.info(f"  🎉 Статусы успешно настроены для проекта {queue_key}")
        else:
            error_count += 1

        # Пауза между проектами
        time.sleep(2)

    # Финальная статистика
    logger.info("=" * 60)
    logger.info("РЕЗУЛЬТАТЫ МИГРАЦИИ СТАТУСОВ:")
    logger.info(f"✓ Успешно настроено: {success_count}")
    logger.info(f"⏭ Пропущено (уже настроены): {skip_count}")
    logger.info(f"✗ Ошибок: {error_count}")
    logger.info("=" * 60)

    if error_count == 0:
        logger.info("🎉 МИГРАЦИЯ СТАТУСОВ ЗАВЕРШЕНА УСПЕШНО!")
        logger.info("Теперь можно запустить step3_issues_migration.py")
    else:
        logger.warning(f"⚠ Миграция завершена с {error_count} ошибками")

if __name__ == "__main__":
    main()