#!/bin/bash
# What CI runs on every pull request: type check, the code rules for lib/, and for every deployed environment a
# synth compared with the recorded production templates in deployed/<stage>/.
#
# The comparison ignores the `component` tag: the template changes the componentization is allowed to make.
# Everything else must be identical.
set -euo pipefail
cd "$(dirname "$0")/.."
npx tsc --noEmit
node tools/check-rules.js . --code-dir lib
status=0
for dir in deployed/*/; do
  stage=$(basename "$dir")
  rm -rf "cdk.out/$stage"
  npx cdk synth --quiet --no-version-reporting --path-metadata false --asset-metadata false --no-lookups --no-notices \
    -c stage="$stage" -o "cdk.out/$stage"
  echo "== $stage"
  python3 tools/compare-templates.py "deployed/$stage" "cdk.out/$stage" --ignore-tag component \
    || status=1
done
exit $status
