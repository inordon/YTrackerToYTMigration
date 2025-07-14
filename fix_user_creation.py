#!/usr/bin/env python3
"""
Исправление создания пользователей с email аутентификацией
"""

def create_email_user_method():
    """Возвращает обновленный метод создания пользователя"""
    return '''
    def create_user(self, user_data: Dict) -> Optional[str]:
        """Создание пользователя в YouTrack с email аутентификацией"""
        try:
            # Подготавливаем данные пользователя
            login = user_data.get('login', user_data.get('id'))
            email = user_data.get('email')
            display_name = user_data.get('display', login)
            
            if not email:
                logger.warning(f"⚠ У пользователя {login} нет email, пропускаем")
                return None
            
            # Сначала создаем базовую запись пользователя через Hub API
            hub_url = f"{self.base_url}/hub/api/rest/users"
            
            hub_user = {
                'login': login,
                'name': display_name,
                'email': email,
                'isActive': True
            }
            
            response = self.session.post(
                hub_url,
                json=hub_user,
                params={'fields': 'id,login,name,email'}
            )
            
            if response.status_code in [200, 201]:
                created_user = response.json()
                user_id = created_user.get('id')
                logger.info(f"✓ Создана базовая запись: {login}")
                
                # Теперь добавляем email аутентификацию
                self._add_email_authentication(user_id, email, login)
                
                return user_id
                
            elif response.status_code == 409:
                logger.warning(f"⚠ Пользователь {login} уже существует")
                return self.get_user_by_login(login)
            else:
                logger.error(f"✗ Ошибка создания пользователя {login}: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"✗ Ошибка создания пользователя: {e}")
            return None
    
    def _add_email_authentication(self, user_id: str, email: str, login: str):
        """Добавление email аутентификации для пользователя"""
        try:
            # Создаем временный пароль
            temp_password = f"TempPass123_{login[-4:]}"
            
            # Добавляем email credential через Hub API
            credentials_url = f"{self.base_url}/hub/api/rest/users/{user_id}/credentials"
            
            credential_data = {
                'email': email,
                'password': temp_password,
                'changeOnLogin': True  # Заставит пользователя сменить пароль при первом входе
            }
            
            response = self.session.post(credentials_url, json=credential_data)
            
            if response.status_code in [200, 201]:
                logger.info(f"  📧 Email аутентификация добавлена для {login}")
                logger.info(f"  🔑 Временный пароль: {temp_password}")
            else:
                logger.warning(f"  ⚠ Не удалось добавить email аутентификацию: {response.status_code}")
                
        except Exception as e:
            logger.warning(f"  ⚠ Ошибка добавления email аутентификации: {e}")
    '''

# Читаем файл step1_users_migration.py
with open('step1_users_migration.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Заменяем метод create_user
import re

# Находим старый метод и заменяем его
old_method_pattern = r'def create_user\(self, user_data: Dict\) -> Optional\[str\]:.*?(?=def|\Z)'
new_method = create_email_user_method()

content = re.sub(old_method_pattern, new_method, content, flags=re.DOTALL)

# Сохраняем файл
with open('step1_users_migration.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("✅ Метод создания пользователей обновлен")
print("📧 Теперь пользователи будут создаваться с email аутентификацией")
print("🔑 Временные пароли будут записаны в лог")