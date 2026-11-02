# AtlasGrid production ECS platform

This Terraform stack defines the production ECS platform for AtlasGrid: its VPC, three subnet tiers, routing and
flow logs; IAM roles; public and internal application load balancers; ECS cluster capacity and shared EFS storage;
per-service repositories, logs, queues, tables, parameters and task definitions; and platform and workload alarms.

The root module calls six local modules: `network`, `identity`, `edge`, `cluster`, `workloads`, and `observability`.
Availability zones and workload services are maps in `variables.tf`. Resources that belong to one map entry use
`for_each`, so the map key remains the stable Terraform instance key across the network, edge, workload, and
observability modules.

`terraform.tfstate` is the production state. This workspace has no AWS access. Initialize from the offline provider
mirror with `terraform init -input=false`, then inspect production with `terraform plan -refresh=false`. Override root
variables in the usual Terraform ways when evaluating a proposed platform change.
