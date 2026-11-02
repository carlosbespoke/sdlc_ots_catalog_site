# Earth observation STAC API infrastructure (sandbox)

This is the Terraform for the live STAC API sandbox in `us-east-1`. It keeps the source
blueprint's PgSTAC and stac-fastapi ECS services, encrypted S3 data bucket and PgSTAC EFS
storage, and expands the network to three availability zones. The four data-processing
folders are backed by queues, topics, logs and backlog alarms so ingestion work can be
operated independently at each stage.

| File | What is in it |
| --- | --- |
| `network.tf` | VPC, public/workbench subnets, internet and NAT gateways, routing, S3 endpoint, per-AZ workbench profiles and the priority-selected workbench subnet and launch template |
| `flow_logs.tf` | VPC flow logs and their CloudWatch/IAM support |
| `storage.tf` | encrypted data bucket, PgSTAC EFS, KMS keys and consumer policies |
| `pipeline.tf` | stage markers, SQS queues, SNS topics, logs, alarms, per-stage configuration and ordered pipeline parameters |
| `services.tf` | ECR, ECS, load balancers, IAM, security groups, secrets and logs for PgSTAC and stac-fastapi |
| `outputs.tf` | values consumed by operators and adjacent stacks |

The SageMaker notebook instance, application autoscaling policies and targets, and the EFS
backup policy from the original reusable components are not present in this offline copy.

## Working on the stack

This checkout has no AWS access. The AWS provider is supplied by a local mirror and
`terraform.tfstate` is a recorded copy of the deployed sandbox state.

Run `scripts/ci-plan.sh` to perform the same offline initialization, validation,
refresh-free plan and policy checks used in CI.
