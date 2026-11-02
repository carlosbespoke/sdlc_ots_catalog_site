#!/bin/bash
# Reference solution: the Pulumi (TypeScript) port of /workspace/terraform - one ComponentResource per Terraform
# module, every Terraform resource instance under its imported URN, one config key per Terraform variable with the
# Terraform defaults, the Terraform outputs as stack outputs. Previews as no changes against the production stack.
set -euo pipefail
cd /workspace/pulumi
rm -f index.ts
cp -R /solution/pulumi/. /workspace/pulumi/
pulumi preview --refresh=false --non-interactive -s dev 2>&1 | tail -n 4
