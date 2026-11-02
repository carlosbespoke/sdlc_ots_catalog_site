# v6mesh production infrastructure

This stack bootstraps the two self-managed IPv6 Kubernetes clusters used for mesh testing. The
`alpha` and `beta` clusters each have their own VPC, public and workload subnets in three
availability zones, DNS64/NAT64 egress through a NAT gateway in every zone, a control-plane auto
scaling group, and three independently sized worker pools. Bootstrap artifacts are kept in S3 and
the operational alarms fan out through SNS and SQS.

The layout is intentionally the same flat root configuration that grew out of the original
dual-cluster prototype:

| File | Contents |
| --- | --- |
| `network.tf` | both dual-stack VPCs, subnets, gateways, routes, and route-table associations |
| `bootstrap.tf` | KMS, S3 bootstrap artifacts, DynamoDB state, and SSM configuration catalogs |
| `platform.tf` | control planes, worker pools, IAM, security groups, launch templates, and ASGs |
| `observability.tf` | alarm delivery and per-pool capacity alarms |
| `outputs.tf` | values consumed by the mesh deployment pipeline |

There is no AWS access in this checkout. Run `scripts/ci-plan.sh` to execute the same offline,
refresh-free plan and policy checks as CI.
