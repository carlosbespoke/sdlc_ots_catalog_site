# GGJam production infrastructure

The production AWS infrastructure of GGJam, a Ghost-backed Gatsby publishing stack. Ghost runs privately in ECS behind
an internal load balancer, MariaDB stores editorial content, S3 holds published artifacts, build artifacts and the log
archive, and a private API Gateway invokes the publication webhook. Site components, delivery channels and Gatsby build
lanes are driven by the `site_components`, `delivery_channels` and `build_lanes` variables: the team adds one by adding a
key. Administrative access is limited to the corporate VPN ranges in `admin_cidr_blocks`.

| File | Contents |
|---|---|
| `network.tf` | VPC, subnets, NAT, routes, endpoints, network ACL, network inventory parameters, NAT alarms |
| `security.tf` | security groups and their rules |
| `content.tf` | content KMS key, site artifact buckets, publishing queues/topics/logs/alarms, locks table, MariaDB, credentials |
| `runtime.tf` | load balancer and listeners, ECS cluster and task, jumpbox and build-runner fleets, release runner, alarms |
| `delivery.tf` | publication webhook (Lambda + private API), delivery channels |
| `build.tf` | build lanes: queues, topics, artifact buckets, logs, alarms, worker policies |
| `logging.tf` | central log archive bucket |

## CI

`scripts/ci-plan.sh` is what CI runs on every change: an offline `terraform init`, `terraform validate`, a plan against
the recorded production state (`terraform.tfstate`) without refreshing AWS, and the platform team's policy pack in
`policies/` evaluated by conftest on the plan's JSON form. The provider is wired for this offline mode (see
`providers.tf`), so nothing in the configuration may need an AWS API call at plan time. Run `terraform fmt` and
`scripts/ci-plan.sh` before review.

The policy pack is owned by the platform security team; `policies/README.md` lists its rules.

## Exceptions

Findings the security team has accepted are recorded in `exceptions/register.json`; CI passes it to conftest as data
(`--data exceptions`), and `policies/EXCEPTIONS.md` describes what an entry must contain. The register is reviewed
quarterly; entries are approved for one review period at a time.
