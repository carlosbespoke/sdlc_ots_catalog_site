# Add the signed-off Final category (and a batch-group crosstab) to the ready-for-client summary.
import sys, json, collections
B = sys.argv[1]
S = json.load(open(f'{B}/rfc/summary.json')); X = json.load(open(f'{B}/rfc/explorer.json'))
I = {k: i for i, k in enumerate(X['keys'])}; g = lambda r, k: X['dicts'][k][r[I[k]]]
dims = {'Final category': collections.Counter(g(r, 'final') for r in X['rows']).most_common(),
        'Final category basis': collections.Counter(g(r, 'fstat') for r in X['rows']).most_common(),
        'Batch group': collections.Counter(g(r, 'fam') for r in X['rows']).most_common()}
dims.update(S['dims']); S['dims'] = dims
cols = [k for k, _ in dims['Final category']]; rows = [k for k, _ in dims['Batch group']]
m = collections.Counter((g(r, 'fam'), g(r, 'final')) for r in X['rows'])
S['xtab'] = {'title': 'Batch group × Final category', 'rows_label': 'Batch group', 'cols_label': 'Final category', 'cols': cols,
             'rows': [[b, [m[(b, c)] for c in cols]] for b in rows]}
S['notes'] = [n for n in S['notes'] if not n.startswith('Final category')] + [
 'Final category: the client-facing classification signed off on 27 Oct 2026. It follows the batch group, except that spec-drift tasks fold into Diagnosis, Debugging, and Bug Fixing, and the 204 fault-tolerance candidates (DeepSWE, Cohere system-design and durability tasks) were split into System design, Fault tolerance or Feature implementation by reading each full instruction. The 5 SRE tasks are parked.']
json.dump(S, open(f'{B}/rfc/summary.json', 'w'), indent=1)
print({k: len(v) for k, v in dims.items()})
