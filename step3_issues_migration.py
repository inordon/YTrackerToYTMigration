#!/usr/bin/env python3
"""
Этап 3: Миграция задач из Yandex Tracker в YouTrack
Создает задачи с комментариями и сохраняет маппинг
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
        logging.FileHandler('step3_issues.log'),
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

    def get_issues(self, queue_key: str, per_page: int = 50) -> List[Dict]:
        """Получение всех задач из очереди с пагинацией"""
        all_issues = []
        page = 1

        while True:
            try:
                params = {
                    'queue': queue_key,
                    'perPage': per_page,
                    'page': page
                }
                response = self.session.get(f"{self.base_url}/issues", params=params)
                response.raise_for_status()
                issues = response.json()

                if not issues:
                    break

                all_issues.extend(issues)
                logger.debug(f"  Получено {len(issues)} задач со страницы {page}")
                page += 1

                # Пауза между запросами
                time.sleep(0.5)

            except requests.RequestException as e:
                logger.error(f"Ошибка получения задач для очереди {queue_key}, страница {page}: {e}")
                break

        logger.info(f"  📝 Всего получено {len(all_issues)} задач для очереди {queue_key}")
        return all_issues

    def get_issue_comments(self, issue_key: str) -> List[Dict]:
        """Получение комментариев к задаче"""
        try:
            response = self.session.get(f"{self.base_url}/issues/{issue_key}/comments")
            response.raise_for_status()
            comments = response.json()
            logger.debug(f"    💬 Получено {len(comments)} комментариев для задачи {issue_key}")
            return comments
        except requests.RequestException as e:
            logger.error(f"Ошибка получения комментариев для задачи {issue_key}: {e}")
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

    def create_issue(self, issue_data: Dict, project_id: str) -> Optional[str]:
        """Создание задачи в YouTrack"""
        try:
            # Подготавливаем данные задачи
            yt_issue = {
                'project': {'id': project_id},
                'summary': issue_data.get('summary'),
                'description': issue_data.get('description', ''),
            }

            # Добавляем дополнительную информацию в описание
            original_info = f"\n\n---\n**Исходная задача:** {issue_data.get('key')}\n"
            original_info += f"**Автор:** {issue_data.get('createdBy', {}).get('display', 'Unknown')}\n"
            original_info += f"**Дата создания:** {issue_data.get('createdAt', '')}\n"

            if issue_data.get('assignee'):
                original_info += f"**Исполнитель:** {issue_data['assignee'].get('display', 'Unknown')}\n"

            yt_issue['description'] += original_info

            response = self.session.post(
                f"{self.base_url}/api/issues",
                json=yt_issue,
                params={'fields': 'id,idReadable'}
            )

            if response.status_code == 200:
                created_issue = response.json()
                logger.debug(f"    ✓ Создана задача: {created_issue.get('idReadable')}")
                return created_issue.get('id')
            else:
                logger.error(f"    ✗ Ошибка создания задачи: {response.status_code} - {response.text}")
                return None

        except requests.RequestException as e:
            logger.error(f"    ✗ Ошибка создания задачи: {e}")
            return None

    def add_comment_to_issue(self, issue_id: str, comment_data: Dict) -> bool:
        """Добавление комментария к задаче"""
        try:
            comment_text = comment_data.get('text', '')
            author = comment_data.get('createdBy', {})
            created_date = comment_data.get('createdAt', '')

            # Формируем текст комментария с информацией об авторе
            formatted_comment = f"**Автор:** {author.get('display', 'Unknown')}\n"
            formatted_comment += f"**Дата:** {created_date}\n\n"
            formatted_comment += comment_text

            response = self.session.post(
                f"{self.base_url}/api/issues/{issue_id}/comments",
                json={'text': formatted_comment},
                params={'fields': 'id'}
            )

            if response.status_code == 200:
                logger.debug(f"      💬 Добавлен комментарий к задаче")
                return True
            else:
                logger.warning(f"      ⚠ Не удалось добавить комментарий: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"      ✗ Ошибка добавления комментария: {e}")
            return False

def load_config() -> Dict:
    """Загрузка конфигурации"""
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error("Файл migration_config.json не найден")
        exit(1)

def load_project_mapping() -> Dict:
    """Загрузка маппинга проектов"""
    try:
        with open('project_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('projects', {})
    except FileNotFoundError:
        logger.error("Файл project_mapping.json не найден")
        logger.error("Сначала запустите step2_projects_migration.py")
        exit(1)

def save_issue_mapping(issue_mapping: Dict):
    """Сохранение маппинга задач"""
    mapping_data = {
        'issues': issue_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'issues_completed'
    }

    with open('issue_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

    logger.info(f"Маппинг задач сохранен в issue_mapping.json")

def load_existing_issue_mapping() -> Dict:
    """Загрузка существующего маппинга задач"""
    try:
        with open('issue_mapping.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            return data.get('issues', {})
    except FileNotFoundError:
        return {}

def main():
    """Главная функция этапа 3"""
    logger.info("=" * 50)
    logger.info("ЭТАП 3: МИГРАЦИЯ ЗАДАЧ")
    logger.info("=" * 50)

    # Загружаем конфигурацию
    config = load_config()

    # Загружаем маппинг проектов
    project_mapping = load_project_mapping()
    if not project_mapping:
        logger.error("Маппинг проектов пуст")
        logger.error("Сначала успешно завершите step2_projects_migration.py")
        exit(1)

    logger.info(f"Загружен маппинг проектов: {len(project_mapping)} проектов")

    # Создаем клиентов
    yandex_client = YandexTrackerClient(
        config['yandex_tracker']['token'],
        config['yandex_tracker']['org_id']
    )

    youtrack_client = YouTrackClient(
        config['youtrack']['url'],
        config['youtrack']['token']
    )

    # Загружаем существующий маппинг задач
    issue_mapping = load_existing_issue_mapping()
    logger.info(f"Загружен существующий маппинг задач: {len(issue_mapping)} задач")

    # Получаем настройки миграции
    migration_options = config.get('migration_options', {})
    migrate_comments = migration_options.get('migrate_comments', True)
    batch_size = migration_options.get('batch_size', 50)

    logger.info(f"Настройки: комментарии={'ВКЛ' if migrate_comments else 'ВЫКЛ'}, размер пакета={batch_size}")

    # Мигрируем задачи по проектам
    total_success = 0
    total_skip = 0
    total_error = 0
    total_issues_processed = 0

    for i, (queue_key, project_id) in enumerate(project_mapping.items(), 1):
        logger.info(f"[{i}/{len(project_mapping)}] 📁 Обрабатываем проект: {queue_key}")

        # Получаем задачи проекта
        yandex_issues = yandex_client.get_issues(queue_key, batch_size)
        if not yandex_issues:
            logger.warning(f"  ⚠ Нет задач в проекте {queue_key}")
            continue

        # Обрабатываем задачи
        project_success = 0
        project_skip = 0
        project_error = 0

        for j, issue in enumerate(yandex_issues, 1):
            issue_key = issue.get('key')
            total_issues_processed += 1

            if j % 10 == 0:
                logger.info(f"    [{j}/{len(yandex_issues)}] Обработано задач в проекте")

            # Пропускаем если уже мигрирована
            if issue_key in issue_mapping:
                project_skip += 1
                continue

            # Создаем задачу
            issue_id = youtrack_client.create_issue(issue, project_id)
            if issue_id:
                issue_mapping[issue_key] = issue_id
                project_success += 1

                # Мигрируем комментарии если включено
                if migrate_comments:
                    comments = yandex_client.get_issue_comments(issue_key)
                    for comment in comments:
                        youtrack_client.add_comment_to_issue(issue_id, comment)
                        time.sleep(0.1)
            else:
                project_error += 1

            # Пауза между задачами
            time.sleep(0.3)

            # Сохраняем промежуточный результат каждые 50 задач
            if total_issues_processed % 50 == 0:
                save_issue_mapping(issue_mapping)
                logger.info(f"  💾 Промежуточное сохранение: {total_issues_processed} задач обработано")

        # Статистика по проекту
        logger.info(f"  📊 Проект {queue_key}: ✓{project_success} ⏭{project_skip} ✗{project_error}")

        total_success += project_success
        total_skip += project_skip
        total_error += project_error

        # Сохраняем результат после каждого проекта
        save_issue_mapping(issue_mapping)

    # Сохраняем финальный результат
    save_issue_mapping(issue_mapping)

    # Выводим финальную статистику
    logger.info("=" * 50)
    logger.info("РЕЗУЛЬТАТЫ ЭТАПА 3:")
    logger.info(f"✓ Успешно создано: {total_success}")
    logger.info(f"⏭ Пропущено (уже существуют): {total_skip}")
    logger.info(f"✗ Ошибок: {total_error}")
    logger.info(f"📊 Всего в маппинге: {len(issue_mapping)}")
    logger.info(f"🔢 Всего обработано: {total_issues_processed}")
    logger.info("=" * 50)

    if total_error == 0:
        logger.info("🎉 ЭТАП 3 ЗАВЕРШЕН УСПЕШНО!")
        logger.info("Теперь можно запустить step4_links_migration.py")
    else:
        logger.warning(f"⚠ Этап завершен с {total_error} ошибками")
        logger.info("Проверьте логи и повторите запуск для исправления ошибок")

if __name__ == "__main__":
    main()