#!/usr/bin/env python3
"""
   
"""

import requests
import json

def load_config():
    with open('migration_config.json', 'r') as f:
        return json.load(f)

def main():
    config = load_config()
    
    #     Yandex Tracker
    yandex_headers = {
        'Authorization': f"OAuth {config['yandex_tracker']['token']}",
        'X-Cloud-Org-Id': config['yandex_tracker']['org_id'],
        'Content-Type': 'application/json'
    }
    
    youtrack_headers = {
        'Authorization': f"Bearer {config['youtrack']['token']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }
    
    print("   ")
    print("=" * 50)
    
    #   Yandex Tracker
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
        if page > 5:  #   
            break
    
    #   YouTrack
    response = requests.get(
        f"{config['youtrack']['url']}/api/users",
        headers=youtrack_headers,
        params={'fields': 'id,login', '$top': 1000}
    )
    youtrack_users = response.json() if response.status_code == 200 else []
    
    #   
    yandex_logins = {user.get('login') for user in yandex_users if user.get('login')}
    youtrack_logins = {user.get('login') for user in youtrack_users if user.get('login')}
    
    #  
    only_in_yandex = yandex_logins - youtrack_logins
    only_in_youtrack = youtrack_logins - yandex_logins
    common = yandex_logins & youtrack_logins
    
    print(f"  :")
    print(f"   Yandex Tracker: {len(yandex_logins)}")
    print(f"   YouTrack: {len(youtrack_logins)}")
    print(f"  : {len(common)}")
    print(f"   Yandex ( ): {len(only_in_yandex)}")
    print(f"   YouTrack: {len(only_in_youtrack)}")
    
    if only_in_yandex:
        print(f"\n   :")
        for i, login in enumerate(sorted(only_in_yandex), 1):
            print(f"  {i}. {login}")
            if i >= 10:
                print(f"  ...   {len(only_in_yandex) - 10}")
                break
    else:
        print(f"\n    YANDEX TRACKER    YOUTRACK!")
        print(f"    !")
    
    #  
    try:
        with open('user_mapping.json', 'r') as f:
            mapping_data = json.load(f)
        mapping_count = len(mapping_data.get('users', {}))
        print(f"\n   : {mapping_count} ")
        
        if mapping_count < len(common):
            print(f"   !  {len(common)} ")
            print(f" :   ")
    except FileNotFoundError:
        print(f"\n    ")

if __name__ == "__main__":
    main()
