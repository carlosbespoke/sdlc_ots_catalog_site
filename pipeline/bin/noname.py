# Remove direct mentions of task names from prose.
import re, json, os
B = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_names = set()
for f in os.listdir(f'{B}/rfc/t'):
    n = json.load(open(f'{B}/rfc/t/{f}'))['name']; _names.add(n)
    b = re.sub(r'^tests-(half-alt|half|quarter|50pct|75pct|25pct)-(go-|python-)?', '', n); _names.add(re.sub(r'(-ots|-shared)$', '', b))
NAMES = sorted((n for n in _names if len(n) >= 6), key=len, reverse=True)
NAME_RX = '(?:' + '|'.join(re.escape(n) for n in NAMES) + ')'
Q = r'`?' + NAME_RX + r'`?'
LIST = Q + r'(?:\s*(?:,|and|or)\s*' + Q + r')*'
def strip_names(text):
    if not isinstance(text, str) or not text: return text
    t = text
    t = re.sub(r'\s*\((?:e\.g\.,?\s*|for example,?\s*|see\s*|as in\s*)?' + LIST + r'\)', '', t)          # (name, name)
    t = re.sub(r'(?:,\s*|\s+)(?:e\.g\.|for example|such as|as in|see)\s+' + LIST, '', t)                # ", e.g. name"
    t = re.sub(r'[:,]\s*' + LIST + r'(?=\s*[.;]|\s*$)', '', t)                                             # ": name." at end
    t = re.sub(r'\b(?:in|from|for|of|with|by)\s+(?:the\s+)?(?:task\s+)?' + Q + r'\b', lambda m: m.group(0).split()[0] + ' one task', t)
    t = re.sub(Q, 'this task', t)                                                                         # anything left
    t = re.sub(r'\s+([.,;:])', r'\1', t); t = re.sub(r'\(\s*\)', '', t); t = re.sub(r'\s{2,}', ' ', t)
    return t.strip()
FIX = [
    (r'this task ships a pre-laid data layer', 'The Java example ships a pre-laid data layer'),
    (r'this task ships a library with panicking stubs', 'The Go example ships a library with panicking stubs'),
    (r'this task, this task and this task in Go', 'three Go tasks'),
    (r'\bThe this task\b', "One task's"),
    (r'this task and this task appear', 'some repositories appear'),
    (r'while the catalog name is this task\.', 'while the catalog uses a different name.'),
    (r'as this task\?', 'as the two example tasks?'),
    (r'(^|[.?]\s+)this task\b', r'\1One task'),
]
_strip = strip_names
def strip_names(text):
    t = _strip(text)
    if not isinstance(t, str): return t
    for a, b in FIX: t = re.sub(a, b, t)
    t = re.sub(r'([.?]\s+)([a-z])', lambda m: m.group(1) + m.group(2).upper(), t)
    return t
