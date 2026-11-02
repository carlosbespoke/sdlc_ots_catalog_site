import sys, os, json, collections
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client
c = client.Client()
items, total = c.paginate('api/tasks', 'tasks', {'projectId': 'a6bb0656-a161-44ed-9304-21c5f4690106', 'status': 'ready-for-client'})
json.dump(items, open(sys.argv[1], 'w'))
print('tasks', len(items), 'reported total', total)
print('status check', collections.Counter(t.get('status') for t in items))
print('formats', collections.Counter(t.get('format') for t in items))
for b, n in collections.Counter(t.get('batch_name') for t in items).most_common(): print(f'{n:5d}  {b}')
