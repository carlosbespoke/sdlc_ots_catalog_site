# Render the D2 environment diagrams for samples that are not OTS catalog examples, with the catalog pipeline's renderer and style.
import json, os, sys
P = '/Users/carlos/code/sdlc_final_samples/pipeline'; H = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.argv = [sys.argv[0], P]; sys.path.insert(0, f'{P}/bin')
from d2gen import render
os.makedirs(f'{H}/catalog/assets', exist_ok=True)
specs = json.load(open(f'{H}/cat/diagrams.json'))
ok = sum(render(s, f"{H}/catalog/assets/env-{s['name']}.svg") for s in specs)
print('rendered', ok, 'of', len(specs))
