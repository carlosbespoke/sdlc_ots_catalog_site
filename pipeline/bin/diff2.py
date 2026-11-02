import sys, csv
from openpyxl import load_workbook
B = sys.argv[1]
ws = load_workbook(f'{B}/v2/sheet.xlsx', data_only=True).worksheets[0]
rows = [[('' if c is None else str(c)) for c in r] for r in ws.iter_rows(values_only=True)]
for r in rows[1:4]: print('INTRO:', r[0])
hi = next(i for i, r in enumerate(rows) if r[0] == 'Rank'); H = rows[hi]
new = {r[1]: dict(zip(H, r)) for r in rows[hi+1:] if len(r) > 1 and r[1]}
old = {r[0]: r for r in csv.reader(open(f'{B}/sheet.csv')) if len(r) > 6 and 'horizon' in r[6]}
print('tasks now:', len(new), 'before:', len(old))
print('ADDED:', sorted(set(new) - set(old)))
print('REMOVED:', sorted(set(old) - set(new)))
idc = lambda u: u.rsplit('/', 1)[-1]
tax_changed = 0
for k in sorted(set(new) & set(old)):
    o, n = old[k], new[k]
    if idc(o[6]) != idc(n['Horizon']): print('  ID CHANGED', k, idc(o[6]), '->', idc(n['Horizon']))
    if str(o[7]).strip() != str(n['Version']).replace('.0', '').strip(): print('  VERSION', k, o[7], '->', n['Version'])
    if o[1].strip() != n['Taxonomy'].strip(): tax_changed += 1
    if o[2].strip() != n['Recommendation source'].strip(): pass
print('taxonomy text changed for', tax_changed, 'tasks; examples:')
for k in list(sorted(set(new) & set(old)))[:4]:
    print(' ', k, '|', repr(old[k][1]), '->', repr(new[k]['Taxonomy'][:200]))
import json; json.dump(new, open(f'{B}/v2/new.json', 'w'))
