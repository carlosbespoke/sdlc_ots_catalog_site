# Cats vs Dogs development infrastructure

This Terraform stack manages the shared AWS application platform for the `web`, `cats`, and `dogs` services. It
includes the VPC and per-availability-zone routing, private service integrations, flow logging, shared encryption,
ECR and ECS foundations, encrypted service storage, load balancing, queues, runtime configuration, and operational
topics and alarms.

The root module calls four local modules:

- `network` owns the VPC, the `availability_zones` subnet and routing map, the `integrations` endpoint map, network
  inventories, and flow logs.
- `platform` owns shared KMS, S3, ECR, ECS, IAM, and DynamoDB resources, including per-`services` storage.
- `services` owns the application load balancer and each entry in the `services` map: logs, networking, queues,
  task identity and definition, and runtime parameters.
- `observability` owns each service's alert topic, metric filters, alarms, and the cross-service catalog.

`terraform.tfstate` is the production snapshot. This machine has no AWS access; initialize from the offline provider
mirror and run `terraform plan -refresh=false` to compare configuration with that snapshot.
