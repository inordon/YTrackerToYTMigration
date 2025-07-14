#!/usr/bin/env python3
"""
Утилита для очистки и восстановления после миграции
Позволяет откатить изменения или очистить данные
"""

import requests
import json
import logging
from typing import Dict, List, Optional
from datetime import datetime
import argparse

logger = logging.getLogger(__name__)

class MigrationCleanup:
    """Класс для очистки данных миграции"""

    def __init__(self, youtrack_url: str, youtrack_token: str):
        self.youtrack_url = youtrack_url.rstrip('/')
        self.youtrack_token = youtrack_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {youtrack_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def delete_issues_by_project(self, project_id: str) -> int:
        """Удаление всех задач проекта"""
        try:
            # Получаем все задачи проекта
            response = self.session.get(
                f"{self.youtrack_url}/api/admin/projects/{project_id}/issues",
                params={'fields': 'id,idReadable', '$top': -1}
            )
            response.raise_for_status()
            issues = response.json()

            deleted_count = 0
            for issue in issues:
                try:
                    delete_response = self.session.delete(
                        f"{self.youtrack_url}/api/issues/{issue['id']}"
                    )
                    if delete_response.status_code == 200:
                        deleted_count += 1
                        logger.debug(f"Удалена задача {issue['idReadable']}")
                    else:
                        logger.warning(f"Не удалось удалить задачу {issue['idReadable']}")
                except Exception as e:
                    logger.error(f"Ошибка удаления задачи {issue['id']}: {e}")

            logger.info(f"Удалено {deleted_count} задач из проекта {project_id}")
            return deleted_count

        except requests.RequestException as e:
            logger.error(f"Ошибка получения задач проекта {project_id}: {e}")
            return 0

    def delete_project(self, project_id: str) -> bool:
        """Удаление проекта"""
        try:
            response = self.session.delete(
                f"{self.youtrack_url}/api/admin/projects/{project_id}"
            )

            if response.status_code == 200:
                logger.info(f"Удален проект {project_id}")
                return True
            else:
                logger.error(f"Не удалось удалить проект {project_id}: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Ошибка удаления проекта {project_id}: {e}")
            return False

    def delete_user(self, user_id: str) -> bool:
        """Удаление пользователя"""
        try:
            # Используем Hub API для удаления пользователя
            response = self.session.delete(
                f"{self.youtrack_url}/hub/api/rest/users/{user_id}"
            )

            if response.status_code == 200:
                logger.info(f"Удален пользователь {user_id}")
                return True
            else:
                logger.error(f"Не удалось удалить пользователя {user_id}: {response.status_code}")
                return False

        except requests.RequestException as e:
            logger.error(f"Ошибка удаления пользователя {user_id}: {e}")
            return False

    def rollback_migration(self, mappings: Dict) -> Dict[str, int]:
        """Откат миграции на основе маппингов"""
        logger.info("=== Начало отката миграции ===")

        stats = {
            'deleted_issues': 0,
            'deleted_projects': 0,
            'deleted_users': 0
        }

        # Удаляем задачи (сначала задачи, потом проекты)
        issue_mapping = mappings.get('issues', {})
        project_mapping = mappings.get('projects', {})

        logger.info("Удаление задач...")
        for project_id in project_mapping.values():
            deleted_count = self.delete_issues_by_project(project_id)
            stats['deleted_issues'] += deleted_count

        # Удаляем проекты
        logger.info("Удаление проектов...")
        for project_id in project_mapping.values():
            if self.delete_project(project_id):
                stats['deleted_projects'] += 1

        # Удаляем пользователей (осторожно!)
        user_mapping = mappings.get('users', {})
        logger.info("Удаление пользователей...")
        logger.warning("ВНИМАНИЕ: Удаление пользователей может повлиять на другие данные!")

        # Запрашиваем подтверждение
        print("Вы уверены, что хотите удалить всех мигрированных пользователей? (yes/no): ")
        confirmation = input().lower()

        if confirmation == 'yes':
            for user_id in user_mapping.values():
                if self.delete_user(user_id):
                    stats['deleted_users'] += 1
        else:
            logger.info("Удаление пользователей пропущено")

        logger.info("=== Откат миграции завершен ===")
        return stats

    def selective_cleanup(self, cleanup_config: Dict) -> Dict[str, int]:
        """Селективная очистка по конфигурации"""
        logger.info("=== Начало селективной очистки ===")

        stats = {
            'deleted_issues': 0,
            'deleted_projects': 0,
            'deleted_users': 0
        }

        # Удаляем конкретные проекты
        projects_to_delete = cleanup_config.get('projects', [])
        for project_shortname in projects_to_delete:
            # Находим проект по короткому имени
            try:
                response = self.session.get(
                    f"{self.youtrack_url}/api/admin/projects",
                    params={'query': project_shortname, 'fields': 'id,shortName'}
                )
                response.raise_for_status()
                projects = response.json()

                for project in projects:
                    if project.get('shortName') == project_shortname:
                        project_id = project.get('id')
                        deleted_issues = self.delete_issues_by_project(project_id)
                        stats['deleted_issues'] += deleted_issues

                        if self.delete_project(project_id):
                            stats['deleted_projects'] += 1
                        break
            except Exception as e:
                logger.error(f"Ошибка при удалении проекта {project_shortname}: {e}")

        # Удаляем конкретных пользователей
        users_to_delete = cleanup_config.get('users', [])
        for user_login in users_to_delete:
            try:
                # Находим пользователя по логину
                response = self.session.get(
                    f"{self.youtrack_url}/api/users",
                    params={'query': user_login, 'fields': 'id,login'}
                )
                response.raise_for_status()
                users = response.json()

                for user in users:
                    if user.get('login') == user_login:
                        user_id = user.get('id')
                        if self.delete_user(user_id):
                            stats['deleted_users'] += 1
                        break
            except Exception as e:
                logger.error(f"Ошибка при удалении пользователя {user_login}: {e}")

        logger.info("=== Селективная очистка завершена ===")
        return stats

class BackupManager:
    """Менеджер для создания резервных копий"""

    def __init__(self, youtrack_url: str, youtrack_token: str):
        self.youtrack_url = youtrack_url.rstrip('/')
        self.youtrack_token = youtrack_token
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {youtrack_token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        })

    def create_projects_backup(self) -> Dict:
        """Создание резервной копии проектов"""
        try:
            response = self.session.get(
                f"{self.youtrack_url}/api/admin/projects",
                params={
                    'fields': 'id,name,shortName,description,leader(id,login,name)',
                    '$top': -1
                }
            )
            response.raise_for_status()
            projects = response.json()

            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'projects': projects
            }

            filename = f"projects_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Резервная копия проектов сохранена в {filename}")
            return backup_data

        except Exception as e:
            logger.error(f"Ошибка создания резервной копии проектов: {e}")
            return {}

    def create_users_backup(self) -> Dict:
        """Создание резервной копии пользователей"""
        try:
            response = self.session.get(
                f"{self.youtrack_url}/api/users",
                params={
                    'fields': 'id,login,name,email',
                    '$top': -1
                }
            )
            response.raise_for_status()
            users = response.json()

            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'users': users
            }

            filename = f"users_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(backup_data, f, ensure_ascii=False, indent=2)

            logger.info(f"Резервная копия пользователей сохранена в {filename}")
            return backup_data

        except Exception as e:
            logger.error(f"Ошибка создания резервной копии пользователей: {e}")
            return {}

def main():
    """Главная функция"""
    parser = argparse.ArgumentParser(description='Утилита очистки миграции')
    parser.add_argument('action', choices=['rollback', 'cleanup', 'backup'],
                        help='Действие: rollback - полный откат, cleanup - селективная очистка, backup - создание резервной копии')
    parser.add_argument('--config', default='migration_config.json',
                        help='Файл конфигурации')
    parser.add_argument('--mappings', default='migration_mappings.json',
                        help='Файл маппингов')
    parser.add_argument('--cleanup-config',
                        help='Файл конфигурации для селективной очистки')

    args = parser.parse_args()

    # Настройка логирования
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('cleanup.log'),
            logging.StreamHandler()
        ]
    )

    # Загружаем основную конфигурацию
    try:
        with open(args.config, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error(f"Файл конфигурации {args.config} не найден")
        return

    youtrack_url = config['youtrack']['url']
    youtrack_token = config['youtrack']['token']

    if args.action == 'backup':
        # Создание резервных копий
        backup_manager = BackupManager(youtrack_url, youtrack_token)
        backup_manager.create_projects_backup()
        backup_manager.create_users_backup()
        logger.info("Резервные копии созданы")

    elif args.action == 'rollback':
        # Полный откат миграции
        try:
            with open(args.mappings, 'r', encoding='utf-8') as f:
                mappings = json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл маппингов {args.mappings} не найден")
            return

        cleanup = MigrationCleanup(youtrack_url, youtrack_token)

        print("ВНИМАНИЕ: Это действие удалит ВСЕ данные, созданные во время миграции!")
        print("Вы уверены, что хотите продолжить? (yes/no): ")
        confirmation = input().lower()

        if confirmation == 'yes':
            stats = cleanup.rollback_migration(mappings)
            logger.info(f"Откат завершен: {stats}")
        else:
            logger.info("Откат отменен")

    elif args.action == 'cleanup':
        # Селективная очистка
        if not args.cleanup_config:
            logger.error("Для селективной очистки требуется файл конфигурации (--cleanup-config)")
            return

        try:
            with open(args.cleanup_config, 'r', encoding='utf-8') as f:
                cleanup_config = json.load(f)
        except FileNotFoundError:
            logger.error(f"Файл конфигурации очистки {args.cleanup_config} не найден")
            return

        cleanup = MigrationCleanup(youtrack_url, youtrack_token)
        stats = cleanup.selective_cleanup(cleanup_config)
        logger.info(f"Селективная очистка завершена: {stats}")

if __name__ == "__main__":
    main()