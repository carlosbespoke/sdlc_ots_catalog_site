#!/bin/bash
# Reference solution: the solver-editable configuration is replaced by the reference (/solution/gold); then the CI
# apply is rehearsed against freshly restored services (grading applies it again in the verifier).
set -euo pipefail
cd /workspace/platform
find . -path ./.terraform -prune -o -type f -name '*.tf' ! -path ./versions.tf ! -path ./providers.tf ! -path ./backend.tf ! -path ./variables.tf -print0 | xargs -0 -r rm -f
cp -R /solution/gold/. /workspace/platform/
terraform init -input=false -no-color >/dev/null
platform-reset >/dev/null
terraform apply -auto-approve -input=false -no-color | tail -n 2
terraform plan -detailed-exitcode -input=false -no-color >/dev/null && echo "second plan clean"
