# PseudoPoll production infrastructure

This directory is the deployable AWS portion of PseudoPoll: the REST API, Lambda microservices,
queue-based vote processing, DynamoDB persistence, and EventBridge choreography. The original
Cloudflare, ACM, IoT authorizer, EventBridge Pipes, log resource policy, and standalone SQS redrive
policy resources are not part of this offline production-state snapshot.

CI runs `scripts/ci-plan.sh`. It initializes from the checked-in provider constraints, validates the
configuration, plans without refreshing the recorded state, and applies the plan-safety policy.
