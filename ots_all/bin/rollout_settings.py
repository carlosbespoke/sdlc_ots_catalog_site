# Per-run settings for the rollout plan, read from each task's own task.toml (rollout_plan/task_infra.json, parsed from the
# tasks pulled at the plan version) and from Horizon's evaluation config. Writes rollout_plan/runs.csv (one row per task and model).
#
# Rules
#   effort: the model's top effort tier (tier 3). Horizon maps it per model: GLM 5.3 Flash -> max, the two Gemini models -> high
#           (they offer no max).
#   backend: Cloud Batch, named explicitly. All the plan tasks install ca-certificates in their Dockerfile, which the tensorlake
#           backend can refuse (HRZN-835 item 19), and only Cloud Batch takes a machine type.
#   machine: the smallest allowed VM whose CPUs cover the largest container (Docker refuses a container asking for more CPUs than
#           the host has, the pre-first-turn failure seen in the pilot) and whose memory covers the agent container plus a
#           separate verifier container (the verifier's own [verifier.environment] when set, else the [environment] size; nothing
#           extra when the verifier shares the agent container).
#   timeouts, network, disk: as the task sets them. The agent timeout is [agent] timeout_sec; it is not a submit option.
import csv, json, os
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__))); OUT = f'{H}/rollout_plan'
MACHINES = [(2, 4096), (4, 8192), (8, 16384), (16, 32768)]  # api/evaluations/config limits.machine_types
EFFORT = {'steppe': 'max', 'kittiwake': 'high', 'umbra': 'high'}  # tier 3 per model, api/evaluations/config
# GCE e2 custom list price, us-central1 (estimate; Horizon does not report VM cost per run)
USD_VCPU_H, USD_GB_H = 0.021811, 0.002923
INF = {o['task_id']: o for o in json.load(open(f'{OUT}/task_infra.json'))}
def machine(o):
    sep = o['verifier_mode'] == 'separate'
    vc = (o['verifier_cpus'] or o['cpus']) if sep else 0
    vm = (o['verifier_memory_mb'] or o['memory_mb']) if sep else 0
    cpu, mem = max(o['cpus'], vc), o['memory_mb'] + vm
    c, m = next((c, m) for c, m in MACHINES if c >= cpu and m >= mem)
    return f'e2-custom-{c}-{m}', c, m, cpu, mem
rows = []
for r in csv.DictReader(open(f'{OUT}/plan.csv')):
    o = INF[r['task_id']]; mt, c, m, need_c, need_m = machine(o)
    wall = float(o['build_timeout_sec']) + float(o['agent_timeout_sec']) + float(o['verifier_timeout_sec'])
    rows.append({'catalog': r['catalog'], 'model': r['model'], 'codename': r['codename'], 'task_id': r['task_id'], 'task': r['task'],
                 'version': r['version'], 'agent_type': 'typhoon', 'max_turns': 1200, 'max_tokens': 32000, 'effort_tier': 3, 'effort': EFFORT[r['codename']],
                 'sandbox_backend': 'cloud_batch', 'machine_type': mt,
                 'agent_cpus': o['cpus'], 'agent_memory_mb': o['memory_mb'], 'storage_mb': o['storage_mb'], 'verifier_mode': o['verifier_mode'],
                 'verifier_cpus': o['verifier_cpus'] or '', 'verifier_memory_mb': o['verifier_memory_mb'] or '', 'needs_cpus': need_c, 'needs_memory_mb': need_m,
                 'network': o['network'], 'gpus': o['gpus'], 'build_timeout_sec': int(float(o['build_timeout_sec'])),
                 'agent_timeout_sec': int(float(o['agent_timeout_sec'])), 'verifier_timeout_sec': int(float(o['verifier_timeout_sec'])),
                 'max_wall_hours': round(wall / 3600, 2), 'vm_usd_per_hour': round(c * USD_VCPU_H + m / 1024 * USD_GB_H, 3),
                 'vm_usd_ceiling_per_run': round(wall / 3600 * (c * USD_VCPU_H + m / 1024 * USD_GB_H), 2)})
with open(f'{OUT}/runs.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0])); w.writeheader(); w.writerows(rows)
import collections
print(len(rows), 'task-model rows,', len({r['task_id'] for r in rows}), 'tasks')
for k in ('machine_type', 'effort', 'agent_timeout_sec', 'verifier_mode'):
    print(k, dict(collections.Counter(r[k] for r in rows)))
print(collections.Counter((r['catalog'], r['model'], r['machine_type'], r['agent_timeout_sec']) for r in rows))
