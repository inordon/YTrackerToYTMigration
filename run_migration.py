#!/usr/bin/env python3
"""
Мастер-скрипт для поэтапного запуска миграции из Yandex Tracker в YouTrack
Управляет последовательным выполнением всех этапов миграции
"""

import subprocess
import sys
import json
import logging
from datetime import datetime
from pathlib import Path

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration_master.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

MIGRATION_STEPS = [
    {
        'name': 'Миграция пользователей',
        'script': 'step1_users_migration.py',
        'description': 'Создание пользователей в YouTrack',
        'output_file': 'user_mapping.json'
    },
    {
        'name': 'Миграция проектов',
        'script': 'step2_projects_migration.py',
        'description': 'Создание проектов со статусами',
        'output_file': 'project_mapping.json'
    },
    {
        'name': 'Миграция задач',
        'script': 'step3_issues_migration.py',
        'description': 'Создание задач с комментариями',
        'output_file': 'issue_mapping.json'
    },
    {
        'name': 'Миграция связей',
        'script': 'step4_links_migration.py',
        'description': 'Создание связей между задачами',
        'output_file': 'links_report.json'
    }
]

def check_prerequisites():
    """Проверка предварительных условий"""
    logger.info("🔍 Проверка предварительных условий...")

    # Проверяем наличие конфигурации
    if not Path('migration_config.json').exists():
        logger.error("❌ Файл migration_config.json не найден")
        logger.info("📝 Создайте конфигурацию согласно документации")
        return False

    # Проверяем конфигурацию
    try:
        with open('migration_config.json', 'r', encoding='utf-8') as f:
            config = json.load(f)

        required_fields = [
            'yandex_tracker.token',
            'yandex_tracker.org_id',
            'youtrack.url',
            'youtrack.token'
        ]

        for field in required_fields:
            keys = field.split('.')
            value = config
            for key in keys:
                value = value.get(key, '')

            if not value or value.startswith('YOUR_'):
                logger.error(f"❌ Поле {field} не заполнено в конфигурации")
                return False

    except json.JSONDecodeError:
        logger.error("❌ Некорректный JSON в файле конфигурации")
        return False
    except Exception as e:
        logger.error(f"❌ Ошибка чтения конфигурации: {e}")
        return False

    # Проверяем наличие скриптов этапов
    for step in MIGRATION_STEPS:
        if not Path(step['script']).exists():
            logger.error(f"❌ Скрипт {step['script']} не найден")
            return False

    logger.info("✅ Все предварительные условия выполнены")
    return True

def run_step(step_info, resume=False):
    """Запуск одного этапа миграции"""
    script_name = step_info['script']
    step_name = step_info['name']
    output_file = step_info['output_file']

    logger.info(f"🚀 Запуск этапа: {step_name}")
    logger.info(f"📄 Скрипт: {script_name}")
    logger.info(f"📝 Описание: {step_info['description']}")

    # Проверяем, завершен ли уже этап (если resume=True)
    if resume and Path(output_file).exists():
        logger.info(f"⏭️ Этап уже выполнен (найден {output_file}), пропускаем")
        return True

    try:
        # Запускаем скрипт
        start_time = datetime.now()
        result = subprocess.run([sys.executable, script_name],
                                capture_output=True, text=True, encoding='utf-8')
        end_time = datetime.now()
        duration = end_time - start_time

        # Выводим результат
        if result.returncode == 0:
            logger.info(f"✅ Этап завершен успешно за {duration}")
            logger.info(f"📊 Создан файл: {output_file}")
            return True
        else:
            logger.error(f"❌ Этап завершился с ошибкой (код {result.returncode})")
            logger.error(f"❌ Stderr: {result.stderr}")
            return False

    except Exception as e:
        logger.error(f"❌ Ошибка запуска скрипта {script_name}: {e}")
        return False

def run_full_migration(resume=False):
    """Запуск полной миграции"""
    logger.info("=" * 60)
    logger.info("🎯 НАЧАЛО ПОЛНОЙ МИГРАЦИИ YANDEX TRACKER → YOUTRACK")
    logger.info("=" * 60)

    start_time = datetime.now()
    failed_steps = []

    for i, step in enumerate(MIGRATION_STEPS, 1):
        logger.info(f"\n📍 ЭТАП {i}/{len(MIGRATION_STEPS)}: {step['name'].upper()}")
        logger.info("-" * 50)

        success = run_step(step, resume)

        if not success:
            failed_steps.append(step['name'])
            logger.error(f"🛑 Этап {step['name']} завершился неудачно")

            # Спрашиваем, продолжать ли дальше
            print(f"\n❓ Этап '{step['name']}' завершился с ошибкой.")
            print("Продолжить выполнение следующих этапов? (y/n): ", end='')
            choice = input().lower()

            if choice != 'y':
                logger.info("🛑 Миграция остановлена пользователем")
                break
        else:
            logger.info(f"✅ Этап {step['name']} завершен успешно")

    end_time = datetime.now()
    total_duration = end_time - start_time

    # Финальный отчет
    logger.info("\n" + "=" * 60)
    logger.info("📊 ИТОГОВЫЙ ОТЧЕТ МИГРАЦИИ")
    logger.info("=" * 60)
    logger.info(f"⏱️ Общее время выполнения: {total_duration}")
    logger.info(f"✅ Успешных этапов: {len(MIGRATION_STEPS) - len(failed_steps)}")
    logger.info(f"❌ Неудачных этапов: {len(failed_steps)}")

    if failed_steps:
        logger.warning("⚠️ Этапы с ошибками:")
        for step in failed_steps:
            logger.warning(f"  - {step}")

    if not failed_steps:
        logger.info("🎉 ВСЯ МИГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО!")
        logger.info("\n🎯 СЛЕДУЮЩИЕ ШАГИ:")
        logger.info("1. 🔍 Запустите validation.py для проверки")
        logger.info("2. 👥 Настройте права доступа пользователей")
        logger.info("3. 🎓 Обучите команду работе с YouTrack")
        logger.info("4. 📧 Настройте уведомления")
    else:
        logger.warning("⚠️ Миграция завершена с ошибками")
        logger.info("🔧 Проверьте логи и повторите проблемные этапы")

def run_specific_step(step_number):
    """Запуск конкретного этапа"""
    if step_number < 1 or step_number > len(MIGRATION_STEPS):
        logger.error(f"❌ Неверный номер этапа: {step_number}")
        logger.info(f"📋 Доступные этапы: 1-{len(MIGRATION_STEPS)}")
        return False

    step = MIGRATION_STEPS[step_number - 1]
    logger.info(f"🎯 Запуск этапа {step_number}: {step['name']}")

    return run_step(step)

def show_status():
    """Показать статус миграции"""
    logger.info("📊 СТАТУС МИГРАЦИИ")
    logger.info("-" * 40)

    for i, step in enumerate(MIGRATION_STEPS, 1):
        output_file = step['output_file']
        if Path(output_file).exists():
            # Читаем статистику из файла
            try:
                with open(output_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                if 'users' in data:
                    count = len(data['users'])
                    status = f"✅ Завершен ({count} пользователей)"
                elif 'projects' in data:
                    count = len(data['projects'])
                    status = f"✅ Завершен ({count} проектов)"
                elif 'issues' in data:
                    count = len(data['issues'])
                    status = f"✅ Завершен ({count} задач)"
                elif 'links_statistics' in data:
                    count = data['links_statistics'].get('links_created', 0)
                    status = f"✅ Завершен ({count} связей)"
                else:
                    status = "✅ Завершен"
            except:
                status = "✅ Завершен"
        else:
            status = "⏸️ Не выполнен"

        logger.info(f"{i}. {step['name']}: {status}")

def create_example_config():
    """Создание примера конфигурации"""
    config = {
        "yandex_tracker": {
            "token": "YOUR_YANDEX_TRACKER_TOKEN",
            "org_id": "YOUR_YANDEX_ORG_ID"
        },
        "youtrack": {
            "url": "https://your-company.myjetbrains.com",
            "token": "YOUR_YOUTRACK_TOKEN"
        },
        "migration_options": {
            "migrate_comments": True,
            "batch_size": 50,
            "rate_limit_delay": 0.5
        }
    }

    with open('migration_config.json', 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

    logger.info("📝 Создан пример конфигурации migration_config.json")
    logger.info("✏️ Отредактируйте файл, заполнив реальные значения токенов")

def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Мастер-скрипт миграции Yandex Tracker → YouTrack')
    parser.add_argument('--step', type=int, help='Запустить конкретный этап (1-4)')
    parser.add_argument('--resume', action='store_true', help='Возобновить миграцию (пропустить выполненные этапы)')
    parser.add_argument('--status', action='store_true', help='Показать статус миграции')
    parser.add_argument('--create-config', action='store_true', help='Создать пример конфигурации')

    args = parser.parse_args()

    # Логотип
    print("""
╔══════════════════════════════════════════════════════════════╗
║              МИГРАЦИЯ YANDEX TRACKER → YOUTRACK              ║
║                        Версия 2.0                           ║
╚══════════════════════════════════════════════════════════════╝
    """)

    if args.create_config:
        create_example_config()
        return

    if args.status:
        show_status()
        return

    # Проверяем предварительные условия
    if not check_prerequisites():
        logger.error("💥 Предварительные условия не выполнены")
        logger.info("🔧 Устраните проблемы и запустите скрипт повторно")
        sys.exit(1)

    try:
        if args.step:
            # Запуск конкретного этапа
            success = run_specific_step(args.step)
            sys.exit(0 if success else 1)
        else:
            # Запуск полной миграции
            run_full_migration(resume=args.resume)

    except KeyboardInterrupt:
        logger.info("\n🛑 Миграция прервана пользователем")
        logger.info("🔄 Для продолжения используйте --resume")
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()