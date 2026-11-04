import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
SUB = ('AtlasGrid runs its production ECS platform from six Terraform modules. Every production resource is already bulk-imported into the Pulumi stack dev, '
       'but its program declares nothing, so a preview would delete everything. The agent writes the TypeScript program that matches the stack today and '
       'plans exactly what Terraform plans when the configuration changes.')
D = Diagram(1100, 1200)
D.title('AtlasGrid: port a six-module Terraform platform to Pulumi TypeScript', SUB)
top = round(64 + len(wrap(SUB, 1100 - 56, 13)) * 13 * 1.35 + 12)
def mono(x, y, s, color=INK, size=10.5):
    D._t(x, y, s, size, False, color, mono=True)
# left: the Terraform reference and the imported stack
h = D.box('tf', 36, top + 52, 268, '/workspace/terraform', 'root calls 6 modules; 27 variables with availability_zones (3 zones) and services (4) as maps; 13 outputs', 'svc', 'terraform')
y = top + 52 + h + 10
for n, k in [('network', 56), ('edge', 35), ('workloads', 33), ('observability', 27), ('cluster', 14), ('identity', 12)]:
    D._t(50, y + 12, n, 11.5, False, INK); D._t(290, y + 12, str(k), 11.5, True, TEAL, 'end')
    D.el.append(f'<rect x="150" y="{y + 3}" width="{k / 56 * 110:.1f}" height="10" rx="2" fill="#b9dcd3"/>')
    y += 19
D._t(50, y + 14, 'instances per module, 177 in all', 10.5, False, GREY)
y += 30
h = D.store('st', 36, y, 268, 'terraform.tfstate', 'production; terraform plan -refresh=false works offline', 'terraform'); y += h + 14
h = D.store('pk', 36, y, 268, 'Pulumi stack dev', 'bulk-imported copy of every production resource, in the local backend', 'pulumi'); lb = y + h
# middle: the program the agent writes
h = D.box('ix', 356, top + 52, 378, 'index.ts', 'empty today: a preview would delete the whole stack', 'new', 'typescript', tag='WRITE')
cy = top + 52 + h + 16
D._t(356, cy + 4, 'ONE COMPONENTRESOURCE PER MODULE', 11, True, TEAL)
cy += 14
comps = ['Network', 'Identity', 'Edge', 'Cluster', 'Workloads', 'Observability']
for i, c in enumerate(comps):
    x = 356 + (i % 2) * 192; yy = cy + (i // 2) * 62
    D.box('c' + c, x, yy, 186, c, 'atlasgrid:modules:' + c, 'svc', h=52)
cy += 3 * 62 + 4
h = D.box('cf', 356, cy, 378, 'Config: one key per Terraform variable', 'atlasgrid-ecs:project, atlasgrid-ecs:services, ... as plain YAML; unset keys take the Terraform default', 'svc'); cy += h + 14
h = D.box('fx', 356, cy, 378, 'Kept byte for byte', 'Pulumi.yaml, Pulumi.dev.yaml, package.json, tsconfig.json, templates/; offline, nothing can be installed', 'muted'); mid_bot = cy + h
# right: the hidden grader
h = D.box('gp', 786, top + 52, 278, 'Previews the program', 'against production and against a copy with every generated ID swapped', 'dark'); y = top + 52 + h + 14
h = D.box('gg', 786, y, 278, 'Gates: score 0 if any fails', 'type-checks with the owned tsconfig, runs unprivileged and offline, no changes on either stack, no banned option or lookup, Terraform outputs', 'fault'); y += h + 14
h = D.box('gq', 786, y, 278, '17 checks', '16 configuration changes and one drift revert, each compared with what the Terraform configuration plans', 'fault'); y += h + 14
h = D.box('gs', 786, y, 278, 'Score', 'binary: 1 only if all 17 checks pass', 'dark'); gb = y + h
zb = max(lb, mid_bot, gb) + 18
D.zone(20, top, 300, zb - top, 'Reference, read only', 'side', 'no AWS access from this machine')
D.zone(340, top, 410, zb - top, 'Agent edits: /workspace/pulumi', 'app', 'TypeScript, @pulumi/aws 6.83.0, Node.js 22')
D.zone(770, top, 310, zb - top, 'Hidden grader', 'grader', 'separate container, no network')
yt = D.pt('tf', 'r')[1]; D.arrow([(304, yt), (356, yt)], 'port', lpos=.5, loff=(0, -6))
yp = D.pt('pk', 'r', .5)[1]; yf = D.pt('cf', 'l')[1]; D.arrow([(304, yp), (330, yp), (330, yf), (356, yf)], 'preview', lpos=.12, loff=(0, -6))
D.arrow([(734, top + 80), (786, top + 80)])
# bottom: the mapping and the changes
y0 = zb + 24
cx1, cx2, ow = 40, 600, 470
D._t(cx1, y0 + 66, 'TERRAFORM RESOURCE INSTANCE', 11, True, GREY); D._t(cx2, y0 + 66, 'PULUMI RESOURCE UNDER ITS COMPONENT', 11, True, TEAL)
rows = [('module.cluster.aws_efs_mount_target.ecs["us-east-1a"]', 'Cluster > aws.efs.MountTarget "ecs-us-east-1a"'),
        ('module.network.aws_nat_gateway.main["us-east-1b"]', 'Network > aws.ec2.NatGateway "main-us-east-1b"'),
        ('module.edge.aws_lb_target_group.service["orders"]', 'Edge > aws.lb.TargetGroup "service-orders"'),
        ('module.identity.aws_iam_role.ecs_task', 'Identity > aws.iam.Role "ecs_task"'),
        ('var.services (map of 4 services)', 'config atlasgrid-ecs:services (YAML mapping)')]
yy = y0 + 92
for old, new in rows:
    D.el.append(f'<rect x="{cx1 - 6}" y="{yy - 15}" width="{ow}" height="22" rx="4" fill="#f4f2ee" stroke="#b9b4ab"/>')
    mono(cx1, yy, old, GREY)
    D.arrow([(cx1 + ow - 6, yy - 4), (cx2 - 10, yy - 4)], kind='new')
    D.el.append(f'<rect x="{cx2 - 6}" y="{yy - 15}" width="{1066 - cx2}" height="22" rx="4" fill="{LIME}" stroke="{TEAL}"/>')
    mono(cx2, yy, new, TEAL)
    yy += 34
yy = D.note(40, yy + 4, 1020, 'Names follow the instruction: the Terraform resource name plus -<key> for for_each instances (example names). Values Terraform reads from another resource come from that resource\'s output, so they stay unknown in the preview exactly where Terraform\'s plan shows them as unknown.', 11.5, '#c83220', True)
sy = yy + 22
D._t(40, sy, 'PULUMI PREVIEW MUST PLAN WHAT TERRAFORM PLAN PLANS', 11, True, TEAL)
cards = [('Production as it is', 'no changes against the imported stack, nor against the copy with every generated ID swapped'),
         ('Add or remove a zone or service', 'the same creates and deletes, with the same settings, as terraform plan with that map'),
         ('Change a setting or rename', 'project, environment and per-entry settings change the same resources in the same way'),
         ('Drift in the stack', 'the preview reverts it as Terraform would; lists built from maps use sorted key order')]
cw = (1020 - 3 * 14) / 4
for i, (t, b) in enumerate(cards):
    D.box(f'k{i}', 40 + i * (cw + 14), sy + 14, cw, t, b, 'client', h=118)
end = sy + 14 + 118 + 18
D.zone(20, y0, 1060, end - y0, 'What the program has to reproduce', 'plain', 'each Terraform resource instance becomes one resource under its module\'s component, and every preview matches the Terraform plan')
D.h = end + 20
D.save(HERE + '/diagram.svg')
