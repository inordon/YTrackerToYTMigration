#!/usr/bin/env python3
"""
Исправление проблемы с ID лидера проекта
"""

import re

def fix_project_creation():
    # Читаем файл
    with open('step2_projects_migration.py', 'r', encoding='utf-8') as f:
        content = f.read()

    # Заменяем метод create_project на исправленную версию
    old_method = r'def create_project\(self, project_data: Dict, leader_id: str\) -> Optional\[str\]:.*?return None'

    new_method = '''def create_project(self, project_data: Dict, leader_hub_id: str) -> Optional[str]:
        """Создание проекта в YouTrack"""
        try:
            # Сначала получаем YouTrack ID пользователя по Hub ID
            youtrack_leader_id = self.get_youtrack_user_id_by_hub_id(leader_hub_id)
            if not youtrack_leader_id:
                logger.error(f"Не удалось найти YouTrack ID для Hub ID: {leader_hub_id}")
                return None
            
            yt_project = {
                'name': project_data.get('name'),
                'shortName': project_data.get('key'),
                'description': project_data.get('description', ''),
                'leader': {'id': youtrack_leader_id}
            }
            
            response = self.session.post(
                f"{self.base_url}/api/admin/projects",
                json=yt_project,
                params={'fields': 'id,shortName,name'}
            )
            
            if response.status_code in [200, 201]:
                created_project = response.json()
                logger.info(f"✓ Создан проект: {created_project.get('shortName')} - {created_project.get('name')}")
                return created_project.get('id')
            elif response.status_code == 409:
                logger.warning(f"⚠ Проект {yt_project['shortName']} уже существует")
                return self.get_project_by_shortname(yt_project['shortName'])
            else:
                logger.error(f"✗ Ошибка создания проекта {yt_project['shortName']}: {response.status_code} - {response.text}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"✗ Ошибка создания проекта: {e}")
            return None
    
    def get_youtrack_user_id_by_hub_id(self, hub_id: str) -> Optional[str]:
        """Получение YouTrack ID пользователя по Hub ID"""
        try:
            # Получаем пользователя из Hub API
            response = self.session.get(
                f"{self.base_url}/hub/api/rest/users/{hub_id}",
                params={'fields': 'id,login'}
            )
            
            if response.status_code == 200:
                hub_user = response.json()
                login = hub_user.get('login')
                
                if login:
                    # Теперь ищем этого пользователя в YouTrack API
                    yt_response = self.session.get(
                        f"{self.base_url}/api/users",
                        params={'query': login, 'fields': 'id,login', '$top': 10}
                    )
                    
                    if yt_response.status_code == 200:
                        yt_users = yt_response.json()
                        for user in yt_users:
                            if user.get('login') == login:
                                logger.debug(f"  Найден YouTrack ID для {login}: {user.get('id')}")
                                return user.get('id')
            
            logger.warning(f"Не удалось найти YouTrack ID для Hub ID: {hub_id}")
            return None
            
        except Exception as e:
            logger.error(f"Ошибка получения YouTrack ID: {e}")
            return None'''

    content = re.sub(old_method, new_method, content, flags=re.DOTALL)

    # Сохраняем
    with open('step2_projects_migration.py', 'w', encoding='utf-8') as f:
        f.write(content)

    print("✅ Метод create_project исправлен")

if __name__ == "__main__":
    fix_project_creation()_