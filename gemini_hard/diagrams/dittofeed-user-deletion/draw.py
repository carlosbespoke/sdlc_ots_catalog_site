import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('Dittofeed: user deletion that stays deleted',
        'Deleting a user removes their events and assignments, but work already in flight (a computation, a late event, a journey waiting at a delay) can bring the user back or still message them. The agent fences every one of these paths in the TypeScript API and worker.')
top, bot = 104, 556
D.zone(20, top, 200, bot - top, 'Clients', 'client')
D.zone(236, top, 284, bot - top, 'Dittofeed services', 'app', 'TypeScript monorepo in /app')
D.zone(540, top, 222, bot - top, 'Hidden grader', 'grader', 'holds, restarts and a receiver')
D.zone(782, top, 298, bot - top, 'Sidecars', 'side', 'internal network, no internet')
D.box('sdk', 34, top + 52, 172, 'identify / track / batch', 'events with their own timestamps', 'client')
D.box('op', 34, top + 170, 172, 'operator', 'DELETE /api/users and /api/users/v2', 'client')
D.box('ls', 34, top + 262, 172, 'POST /api/users', 'listing with segments and user properties', 'client')
D.box('api', 252, top + 52, 252, 'API', 'ingest routes and the two delete routes', 'svc', 'typescript', tag='EXTENDED')
D.box('wm', 252, top + 156, 252, 'Deletion watermark', 'durable per user and workspace, recorded before the delete returns; schema migration included', 'new', tag='NEW')
D.box('wk', 252, top + 282, 252, 'Worker', 'computes segments and user properties, runs journeys', 'svc', 'nodedotjs', tag='EXTENDED')
D.box('hold', 556, top + 136, 190, 'ClickHouse write hold', 'pauses a computed assignment write mid-flight', 'fault', h=72)
D.box('rcv', 556, top + 222, 190, 'Webhook receiver', 'records every journey message it is sent', 'fault', h=72)
D.box('rs', 556, top + 322, 190, 'API restart', 'kills and restarts the API process', 'fault', h=72)
D.note(556, top + 416, 190, '6 hidden tests and 12 hidden guards, plus 51 existing users tests', 11, '#c83220')
D.store('PG', 800, top + 46, 262, 'PostgreSQL 15', 'workspaces, segments, journey events', 'postgresql')
D.store('CH', 800, top + 140, 262, 'ClickHouse 24.12', 'user events and computed assignments', 'database')
D.store('TM', 800, top + 262, 262, 'Temporal 1.18.5', 'journey workflows and their delays', 'clock')
D.link('sdk', 'r', 'api', 'l', fb=.35)
D.link('op', 'r', 'api', 'l', via=[(230, top + 202), (230, top + 108)], fb=.75)
D.link('ls', 'r', 'api', 'l', via=[(226, top + 294), (226, top + 118)], fb=.9)
D.arrow([(378, top + 136), (378, top + 156)], kind='new')
D.arrow([(504, top + 72), (800, top + 72)], 'state and journeys', lpos=.55)
D.arrow([(504, top + 104), (786, top + 104), (786, top + 166), (800, top + 166)], 'insert and delete events', lpos=.4)
D.arrow([(504, top + 290), (526, top + 290), (526, top + 172), (556, top + 172)])
D.arrow([(746, top + 196), (800, top + 196)])
D.arrow([(504, top + 302), (540, top + 302), (540, top + 258), (556, top + 258)])
D.arrow([(504, top + 316), (800, top + 316)], 'delays and timers', lpos=.5)
y0 = bot + 26
end = D.seq(36, y0 + 64, 1028, [('C', 'Client', 'client'), ('A', 'API', 'svc'), ('W', 'Worker', 'svc'), ('CH', 'ClickHouse', 'svc'), ('R', 'Webhook receiver', 'svc')], [
    {'a': 'C', 'b': 'A', 'label': 'identify user u (old traits)'},
    {'a': 'A', 'b': 'CH', 'label': 'store event'},
    {'a': 'W', 'b': 'CH', 'label': 'compute: reads u, assignment write held', 'kind': 'fault'},
    {'a': 'C', 'b': 'A', 'label': 'DELETE /api/users  [u]'},
    {'a': 'A', 'label': 'record the deletion watermark, then return', 'kind': 'new'},
    {'a': 'A', 'b': 'CH', 'label': "delete u's events"},
    {'a': 'W', 'b': 'CH', 'label': 'held write released after the delete', 'kind': 'fault', 'gap': .2},
    {'a': 'CH', 'label': 'u must stay erased', 'kind': 'fault'},
    {'a': 'C', 'b': 'A', 'label': 'late batch, timestamp before the delete', 'kind': 'fault', 'mark': 'x'},
    {'a': 'W', 'label': "u's journey wakes from its delay: message step recorded", 'gap': .2},
    {'a': 'W', 'b': 'R', 'label': 'webhook to u', 'kind': 'fault', 'mark': 'x'},
    {'a': 'C', 'b': 'A', 'label': 'identify u, later timestamp', 'kind': 'ok', 'mark': 'ok', 'gap': .2},
    {'a': 'A', 'label': 'a fresh u with only the new traits', 'kind': 'ok'},
], row=31)
fin = D.note(36, end + 22, 1028, 'The erased user drops out of the listing within 10 seconds of the delete and stays out for at least 60 seconds; other users and the same id in another workspace are untouched.', 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'What the instruction asks for', 'plain', 'in-flight work arrives after the delete')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
