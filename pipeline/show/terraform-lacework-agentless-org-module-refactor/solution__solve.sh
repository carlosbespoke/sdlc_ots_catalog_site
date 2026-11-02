#!/bin/bash
# Reference solution: replace the flat root module with the modular layout. moved.tf maps every legacy address
# to its module address, so the plan against the production state is moves only.
set -euo pipefail
cd /workspace/infra
find . -maxdepth 1 -type f -name '*.tf' ! -name providers.tf ! -name versions.tf -delete
cp -R /solution/infra/. /workspace/infra/
terraform init -input=false -no-color >/dev/null
terraform plan -refresh=false -input=false -lock=false -no-color | tail -n 3
