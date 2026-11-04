import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('Immich: hard storage quotas while uploads are streaming',
        'Concurrent uploads can each pass the quota check against the same old usage, and a dead API process leaves half-written originals on disk. The agent makes the per-user quota a hard limit across separate API processes and the background worker.')
top, bot = 104, 576
D.zone(20, top, 200, bot - top, 'Clients', 'client')
D.zone(236, top, 284, bot - top, 'Immich server', 'app', 'TypeScript (NestJS) in /app')
D.zone(540, top, 222, bot - top, 'Hidden grader', 'grader', 'kills, aborts and slow streams')
D.zone(782, top, 298, bot - top, 'Sidecars', 'side', 'internal network, no internet')
D.box('u1', 34, top + 52, 172, 'uploader', 'multipart POST /api/assets, size declared or not', 'client')
D.box('u2', 34, top + 160, 172, 'shared-link uploader', 'upload into an album through its link', 'client')
D.box('me', 34, top + 258, 172, 'owner', 'GET /api/users/me, trash, restore, empty trash', 'client')
D.box('ad', 34, top + 366, 172, 'admin', 'PUT a new quota, queue UserSyncUsage', 'client')
D.box('A', 252, top + 52, 252, 'API instance A', 'counts bytes as they arrive and refuses past the quota (400 or 413)', 'svc', 'typescript', tag='EXTENDED')
D.box('B', 252, top + 150, 252, 'API instance B', 'same build, separate process', 'svc', 'typescript', tag='EXTENDED')
D.box('W', 252, top + 272, 252, 'Microservices worker', 'backgroundTask queue: AssetDelete, UserSyncUsage', 'svc', 'nodedotjs', tag='EXTENDED')
D.note(252, top + 382, 252, 'Each API process runs with IMMICH_WORKERS_INCLUDE set to api, the worker with microservices.', 11)
D.box('kill', 556, top + 96, 190, 'Process kill', 'kills an API instance mid-upload', 'fault', h=72)
D.box('ab', 556, top + 180, 190, 'Client abort', 'drops a stream before it ends', 'fault', h=72)
D.box('tr', 556, top + 264, 190, 'Slow trickle', 'half a MiB every 5 s for 35 s', 'fault', h=72)
D.box('dup', 556, top + 348, 190, 'Duplicate jobs', 'the same AssetDelete queued twice', 'fault', h=72)
D.note(556, top + 436, 190, '5 hidden tests and 5 hidden guards, plus 2,301 existing tests', 11, '#c83220')
D.store('PG', 800, top + 46, 262, 'PostgreSQL 14', 'VectorChord 0.4.3 image: users, assets, quota usage', 'postgresql')
D.store('FS', 800, top + 146, 262, '/data upload volume', 'shared by every process; originals land here while they stream', 'folder')
D.store('RD', 800, top + 272, 262, 'Redis 7', 'job queues', 'redis')
D.link('u1', 'r', 'A', 'l', fb=.35)
D.link('u2', 'r', 'B', 'l', fb=.35)
D.link('me', 'r', 'B', 'l', via=[(230, top + 290), (230, top + 196)], fb=.7)
D.link('ad', 'r', 'B', 'l', via=[(224, top + 398), (224, top + 204)], fb=.85)
D.arrow([(504, top + 74), (800, top + 74)], 'quota usage', lpos=.55)
D.arrow([(504, top + 300), (522, top + 300), (522, top + 74)], head=False)
D.arrow([(504, top + 112), (522, top + 112)], head=False)
D.arrow([(504, top + 180), (522, top + 180)], head=False)
D.arrow([(522, top + 174), (800, top + 174)], head=True)
D.arrow([(504, top + 342), (800, top + 342)], head=True)
y0 = bot + 26
end = D.seq(36, y0 + 64, 1028, [('C1', 'Uploader', 'client'), ('C2', 'Second uploader', 'client'), ('A', 'API A', 'svc'), ('B', 'API B', 'svc'), ('FS', '/data', 'svc')], [
    {'a': 'C1', 'b': 'A', 'label': 'upload 4 MiB, still streaming'},
    {'a': 'C2', 'b': 'B', 'label': 'upload 4 MiB, still streaming'},
    {'a': 'A', 'b': 'FS', 'label': 'unfinished original grows'},
    {'a': 'C2', 'b': 'B', 'label': 'third 4 MiB upload: committed plus in flight would pass 10 MiB', 'kind': 'fault', 'mark': 'x'},
    {'a': 'B', 'label': 'quota error, 400 or 413', 'kind': 'fault'},
    {'a': 'A', 'label': 'API A is killed mid-stream', 'kind': 'fault', 'mark': 'bolt', 'gap': .2},
    {'a': 'A', 'label': 'within 45 s, with no new request: the partial original leaves /data and its space is free', 'kind': 'ok'},
    {'a': 'C2', 'b': 'B', 'label': 'first upload finishes: 201', 'kind': 'ok', 'mark': 'ok', 'gap': .5},
    {'a': 'B', 'label': 'its 4 MiB is charged once', 'kind': 'ok'},
], row=31)
fin = D.note(36, end + 22, 1028, 'GET /api/users/me shows committed usage only. A client abort frees its space within 5 seconds; deleting an original releases its usage exactly once.', 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'What the instruction asks for', 'plain', 'illustrative sizes: a quota 10 MiB above current usage')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
