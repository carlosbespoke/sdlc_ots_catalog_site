import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
C = dict(
    title='centralwatch: split a flat alert-routing stack into three modules',
    sub='A central monitoring account routes operational events through EventBridge, SQS and an enricher Lambda to per-team, per-severity and per-channel SNS topics, all in one flat Terraform root indexed by list position. The agent splits it into eventing, messaging and processing modules keyed by team, source, severity and channel, and the plan against production must contain nothing but moves.',
    state='copy of production: 65 resource blocks, 260 instances; per-team, per-source, per-severity and per-channel ones count-indexed',
    flat='enricher.tf 278 lines, teams.tf 159, eventbridge.tf 158, channels.tf 151, severities.tf 146, iam.tf 96, queues.tf 41, kms.tf 14; order lists and settings in locals.tf',
    root='calls 3 modules, declares no resources; 29 variables (teams, sources, severities, channels, tags, queue, Lambda and alarm settings, ...); 17 outputs',
    mods=[('eventing', 'KMS key, EventBridge bus and role, per-source rules, logs, dead-letter queues, alarms and filters'),
          ('messaging', 'central queues; per-team, per-severity and per-channel topics, queues and subscriptions; escalation topic'),
          ('processing', 'enricher Lambda with its role, mapping and alarms; per-channel logs, alarms and route parameters')],
    mod_h=96,
    gates='static bans, offline init and plan, moves only, policies, no pasted IDs, remapped state',
    probes=('37 probes on changed inputs', 'add, remove and edit a team, source, severity or channel, remove a default entry, rename project and environment'),
    score='passed share of 46 requirement checks',
    rows=[('aws_sns_topic.this[0]', 'module.messaging.aws_sns_topic.this["operations"]'),
          ('aws_sns_topic.this[9]', 'module.messaging.aws_sns_topic.this["payments"]'),
          ('aws_cloudwatch_event_rule.source[1]', 'module.eventing.aws_cloudwatch_event_rule.source["backup"]'),
          ('aws_sqs_queue.severity[2]', 'module.messaging.aws_sqs_queue.severity["emergency"]'),
          ('aws_ssm_parameter.channel_route[0]', 'module.processing.aws_ssm_parameter.channel_route["webhook"]'),
          ('aws_lambda_function.cwalarms_sns_enricher', 'module.processing.aws_lambda_function.cwalarms_sns_enricher')],
    ow=320, cx2=560,
    order='No list is alphabetical: locals.tf keeps 10 teams in rollout order (operations first, payments last), 7 sources, 5 severities (critical, warning, emergency, info, high) and 4 channels in runbook order, so a key cannot be guessed from the index.',
    cards=[('Add a team, source, severity or channel', 'creates only that entry\'s topics, queues, logs, alarms and parameters; maps and policies that list every entry take in its part'),
           ('Remove the operations team', 'destroys only its team resources; the separate escalation topic stays, and the default team becomes the lexicographically first remaining one'),
           ('Edit one entry', 'changes exactly the settings that entry provides, for that team, source, severity or channel alone'),
           ('Rename project or environment', 'every name, tag and document value that carries centralwatch or prod follows the variable')],
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
