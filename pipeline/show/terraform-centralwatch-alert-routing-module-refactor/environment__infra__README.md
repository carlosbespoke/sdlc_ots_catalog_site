# centralwatch infrastructure (prod)

This repository deploys the central monitoring account pipeline in `us-east-1`. EventBridge
rules collect operational event families into an encrypted SQS queue, the enricher Lambda
routes them using SSM metadata, and per-team, per-severity and per-channel topics deliver
notifications. Dedicated dead-letter queues, log groups and alarms make failures observable.

The stack began as the AWS sample `central-monitoring-account`. Production added more event
families and notification teams while retaining the original flat, list-indexed layout.

| File | Responsibility |
| --- | --- |
| `eventbridge.tf` | central bus, source rules and targets, source log groups, dead-letter queues and alarms |
| `teams.tf` | team topics, subscriptions, delivery queues, log groups, alarms and routing parameters |
| `severities.tf` | severity topics, queues, policies, subscriptions, log groups, alarms and routing parameters |
| `channels.tf` | delivery-channel topics, queues, policies, subscriptions, log groups, alarms and routing parameters |
| `queues.tf` | central alarm and dead-letter queues |
| `enricher.tf` | Lambda archive, function, event mapping, shared parameters and pipeline alarms |
| `iam.tf` | EventBridge and Lambda roles and policies |
| `kms.tf` | shared encryption key and alias |

## CI

This checkout is offline. The provider is installed from a local mirror and
`terraform.tfstate` is a production-state copy. Run `scripts/ci-plan.sh` to perform the same
refresh-free plan and policy checks as CI.
