#!/usr/bin/env python3
"""
Исправление логики определения существующих пользователей
"""

import re

def create_fixed_user_methods():
    """Создает исправленные методы для работы с пользователями"""
    return '''    def create_user(self, user_data: Dict) -> Optional[str]:
        """Создание пользователя в YouTrack через Hub API"""
        try:
            login = user_data.get('login', user_data.get('id'))
            email = user_data.get('email')
            display_name = user_data.get('display', login)
            
            logger.debug(f"    Попытка создания пользователя: {login}")
            
            # Подготавливаем данные пользователя
            yt_user = {
                'login': login,
                'name': display_name,
                'isActive': True
            }
            
            # Добавляем email если есть
            if email:
                yt_user['email'] = email
            
            # Пытаемся создать пользователя
            hub_url = f"{self.base_url}/hub/api/rest/users"
            
            response = self.session.post(
                hub_url,
                json=yt_user,
                params={'fields': 'id,login,name,email'}
            )
            
            if response.status_code in [200, 201]:
                created_user = response.json()
                logger.info(f"✓ Создан пользователь: {login}")
                return created_user.get('id')
                
            elif response.status_code == 409:
                # Пользователь уже существует, пытаемся найти его ID
                logger.debug(f"    Пользователь {login} уже существует, ищем ID...")
                existing_id = self.find_existing_user_id(login)
                if existing_id:
                    logger.info(f"⏭ Пользователь {login} уже существует (ID: {existing_id})")
                    return existing_id
                else:
                    logger.warning(f"⚠ Пользователь {login} существует, но не найден его ID")
                    return None
                    
            else:
                logger.error(f"✗ Ошибка создания пользователя {login}: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"✗ Ошибка создания пользователя: {e}")
            return None
    
    def find_existing_user_id(self, login: str) -> Optional[str]:
        """Поиск ID существующего пользователя"""
        try:
            # Сначала пробуем через обычный API
            response = self.session.get(
                f"{self.base_url}/api/users",
                params={
                    'query': login,
                    'fields': 'id,login',
                    '$top': 100
                }
            )
            
            if response.status_code == 200:
                users = response.json()
                for user in users:
                    if user.get('login') == login:
                        logger.debug(f"    Найден через API: {login} -> {user.get('id')}")
                        return user.get('id')
            
            # Если не найден через API, пробуем через Hub API
            response = self.session.get(
                f"{self.base_url}/hub/api/rest/users",
                params={
                    'query': login,
                    'fields': 'id,login',
                    '$top': 100
                }
            )
            
            if response.status_code == 200:
                users = response.json()
                for user in users:
                    if user.get('login') == login:
                        logger.debug(f"    Найден через Hub API: {login} -> {user.get('id')}")
                        return user.get('id')
            
            logger.debug(f"    Пользователь {login} не найден ни через API, ни через Hub API")
            return None
            
        except requests.RequestException as e:
            logger.error(f"Ошибка поиска пользователя {login}: {e}")
            return None
    
    def get_user_by_login(self, login: str) -> Optional[str]:
        """Получение ID пользователя по логину (оставлено для совместимости)"""
        return self.find_existing_user_id(login)'''

# Читаем файл
with open('step1_users_migration.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем методы create_user и get_user_by_login
pattern1 = r'    def create_user\(self, user_data: Dict\) -> Optional\[str\]:.*?return None'
pattern2 = r'    def get_user_by_login\(self, login: str\) -> Optional\[str\]:.*?return None'

replacement = create_fixed_user_methods()

# Заменяем оба метода
content = re.sub(pattern1, '', content, flags=re.DOTALL)
content = re.sub(pattern2, '', content, flags=re.DOTALL)

# Добавляем новые методы после __init__
init_pattern = r'(\s+)(def __init__\(self.*?\n\s+)(\n\s+def)'
content = re.sub(init_pattern, r'\1\2' + replacement + r'\3', content, flags=re.DOTALL)

# Сохраняем
with open('step1_users_migration.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Методы создания и поиска пользователей исправлены")
print("🔍 Теперь скрипт будет корректно определять существующих пользователей")