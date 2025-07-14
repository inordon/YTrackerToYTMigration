#!/usr/bin/env python3
"""
   
"""

import requests
import json
import time
import logging
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migrate_missing_users.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def load_user_mapping():
    try:
        with open('user_mapping.json', 'r') as f:
            data = json.load(f)
            return data.get('users', {})
    except FileNotFoundError:
        return {}

def save_user_mapping(user_mapping):
    mapping_data = {
        'users': user_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'users_missing_migrated'
    }
    
    with open('user_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

def get_missing_users_list():
    """  ,    YouTrack"""
    config = load_config()
    
    #     
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
    }
    
    youtrack_headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    # Yandex 
    yandex_users = []
    page = 1
    while True:
        response = requests.get(
            f'https://api.tracker.yandex.net/v2/users?page={page}&perPage=50',
            headers=yandex_headers
        )
        users = response.json()
        if not users:
            break
        yandex_users.extend(users)
        page += 1
        if page > 5:
            break
    
    # YouTrack 
    response = requests.get(
        f"{config['youtrack']['url']}/api/users",
        headers=youtrack_headers,
        params={'fields': 'login', '$top': 1000}
    )
    youtrack_users = response.json() if response.status_code == 200 else []
    youtrack_logins = {user.get('login') for user in youtrack_users}
    
    #  
    missing_users = []
    for user in yandex_users:
        if user.get('login') not in youtrack_logins:
            missing_users.append(user)
    
    return missing_users

def migrate_missing_users():
    config = load_config()
    user_mapping = load_user_mapping()
    
    missing_users = get_missing_users_list()
    
    logger.info(f"  {len(missing_users)}   ")
    
    if not missing_users:
        logger.info("    !")
        return
    
    headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    success_count = 0
    error_count = 0
    
    for i, user in enumerate(missing_users, 1):
        login = user.get('login')
        yandex_id = user.get('id')
        
        logger.info(f"[{i}/{len(missing_users)}] : {login}")
        
        yt_user = {
            'login': login,
            'name': user.get('display', login),
            'isActive': True
        }
        
        if user.get('email'):
            yt_user['email'] = user.get('email')
        
        try:
            response = requests.post(
                f"{config['youtrack']['url']}/hub/api/rest/users",
                headers=headers,
                json=yt_user,
                params={'fields': 'id,login,name'}
            )
            
            if response.status_code in [200, 201]:
                created_user = response.json()
                youtrack_id = created_user.get('id')
                user_mapping[yandex_id] = youtrack_id
                logger.info(f" : {login} -> {youtrack_id}")
                success_count += 1
            elif response.status_code == 409:
                logger.warning(f"  : {login}")
            else:
                logger.error(f"  {login}: {response.status_code} - {response.text}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"  {login}: {e}")
            error_count += 1
        
        time.sleep(1)
        
        #   10 
        if i % 10 == 0:
            save_user_mapping(user_mapping)
            logger.info(f"  ")
    
    save_user_mapping(user_mapping)
    
    logger.info(f"\n  :")
    logger.info(f" : {success_count}")
    logger.info(f" : {error_count}")
    logger.info(f"   : {len(user_mapping)}")

if __name__ == "__main__":
    migrate_missing_users()
