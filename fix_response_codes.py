#!/usr/bin/env python3
"""
Исправление кодов ответа для YouTrack API
"""

import re

def fix_response_codes(filename):
    """Исправляет коды ответа в файле"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Исправляем проверку создания пользователя
    old_check = r'if response\.status_code == 201:'
    new_check = 'if response.status_code in [200, 201]:'
    content = re.sub(old_check, new_check, content)

    # Исправляем проверку создания проекта
    old_project_check = r'if response\.status_code == 200:'
    new_project_check = 'if response.status_code in [200, 201]:'
    # Применяем только к созданию проектов, не к другим запросам
    content = re.sub(
        r'(response = self\.session\.post\([^)]+\)\s+if response\.status_code) == 200:',
        r'\1 in [200, 201]:',
        content
    )

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Исправлены коды ответа в {filename}")

# Исправляем все файлы
files_to_fix = [
    'step1_users_migration.py',
    'step2_projects_migration.py',
    'step3_issues_migration.py'
]

for filename in files_to_fix:
    try:
        fix_response_codes(filename)
    except FileNotFoundError:
        print(f"⚠️ Файл {filename} не найден")
    except Exception as e:
        print(f"❌ Ошибка исправления {filename}: {e}")

print("\n🚀 Теперь можно запускать миграцию!")