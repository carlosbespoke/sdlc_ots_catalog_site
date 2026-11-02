# Rider onboarding production infrastructure

This repository provisions the production user-onboarding workflow for the ride-hailing platform. API Gateway starts
the Step Functions workflow, which invokes one Lambda worker per onboarding stage. Cognito owns user identities while
DynamoDB, SNS and SQS hold audience-specific profiles and notifications. The static S3 bucket serves the onboarding
help page.

The stack is intentionally kept in its original flat layout. Resource lists use stable positional ordering because the
recorded production state predates keyed resources.

CI runs `scripts/ci-plan.sh` against the checked-in state snapshot. It initializes from the offline provider mirror,
uses `terraform plan -refresh=false`, and checks the plan with the repository policy.
