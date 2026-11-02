# CSYE application infrastructure (production)

This repository manages the production AWS foundation for the CSYE web application in `us-east-1`: three network
tiers, the public application load balancer and launch template, MySQL, purpose-specific object stores, and the SNS,
SQS, DynamoDB and Lambda resources behind each notification channel.

The root `availability_zones`, `channels` and `buckets` maps are the operating interface. Adding or removing a key
adds or retires that slice of the stack. Channel entries retain their own queue, function, table, alarm, owner and
optional log-retention settings; bucket entries retain classification, owner, lifecycle and capacity-alarm settings.
The map types and validations describe the combinations the platform supports.

Production state is included for refresh-free planning. Run `scripts/ci-plan.sh` to perform the same offline init,
validation, plan and OPA/conftest checks used by CI; the platform policy pack is in `policies/` in the task checkout.
