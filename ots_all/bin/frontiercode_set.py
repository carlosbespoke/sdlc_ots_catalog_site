# A FrontierCode-shaped subset of the OTS catalog: PR-sized bug fixes, features, performance and security fixes in real
# open-source repos, with a spread of languages (Python about 30%, Go about 25%, every other-language task kept).
# Leaves out the multi-service system-design tasks (pdk-*) and the test-writing-only tasks (tests-*).
# Within each language and type cell: a repo not used yet first, then a domain used less, then more graded runs.
#     python bin/frontiercode_set.py  ->  frontiercode_set.csv
import csv, collections, os, re, zlib
H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = [r for r in csv.DictReader(open(f'{H}/ots_tasks.csv'))
     if r['Catalog'] in ('System design', 'Feature implementation') or r['Catalog'].startswith('Diagnosis')]
def kind(r):
    t = r['Task']
    if t.startswith('tests'): return None
    if r['Catalog'] == 'System design':
        if t.startswith('pdk'): return None
        return 'Performance' if ('perf' in t or 'optimiz' in t) else 'Feature'
    if r['Catalog'] == 'Feature implementation': return 'Feature'
    return 'Security fix' if r['Domain'] == 'Security' else 'Bug fix'
def repo(t):
    m = re.match(r'(.+?)-[0-9a-f]{8}-blind', t)
    if m: return m.group(1)
    t = re.sub(r'-(canonical|pdk|pipeline)-ots$|-ots$', '', t)
    return t.split('-')[1] if t.startswith('sdrift-') else t.split('-')[0]
QUOTA = {  # (language, type) -> tasks; None = all of them
    ('Python', 'Feature'): 18, ('Python', 'Performance'): None, ('Python', 'Security fix'): 2, ('Python', 'Bug fix'): 5,
    ('Go', 'Feature'): 18, ('Go', 'Performance'): None, ('Go', 'Security fix'): 2, ('Go', 'Bug fix'): 4,
}
cells = collections.defaultdict(list)
for r in R:
    k = kind(r)
    if k: cells[(r['Language'], k)].append(r)
used_repo, used_dom, out = set(), collections.Counter(), []
# small cells first, so the cells taken whole claim their repos before the Python and Go picks
for key in sorted(cells, key=lambda k: (k in QUOTA and QUOTA[k] is not None, k)):
    pool, n = cells[key], QUOTA.get(key)
    n = len(pool) if n is None else n
    for _ in range(n):
        pool.sort(key=lambda r: (repo(r['Task']) in used_repo, used_dom[r['Domain']], -int(r['Graded runs'] or 0),
                                 zlib.crc32(r['Task'].encode())))
        r = pool.pop(0); used_repo.add(repo(r['Task'])); used_dom[r['Domain']] += 1
        out.append({'Task': r['Task'], 'Horizon task id': r['Horizon task id'], 'Task version': r['Task version'],
                    'Horizon URL': f"https://horizon.bespokelabs.ai/tasks/{r['Horizon task id']}",
                    'Source catalog': r['Catalog'], 'Task type': key[1], 'Language': r['Language'], 'Repo': repo(r['Task']),
                    'Domain': r['Domain'], 'Sub-domain': r['Sub-domain'], 'Seniority': r['Seniority'],
                    'Graded runs': r['Graded runs'], 'Average reward (all models)': r['Average reward (all models)']})
LANG = ['Python', 'Go', 'C', 'Rust', 'TypeScript', 'C#', 'Java']
TYPE = ['Bug fix', 'Feature', 'Performance', 'Security fix']
out.sort(key=lambda o: (LANG.index(o['Language']), TYPE.index(o['Task type']), o['Task']))
with open(f'{H}/frontiercode_set.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(out[0])); w.writeheader(); w.writerows(out)
print(len(out), 'tasks;', len({o['Repo'] for o in out}), 'repos')
print(collections.Counter(o['Language'] for o in out)); print(collections.Counter(o['Task type'] for o in out))
print(collections.Counter(o['Source catalog'] for o in out))
