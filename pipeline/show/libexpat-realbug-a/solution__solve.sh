#!/usr/bin/env bash
# Reference solution: the upstream fix of each bug, and the expected report.
# Proves the task is solvable. Never present in the agent image.
set -euo pipefail
cd /workspace/repo
git apply --whitespace=nowarn /solution/solution.patch
mkdir -p /app
cat > /app/rca.json <<'RCA'
{
  "causes": [
    {
      "file": "expat/lib/xmlparse.c",
      "function": "accountingGetCurrentAmplification"
    },
    {
      "file": "expat/lib/xmlparse.c",
      "function": "internalEntityProcessor"
    },
    {
      "file": "expat/lib/xmlparse.c",
      "function": "XML_GetBuffer"
    },
    {
      "file": "expat/lib/xmltok.c",
      "function": "doParseXmlDecl"
    }
  ]
}
RCA
