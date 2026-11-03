import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('BaGetter: fenced package writes across two replicas',
        'Two NuGet server replicas share one PostgreSQL database and one S3 bucket. The agent changes the C# server so that every version write stays consistent through races, crashes and network cuts.')
D.zone(20, 92, 200, 438, 'Clients', 'client')
D.zone(236, 92, 284, 438, 'BaGetter cluster', 'app', 'C# / .NET 9 source in /app')
D.zone(540, 92, 222, 438, 'Hidden grader', 'grader', 'proxies and process faults')
D.zone(782, 92, 298, 438, 'Sidecars', 'side', 'internal network, no internet')
D.box('p1', 34, 142, 172, 'dotnet nuget push', "v2.0.0 'alpha'", 'client')
D.box('p2', 34, 300, 172, 'dotnet nuget push', "v2.0.0 'beta', same moment", 'client')
D.box('rd', 34, 384, 172, 'restore / download', 'from either replica', 'client')
D.box('op', 34, 452, 172, 'operator', 'API key', 'client')
D.box('A', 252, 142, 252, 'Replica A', 'push, indexing and S3 storage services', 'svc', 'dotnet', tag='FAULTED')
D.box('B', 252, 300, 252, 'Replica B', 'same build and configuration', 'svc', 'dotnet')
D.box('R', 252, 430, 252, 'POST /api/v2/admin/reconcile', 'reclaims expired writes, removes orphan objects', 'new', tag='NEW')
D.box('hold', 556, 136, 190, 'S3 hold proxy', 'freezes a PUT mid-flight', 'fault')
D.box('cut', 556, 220, 190, 'DB cut proxy', 'cuts the database link 4 s', 'fault')
D.box('kill', 556, 372, 190, 'Process faults', 'kill or SIGSTOP a replica mid-push', 'fault')
D.store('S3', 800, 136, 262, 'LocalStack S3', 'bucket packages: packages/{id}/{version}/ .nupkg + .nuspec', 'amazons3')
D.store('PG', 800, 280, 262, 'PostgreSQL 16', 'package rows, plus write claims with a 3 s expiry and a fencing token', 'postgresql')
D.link('p1', 'r', 'A', 'l')
D.link('p2', 'r', 'B', 'l', fb=.4)
D.link('rd', 'r', 'B', 'l', via=[(230, 414), (230, 345)], fb=.75)
D.link('op', 'r', 'R', 'l', fa=.5, fb=.5, via=[(230, 482), (230, 468)])
D.arrow([(504, 160), (556, 160)])
D.arrow([(746, 160), (800, 160)], 'PUT objects', lpos=.5)
D.arrow([(504, 190), (528, 190), (528, 250), (556, 250)])
D.arrow([(746, 250), (770, 250), (770, 318), (800, 318)], 'claim', lpos=.12)
D.arrow([(504, 312), (786, 312), (786, 212), (800, 212)], 'PUT objects (no proxy)', lpos=.3)
D.arrow([(504, 345), (800, 345)], 'claim and commit (no proxy)', lpos=.45)
D.arrow([(504, 476), (931, 476), (931, 371)], 'reclaim expired claims, delete unowned objects', lpos=.45)
y0 = 556
end = D.seq(36, y0 + 64, 1028, [('A', 'Replica A', 'svc'), ('PG', 'PostgreSQL', 'svc'), ('S3', 'S3 bucket', 'svc'), ('B', 'Replica B', 'svc')], [
    {'a': 'A', 'b': 'PG', 'label': 'claim 3.0.2 (token 7)'},
    {'a': 'A', 'b': 'S3', 'label': "PUT 'partitioned', held by the proxy", 'kind': 'fault'},
    {'a': 'A', 'label': 'database link cut for 4 s: the claim expires', 'kind': 'fault', 'mark': 'bolt'},
    {'a': 'B', 'b': 'PG', 'label': 'claim 3.0.2 (token 8)'},
    {'a': 'B', 'b': 'S3', 'label': "PUT 'winner'"},
    {'a': 'B', 'b': 'PG', 'label': 'commit: 201 Created', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'A', 'b': 'S3', 'label': 'late PUT released', 'kind': 'fault', 'gap': .2},
    {'a': 'S3', 'label': "must not replace the 'winner' bytes", 'kind': 'fault'},
    {'a': 'A', 'b': 'PG', 'label': 'commit with token 7', 'kind': 'fault', 'mark': 'x'},
    {'a': 'B', 'b': 'S3', 'label': 'reconcile: delete the orphan objects', 'kind': 'new', 'gap': .2},
], row=31)
fin = D.note(36, end + 22, 1028, "Both replicas then serve the 'winner' bytes, and exactly two objects remain under packages/{id}/3.0.2/.", 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'One graded scenario', 'plain', 'a writer is cut off after its PUT and comes back late')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
