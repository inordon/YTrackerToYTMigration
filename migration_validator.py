#!/usr/bin/env python3
"""
Модуль валидации и проверки миграции
Проверяет корректность перенесенных данных и создает детальные отчеты
"""

import requests
import json
import logging
from typing import Dict, List, Tuple, Any
from datetime import datetime
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class ValidationResult:
    """Результат валидации"""
    success: bool
    errors: List[str]
    warnings: List[str]
    stats: Dict[str, Any]

class MigrationValidator:
    """Класс для валидации результатов миграции"""

    def __init__(self, yandex_client, youtrack_client, mappings: Dict):
        self.yandex_client = yandex_client
        self.youtrack_client = youtrack_client
        self.mappings = mappings
        self.validation_results = []

    def validate_users(self) -> ValidationResult:
        """Валидация миграции пользователей"""
        logger.info("Валидация пользователей...")

        errors = []
        warnings = []
        stats = {}

        try:
            # Получаем пользователей из обеих систем
            yandex_users = self.yandex_client.get_users()
            user_mapping = self.mappings.get('users', {})

            stats['yandex_users_total'] = len(yandex_users)
            stats['migrated_users_total'] = len(user_mapping)

            # Проверяем каждого пользователя
            missing_users = []
            for yandex_user in yandex_users:
                yandex_id = yandex_user.get('id')
                if yandex_id not in user_mapping:
                    missing_users.append(yandex_user.get('login', yandex_id))

            if missing_users:
                errors.append(f"Не мигрированы пользователи: {', '.join(missing_users)}")

            # Проверяем существование пользователей в YouTrack
            invalid_mappings = []
            for yandex_id, youtrack_id in user_mapping.items():
                try:
                    response = self.youtrack_client.session.get(
                        f"{self.youtrack_client.base_url}/api/users/{youtrack_id}",
                        params={'fields': 'id,login'}
                    )
                    if response.status_code != 200:
                        invalid_mappings.append(f"{yandex_id} -> {youtrack_id}")
                except Exception as e:
                    invalid_mappings.append(f"{yandex_id} -> {youtrack_id} (error: {e})")

            if invalid_mappings:
                errors.append(f"Некорректные маппинги пользователей: {', '.join(invalid_mappings)}")

            stats['missing_users'] = len(missing_users)
            stats['invalid_mappings'] = len(invalid_mappings)

        except Exception as e:
            errors.append(f"Ошибка валидации пользователей: {e}")

        success = len(errors) == 0
        return ValidationResult(success, errors, warnings, stats)

    def validate_projects(self) -> ValidationResult:
        """Валидация миграции проектов"""
        logger.info("Валидация проектов...")

        errors = []
        warnings = []
        stats = {}

        try:
            yandex_queues = self.yandex_client.get_queues()
            project_mapping = self.mappings.get('projects', {})

            stats['yandex_queues_total'] = len(yandex_queues)
            stats['migrated_projects_total'] = len(project_mapping)

            # Проверяем соответствие проектов
            missing_projects = []
            for queue in yandex_queues:
                queue_key = queue.get('key')
                if queue_key not in project_mapping:
                    missing_projects.append(queue_key)

            if missing_projects:
                errors.append(f"Не мигрированы проекты: {', '.join(missing_projects)}")

            # Проверяем существование проектов в YouTrack
            invalid_project_mappings = []
            for queue_key, project_id in project_mapping.items():
                try:
                    response = self.youtrack_client.session.get(
                        f"{self.youtrack_client.base_url}/api/admin/projects/{project_id}",
                        params={'fields': 'id,shortName,name'}
                    )
                    if response.status_code != 200:
                        invalid_project_mappings.append(f"{queue_key} -> {project_id}")
                except Exception as e:
                    invalid_project_mappings.append(f"{queue_key} -> {project_id} (error: {e})")

            if invalid_project_mappings:
                errors.append(f"Некорректные маппинги проектов: {', '.join(invalid_project_mappings)}")

            stats['missing_projects'] = len(missing_projects)
            stats['invalid_project_mappings'] = len(invalid_project_mappings)

        except Exception as e:
            errors.append(f"Ошибка валидации проектов: {e}")

        success = len(errors) == 0
        return ValidationResult(success, errors, warnings, stats)

    def validate_issues(self) -> ValidationResult:
        """Валидация миграции задач"""
        logger.info("Валидация задач...")

        errors = []
        warnings = []
        stats = {}

        try:
            issue_mapping = self.mappings.get('issues', {})
            project_mapping = self.mappings.get('projects', {})

            # Подсчитываем общее количество задач в Yandex Tracker
            total_yandex_issues = 0
            for queue_key in project_mapping.keys():
                yandex_issues = self.yandex_client.get_issues(queue_key)
                total_yandex_issues += len(yandex_issues)

            stats['yandex_issues_total'] = total_yandex_issues
            stats['migrated_issues_total'] = len(issue_mapping)

            # Проверяем процент миграции
            migration_percentage = (len(issue_mapping) / total_yandex_issues * 100) if total_yandex_issues > 0 else 0
            stats['migration_percentage'] = round(migration_percentage, 2)

            if migration_percentage < 95:
                warnings.append(f"Мигрировано только {migration_percentage:.1f}% задач")

            # Выборочная проверка задач в YouTrack
            sample_size = min(10, len(issue_mapping))
            sample_issues = list(issue_mapping.items())[:sample_size]

            invalid_issue_mappings = []
            for yandex_key, youtrack_id in sample_issues:
                try:
                    response = self.youtrack_client.session.get(
                        f"{self.youtrack_client.base_url}/api/issues/{youtrack_id}",
                        params={'fields': 'id,idReadable,summary'}
                    )
                    if response.status_code != 200:
                        invalid_issue_mappings.append(f"{yandex_key} -> {youtrack_id}")
                except Exception as e:
                    invalid_issue_mappings.append(f"{yandex_key} -> {youtrack_id} (error: {e})")

            if invalid_issue_mappings:
                errors.append(f"Некорректные маппинги задач (выборка): {', '.join(invalid_issue_mappings)}")

            stats['checked_issues'] = sample_size
            stats['invalid_issue_mappings'] = len(invalid_issue_mappings)

        except Exception as e:
            errors.append(f"Ошибка валидации задач: {e}")

        success = len(errors) == 0
        return ValidationResult(success, errors, warnings, stats)

    def validate_links(self) -> ValidationResult:
        """Валидация связей между задачами"""
        logger.info("Валидация связей задач...")

        errors = []
        warnings = []
        stats = {}

        try:
            issue_mapping = self.mappings.get('issues', {})

            # Выборочная проверка связей
            sample_issues = list(issue_mapping.keys())[:5]  # Проверяем первые 5 задач

            total_yandex_links = 0
            total_youtrack_links = 0

            for yandex_key in sample_issues:
                youtrack_id = issue_mapping.get(yandex_key)
                if not youtrack_id:
                    continue

                # Получаем связи из Yandex Tracker
                yandex_links = self.yandex_client.get_issue_links(yandex_key)
                total_yandex_links += len(yandex_links)

                # Получаем связи из YouTrack
                try:
                    response = self.youtrack_client.session.get(
                        f"{self.youtrack_client.base_url}/api/issues/{youtrack_id}/links",
                        params={'fields': 'id,linkType,issues(id)'}
                    )
                    if response.status_code == 200:
                        youtrack_links = response.json()
                        total_youtrack_links += len(youtrack_links)
                except Exception as e:
                    warnings.append(f"Не удалось проверить связи для задачи {yandex_key}: {e}")

            stats['checked_issues'] = len(sample_issues)
            stats['yandex_links_total'] = total_yandex_links
            stats['youtrack_links_total'] = total_youtrack_links

            if total_yandex_links > 0:
                link_migration_percentage = (total_youtrack_links / total_yandex_links * 100)
                stats['link_migration_percentage'] = round(link_migration_percentage, 2)

                if link_migration_percentage < 80:
                    warnings.append(f"Мигрировано только {link_migration_percentage:.1f}% связей")

        except Exception as e:
            errors.append(f"Ошибка валидации связей: {e}")

        success = len(errors) == 0
        return ValidationResult(success, errors, warnings, stats)

    def run_full_validation(self) -> Dict[str, ValidationResult]:
        """Запуск полной валидации"""
        logger.info("=== Начало валидации миграции ===")

        results = {
            'users': self.validate_users(),
            'projects': self.validate_projects(),
            'issues': self.validate_issues(),
            'links': self.validate_links()
        }

        return results

    def generate_validation_report(self, results: Dict[str, ValidationResult]) -> str:
        """Генерация отчета валидации"""
        report = []
        report.append("=== ОТЧЕТ ВАЛИДАЦИИ МИГРАЦИИ ===")
        report.append(f"Дата: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report.append("")

        overall_success = all(result.success for result in results.values())
        status = "✅ УСПЕШНО" if overall_success else "❌ ОБНАРУЖЕНЫ ПРОБЛЕМЫ"
        report.append(f"ОБЩИЙ СТАТУС: {status}")
        report.append("")

        for category, result in results.items():
            report.append(f"{category.upper()}:")
            status_icon = "✅" if result.success else "❌"
            report.append(f"  Статус: {status_icon}")

            if result.errors:
                report.append("  Ошибки:")
                for error in result.errors:
                    report.append(f"    - {error}")

            if result.warnings:
                report.append("  Предупреждения:")
                for warning in result.warnings:
                    report.append(f"    - {warning}")

            if result.stats:
                report.append("  Статистика:")
                for key, value in result.stats.items():
                    report.append(f"    {key}: {value}")

            report.append("")

        # Общие рекомендации
        report.append("РЕКОМЕНДАЦИИ:")

        if not overall_success:
            report.append("1. ❗ Устраните обнаруженные ошибки")
            report.append("2. 🔄 Перезапустите проблемные этапы миграции")

        report.append("3. 👥 Проверьте права доступа пользователей")
        report.append("4. 🔧 Настройте рабочие процессы проектов")
        report.append("5. 📧 Настройте уведомления")
        report.append("6. 🗃️ Создайте резервную копию")

        report_text = "\n".join(report)

        # Сохраняем отчет валидации
        filename = f"validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(report_text)

        logger.info(f"Отчет валидации сохранен в {filename}")
        return report_text

def main():
    """Запуск валидации как отдельного скрипта"""
    from tracker_migration import YandexTrackerClient, YouTrackClient
    import json

    # Загружаем конфигурацию
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        logger.error("Файл конфигурации не найден")
        return

    # Загружаем маппинги
    try:
        with open('migration_mappings.json', 'r', encoding='utf-8') as f:
            mappings = json.load(f)
    except FileNotFoundError:
        logger.error("Файл маппингов не найден")
        return

    # Создаем клиентов
    yandex_client = YandexTrackerClient(
        config['yandex_tracker']['token'],
        config['yandex_tracker']['org_id']
    )

    youtrack_client = YouTrackClient(
        config['youtrack']['url'],
        config['youtrack']['token']
    )

    # Запускаем валидацию
    validator = MigrationValidator(yandex_client, youtrack_client, mappings)
    results = validator.run_full_validation()

    # Генерируем отчет
    report = validator.generate_validation_report(results)
    print(report)

if __name__ == "__main__":
    main()