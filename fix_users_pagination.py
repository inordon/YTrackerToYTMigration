#!/usr/bin/env python3
"""
Исправление для получения всех пользователей через пагинацию
"""

import re

def create_paginated_get_users():
    """Создает метод get_users с пагинацией"""
    return '''    def get_users(self) -> List[Dict]:
        """Получение всех пользователей с пагинацией"""
        all_users = []
        page = 1
        per_page = 50  # Размер страницы (максимум что возвращает API)
        
        logger.info("Получение пользователей с пагинацией...")
        
        while True:
            try:
                params = {
                    'page': page,
                    'perPage': per_page
                }
                
                response = self.session.get(f"{self.base_url}/users", params=params)
                response.raise_for_status()
                users = response.json()
                
                if not users:
                    logger.info(f"  Страница {page}: пустая, завершаем")
                    break
                    
                all_users.extend(users)
                logger.info(f"  Страница {page}: получено {len(users)} пользователей")
                
                # Если получили меньше чем per_page, значит это последняя страница
                if len(users) < per_page:
                    logger.info(f"  Последняя страница достигнута")
                    break
                    
                page += 1
                
                # Пауза между запросами
                time.sleep(0.3)
                
            except requests.RequestException as e:
                logger.error(f"Ошибка получения пользователей, страница {page}: {e}")
                break
        
        logger.info(f"Всего получено {len(all_users)} пользователей из Yandex Tracker")
        return all_users'''

# Читаем файл
with open('step1_users_migration.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Находим и заменяем метод get_users
pattern = r'    def get_users\(self\) -> List\[Dict\]:.*?return \[\]'
replacement = create_paginated_get_users()

content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Сохраняем
with open('step1_users_migration.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Метод get_users обновлен с поддержкой пагинации")