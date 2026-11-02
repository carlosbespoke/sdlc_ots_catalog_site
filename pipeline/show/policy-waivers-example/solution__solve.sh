#!/bin/bash
# Reference solution: the remediated configuration files, copied over the repository. Every recorded resource is
# updated in place (or left alone), new resources are only of the allowed types, and every per-key fix is written once
# over the stack's collection variables.
set -euo pipefail
cd /workspace/infra
cp -R /solution/infra/. /workspace/infra/
terraform fmt -check -recursive >/dev/null
terraform init -input=false -no-color >/dev/null
scripts/ci-plan.sh | tail -n 4
