#!/usr/bin/env python3
"""
   
"""

import requests
import json

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def load_project_mapping():
    try:
        with open('project_mapping.json', 'r') as f:
            data = json.load(f)
            return data.get('projects', {})
    except FileNotFoundError:
        return {}

def check_migration_status():
    config = load_config()
    project_mapping = load_project_mapping()
    
    #     Yandex Tracker
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
    }
    
    youtrack_headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    print("   ")
    print("=" * 50)
    
    #    Yandex
    try:
        response = requests.get(
            'https://api.tracker.yandex.net/v2/queues',
            headers=yandex_headers
        )
        yandex_queues = response.json() if response.status_code == 200 else []
    except Exception as e:
        print(f"    Yandex: {e}")
        return
    
    #    YouTrack
    try:
        response = requests.get(
            f"{config['youtrack']['url']}/api/admin/projects",
            headers=youtrack_headers,
            params={'fields': 'id,shortName,name', '$top': 100}
        )
        youtrack_projects = response.json() if response.status_code == 200 else []
    except Exception as e:
        print(f"    YouTrack: {e}")
        youtrack_projects = []
    
    # 
    migrated_queues = set(project_mapping.keys())
    all_yandex_queues = {q.get('key') for q in yandex_queues if q.get('key')}
    youtrack_shortnames = {p.get('shortName') for p in youtrack_projects if p.get('shortName')}
    
    not_migrated = all_yandex_queues - migrated_queues
    
    print(f" :")
    print(f"    Yandex: {len(all_yandex_queues)}")
    print(f"   : {len(migrated_queues)}")
    print(f"  : {len(not_migrated)}")
    print(f"   YouTrack: {len(youtrack_shortnames)}")
    
    if not_migrated:
        print(f"\n   :")
        for i, queue_key in enumerate(sorted(not_migrated), 1):
            #   
            queue_details = next((q for q in yandex_queues if q.get('key') == queue_key), {})
            queue_name = queue_details.get('name', ' ')
            print(f"  {i}. {queue_key} - {queue_name}")
            
            if i >= 10:
                print(f"  ...   {len(not_migrated) - 10}")
                break
    
    #   
    print(f"\n  :")
    
    #  
    try:
        with open('step2_projects.log', 'r') as f:
            log_content = f.read()
        
        error_count = log_content.count('ERROR')
        warning_count = log_content.count('WARNING')
        
        print(f"   :")
        print(f"   : {error_count}")
        print(f"    : {warning_count}")
        
        #   
        if 'Invalid structure of entity id' in log_content:
            print(f"     ID  ")
        
        if ' ' in log_content or 'already exists' in log_content:
            existing_count = log_content.count(' ')
            print(f"      : {existing_count}")
            
    except FileNotFoundError:
        print(f"    ")
    
    return not_migrated, yandex_queues

def create_retry_script(failed_queues, all_queues):
    """      """
    
    failed_queue_details = []
    for queue in all_queues:
        if queue.get('key') in failed_queues:
            failed_queue_details.append(queue)
    
    retry_script = f'''#!/usr/bin/env python3
"""
  {len(failed_queues)}  
"""

import requests
import json
import time
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def load_project_mapping():
    try:
        with open('project_mapping.json', 'r') as f:
            data = json.load(f)
            return data.get('projects', {{}})
    except FileNotFoundError:
        return {{}}

def save_project_mapping(project_mapping):
    mapping_data = {{
        'projects': project_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'projects_retry_completed'
    }}
    
    with open('project_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

def retry_failed_queues():
    config = load_config()
    project_mapping = load_project_mapping()
    
    headers = {{
        'Authorization': f"Bearer {{config['youtrack']['token']}}",
        'Content-Type': 'application/json'
    }}
    
    base_url = config['youtrack']['url'].rstrip('/')
    
    #     
    try:
        response = requests.get(f"{{base_url}}/api/users/me", headers=headers)
        current_user = response.json()
        leader_id = current_user.get('id')
        logger.info(f" : {{current_user.get('login')}} (ID: {{leader_id}})")
    except Exception as e:
        logger.error(f"    : {{e}}")
        return
    
    failed_queues = {failed_queue_details}
    
    logger.info(f"   {{len(failed_queues)}} ")
    
    success_count = 0
    error_count = 0
    
    for i, queue in enumerate(failed_queues, 1):
        queue_key = queue.get('key')
        queue_name = queue.get('name', queue_key)
        
        logger.info(f"[{{i}}/{{len(failed_queues)}}] : {{queue_key}} - {{queue_name}}")
        
        #    
        if queue_key in project_mapping:
            logger.info(f" {{queue_key}}   ")
            continue
            
        yt_project = {{
            'name': queue_name,
            'shortName': queue_key,
            'description': queue.get('description', ''),
            'leader': {{'id': leader_id}}
        }}
        
        try:
            response = requests.post(
                f"{{base_url}}/api/admin/projects",
                headers=headers,
                json=yt_project,
                params={{'fields': 'id,shortName,name'}}
            )
            
            if response.status_code in [200, 201]:
                created_project = response.json()
                project_id = created_project.get('id')
                project_mapping[queue_key] = project_id
                logger.info(f" : {{queue_key}} -> {{project_id}}")
                success_count += 1
                
            elif response.status_code == 409:
                logger.warning(f" {{queue_key}}  ")
                #   
                try:
                    search_response = requests.get(
                        f"{{base_url}}/api/admin/projects",
                        headers=headers,
                        params={{'query': queue_key, 'fields': 'id,shortName'}}
                    )
                    if search_response.status_code == 200:
                        projects = search_response.json()
                        for project in projects:
                            if project.get('shortName') == queue_key:
                                project_mapping[queue_key] = project.get('id')
                                logger.info(f"  : {{queue_key}} -> {{project.get('id')}}")
                                success_count += 1
                                break
                except:
                    pass
                    
            else:
                logger.error(f"  {{queue_key}}: {{response.status_code}} - {{response.text}}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"  {{queue_key}}: {{e}}")
            error_count += 1
        
        time.sleep(1)
        
        #   5 
        if i % 5 == 0:
            save_project_mapping(project_mapping)
    
    save_project_mapping(project_mapping)
    
    logger.info(f"\\n   :")
    logger.info(f" : {{success_count}}")
    logger.info(f" : {{error_count}}")
    logger.info(f"   : {{len(project_mapping)}}")

if __name__ == "__main__":
    retry_failed_queues()
'''
    
    with open('retry_queue_migration.py', 'w', encoding='utf-8') as f:
        f.write(retry_script)
    
    print(f"\n    : retry_queue_migration.py")

def main():
    failed_queues, all_queues = check_migration_status()
    
    if failed_queues:
        print(f"\n :")
        print(f"1.     ")
        print(f"2.      ")
        print(f"3.     ")
        
        create_retry_script(failed_queues, all_queues)
        
        print(f"\n     :")
        print(f"   python retry_queue_migration.py")
    else:
        print(f"\n    !")

if __name__ == "__main__":
    main()
