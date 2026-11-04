import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
C = dict(
    title='Multi-model router: split a flat ECS inference stack into eight modules',
    sub='Three model services run on ECS behind one load balancer, with model artifacts in S3 and ECR, three availability zones, three asynchronous inference queues and three public entrypoints, all in one flat Terraform root indexed by list position. The agent splits it into eight modules keyed by zone, model, queue and entrypoint, and the plan against production must contain nothing but moves.',
    state='copy of production: 98 resource blocks, 215 instances; per-AZ, per-model, per-queue and per-entrypoint ones count-indexed',
    flat='network.tf 277 lines, artifacts.tf 208, observability.tf 188, queues.tf 164, iam.tf 124, routing.tf 119, security.tf 76, ecs.tf 65; order lists in locals.tf',
    root='calls 8 modules, declares no resources; 26 variables (models, queues, entrypoints, availability zones, tags, ...); 19 outputs',
    mods=[('network', 'VPC, subnets, NAT, routes, ACLs, S3 endpoint, flow log'),
          ('security', 'load balancer and task security groups and rules'),
          ('identity', 'ECS roles, policy attachments, instance profile'),
          ('artifacts', 'ECR, model buckets, ALB log bucket, model parameters'),
          ('compute', 'ECS cluster, task definitions, model log groups'),
          ('routing', 'ALB, target groups, listeners, path rules'),
          ('observability', 'topics and alarms per model, AZ and entrypoint'),
          ('queues', 'async queues, dead-letter queues, alarms, worker roles')],
    mod_h=80,
    gates='static bans, offline init and plan, moves only, policies, no pasted IDs, remapped state',
    probes=('35 probes on changed inputs', 'add, remove and edit an AZ, model, queue or entrypoint, move the primary model and the entrypoint roles, rename project and environment'),
    score='passed share of 50 requirement checks',
    rows=[('aws_subnet.private[0]', 'module.network.aws_subnet.private["us-east-1b"]'),
          ('aws_ecs_task_definition.model[2]', 'module.compute.aws_ecs_task_definition.model["opt"]'),
          ('aws_sqs_queue.inference[1]', 'module.queues.aws_sqs_queue.inference["interactive"]'),
          ('aws_lb_listener.entrypoint[0]', 'module.routing.aws_lb_listener.entrypoint["partner"]'),
          ('aws_iam_role_policy.task_queues', 'module.queues.aws_iam_role_policy.task_queues'),
          ('aws_ecs_cluster.main', 'module.compute.aws_ecs_cluster.main')],
    ow=300, cx2=560,
    order='No list is alphabetical: locals.tf keeps zones as us-east-1b, us-east-1c, us-east-1a, models as llama, embed, opt, queues as batch, interactive, bulk and entrypoints as partner, public, operations, so a key cannot be guessed from the index.',
    cards=[('Add an AZ, model, queue or entrypoint', 'creates only that entry\'s resources, configured like the others; catalogs and policies that list every entry take in its part'),
           ('Move the primary model', 'NAT alarms switch to the new primary model\'s alert topic; with no primary left their action lists become empty'),
           ('Move the entrypoint roles', 'path rules follow the "routes" entrypoint\'s listener; the primary-entrypoint parameter holds the "primary" key, or "none"'),
           ('Rename project or environment', 'every name, tag and document value that carries modelrouter or prod follows the variable')],
    card_h=134,
    plan_sub='every instance in the state moves to a module address keyed by name; nothing is created, changed or destroyed (example addresses)',
)
D = Diagram(1100, 1200)
D.title(C['title'], C['sub'])
top = round(64 + len(wrap(C['sub'], 1100 - 56, 13)) * 13 * 1.35 + 12)
def mono(x, y, s, color=INK, size=10.5):
    D._t(x, y, s, size, False, color, mono=True)
# left: production inputs the agent cannot change
h = D.store('st', 36, top + 52, 268, 'terraform.tfstate', C['state'], 'terraform')
y = top + 52 + h + 16
h = D.box('pm', 36, y, 268, 'Provider mirror', 'terraform init works offline; AWS provider 5.100.0, Terraform 1.16.4', 'muted'); y += h + 14
h = D.box('fx', 36, y, 268, 'providers.tf and policies/', 'guardrail policies, kept byte for byte', 'muted'); y += h + 14
h = D.box('ci', 36, y, 268, 'scripts/ci-plan.sh', 'what CI runs: terraform plan -refresh=false against the state, then the policies', 'svc'); lb = y + h
# middle: the configuration the agent rewrites
h = D.box('fl', 356, top + 52, 378, 'Today: one flat root module', C['flat'], 'muted')
ry = top + 52 + h + 30
D.arrow([(545, top + 52 + h + 2), (545, ry - 2)], 'refactor', kind='new', lpos=.5, loff=(36, 4))
h = D.box('rt', 356, ry, 378, 'Root module', C['root'], 'new', tag='NEW')
my = ry + h + 18
need = lambda n, b: 14 + len(wrap('module "' + n + '"', 186 - 22, 13, True)) * 17 + 6 + len(wrap(b, 186 - 24, 11.5)) * 15.5 + 8
yy = my
for r in range(0, len(C['mods']), 2):
    row = C['mods'][r:r + 2]; mh = max(need(n, b) for n, b in row)
    for j, (n, b) in enumerate(row): D.box('m' + n, 356 + j * 192, yy, 186, 'module "' + n + '"', b, 'svc', h=mh)
    yy += mh + 12
mid_bot = yy - 12
# right: the hidden grader
h = D.box('gp', 786, top + 52, 278, 'CI plan on its own state copy', 'plans the repository alone; local state edits never reach it', 'dark'); y = top + 52 + h + 14
h = D.box('gg', 786, y, 278, 'Gates: score 0 if any fails', C['gates'], 'fault'); y += h + 14
h = D.box('gq', 786, y, 278, C['probes'][0], C['probes'][1], 'fault'); y += h + 14
h = D.box('gs', 786, y, 278, 'Score', C['score'], 'dark'); gb = y + h
zb = max(lb, mid_bot, gb) + 18
D.zone(20, top, 300, zb - top, 'Production, read only', 'side', 'no AWS access from this machine')
D.zone(340, top, 410, zb - top, 'Agent edits: /workspace/infra', 'app', 'Terraform only; the migration lives in the configuration')
D.zone(770, top, 310, zb - top, 'Hidden grader', 'grader', 'separate container, no network')
yc = D.pt('ci', 'r')[1]; D.arrow([(304, yc), (340, yc)], 'plans', lpos=.5, loff=(0, -6))
D.arrow([(734, ry + 30), (760, ry + 30), (760, top + 90), (786, top + 90)])
# bottom: the moves-only plan
y0 = zb + 24
cx1, cx2 = 40, C.get('cx2', 600)
D._t(cx1, y0 + 66, 'TODAY: COUNT INDEX', 11, True, GREY); D._t(cx2, y0 + 66, 'AFTER: FOR_EACH KEY IN ITS MODULE', 11, True, TEAL)
yy = y0 + 92
ow = C.get('ow', 300)
for old, new in C['rows']:
    D.el.append(f'<rect x="{cx1 - 6}" y="{yy - 15}" width="{ow}" height="22" rx="4" fill="#f4f2ee" stroke="#b9b4ab"/>')
    mono(cx1, yy, old, GREY)
    D.arrow([(cx1 + ow - 6, yy - 4), (cx2 - 10, yy - 4)], 'moved', kind='new', lpos=.5, loff=(0, -5))
    D.el.append(f'<rect x="{cx2 - 6}" y="{yy - 15}" width="{1066 - cx2}" height="22" rx="4" fill="{LIME}" stroke="{TEAL}"/>')
    mono(cx2, yy, new, TEAL)
    yy += 34
yy = D.note(40, yy + 4, 1020, C['order'], 11.5, '#c83220', True)
sy = yy + 22
D._t(40, sy, 'THEN THE INPUTS CHANGE, AND EACH PLAN MUST TOUCH ONLY WHAT CHANGED', 11, True, TEAL)
cw = (1020 - 3 * 14) / 4; ch = C.get('card_h', 118)
for i, (t, b) in enumerate(C['cards']):
    D.box(f'c{i}', 40 + i * (cw + 14), sy + 14, cw, t, b, 'client', h=ch)
end = sy + 14 + ch + 18
D.zone(20, y0, 1060, end - y0, 'What the plan has to show', 'plain', C['plan_sub'])
D.h = end + 20
D.save(HERE + '/diagram.svg')
