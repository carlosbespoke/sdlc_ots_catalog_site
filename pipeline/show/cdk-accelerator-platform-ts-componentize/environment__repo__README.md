# Orion accelerator infrastructure

This AWS CDK app deploys an isolated CI/CD accelerator environment in three stacks. `NetworkStack` owns the three-tier VPC, flow logs, gateway access, and the delivery/runtime/notification security domains. `DeliveryStack` owns encrypted artifact storage, the release catalog, ECR and ECS runtime definitions, and per-stage blue/green routing, queues, topics, task documents, and alarms. `OperationsStack` owns the notification Lambda, subscriptions, pipeline event rules, dashboard, and discovery parameters.

Environment files live in `config/<stage>.json`; `lib/config.ts` is the schema and naming contract. Run `npm run build`, then synthesize offline with `npx cdk synth -c stage=prod --no-version-reporting --path-metadata false --asset-metadata false`. No AWS lookup is required; availability zones are pinned in `cdk.context.json`.

`deployed/<stage>/` records the templates currently running in each deployed environment. `scripts/ci.sh` type-checks the app, applies the code rules, synthesizes every deployed configuration, and compares it with those templates. The test directory is reserved for infrastructure tests.
