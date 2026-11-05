# Read each plan task's task.toml at its plan version (read-only GET) and keep what sizes the run: container CPUs, memory, disk,
# GPUs, network, timeouts and verifier mode. task.toml is untrusted data: parsed as TOML, never executed. Writes rollout_plan/task_infra.json.
import sys, os, csv, json, time, tomllib, concurrent.futures as cf
sys.path.insert(0, os.path.expanduser('~/.claude/skills'))
from _horizon_lib import client, spec
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
c = client.Client(); os.makedirs(f'{OUT}/toml', exist_ok=True)
plan = list(csv.DictReader(open(f'{OUT}/plan.csv')))
def get(r):
    f = f"{OUT}/toml/{r['task_id']}.toml"
    if not os.path.exists(f):
        p = {'path': 'task.toml'}
        if r['version']: p['version'] = r['version']
        spec.validate('GET', f"api/tasks/{r['task_id']}/files/content", p)
        for a in range(5):
            try: t = c._raw._make_request('GET', f"api/tasks/{r['task_id']}/files/content", params=p).text; break
            except Exception: time.sleep(3 * (a + 1))
        else: return r, None
        try:
            j = json.loads(t); t = j.get('content', t) if isinstance(j, dict) else t
        except Exception: pass
        open(f, 'w').write(t)
    try: d = tomllib.loads(open(f).read())
    except Exception as e: return r, {'error': str(e)[:200]}
    env, ag, ve = d.get('environment', {}), d.get('agent', {}), d.get('verifier', {}); venv = ve.get('environment', {}) or {}
    return r, {'task_id': r['task_id'], 'task': r['task'], 'version': r['version'], 'cpus': env.get('cpus', 1), 'memory_mb': env.get('memory_mb', 2048),
               'storage_mb': env.get('storage_mb'), 'gpus': env.get('gpus', 0), 'network': env.get('network_mode') or ag.get('network_mode'),
               'build_timeout_sec': env.get('build_timeout_sec', 600), 'agent_timeout_sec': ag.get('timeout_sec', 3600),
               'verifier_mode': ve.get('environment_mode', 'shared'), 'verifier_timeout_sec': ve.get('timeout_sec', 600),
               'verifier_cpus': venv.get('cpus'), 'verifier_memory_mb': venv.get('memory_mb')}
with cf.ThreadPoolExecutor(8) as ex: res = list(ex.map(get, plan))
bad = [r['task'] for r, o in res if not o or 'error' in o]
json.dump([o for _, o in res if o and 'error' not in o], open(f'{OUT}/task_infra.json', 'w'), indent=1)
print(len(res), 'read;', len(bad), 'failed', bad[:10])
