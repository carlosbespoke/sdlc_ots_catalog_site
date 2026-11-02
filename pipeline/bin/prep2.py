import json, sys, csv
B = sys.argv[1]
new = json.load(open(f'{B}/v2/new.json'))
old = {l.split('\t')[0] for l in open(f'{B}/tasks.tsv').read().splitlines() if l.strip()}
with open(f'{B}/v2/tasks.tsv', 'w') as f:
    for k, r in new.items():
        f.write(f"{k}\t{r['Horizon'].rsplit('/',1)[-1]}\t{r['Version']}\n")
with open(f'{B}/v2/tasks_new.tsv', 'w') as f:
    for k, r in new.items():
        if k not in old: f.write(f"{k}\t{r['Horizon'].rsplit('/',1)[-1]}\t{r['Version']}\n")
# a CSV in the old column layout so digest.py works
with open(f'{B}/v2/sheet.csv', 'w', newline='') as f:
    w = csv.writer(f)
    for k, r in new.items():
        w.writerow([k, r['Taxonomy'], r['Recommendation source'], r['What it does, why it matters, skills'], r['Why selected / portfolio contribution'], r['Prompt and evidence notes'], r['Horizon'], r['Version']])
print(sum(1 for _ in open(f'{B}/v2/tasks_new.tsv')))
