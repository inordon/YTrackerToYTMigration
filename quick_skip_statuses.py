# quick_skip_statuses.py
import json

#   2    
with open('project_mapping.json', 'r') as f:
    data = json.load(f)

print(f"  2  ")
print(f"  : {len(data.get('projects', {}))}")
print(f"       YouTrack")
print(f"     3: python step3_issues_migration.py")
