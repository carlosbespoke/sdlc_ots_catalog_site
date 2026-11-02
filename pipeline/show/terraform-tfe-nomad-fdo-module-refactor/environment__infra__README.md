# Terraform Enterprise on Nomad (prod)

This repository manages the production Terraform Enterprise FDO installation on a small
Nomad cluster in `us-east-1`. It grew from the original two-node deployment into three
node groups spread across the VPC, backed by PostgreSQL, Redis and encrypted S3 storage.

The Terraform is intentionally split by concern, but all resources still live in the root
module. `network.tf` owns the VPC and routing, `compute.tf` the Nomad nodes, `data.tf` the
TFE data services, and `identity.tf` the instance role.

This checkout is an offline copy of production. Run `scripts/ci-plan.sh` to perform the same
refresh-free plan and policy checks as CI. Do not refresh the recorded state: this sandbox
has no AWS credentials or network access.
