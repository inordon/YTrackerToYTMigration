#!/usr/bin/env python3
"""
Исправление для поддержки облачных организаций Yandex Tracker
"""

import re
import json

def fix_file(filename):
    """Исправляет файл для поддержки облачных организаций"""
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    # Исправляем __init__ метод YandexTrackerClient
    old_init = r'def __init__\(self, token: str, org_id: str\):'
    new_init = 'def __init__(self, token: str, org_id: str, is_cloud_org: bool = False):'
    content = re.sub(old_init, new_init, content)

    # Исправляем заголовки
    old_headers = r"'X-Org-ID': org_id,"
    new_headers = """# Выбираем правильный заголовок для организации
        org_header = 'X-Cloud-Org-Id' if is_cloud_org else 'X-Org-ID'
        self.session.headers.update({
            'Authorization': f'OAuth {token}',
            org_header: org_id,
            'Content-Type': 'application/json'
        })"""

    # Заменяем весь блок headers
    content = re.sub(
        r'self\.session\.headers\.update\(\{\s*\'Authorization\': f\'OAuth \{token\}\',\s*\'X-Org-ID\': org_id,\s*\'Content-Type\': \'application/json\'\s*\}\)',
        new_headers,
        content
    )

    # Исправляем создание клиента в main()
    old_client_creation = r'yandex_client = YandexTrackerClient\(\s*config\[\'yandex_tracker\'\]\[\'token\'\],\s*config\[\'yandex_tracker\'\]\[\'org_id\'\]\s*\)'
    new_client_creation = '''is_cloud_org = config['yandex_tracker'].get('is_cloud_org', False)
    
    yandex_client = YandexTrackerClient(
        config['yandex_tracker']['token'],
        config['yandex_tracker']['org_id'],
        is_cloud_org
    )'''

    content = re.sub(old_client_creation, new_client_creation, content)

    # Сохраняем исправленный файл
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

    print(f"✅ Файл {filename} исправлен для облачных организаций")

# Исправляем все файлы этапов
files_to_fix = [
    'step1_users_migration.py',
    'step2_projects_migration.py',
    'step3_issues_migration.py',
    'step4_links_migration.py'
]

print("🔧 Исправление файлов для поддержки облачных организаций...")

for filename in files_to_fix:
    try:
        fix_file(filename)
    except FileNotFoundError:
        print(f"⚠️ Файл {filename} не найден, пропускаем")
    except Exception as e:
        print(f"❌ Ошибка исправления {filename}: {e}")

# Обновляем конфигурацию
config = {
    "yandex_tracker": {
        "token": "y0__xCH-cWlqveAAhjTuDUggYrdqhL8M_i7Evqh2oZPuiY6BLv5n6Uh-g",
        "org_id": "bpfdnoim0ts5emqkj1u4",
        "is_cloud_org": True
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

print("✅ Конфигурация обновлена")
print("\n🚀 Теперь можно запускать:")
print("python step1_users_migration.py")