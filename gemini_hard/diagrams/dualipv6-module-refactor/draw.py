import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1200)
D.title('v6mesh: split a flat dual IPv6 Kubernetes stack into four modules',
        'Two IPv6 Kubernetes clusters live in one flat Terraform root with count-indexed lists and hard-coded names. The agent splits it into network, bootstrap, platform and observability modules keyed by availability zone and worker pool, and the plan against production must contain nothing but moves.')
top = 104
def mono(x, y, s, color=INK, size=10.5, bold=False):
    D._t(x, y, s, size, bold, color, mono=True)
# left: production inputs the agent cannot change
h = D.store('st', 36, top + 52, 268, 'terraform.tfstate', 'copy of production: 85 resource blocks, 167 instances; per-AZ and per-pool ones count-indexed [0] [1] [2]', 'terraform')
y = top + 52 + h + 16
h = D.box('pm', 36, y, 268, 'Provider mirror', 'terraform init works offline; AWS provider 5.100.0, Terraform 1.16.4', 'muted'); y += h + 14
h = D.box('fx', 36, y, 268, 'providers.tf and policies/', 'guardrail policies, kept byte for byte', 'muted'); y += h + 14
h = D.box('ci', 36, y, 268, 'scripts/ci-plan.sh', 'what CI runs: terraform plan -refresh=false against the state, then the policies', 'svc'); lb = y + h
# middle: the configuration the agent rewrites
h = D.box('fl', 356, top + 52, 378, 'Today: one flat root module', 'network.tf 224 lines, bootstrap.tf 104, platform.tf 517, observability.tf 76; lists in locals.tf, names and tags hard-coded', 'muted')
ry = top + 52 + h + 30
D.arrow([(545, top + 52 + h + 2), (545, ry - 2)], 'refactor', kind='new', lpos=.5, loff=(36, 4))
h = D.box('rt', 356, ry, 378, 'Root module', 'calls 4 modules, declares no resources; 12 variables (project, environment, availability_zones, worker_pools, tags, ...); 11 outputs', 'new', tag='NEW')
my = ry + h + 18
mods = [('network', 'VPCs, gateways, subnets, NAT64 gateways, routes', 'AZ'),
        ('bootstrap', 'KMS, S3 bucket and objects, DynamoDB, SSM catalogs', 'pool'),
        ('platform', 'IAM, security groups, logs, launch templates, ASGs', 'pool'),
        ('observability', 'SNS, SQS, per-pool capacity alarms', 'pool')]
for i, (n, b, k) in enumerate(mods):
    x = 356 + (i % 2) * 192; yy = my + (i // 2) * 92
    D.box('m' + n, x, yy, 186, 'module "' + n + '"', b, 'svc', h=80)
mid_bot = my + 2 * 92 - 12
# right: the hidden grader
h = D.box('gp', 786, top + 52, 278, 'CI plan on its own state copy', 'plans the repository alone; local state edits never reach it', 'dark'); y = top + 52 + h + 14
h = D.box('gg', 786, y, 278, 'Gates: score 0 if any fails', 'static bans, offline init and plan, moves only, policies, no pasted IDs, remapped state, outputs', 'fault'); y += h + 14
h = D.box('gq', 786, y, 278, '16 probes on changed inputs', 'add, remove and edit an AZ or a pool, also under a fresh key nobody can list in advance; rename project and environment', 'fault'); y += h + 14
h = D.box('gs', 786, y, 278, 'Score', 'passed share of 33 requirement checks; a failed core check scores 0', 'dark'); gb = y + h
zb = max(lb, mid_bot, gb) + 18
D.zone(20, top, 300, zb - top, 'Production, read only', 'side', 'no AWS access from this machine')
D.zone(340, top, 410, zb - top, 'Agent edits: /workspace/infra', 'app', 'Terraform only; the migration lives in the configuration')
D.zone(770, top, 310, zb - top, 'Hidden grader', 'grader', 'separate container, no network')
# arrows across the top
yc = D.pt('ci', 'r')[1]; D.arrow([(304, yc), (356, yc)], 'plans', lpos=.5, loff=(0, -6))
D.arrow([(734, ry + 30), (760, ry + 30), (760, top + 90), (786, top + 90)])
# bottom: the moves-only plan
y0 = zb + 24
PZ = (20, y0, 1060)
ZT = ('What the plan has to show', 'plain', 'every instance in the state moves to a module address keyed by name; nothing is created, changed or destroyed (example addresses)')
cx1, cx2 = 40, 600
D._t(cx1, y0 + 66, 'TODAY: COUNT INDEX', 11, True, GREY); D._t(cx2, y0 + 66, 'AFTER: FOR_EACH KEY IN ITS MODULE', 11, True, TEAL)
rows = [('aws_subnet.primary_workload[0]', 'module.network.aws_subnet.primary_workload["us-east-1b"]', 'AZ'),
        ('aws_subnet.primary_workload[2]', 'module.network.aws_subnet.primary_workload["us-east-1a"]', 'AZ'),
        ('aws_nat_gateway.secondary[1]', 'module.network.aws_nat_gateway.secondary["us-east-1c"]', 'AZ'),
        ('aws_s3_object.pool_bootstrap[0]', 'module.bootstrap.aws_s3_object.pool_bootstrap["gateway"]', 'pool'),
        ('aws_autoscaling_group.primary_worker[2]', 'module.platform.aws_autoscaling_group.primary_worker["mesh"]', 'pool'),
        ('aws_sns_topic.alerts', 'module.observability.aws_sns_topic.alerts', 'single')]
yy = y0 + 92
for old, new, k in rows:
    D.el.append(f'<rect x="{cx1 - 6}" y="{yy - 15}" width="{300}" height="22" rx="4" fill="#f4f2ee" stroke="#b9b4ab"/>')
    mono(cx1, yy, old, GREY, 10.5)
    D.arrow([(cx1 + 300, yy - 4), (cx2 - 10, yy - 4)], 'moved', kind='new', lpos=.5, loff=(0, -5))
    D.el.append(f'<rect x="{cx2 - 6}" y="{yy - 15}" width="{460}" height="22" rx="4" fill="{LIME}" stroke="{TEAL}"/>')
    mono(cx2, yy, new, TEAL, 10.5)
    yy += 34
yy = D.note(40, yy + 4, 1020, 'Index [0] is us-east-1b, not us-east-1a: locals.tf lists the zones as us-east-1b, us-east-1c, us-east-1a and the pools as gateway, system, mesh, so a key cannot be guessed from the index.', 11.5, '#c83220', True)
# then the grader varies the inputs
sy = yy + 22
D._t(40, sy, 'THEN THE INPUTS CHANGE, AND EACH PLAN MUST TOUCH ONLY WHAT CHANGED', 11, True, TEAL)
cards = [('Add an AZ', 'creates only that zone\'s subnets, NAT64 gateway, routes and associations, configured like the others; lists that collect every AZ take in its part'),
         ('Remove a worker pool', 'destroys only that pool\'s resources (IAM, security group, logs, launch template, ASG, bootstrap object, alarm); lists that collect every pool drop its part'),
         ('Edit one entry', 'changes exactly the settings that entry provides, for that AZ or pool alone'),
         ('Rename project or environment', 'every name, tag and user-data value that carries v6mesh or prod follows the variable')]
cw = (1020 - 3 * 14) / 4
for i, (t, b) in enumerate(cards):
    D.box(f'c{i}', 40 + i * (cw + 14), sy + 14, cw, t, b, 'client', h=118)
end = sy + 14 + 118 + 18
D.zone(*PZ, end - y0, *ZT)
D.h = end + 20
D.save(HERE + '/diagram.svg')
