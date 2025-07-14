#!/usr/bin/env python3
"""
  1  
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
            return data.get('projects', {})
    except FileNotFoundError:
        return {}

def save_project_mapping(project_mapping):
    mapping_data = {
        'projects': project_mapping,
        'timestamp': datetime.now().isoformat(),
        'step': 'projects_retry_completed'
    }
    
    with open('project_mapping.json', 'w', encoding='utf-8') as f:
        json.dump(mapping_data, f, ensure_ascii=False, indent=2)

def retry_failed_queues():
    config = load_config()
    project_mapping = load_project_mapping()
    
    headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    base_url = config['youtrack']['url'].rstrip('/')
    
    #     
    try:
        response = requests.get(f"{base_url}/api/users/me", headers=headers)
        current_user = response.json()
        leader_id = current_user.get('id')
        logger.info(f" : {current_user.get('login')} (ID: {leader_id})")
    except Exception as e:
        logger.error(f"    : {e}")
        return
    
    failed_queues = [{'self': 'https://api.tracker.yandex.net/v2/queues/MAPI', 'id': 22, 'key': 'MAPI', 'version': 5, 'name': 'MAPI Connector', 'lead': {'self': 'https://api.tracker.yandex.net/v2/users/1130000065011014', 'id': '1130000065011014', 'display': 'Борис Николаевич Моисеев', 'cloudUid': 'ajegplvhbclcgo0s7h2f', 'passportUid': 1130000065011014}, 'assignAuto': False, 'defaultType': {'self': 'https://api.tracker.yandex.net/v2/issuetypes/2', 'id': '2', 'key': 'task', 'display': 'Задача'}, 'defaultPriority': {'self': 'https://api.tracker.yandex.net/v2/priorities/3', 'id': '3', 'key': 'normal', 'display': 'Средний'}, 'denyVoting': False, 'denyConductorAutolink': False, 'denyTrackerAutolink': False, 'useComponentPermissionsIntersection': False, 'addSummoneeToIssueAccess': True, 'addCommentAuthorToIssueFollowers': True, 'workflowActionsStyle': 'hidden', 'useLastSignature': False}]
    
    logger.info(f"   {len(failed_queues)} ")
    
    success_count = 0
    error_count = 0
    
    for i, queue in enumerate(failed_queues, 1):
        queue_key = queue.get('key')
        queue_name = queue.get('name', queue_key)
        
        logger.info(f"[{i}/{len(failed_queues)}] : {queue_key} - {queue_name}")
        
        #    
        if queue_key in project_mapping:
            logger.info(f" {queue_key}   ")
            continue
            
        yt_project = {
            'name': queue_name,
            'shortName': queue_key,
            'description': queue.get('description', ''),
            'leader': {'id': leader_id}
        }
        
        try:
            response = requests.post(
                f"{base_url}/api/admin/projects",
                headers=headers,
                json=yt_project,
                params={'fields': 'id,shortName,name'}
            )
            
            if response.status_code in [200, 201]:
                created_project = response.json()
                project_id = created_project.get('id')
                project_mapping[queue_key] = project_id
                logger.info(f" : {queue_key} -> {project_id}")
                success_count += 1
                
            elif response.status_code == 409:
                logger.warning(f" {queue_key}  ")
                #   
                try:
                    search_response = requests.get(
                        f"{base_url}/api/admin/projects",
                        headers=headers,
                        params={'query': queue_key, 'fields': 'id,shortName'}
                    )
                    if search_response.status_code == 200:
                        projects = search_response.json()
                        for project in projects:
                            if project.get('shortName') == queue_key:
                                project_mapping[queue_key] = project.get('id')
                                logger.info(f"  : {queue_key} -> {project.get('id')}")
                                success_count += 1
                                break
                except:
                    pass
                    
            else:
                logger.error(f"  {queue_key}: {response.status_code} - {response.text}")
                error_count += 1
                
        except Exception as e:
            logger.error(f"  {queue_key}: {e}")
            error_count += 1
        
        time.sleep(1)
        
        #   5 
        if i % 5 == 0:
            save_project_mapping(project_mapping)
    
    save_project_mapping(project_mapping)
    
    logger.info(f"\n   :")
    logger.info(f" : {success_count}")
    logger.info(f" : {error_count}")
    logger.info(f"   : {len(project_mapping)}")

if __name__ == "__main__":
    retry_failed_queues()
