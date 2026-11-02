#!/usr/bin/env bash
# The checks CI runs on every change to this stack: offline init, validate, a refresh-free plan against the recorded
# production state, and the platform policy pack in policies/ evaluated by conftest on the plan's JSON form (every
# rule package of the pack), with the team's exceptions register (exceptions/register.json) loaded as data: the
# register's valid entries waive the findings they name (policies/EXCEPTIONS.md).
set -euo pipefail
cd "$(dirname "$0")/.."

terraform init -input=false -no-color >/dev/null
terraform validate -no-color
terraform plan -refresh=false -input=false -lock=false -no-color -out=.ci.tfplan "$@"
terraform show -json .ci.tfplan > .ci-plan.json
conftest test --no-color --all-namespaces --policy policies --data exceptions .ci-plan.json
