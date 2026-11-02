# Wrap paths, file names, identifiers, env vars, flags and commands in prose with backticks (code style).
import re
EXT = r'(?:py|sh|md|json|jsonl|toml|ya?ml|go|rs|tf|tfvars|tfstate|ts|tsx|js|txt|csv|tsv|sql|patch|diff|db|sqlite|parquet|xml|7z|zip|c|h|cc|cpp|hpp|java|kt|lock|cfg|ini|rst|html|proto|star|whl|so|bin|log|env|mod|sum)'
DIRS = r'(?:app|tests?|environment|workspace|workdir|data|srv|opt|src|infra|docs|solution|lib|cmd|internal|pkg|scripts|logs|tmp|usr|etc|var|home|repo|deployed|policies|terraform|pulumi|integration_tests|models|macros|seeds)'
CMDS = r'(?:terraform (?:plan|apply|validate|fmt|init)|pulumi (?:preview|up)|cdk (?:synth|diff)|dbt (?:build|test|run)|go (?:test|build|vet)|cargo (?:test|build)|git (?:diff|log)|npm (?:test|run)|poe check|mvn test|python manage\.py \w+|pytest)'
PATTERNS = [
    CMDS,
    r'(?<![\w`])(?:\.{1,2}|~)?/(?:[\w.\-]+/)*[\w.\-]*[\w/]',                    # absolute or ./ paths
    r'(?<![\w`/])' + DIRS + r'/(?:[\w.\-]+/?)*',                                 # known relative dirs
    r'(?<![\w`/])[\w\-]+(?:/[\w.\-]+)*\.' + EXT + r'\b',                          # file names
    r'(?<![\w`-])--[a-z][\w-]+',                                                 # CLI flags
    r'\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b',                                        # ENV_VARS
    r'\b[a-z][a-z0-9]*(?:_[a-z0-9]+)+\b',                                        # snake_case identifiers
    r'\b[A-Z][a-z]+(?:[A-Z][a-z0-9]+)+(?:\.[A-Za-z_]\w*)+\b',                     # Type.method
]
RX = re.compile('|'.join(f'(?:{p})' for p in PATTERNS))
def codeify(text):
    if not isinstance(text, str) or not text: return text
    parts = re.split(r'(`[^`]*`)', text)
    out = []
    for i, p in enumerate(parts):
        if i % 2: out.append(p); continue
        def rep(m):
            s = m.group(0); trail = ''
            while s and s[-1] in '.,;:)': trail = s[-1] + trail; s = s[:-1]
            if not s.strip('/') or (s.endswith('/') and s.count('/') == 1 and len(s) < 3): return m.group(0)
            return f'`{s}`{trail}' if s else m.group(0)
        out.append(RX.sub(rep, p))
    return ''.join(out)
