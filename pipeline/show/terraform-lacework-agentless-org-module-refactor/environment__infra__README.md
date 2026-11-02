# Lacework agentless scanning production stack

This is the production deployment of the Lacework agentless scanner for the organization. It follows the upstream
multi-account Lacework Organization example: global IAM, Secrets Manager and S3 resources live once in the scanning
account, a complete VPC and Fargate scanner is deployed for every enabled region, and a snapshot role is installed for
every monitored account. Regional KMS keys and alarms were added after the initial rollout so task logs are encrypted
and failures page the security operations team.

The regional and monitored-account lists are deliberately ordered to match the rollout order. Their `count` indexes
are part of the current Terraform state, so changing either list's order would retarget production resources.

CI is run with `scripts/ci-plan.sh`. It initializes from the company provider mirror, validates the configuration,
plans with refresh disabled against the checked-in production-state copy, and evaluates the plan guardrails. The
provider configuration is maintained by the platform team and must not be changed.
