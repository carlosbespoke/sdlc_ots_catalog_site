import json,sys
def walk(n,d=0):
    t=n['type']
    if t=='doc': print(f"D  TITLE: {n['title']}")
    elif t=='section': print('  '*d+f"{n['id']} [S{n['level']}] {n['title']}")
    elif t in('sentence','item'): print('  '*d+f"{n['id']} {n['text']}")
    elif t=='block': print('  '*d+f"{n['id']} [block] {n['text'][:90].replace(chr(10),' ')}")
    else: print('  '*d+f"{n['id']} [{t}]")
    for c in n.get('children',[]): walk(c,d+1)
walk(json.load(open(sys.argv[1])))
