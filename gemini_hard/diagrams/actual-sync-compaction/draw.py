import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1200)
D.title('Actual Budget: checkpoint the sync log without losing offline edits',
        'Every budget change is an encrypted CRDT message that the sync server keeps forever. The agent adds checkpoints: a device uploads a compact snapshot, and the server drops the messages it covers while the sync group stays the same.')
top = 104
# server boxes first, stacked by their real heights
y = 156; Y = {}
for k, t, body, kind, tag in [
        ('cm', 'POST /sync/commit-checkpoint', 'snapshot body plus base, checkpoint id and merkle headers; 200 only if the base and prior checkpoint still match, else 409; 400 on a bad base', 'new', 'NEW'),
        ('sy', 'POST /sync/sync  (protobuf)', 'adds checkpointId (field 7) to the request and checkpointWanted, checkpointRequired, checkpointBase (3, 4, 6) to the response; asks for a checkpoint past ACTUAL_SYNC_CHECKPOINT_THRESHOLD messages', 'svc', 'EXTENDED'),
        ('in', 'get-user-file-info', 'adds messageCount, checkpointId and checkpointBase', 'svc', 'EXTENDED'),
        ('ex', 'upload, download, login', 'unchanged routes that must keep working', 'muted', None)]:
    Y[k] = y; y += D.box(k, 292, y, 416, t, body, kind, tag=tag) + 18
bot = y + 2
D.zone(20, top, 236, bot - top, 'Budget devices', 'client', 'loot-core client via @actual-app/api')
D.zone(276, top, 448, bot - top, 'Sync server', 'app', 'TypeScript in /app, edited by the agent')
D.zone(744, top, 336, bot - top, 'Server storage', 'side', 'SQLite files under ACTUAL_DATA_DIR')
D.box('A', 34, Y['cm'], 208, 'Device A', 'stays online, makes the edits and proposes the checkpoint', 'client')
D.box('B', 34, Y['sy'] + 52, 208, 'Device B', 'goes offline with unsent edits, rejoins later', 'client')
D.box('C', 34, Y['ex'] - 6, 208, 'Device C', 'downloads the budget fresh', 'client')
D.store('uf', 760, Y['cm'] - 6, 304, 'User files', 'encrypted budget file, replaced by the snapshot on commit', 'sqlite')
D.store('lg', 760, Y['sy'] + 10, 304, 'group-{id}.sqlite', 'CRDT message log; a commit deletes exactly the messages up to its base', 'sqlite')
D.store('ac', 760, Y['in'] - 6, 304, 'Account database', 'file info: group id, checkpoint id', 'sqlite')
ya = Y['cm'] + 30; D.arrow([(242, ya), (292, ya)], 'commit', lpos=.5)
yb = D.pt('A', 'b')[1] - 14; D.arrow([(242, yb), (264, yb), (264, Y['sy'] + 30), (292, Y['sy'] + 30)])
yB = D.pt('B', 'l', .5)[1]; D.arrow([(242, yB), (292, yB)], 'sync', lpos=.5)
yC = D.pt('ex', 'l')[1]; D.arrow([(242, yC), (292, yC)], 'download', lpos=.5)
D.arrow([(708, Y['cm'] + 24), (760, Y['cm'] + 24)])
D.arrow([(708, Y['cm'] + 60), (730, Y['cm'] + 60), (730, Y['sy'] + 44), (760, Y['sy'] + 44)])
D.arrow([(708, Y['sy'] + 80), (760, Y['sy'] + 80)])
D.arrow([(708, Y['in'] + 30), (760, Y['in'] + 30)])
# hidden grader strip
gy = bot + 20
D.zone(20, gy, 1060, 132, 'Hidden grader', 'grader', 'starts the real server and real devices, then forces the hard timings')
fx = 36
for i, (t, b, k) in enumerate([
        ('10 node tests', '8 new behaviours, 2 guards on existing routes', 'dark'),
        ('Commit proxy', 'holds two checkpoint proposals, then releases both', 'fault'),
        ('Truncated body', 'declares 8192 bytes, sends 4096 and hangs up', 'fault'),
        ('Late arrival', 'a message older than the base, just before a commit', 'fault'),
        ('Old-format client', 'syncs from before the checkpoint', 'fault')]):
    D.box(f'g{i}', fx + i * 207, gy + 48, 195, t, b, k, h=72)
# scenario
y0 = gy + 132 + 24
end = D.seq(36, y0 + 64, 1028, [('A', 'Device A', 'client'), ('S', 'Sync server', 'svc'), ('B', 'Device B', 'client'), ('C', 'Device C', 'client')], [
    {'a': 'A', 'b': 'S', 'label': 'upload budget: group G'},
    {'a': 'B', 'b': 'S', 'label': 'download budget'},
    {'a': 'B', 'label': 'goes offline, makes 8 edits that are not sent', 'kind': 'fault', 'mark': 'bolt'},
    {'a': 'A', 'b': 'S', 'label': 'sync 30 edits'},
    {'a': 'S', 'b': 'A', 'label': 'checkpointWanted, checkpointBase N', 'kind': 'new'},
    {'a': 'A', 'b': 'S', 'label': 'commit-checkpoint: snapshot up to N', 'kind': 'new'},
    {'a': 'S', 'label': '200: log pruned to N, file replaced, group G kept', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'C', 'b': 'S', 'label': 'fresh download: gets the snapshot', 'gap': .2},
    {'a': 'B', 'b': 'S', 'label': 'rejoin: sync with the old checkpoint id'},
    {'a': 'S', 'b': 'B', 'label': 'checkpointRequired', 'kind': 'new'},
    {'a': 'B', 'b': 'S', 'label': 'load snapshot, resend the 8 edits', 'kind': 'ok', 'mark': 'ok'},
], row=31)
fin = D.note(36, end + 22, 1028, 'After two syncs all three devices hold the 30 online edits and the 8 offline ones, in group G, with at most one log message per cell.', 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'One graded scenario', 'plain', 'a device that was offline during the checkpoint rejoins without losing its edits (test threshold: 3 messages)')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
