#!/usr/bin/env python3
"""
   Yandex Tracker  YouTrack  state bundles
"""

import requests
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def load_project_mapping():
    with open('project_mapping.json', 'r') as f:
        data = json.load(f)
        return data.get('projects', {})

def get_yandex_queue_statuses(config, queue_key):
    """    Yandex Tracker"""
    headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
    }
    
    try:
        response = requests.get(
            f'https://api.tracker.yandex.net/v2/queues/{queue_key}/statuses',
            headers=headers
        )
        
        if response.status_code == 200:
            return response.json()
        elif response.status_code == 403:
            logger.warning(f"     {queue_key}")
            return None
        else:
            logger.error(f"   {queue_key}: {response.status_code}")
            return None
    except Exception as e:
        logger.error(f"    {queue_key}: {e}")
        return None

def create_state_bundle(config, bundle_name, statuses):
    """  state bundle  YouTrack"""
    headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    base_url = config['youtrack']['url'].rstrip('/')
    
    #    bundle
    bundle_states = []
    for status in statuses:
        state_data = {
            'name': status.get('name', status.get('key')),
            'description': status.get('description', ''),
            'color': {
                'id': status.get('color', '#6B73FF').replace('#', '')
            }
        }
        bundle_states.append(state_data)
    
    bundle_data = {
        'name': bundle_name,
        'states': bundle_states
    }
    
    try:
        response = requests.post(
            f"{base_url}/api/admin/customFieldSettings/bundles/state",
            headers=headers,
            json=bundle_data,
            params={'fields': 'id,name,states(id,name)'}
        )
        
        if response.status_code in [200, 201]:
            created_bundle = response.json()
            logger.info(f"  state bundle: {bundle_name} (ID: {created_bundle.get('id')})")
            return created_bundle.get('id')
        else:
            logger.error(f"   bundle {bundle_name}: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        logger.error(f"    bundle: {e}")
        return None

def assign_bundle_to_project(config, project_id, bundle_id):
    """ state bundle """
    headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    base_url = config['youtrack']['url'].rstrip('/')
    
    #   State field
    try:
        #   
        response = requests.get(
            f"{base_url}/api/admin/customFieldSettings/customFields",
            headers=headers,
            params={'fields': 'id,name,fieldType', '$top': 100}
        )
        
        state_field_id = None
        if response.status_code == 200:
            fields = response.json()
            for field in fields:
                if field.get('name') == 'State' and 'state' in field.get('fieldType', '').lower():
                    state_field_id = field.get('id')
                    break
        
        if not state_field_id:
            logger.error(f"   State")
            return False
        
        #  bundle 
        custom_field_data = {
            'field': {'id': state_field_id},
            'bundle': {'id': bundle_id}
        }
        
        response = requests.post(
            f"{base_url}/api/admin/projects/{project_id}/customFields",
            headers=headers,
            json=custom_field_data,
            params={'fields': 'id,field(name),bundle(name)'}
        )
        
        if response.status_code in [200, 201]:
            logger.info(f" Bundle   {project_id}")
            return True
        elif response.status_code == 409:
            logger.info(f" Bundle    {project_id}")
            return True
        else:
            logger.error(f"   bundle: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        logger.error(f"    bundle: {e}")
        return False

def migrate_project_statuses():
    """   """
    config = load_config()
    project_mapping = load_project_mapping()
    
    if not project_mapping:
        logger.error("    ")
        return
    
    logger.info(f"     {len(project_mapping)} ")
    
    success_count = 0
    skip_count = 0
    error_count = 0
    
    for i, (queue_key, project_id) in enumerate(project_mapping.items(), 1):
        logger.info(f"\n[{i}/{len(project_mapping)}]  : {queue_key}")
        
        #    Yandex Tracker
        yandex_statuses = get_yandex_queue_statuses(config, queue_key)
        
        if not yandex_statuses:
            logger.warning(f"  {queue_key} -   ")
            skip_count += 1
            continue
        
        if len(yandex_statuses) == 0:
            logger.warning(f"  {queue_key} -  ")
            skip_count += 1
            continue
        
        logger.info(f"     {len(yandex_statuses)}   Yandex")
        
        #     bundle
        bundle_name = f"{queue_key} States"
        
        #  state bundle
        bundle_id = create_state_bundle(config, bundle_name, yandex_statuses)
        
        if bundle_id:
            #  bundle 
            if assign_bundle_to_project(config, project_id, bundle_id):
                success_count += 1
                logger.info(f"        {queue_key}")
            else:
                error_count += 1
                logger.error(f"         {queue_key}")
        else:
            error_count += 1
            logger.error(f"       bundle  {queue_key}")
        
        #   
        time.sleep(2)
        
        #    5 
        if i % 5 == 0:
            logger.info(f"     : {success_count} {skip_count} {error_count}")
    
    #  
    logger.info(f"\n   :")
    logger.info(f" : {success_count}")
    logger.info(f" : {skip_count}")
    logger.info(f" : {error_count}")
    
    if success_count > 0:
        logger.info(f"\n :")
        logger.info(f"1.    YouTrack: Administration  Custom Fields  State")
        logger.info(f"2.       ")
        logger.info(f"3.     !")

if __name__ == "__main__":
    migrate_project_statuses()
