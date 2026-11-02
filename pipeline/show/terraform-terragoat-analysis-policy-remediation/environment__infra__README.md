# Terragoat production analysis platform

This Terraform stack runs Terragoat's shared production network, per-service compute pools, analysis queues and
functions, service data stores, and the retained compatibility hosts. `var.services` drives each analysis workload;
`var.availability_zones` drives the repeated public, private, and database network tiers.

CI runs `scripts/ci-plan.sh` against the recorded production state and checks the resulting plan with the platform
policy pack in `policies/`. The provider mirror is local, so CI does not contact AWS.
