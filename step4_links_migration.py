#!/usr/bin/env python3
"""
Этап 4: Миграция связей между задачами из Yandex Tracker в YouTrack
Создает связи между мигрированными задачами
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
        logging.FileHandler('step4_links.log'),
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

    def get_issue_links(self, issue_key: str) -> List[Dict]:
        """Получение связей задачи"""
        try:
            response = self.session.get(f"{self.base_url}/issues/{issue_key}/links")
            response.raise_for_status()
            links = response.json()
            logger.debug(f"    🔗 Получено {len(links)} связей для задачи {issue_key}")
            return links
        except requests.RequestException as e:
            logger.error(f"Ошибка получения связей для задачи {issue_key}: {e}")
            return []

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

    def get_link_types(self) -> Dict[str, str]:
        """Получение доступных типов связей"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/admin/issueLinkTypes",
                params={'fields': 'name,inward,outward'}
            )
            response.raise_for_status()
            link_types = response.json()

            # Создаем маппинг типов связей
            type_mapping = {}
            for link_type in link_types:
                name = link_type.get('name', '')
                inward = link_type.get('inward', '')
                outward = link_type.get('outward', '')

                # Стандартные типы связей
                if 'depend' in name.lower() or 'блокир' in name.lower():
                    type_mapping['depends'] = name
                elif 'duplicate' in name.lower() or 'дубликат' in name.lower():
                    type_mapping['duplicates'] = name
                elif 'relate' in name.lower() or 'связ' in name.lower():
                    type_mapping['relates'] = name
                elif 'parent' in name.lower() or 'родител' in name.lower():
                    type_mapping['parent'] = name

            # Добавляем дефолтный тип связи
            if not type_mapping:
                type_mapping['relates'] = 'relates'

            logger.info(f"  🔗 Найдено типов связей: {len(type_mapping)}")
            return type_mapping

        except requests.RequestException as e:
            logger.error(f"Ошибка получения типов связей: {e}")
            return {'relates': 'relates'}

    def create_issue_link(self, issue_id: str, target_issue_id: str, link_type: str = 'relates') -> bool:
        """Создание связи между задачами"""
        try:
            link_request = {
                'linkType': link_type,
                'issues': [{'id': target_issue_id}]
            }

            response = self.session.post(
                f"{self.base_url}/api/issues/{issue_id}/links",
                json=link_request,
                params={'fields': 'id'}
            )

            if response.status_code == 200:
                logger.debug(f"      ✓ Создана связь {link_type}")
                return True
            else:
                logger.warning(f"      ⚠ Не удалось создать связь: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"      ✗ Ошибка создания связи: {e}")
            return False

def load_config() -> Dict:
    """Загрузка конфигурации"""
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        exit(1)

def load_issue_mapping() -> Dict:
    """Загрузка маппинга задач"""
    try:
        with open('issue_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('issues', {})
    except FileNotFoundError:
        logger.error("Файл issue_mapping.json не найден")
        logger.error("Сначала запустите step3_issues_migration.py")
        exit(1)

def save_links_report(links_stats: Dict):
    """Сохранение отчета о связях"""
    report_data = {
        'links_statistics': links_stats,
        'timestamp': datetime.now().isoformat(),
        'step': 'links_completed'
    }

    with open('links_report.json', 'w', encoding='utf-8') as f:
        json.dump(report_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Отчет о связях сохранен в links_report.json")

def map_link_type(yandex_link_type: str, youtrack_link_types: Dict[str, str]) -> str:
    """Маппинг типов связей из Yandex Tracker в YouTrack"""
    yandex_type = yandex_link_type.lower()

    # Стандартные маппинги
    if 'depend' in yandex_type or 'блокир' in yandex_type:
        return youtrack_link_types.get('depends', 'relates')
    elif 'duplicate' in yandex_type or 'дубликат' in yandex_type:
        return youtrack_link_types.get('duplicates', 'relates')
    elif 'parent' in yandex_type or 'родител' in yandex_type:
        return youtrack_link_types.get('parent', 'relates')
    else:
        return youtrack_link_types.get('relates', 'relates')

def main():
    """Главная функция этапа 4"""
    logger.info("=" * 50)
    logger.info("ЭТАП 4: МИГРАЦИЯ СВЯЗЕЙ")
    logger.info("=" * 50)

    # Загружаем конфигурацию
    config = load_config()

    # Загружаем маппинг задач
    issue_mapping = load_issue_mapping()
    if not issue_mapping:
        logger.error("Маппинг задач пуст")
        logger.error("Сначала успешно завершите step3_issues_migration.py")
        exit(1)

    logger.info(f"Загружен маппинг задач: {len(issue_mapping)} задач")

    # Создаем клиентов
    yandex_client = YandexTrackerClient(
        config['yandex_tracker']['token'],
        config['yandex_tracker']['org_id']
    )

    youtrack_client = YouTrackClient(
        config['youtrack']['url'],
        config['youtrack']['token']
    )

    # Получаем типы связей YouTrack
    youtrack_link_types = youtrack_client.get_link_types()
    logger.info(f"Доступные типы связей: {list(youtrack_link_types.keys())}")

    # Статистика
    links_stats = {
        'total_issues_checked': 0,
        'total_links_found': 0,
        'links_created': 0,
        'links_skipped': 0,
        'links_failed': 0,
        'link_types_used': {}
    }

    # Создаем множество для отслеживания уже созданных связей
    created_links = set()

    logger.info("Начинаем анализ и создание связей...")

    # Обрабатываем задачи
    issue_list = list(issue_mapping.items())

    for i, (yandex_issue_key, youtrack_issue_id) in enumerate(issue_list, 1):
        if i % 100 == 0:
            logger.info(f"[{i}/{len(issue_list)}] Обработано задач")

        links_stats['total_issues_checked'] += 1

        # Получаем связи задачи из Yandex Tracker
        yandex_links = yandex_client.get_issue_links(yandex_issue_key)
        if not yandex_links:
            continue

        links_stats['total_links_found'] += len(yandex_links)
        logger.debug(f"  🔍 Задача {yandex_issue_key}: найдено {len(yandex_links)} связей")

        # Обрабатываем каждую связь
        for link in yandex_links:
            # Получаем ключ связанной задачи
            target_issue_key = None
            if link.get('object'):
                target_issue_key = link['object'].get('key')
            elif link.get('target'):
                target_issue_key = link['target'].get('key')

            if not target_issue_key:
                logger.debug(f"    ⚠ Не удалось определить целевую задачу для связи")
                links_stats['links_skipped'] += 1
                continue

            # Проверяем, что целевая задача тоже мигрирована
            target_youtrack_id = issue_mapping.get(target_issue_key)
            if not target_youtrack_id:
                logger.debug(f"    ⚠ Целевая задача {target_issue_key} не найдена в маппинге")
                links_stats['links_skipped'] += 1
                continue

            # Определяем тип связи
            yandex_link_type = link.get('type', {}).get('key', 'relates')
            youtrack_link_type = map_link_type(yandex_link_type, youtrack_link_types)

            # Создаем уникальный идентификатор связи для избежания дублей
            link_signature = f"{youtrack_issue_id}-{target_youtrack_id}-{youtrack_link_type}"
            reverse_link_signature = f"{target_youtrack_id}-{youtrack_issue_id}-{youtrack_link_type}"

            if link_signature in created_links or reverse_link_signature in created_links:
                logger.debug(f"    ⏭ Связь уже создана")
                links_stats['links_skipped'] += 1
                continue

            # Создаем связь
            if youtrack_client.create_issue_link(youtrack_issue_id, target_youtrack_id, youtrack_link_type):
                created_links.add(link_signature)
                links_stats['links_created'] += 1

                # Статистика по типам связей
                if youtrack_link_type not in links_stats['link_types_used']:
                    links_stats['link_types_used'][youtrack_link_type] = 0
                links_stats['link_types_used'][youtrack_link_type] += 1

            else:
                links_stats['links_failed'] += 1

            # Пауза между создением связей
            time.sleep(0.2)

        # Пауза между задачами
        time.sleep(0.1)

    # Сохраняем отчет
    save_links_report(links_stats)

    # Выводим финальную статистику
    logger.info("=" * 50)
    logger.info("РЕЗУЛЬТАТЫ ЭТАПА 4:")
    logger.info(f"🔍 Проверено задач: {links_stats['total_issues_checked']}")
    logger.info(f"🔗 Найдено связей: {links_stats['total_links_found']}")
    logger.info(f"✓ Создано связей: {links_stats['links_created']}")
    logger.info(f"⏭ Пропущено связей: {links_stats['links_skipped']}")
    logger.info(f"✗ Ошибок создания: {links_stats['links_failed']}")
    logger.info("")
    logger.info("📊 Статистика по типам связей:")
    for link_type, count in links_stats['link_types_used'].items():
        logger.info(f"  {link_type}: {count}")
    logger.info("=" * 50)

    if links_stats['links_failed'] == 0:
        logger.info("🎉 ЭТАП 4 ЗАВЕРШЕН УСПЕШНО!")
        logger.info("🎊 ВСЯ МИГРАЦИЯ ЗАВЕРШЕНА!")
        logger.info("")
        logger.info("Рекомендуется:")
        logger.info("1. Запустить validation.py для проверки результатов")
        logger.info("2. Настроить права доступа пользователей")
        logger.info("3. Обучить команду работе с YouTrack")
    else:
        logger.warning(f"⚠ Этап завершен с {links_stats['links_failed']} ошибками")
        logger.info("Проверьте логи, но это не критично для работы системы")

if __name__ == "__main__":
    main()