#!/usr/bin/env python3
"""
    
"""

import requests
import json
import logging
from typing import Dict, List

logging.basicConfig(level=logging.INFO)
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

def fix_project_statuses():
    config = load_config()
    project_mapping = load_project_mapping()
    
    if not project_mapping:
        print("     ")
        return
    
    youtrack_headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
    }
    
    base_url = config['youtrack']['url'].rstrip('/')
    
    print(f"    {len(project_mapping)} ")
    
    success_count = 0
    skip_count = 0
    
    for queue_key, project_id in project_mapping.items():
        print(f"\n  : {queue_key} (ID: {project_id})")
        
        # 1.     Yandex Tracker
        try:
            response = requests.get(
                f'https://api.tracker.yandex.net/v2/queues/{queue_key}/statuses',
                headers=yandex_headers
            )
            
            if response.status_code == 200:
                yandex_statuses = response.json()
                print(f"    {len(yandex_statuses)}   Yandex")
                
                # 2.    YouTrack
                created_count = 0
                for status in yandex_statuses:
                    status_name = status.get('name', status.get('key'))
                    
                    status_data = {
                        'name': status_name,
                        'description': status.get('description', ''),
                        'color': status.get('color', '#6B73FF')
                    }
                    
                    try:
                        create_response = requests.post(
                            f"{base_url}/api/admin/projects/{project_id}/statuses",
                            headers=youtrack_headers,
                            json=status_data,
                            params={'fields': 'id,name'}
                        )
                        
                        if create_response.status_code in [200, 201]:
                            created_count += 1
                        elif create_response.status_code == 409:
                            #   
                            pass
                        else:
                            print(f"         {status_name}: {create_response.status_code}")
                    except Exception as e:
                        print(f"        {status_name}: {e}")
                
                if created_count > 0:
                    print(f"    {created_count}  ")
                    success_count += 1
                else:
                    print(f"      ")
                    skip_count += 1
                    
            elif response.status_code == 403:
                print(f"        {queue_key}")
                #   
                basic_statuses = [
                    {'name': 'Open', 'color': '#6B73FF'},
                    {'name': 'In Progress', 'color': '#FFA500'}, 
                    {'name': 'Resolved', 'color': '#00AA00'},
                    {'name': 'Closed', 'color': '#808080'}
                ]
                
                created_count = 0
                for status in basic_statuses:
                    try:
                        create_response = requests.post(
                            f"{base_url}/api/admin/projects/{project_id}/statuses",
                            headers=youtrack_headers,
                            json=status,
                            params={'fields': 'id,name'}
                        )
                        
                        if create_response.status_code in [200, 201]:
                            created_count += 1
                    except:
                        pass
                
                print(f"    {created_count}  ")
                success_count += 1
                
            else:
                print(f"     : {response.status_code}")
                
        except Exception as e:
            print(f"   : {e}")
    
    print(f"\n :")
    print(f"  : {success_count}")
    print(f" : {skip_count}")

if __name__ == "__main__":
    fix_project_statuses()
