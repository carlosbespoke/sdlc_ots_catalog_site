# Cognito Nakama development infrastructure

This directory is the Terraform stack for the development deployment of the dual-token
Nakama game service. It provisions the VPC, a NAT gateway in each availability zone,
Cognito player identity, the ECS/Fargate workload definition, the HTTP and WebSocket load
balancers, encrypted logs and secrets, and the operator access policy. API routes carry
their own target groups, observability and discovery parameters. Matchmaking, presence,
leaderboard and telemetry jobs exchange work through service-specific SNS topics and SQS
queues, with per-service worker roles, logs and alarms. The service rollout itself is
performed by the application deployment pipeline after it publishes an image.

Casual, ranked and tournament play are configured as game modes. Each mode contributes
runtime session and rate settings, a generated access policy, encrypted logs and alarms.
The task definition carries the ordered mode catalog and the lowest-priority primary mode.
The observability layer consumes all availability zones, routes, asynchronous services and
game modes: it installs a metric filter and alarm for every key and publishes a generated
inventory of the backing log groups, target groups, topics and policies.

CloudFront and its WAF are managed outside this sandbox deployment. The load balancers
therefore accept client traffic directly, while the ECS tasks remain isolated in private
subnets. Secret values are populated by the deployment pipeline after the secret
containers are created; Terraform intentionally manages no secret payloads.

The root module calls six direct local modules: `network`, `security`, `messaging`,
`runtime`, `operations`, and `observability`. Availability zones, API routes, asynchronous
services and game modes are maps in `variables.tf`; their repeated resources use
`for_each` with the map key as the stable instance key. Each map is consumed by both its
owning module and observability. Catalog parameters, inventory policies, task environment
settings and primary selections derive their membership from the complete maps. Legacy
order is preserved for the original keys, while newly introduced keys are appended in
lexicographic order; the cross-collection observability inventory is fully lexicographic.

`terraform.tfstate` is the production state. AWS is unavailable from this machine:
initialize from the offline provider mirror and run `terraform plan -refresh=false`
against the recorded state.
