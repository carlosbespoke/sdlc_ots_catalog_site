"""Turn the single-file catalog (ots-catalogs-all-models.html) into the page published as a claude.ai Artifact.

The Artifact host wraps the page in its own doctype, html, head and body, so this drops those tags and keeps the
title, the stylesheet, the views and the scripts. The page keeps its single light look.

    python build_artifact.py   ->  artifact/coding-ots-rl-envs.html
"""
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, 'ots-catalogs-all-models.html')
OUT = os.path.join(HERE, 'artifact', 'coding-ots-rl-envs.html')

doc = open(SRC, encoding='utf-8').read()
style = re.search(r'<style>.*?</style>', doc, re.S).group(0)
body = re.search(r'<body id="top">(.*)</body>', doc, re.S).group(1)
page = ('<title>Coding OTS RL Envs</title>\n'
        '<meta name="color-scheme" content="light">\n'
        + style + '\n<div id="top">' + body + '</div>\n')
os.makedirs(os.path.dirname(OUT), exist_ok=True)
open(OUT, 'w', encoding='utf-8').write(page)
print(f'wrote {OUT} ({len(page) / 1e6:.1f} MB)')
