#!/usr/bin/env python3
"""
Исправление обработки формата Hub API
"""

import re

def fix_hub_api_handling():
    """Исправляет обработку ответов Hub API"""

    # Читаем файл
    with open('step1_users_migration.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Исправляем метод find_existing_user_id
    old_hub_search = r'''response = self\.session\.get\(
                f"\{self\.base_url\}/hub/api/rest/users",
                params=\{'query': login, 'fields': 'id,login', '\$top': 100\}
            \)
            if response\.status_code == 200:
                users = response\.json\(\)
                logger\.info\(f"      Hub API: найдено \{len\(users\)\} пользователей"\)
                for user in users:
                    if user\.get\('login'\) == login:
                        logger\.info\(f"      ✅ Найден через Hub: \{login\} -> \{user\.get\('id'\)\}"\)
                        return user\.get\('id'\)'''

    new_hub_search = '''response = self.session.get(
                f"{self.base_url}/hub/api/rest/users",
                params={'query': login, 'fields': 'id,login', '$top': 100}
            )
            if response.status_code == 200:
                hub_response = response.json()
                # Hub API возвращает объект с полем 'users'
                if isinstance(hub_response, dict) and 'users' in hub_response:
                    users = hub_response['users']
                    logger.debug(f"      Hub API: найдено {len(users)} пользователей")
                    for user in users:
                        if isinstance(user, dict) and user.get('login') == login:
                            logger.debug(f"      ✅ Найден через Hub: {login} -> {user.get('id')}")
                            return user.get('id')
                else:
                    logger.debug(f"      Hub API: неожиданный формат ответа")'''

    content = re.sub(old_hub_search, new_hub_search, content, flags=re.DOTALL)

    # Сохраняем
    with open('step1_users_migration.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Исправлена обработка Hub API")

if __name__ == "__main__":
    fix_hub_api_handling()