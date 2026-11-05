# Per-run settings for the Argon rollout (rollout_plan/plan.csv x task_infra.json), the same rules as the 4 Nov rollout
# (../ots_all/bin/rollout_settings.py): Terminus V2 (typhoon), 1,200 turns, 32k output tokens, effort tier 3 (high for Argon),
# Cloud Batch with the smallest VM whose CPUs cover the largest container and whose memory covers the agent container plus a
# separate verifier container. Timeouts and network are the task's own. Writes rollout_plan/runs.csv.
import csv, json, os, collections
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
MACHINES = [(2, 4096), (4, 8192), (8, 16384), (16, 32768)]
USD_VCPU_H, USD_GB_H = 0.021811, 0.002923  # GCE e2 custom list price, us-central1 (estimate)
INF = {o['task_id']: o for o in json.load(open(f'{OUT}/task_infra.json'))}
def machine(o):
    sep = o['verifier_mode'] == 'separate'
    vc = (o['verifier_cpus'] or o['cpus']) if sep else 0
    vm = (o['verifier_memory_mb'] or o['memory_mb']) if sep else 0
    cpu, mem = max(o['cpus'], vc), o['memory_mb'] + vm
    c, m = next((c, m) for c, m in MACHINES if c >= cpu and m >= mem)
    return f'e2-custom-{c}-{m}', c, m
rows = []
for r in csv.DictReader(open(f'{OUT}/plan.csv')):
    o = INF[r['task_id']]; mt, c, m = machine(o)
    wall = float(o['build_timeout_sec']) + float(o['agent_timeout_sec']) + float(o['verifier_timeout_sec'])
    rows.append({**r, 'model': 'Gemini 4 Argon', 'codename': 'umbra', 'agent_type': 'typhoon', 'max_turns': 1200, 'max_tokens': 32000, 'effort_tier': 3,
                 'sandbox_backend': 'cloud_batch', 'machine_type': mt, 'agent_cpus': o['cpus'], 'agent_memory_mb': o['memory_mb'],
                 'verifier_mode': o['verifier_mode'], 'network': o['network'] or '', 'agent_timeout_sec': int(float(o['agent_timeout_sec'])),
                 'max_wall_hours': round(wall / 3600, 2), 'vm_usd_ceiling_per_run': round(wall / 3600 * (c * USD_VCPU_H + m / 1024 * USD_GB_H), 2)})
with open(f'{OUT}/runs.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
print(len(rows), dict(collections.Counter(r['machine_type'] for r in rows)), 'VM ceiling per wave $', round(sum(r['vm_usd_ceiling_per_run'] for r in rows)))
