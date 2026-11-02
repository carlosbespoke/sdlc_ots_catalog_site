import os, json, csv, re, collections, sys
B = sys.argv[1]
rows = {r[0]: r for r in csv.reader(open(f'{B}/sheet.csv')) if len(r) > 6 and 'horizon' in r[6]}
look = {l.split('\t')[0]: l.split('\t') for l in open(f'{B}/lookup.tsv').read().splitlines()}
EXT = {'.py':'py','.go':'go','.rs':'rs','.java':'java','.ts':'ts','.tsx':'ts','.js':'js','.c':'c','.h':'c','.cc':'cpp','.cpp':'cpp','.tf':'tf','.sql':'sql','.rb':'rb','.kt':'kt','.cs':'cs','.php':'php','.sh':'sh','.lg':'logo','.yml':'yaml','.yaml':'yaml','.scala':'scala','.ex':'ex'}
for name in rows:
    d = f'{B}/tasks/{name}'
    files = json.load(open(f'{d}/files.json')) if os.path.exists(f'{d}/files.json') else []
    cnt = collections.Counter(EXT[os.path.splitext(f)[1]] for f in files if os.path.splitext(f)[1] in EXT)
    df = ''
    for fn in os.listdir(d):
        if 'Dockerfile' in fn:
            t = open(f'{d}/{fn}').read()
            froms = re.findall(r'^FROM\s+(\S+)', t, re.M)
            pk = re.findall(r'(?:apt-get install|pip install|npm install|go install|cargo install|uv pip install)[^\n&]*', t)
            df += ' FROM=' + ','.join(froms) + ' PKG=' + ' | '.join(p[:120] for p in pk[:4])
    tags = ''
    if os.path.exists(f'{d}/task.toml'):
        t = open(f'{d}/task.toml').read()
        tags = ' '.join(re.findall(r'^(?:category|tags|difficulty)\s*=.*', t, re.M))
    r = rows[name]
    does = r[3].split('\n')
    does = ' '.join(x for x in does if x.startswith(('Does', 'Skills')))
    print(f"## {name} | batch={look.get(name,['','',''])[2]} | tax={r[1]}\n{does}\nEXT={dict(cnt.most_common(6))}{df}\n{tags}\n")
