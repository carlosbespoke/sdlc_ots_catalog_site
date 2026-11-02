# Terraform Enterprise air-gap production stack

This repository provisions the production `tfeairgap` installation in `us-east-1`. It keeps the original stack's
external-services architecture: installation artifacts are staged in S3, PostgreSQL stores application data, and an
Auto Scaling group runs Terraform Enterprise behind an application load balancer. The network spans three availability
zones; artifact intake is tracked with queues, parameters, logs, and alarms so operators can audit each package before
an air-gap upgrade.

The checked-in state is the production migration baseline. Run `scripts/ci-plan.sh` to reproduce CI's offline plan and
policy checks. A clean change must preserve all managed objects.

