#!/bin/bash
# Reference solution: replace lib/ with the component layout. The components are written as if new; a small
# compatibility layer maps every construct path of the component layout back to the path the same construct had in
# the flat layout (Stack allocateLogicalId) and an Aspect rewrites the values CDK derives from construct paths or unique
# IDs, so production keeps every resource.
set -euo pipefail
cd /workspace/accelerator-platform
rm -rf lib
mkdir -p lib
cp -R /solution/lib/. lib/
for extra in test tests; do
  if [ -d "/solution/$extra" ]; then mkdir -p "$extra"; cp -R "/solution/$extra/." "$extra/"; fi
done
bash scripts/ci.sh | grep -E '^(==|RESULT)'
