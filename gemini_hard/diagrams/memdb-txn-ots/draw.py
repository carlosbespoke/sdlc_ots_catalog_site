import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('go-memdb: restore transactions, queries and watches',
        'HashiCorp\'s in-memory database has 30 public methods replaced by panics. The agent restores them from the remaining code, the API comments and the README, so writers commit atomically, readers query consistent snapshots and watchers wake when their results change.')
top, bot = 104, 528
D.zone(20, top, 290, bot - top, 'What still works', 'side', 'hashicorp/go-memdb v1.3.5, Go 1.25, offline')
y = top + 50
for k, t, body, kind, ic in [('rd', 'README.md and API comments', 'describe every method and its contract', 'file', 'markdown'),
        ('sc', 'Schema, Insert, change tracking', 'schema.go, changes.go, watch_few.go and the rest of txn.go', 'svc', 'go'),
        ('ix', 'go-immutable-radix v1.3.1', 'one copy-on-write radix tree per index; every node has a watch channel', 'svc', 'binary-tree'),
        ('rules', 'Constraints', 'keep public names, signatures and Txn.write; no syscall, os/exec, cgo, linkname or embed; text Go diffs only', 'muted', None)]:
    y += D.box(k, 36, y, 258, t, body, kind, ic) + 12
D.zone(330, top, 420, bot - top, 'Agent restores: 30 panicking methods', 'app', 'root package memdb in /app')
files = [('txn.go', 18, 'Abort, Commit, Delete, DeletePrefix, DeleteAll, FirstWatch, First, Last, LongestPrefix, Get, GetReverse, LowerBound, ReverseLowerBound, Defer, iterator Next and WatchCh, Snapshot'),
         ('watch.go', 6, 'NewWatchSet, Add, AddWithLimit, Watch, WatchCtx, WatchCh'),
         ('index.go', 3, 'PrefixFromArgs for string and compound indexes, CompoundMultiIndex.FromArgs'),
         ('filter.go', 2, 'NewFilterIterator, Next'),
         ('memdb.go', 1, 'MemDB.Snapshot')]
y = top + 50
for i, (f, n, body) in enumerate(files[:3]):
    y += D.box(f'f{i}', 346, y, 388, f, body, 'new' if i == 0 else 'svc', 'go', tag=f'{n} STUBS') + 14
for i, (f, n, body) in enumerate(files[3:]):
    D.box(f'g{i}', 346 + i * 200, y, 188, f, body, 'svc', 'go', tag=f'{n} STUB' + ('S' if n > 1 else ''))
D.arrow([(294, top + 200), (346, top + 200)], 'context', lpos=.5, loff=(0, -6))
D.zone(770, top, 310, bot - top, 'Hidden grader', 'grader', 'runs after the session')
D.box('sp', 786, top + 50, 278, '105 required tests', '74 for the restored methods, 31 index and schema regressions', 'fault', 'test-pipe')
y = top + 138
for name, n in [('supplementary', 37), ('index', 28), ('txn', 25), ('integration', 4), ('watch', 4), ('schema', 3), ('filter', 2), ('memdb', 1), ('isolation', 1)]:
    D._t(800, y + 4, name, 12, False, INK); D._t(1052, y + 4, str(n), 12, True, '#c83220', 'end')
    D.el.append(f'<rect x="910" y="{y - 6}" width="{n / 37 * 110:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 19
D.box('sc2', 786, y + 6, 278, 'All or nothing', 'reward 1 only if all 105 pass; the patch is scanned for banned calls first', 'dark')
D.arrow([(750, top + 80), (786, top + 80)], 'patch', lpos=.5, loff=(0, -6))
# bottom: one transaction's life
y0 = bot + 28
end = D.seq(36, y0 + 64, 1028, [('R', 'Reader', 'client'), ('DB', 'MemDB', 'svc'), ('W', 'Write txn', 'svc'), ('WS', 'WatchSet', 'svc')], [
    {'a': 'R', 'b': 'DB', 'label': 'Txn(false).FirstWatch("person", "id", "joe")'},
    {'a': 'DB', 'b': 'R', 'label': 'joe + watch channel of that tree node', 'kind': 'ok'},
    {'a': 'R', 'b': 'WS', 'label': 'ws.Add(ch), then ws.WatchCtx(ctx) blocks'},
    {'a': 'W', 'b': 'DB', 'label': 'Txn(true).Delete("person", joe); Defer(notify)', 'gap': .2},
    {'a': 'R', 'b': 'DB', 'label': 'the old snapshot still returns joe', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'W', 'b': 'DB', 'label': 'Commit(): swap in the new tree roots', 'kind': 'new'},
    {'a': 'DB', 'b': 'WS', 'label': "close the changed node's channel", 'kind': 'new'},
    {'a': 'WS', 'b': 'R', 'label': 'WatchCtx returns nil: the result changed', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'W', 'label': 'then run deferred notify(); Abort() instead would discard the delete', 'kind': 'muted'},
], row=32)
fin = D.note(36, end + 22, 1028, 'A value received on a watched channel must wake WatchCtx the same way a closed channel does.', 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'One transaction, as the restored methods must handle it', 'plain', 'readers keep a consistent snapshot while a writer commits, and watchers wake when their query result changes')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
