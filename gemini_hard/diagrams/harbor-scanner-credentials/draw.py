import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1400)
D.title('Harbor: short-lived, single-repository scanner credentials',
        'Today every vulnerability scan creates a robot account that never expires, can pull the whole project, and whose secret sits in Redis job stats. The agent replaces that lifecycle in the Go code of core and jobservice for scans started by the scan API and by scan-on-push.')
top = 104
D.box('api', 34, 160, 166, 'Scan API', 'POST .../artifacts/{ref}/scan', 'client')
D.box('push', 34, 290, 166, 'Scan on push', 'manifest push into a scan-on-push project', 'client')
D.box('ca', 236, 156, 250, 'core, instance A', 'scan controller; creates and revokes the scan credential', 'svc', 'go', tag='EDITED')
D.box('cb', 236, 280, 250, 'core, instance B', 'same build; scans run on both at once', 'svc', 'go')
D.box('au', 512, 156, 252, '/v2/ and /service/token', 'a scan credential may only pull the scanned repository', 'new', tag='NEW RULE')
D.box('js', 512, 280, 252, 'jobservice', 'runs the IMAGE_SCAN job; no secret in job parameters, Redis or logs', 'svc', 'go', tag='EDITED')
D.box('sc', 816, 156, 248, 'Scanner adapter (fake)', 'registered by the grader; uses Basic or Bearer registry authorization; can hold a scan for 3 minutes', 'fault')
D.box('rep', 816, 290, 248, 'Vulnerability report', 'published to the artifact when the scan succeeds', 'muted')
bot = 396
D.zone(20, top, 194, bot - top, 'Who starts a scan', 'client')
D.zone(222, top, 556, bot - top, 'Harbor', 'app', 'Go module in /app/src, edited by the agent')
D.zone(800, top, 280, bot - top, 'Scanner', 'grader', 'part of the hidden test harness')
D.arrow([(200, 188), (236, 188)])
D.arrow([(200, 318), (236, 318)])
D.arrow([(486, 214), (498, 214), (498, 296), (512, 296)])
D.arrow([(486, 322), (512, 322)])
D.arrow([(764, 320), (790, 320), (790, 240), (816, 240)], 'scan request', lpos=.5, loff=(8, 0), lanchor='start')
D.arrow([(816, 186), (764, 186)], 'pull image', lpos=.5)
D.arrow([(1010, D.pt('sc', 'b')[1]), (1010, 290)])
# backing services
by = bot + 20
D.zone(20, by, 1060, 128, 'Services in the container', 'side', 'started with sudo service; no Docker inside the agent container')
D.store('pg', 236, by + 42, 250, 'PostgreSQL', 'robot accounts, scan tasks', 'postgresql', h=66)
D.store('rd', 512, by + 42, 252, 'Redis', 'job queue and stats; never a secret', 'redis', h=66)
D.store('rg', 816, by + 42, 248, 'docker-registry', 'image storage behind /v2/', 'docker', h=66)
D.arrow([(361, D.pt('cb', 'b')[1]), (361, by + 42)])
D.arrow([(638, D.pt('js', 'b')[1]), (638, by + 42)])
# hidden grader strip
gy = by + 128 + 20
D.zone(20, gy, 1060, 136, 'Hidden grader', 'grader', 'runs real core, jobservice, registry, PostgreSQL and Redis processes')
for i, (t, b, k) in enumerate([
        ('19 tests', '7 new, 4 guards, 8 existing unit tests', 'dark'),
        ('Kill jobservice', 'mid-scan, so no final hook ever arrives', 'fault'),
        ('jobservice down', 'when a scan is requested', 'fault'),
        ('Two core processes', 'scan different repositories at the same time', 'fault'),
        ('Secret search', 'Redis, the job API, job parameters and logs', 'fault')]):
    D.box(f'g{i}', 36 + i * 207, gy + 48, 195, t, b, k, h=72)
# scenario
y0 = gy + 136 + 24
end = D.seq(36, y0 + 64, 1028, [('T', 'Test client', 'client'), ('C', 'Harbor core', 'svc'), ('J', 'jobservice', 'svc'), ('S', 'Scanner adapter', 'fault')], [
    {'a': 'T', 'b': 'C', 'label': 'POST scan abandoned/image'},
    {'a': 'C', 'b': 'J', 'label': 'IMAGE_SCAN job, no secret inside', 'kind': 'new'},
    {'a': 'J', 'b': 'S', 'label': 'scan request with the credential'},
    {'a': 'S', 'b': 'C', 'label': 'pull abandoned/image: 200', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'S', 'b': 'C', 'label': 'push, or pull another repository', 'kind': 'fault', 'mark': 'x'},
    {'a': 'J', 'label': 'killed mid-scan: no final hook', 'kind': 'fault', 'mark': 'bolt', 'gap': .2},
    {'a': 'S', 'b': 'C', 'label': 'pull again with the same credential', 'kind': 'fault', 'gap': .2},
    {'a': 'C', 'label': '401 or 403 within 2 minutes; robot account deleted', 'kind': 'ok'},
], row=32)
fin = D.note(36, end + 22, 1028, 'When the scan ends normally instead, /v2/ and /service/token reject the credential within 30 seconds of the final status.', 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'Life of one scanner credential', 'plain', 'from the pull-only and killed-jobservice tests')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
