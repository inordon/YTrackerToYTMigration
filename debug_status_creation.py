#!/usr/bin/env python3
"""
   
"""

import requests
import json

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def load_project_mapping():
    with open('project_mapping.json', 'r') as f:
        data = json.load(f)
        return data.get('projects', {})

def debug_status_creation():
    config = load_config()
    project_mapping = load_project_mapping()
    
    base_url = config['youtrack']['url'].rstrip('/')
    headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json'
    }
    
    #     
    first_project = list(project_mapping.items())[0]
    queue_key, project_id = first_project
    
    print(f"   ")
    print(f" : {queue_key} (ID: {project_id})")
    print("=" * 50)
    
    # 1. ,   
    print("1.    :")
    try:
        response = requests.get(
            f"{base_url}/api/admin/projects/{project_id}",
            headers=headers,
            params={'fields': 'id,shortName,name'}
        )
        print(f"   : {response.status_code}")
        if response.status_code == 200:
            project = response.json()
            print(f"     : {project.get('shortName')} - {project.get('name')}")
        else:
            print(f"      : {response.text}")
            return
    except Exception as e:
        print(f"    : {e}")
        return
    
    # 2.    
    print("\n2.    :")
    try:
        response = requests.get(
            f"{base_url}/api/admin/projects/{project_id}/statuses",
            headers=headers,
            params={'fields': 'id,name,color'}
        )
        print(f"   : {response.status_code}")
        if response.status_code == 200:
            statuses = response.json()
            print(f"     {len(statuses)} :")
            for status in statuses[:5]:  #   5
                print(f"     - {status.get('name')} (ID: {status.get('id')})")
        else:
            print(f"      : {response.text}")
    except Exception as e:
        print(f"    : {e}")
    
    # 3.      
    print("\n3.    :")
    
    test_status = {
        'name': 'Test Status ' + str(int(time.time())),
        'description': ' ',
        'color': '#FF0000'
    }
    
    #  1:  API admin/projects
    print(f"    1: POST /api/admin/projects/{project_id}/statuses")
    try:
        response = requests.post(
            f"{base_url}/api/admin/projects/{project_id}/statuses",
            headers=headers,
            json=test_status,
            params={'fields': 'id,name'}
        )
        print(f"     : {response.status_code}")
        print(f"     : {response.text}")
    except Exception as e:
        print(f"      : {e}")
    
    #  2:  API admin/customFieldSettings/statuses
    print(f"\n    2: POST /api/admin/customFieldSettings/statuses")
    try:
        response = requests.post(
            f"{base_url}/api/admin/customFieldSettings/statuses",
            headers=headers,
            json=test_status,
            params={'fields': 'id,name'}
        )
        print(f"     : {response.status_code}")
        print(f"     : {response.text}")
    except Exception as e:
        print(f"      : {e}")
    
    #  3:  API admin/projects/customFields
    print(f"\n    3:   API endpoints")
    try:
        #      
        response = requests.get(
            f"{base_url}/api/admin/projects/{project_id}/customFields",
            headers=headers,
            params={'fields': 'field(name)', '$top': 5}
        )
        print(f"     Custom Fields : {response.status_code}")
        if response.status_code == 200:
            print(f"      Custom Fields ")
        
        #   bundle 
        response = requests.get(
            f"{base_url}/api/admin/customFieldSettings/bundles/state",
            headers=headers,
            params={'fields': 'id,name', '$top': 5}
        )
        print(f"     State Bundles : {response.status_code}")
        if response.status_code == 200:
            bundles = response.json()
            print(f"       {len(bundles)} state bundles")
            for bundle in bundles[:3]:
                print(f"       - {bundle.get('name')} (ID: {bundle.get('id')})")
        
    except Exception as e:
        print(f"      : {e}")

if __name__ == "__main__":
    import time
    debug_status_creation()
