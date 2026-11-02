import sys, csv
from openpyxl import load_workbook
B = sys.argv[1]
wb = load_workbook(f'{B}/v2/sheet.xlsx', data_only=True)
for ws in wb.worksheets: print('TAB', ws.title, ws.max_row, ws.max_column)
old = {r[0]: r for r in csv.reader(open(f'{B}/sheet.csv')) if len(r) > 6 and 'horizon' in r[6]}
for ws in wb.worksheets:
    rows = [[('' if c is None else str(c)) for c in r] for r in ws.iter_rows(values_only=True)]
    hdr = next((r for r in rows if r and r[0] == 'Task'), None)
    print('\n==', ws.title, 'header:', hdr)
    if not hdr: 
        for r in rows[:8]: print('  ', [x[:40] for x in r if x])
        continue
    new = {r[0]: r for r in rows if r and r[0] and r[0] != 'Task' and any('horizon' in x for x in r)}
    print('tasks:', len(new), '| added:', sorted(set(new)-set(old)), '| removed:', sorted(set(old)-set(new)))
    for k in sorted(set(new) & set(old)):
        o, n = old[k], new[k]
        for i in range(min(len(o), 8)):
            if i < len(n) and o[i].strip() != n[i].strip():
                print(f'  CHANGED {k} col {hdr[i]!r}: {o[i][:80]!r} -> {n[i][:80]!r}')
