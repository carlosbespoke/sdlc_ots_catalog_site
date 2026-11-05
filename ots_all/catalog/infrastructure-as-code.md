# Infrastructure as code

## Executive summary

<div class="kpis"><div class="kpi"><div class="kpi-value">301</div><div class="kpi-label">Tasks</div></div><div class="kpi"><div class="kpi-value">66%</div><div class="kpi-label">z-ai/glm-5.3-flash average reward</div></div><div class="kpi"><div class="kpi-value">67%</div><div class="kpi-label">google/gemini-3.8-flash average reward</div></div><div class="kpi"><div class="kpi-value">78%</div><div class="kpi-label">google/gemini-4-argon average reward</div></div></div>

Each task restructures infrastructure code that is already deployed. The agent splits a flat Terraform stack into modules with stable keys, componentizes a CDK app or moves a stack to Pulumi, so that the plan against production state changes nothing that is running. The main languages are HCL (Terraform) (99%), TypeScript (1%) and Python (0%).

Every task has graded runs. The model with the most runs here, z-ai/glm-5.3-flash, has an average reward of 66% over 1,601 graded runs and scores 0 on every run of 3% of the 295 tasks it ran.

## Why this catalog

### Problems engineers face

Platform engineers restructure infrastructure code that is already running, and the change must reach production as address moves only, because the team cannot plan against a live account. The most common case is a flat Terraform root module that has to become local modules with `for_each` keys. Others replace positional `count` with stable keys, extract reusable components from an app that builds everything inline, move a stack between tools while the preview stays clean, or bring a stack under a policy pack without replacing resources.

### How the tasks reproduce them

Each task ships a copy of the stack with its recorded production state or recorded templates, an offline toolchain and no network. The instruction states module ownership, key rules, root variables with today's defaults and outputs. After the session, a separate verifier with its own pristine state plans the agent's configuration with refresh disabled and expects moves only, then plans hidden changes such as an added key, a removed key or a changed entry. Most tasks score zero when a gate fails.

### Typical prompts

- A first-person request to modularize a named production stack, listing target modules, ownership, key rules, root variables and outputs, and requiring a plan of moves only.
- A componentization request that lists every construct class with its path, props and public properties, and requires identical synthesized templates.
- A migration brief for an imported stack with an empty program, with naming, config and equivalence rules and banned options.

## Domain breakdown

The tasks span two domains. The largest, Cloud infrastructure & IaC, makes up 99% of the catalog.

<div class="cx" data-chart="bars" data-dims="g>c=Domain" data-hint="Click a domain to filter the charts on this page; use the arrow to see its sub-domains.">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Share of tasks by domain</h4></div>
<div class="fig-box" data-body></div>
</div>

## Language and seniority

<div class="cx" data-chart="bars" data-dims="l:8=Primary language,s=Seniority">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Primary language and seniority</h4></div>
<div class="fig-box" data-body></div>
</div>

### Primary language

| Primary language | % of catalog |
|---|---:|
| HCL (Terraform) | 98.7% |
| TypeScript | 1.0% |
| Python | 0.3% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Senior | 99.7% |
| Staff+ | 0.3% |

## Model average reward across the catalog

A model's average reward is average@k: on each task, the mean grader score over its graded runs, with partial credit counted as scored; then the mean over the tasks it ran. Runs that errored are left out. Models are listed by number of runs, and a model needs graded runs on five or more tasks for a row.

| Model | Tasks run | Graded runs | Average reward | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|---:|---:|
| z-ai/glm-5.3-flash | 295 | 1,601 | 66% | 3% | 88% | 0% |
| google/gemini-4-argon | 20 | 40 | 78% | 15% | 15% | 70% |
| google/gemini-3.8-flash | 8 | 24 | 67% | 12% | 50% | 38% |

<div class="cx" data-chart="reward">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Per-task average reward by model</h4></div>
<div class="fig-box" data-body></div>
</div>

## Turn counts and long-horizon tasks

A task's turn count is the average over its completed runs, from every model. A task is long horizon when that average is 200 or more turns. 301 of the 301 tasks have a completed run.

| Measure | Value |
|---|---:|
| Average turn count | 115.2 |
| Median turn count | 109.2 |
| Range | 39 to 292 |
| Long-horizon tasks (200+ turns) | 5% of tasks |

<div class="cx" data-chart="turns" data-group="Domain">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Turns per task</h4></div>
<div class="fig-box" data-body></div>
</div>

| Model | % of tasks | Mean turns | % of runs with 200+ turns |
|---|---:|---:|---:|
| z-ai/glm-5.3-flash | 98% | 116.7 | 11% |
| google/gemini-4-argon | 7% | 74.6 | 5% |
| google/gemini-3.8-flash | 3% | 170.5 | 33% |

## Sample tasks

### Example 1: Cloud infra: containers & self-hosted platforms (Terraform)

| Field | Value |
|---|---|
| Task id | [`dualipv6-module-refactor`](https://drive.google.com/file/d/1Yg1iLWpltsqLdJS0jpUj4v3Wb3K4JlE-/view) |
| Final category | Infrastructure as code |
| Domain | Cloud infrastructure & IaC |
| Sub-domain | Cloud infra: containers & self-hosted platforms |
| Language | HCL (Terraform) |
| Seniority | Senior |
| Turn count | 100 (z-ai/glm-5.3-flash), 46 (google/gemini-4-argon) |
| Long horizon | no |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

The Terraform for our dual IPv6 Kubernetes production stack in `/workspace/infra` has grown into one flat root module: everything is declared at the top level, the per-AZ resources are `count`-indexed by list position, and names, settings and tags are hard-coded all over the files. Split it into four local modules (network, bootstrap, platform and observability) without touching the running infrastructure: against the current state, the plan has to come out as nothing but moves.

There is no AWS access from this machine. `terraform init` works offline from the local provider mirror, `terraform.tfstate` is a copy of the production state, and `scripts/ci-plan.sh` runs what CI runs: a `terraform plan -refresh=false` against the state followed by the guardrail policies in `policies/`.

###### Detailed Constraints

**How CI judges the change.** CI takes the repository alone and plans it with `terraform plan -refresh=false` against its own copy of the production state. Local `terraform state` commands and edits to `terraform.tfstate` never reach it, so the whole migration has to be expressed in the configuration. That plan must:
- still manage every resource that is in the state today, and
- contain no create, update, replace, destroy or forget: only resources moving to new addresses.

The guardrail policies in `policies/` must pass on that plan, and `providers.tf` and everything in `policies/` stay exactly as they are, byte for byte.

**Layout.**
- The root module calls `module "network"`, `module "bootstrap"`, `module "platform"` and `module "observability"`, with sources `./modules/network`, `./modules/bootstrap`, `./modules/platform` and `./modules/observability` and one instance each, calls no other module and declares no resources of its own.
- Which module owns what (every instance of the resources described, wherever they are declared today):
  - network: both VPCs, their internet gateways, public and workload subnets, Elastic IPs and NAT64-capable NAT gateways, route tables, IPv4 and IPv6 routes, and route table associations;
  - bootstrap: the bootstrap KMS key and alias, S3 bucket and every bucket settings resource, the per-pool bootstrap objects, the DynamoDB bootstrap table, and the network and worker SSM configuration catalogs;
  - platform: both clusters' control-plane and worker IAM roles, inline policies and instance profiles, security groups and rules, CloudWatch log groups, launch templates and auto scaling groups;
  - observability: the alert SNS topic, SQS queue, subscription and queue policy, and both clusters' per-pool capacity alarms.
- Each of these modules declares the resources it owns itself and calls no other module.
- Modules get each other's IDs and ARNs through module outputs and variables. Never paste an ID, ARN, IP address or DNS name of an existing resource, or any part of one (such as an ARN suffix), into the `.tf` files or templates. The configuration reads files only through literal paths inside its own module (such as `"${path.module}/templates/..."`; in a child module a path starts with `${path.module}/`, because Terraform resolves any other relative path from the root directory, not from the module): no computed paths, no `terraform_remote_state` data sources, and never the state or a plan file.

**Keys.**
- Everything that exists once per availability zone today is a `for_each` resource keyed by the AZ name (for example `["us-east-1a"]`), including each instance of a list that also holds things that belong to no single availability zone.
- Everything that exists once per worker pool today is a `for_each` resource keyed by the pool name (for example `["mesh"]`), including each instance of a list that also holds things that belong to no single worker pool.
- Don't use `count` anywhere. Other repeated resources use `for_each` with string keys that are not numbers (a name such as `["assets"]`, never `["0"]`).
- Each existing availability zone's entry in `availability_zones` is the only source of its values: changing an entry changes, for that availability zone alone, exactly the settings the entry provides, and changes nothing else.
- Adding an availability zone to `availability_zones` must plan only the creation of that availability zone's resources, each configured exactly like its counterparts in the existing availability zones apart from the availability zone itself and the values its entry in `availability_zones` gives it (same settings, names and tags), and removing one only the destruction of that availability zone's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every availability zone today (wherever a setting holds a part of every availability zone: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that availability zone's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing worker pool's entry in `worker_pools` is the only source of its values: changing an entry changes, for that worker pool alone, exactly the settings the entry provides, and changes nothing else.
- Adding a worker pool to `worker_pools` must plan only the creation of that worker pool's resources, each configured exactly like its counterparts in the existing worker pools apart from the worker pool itself and the values its entry in `worker_pools` gives it (same settings, names and tags), and removing one only the destruction of that worker pool's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every worker pool today (wherever a setting holds a part of every worker pool: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that worker pool's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.

**Root variables.** Declare these in the root module, each defaulting to today's value:
- `project` (`string`, `"v6mesh"`): every whole-word occurrence of `v6mesh` in a resource name, identifier or tag value today comes from it (whole word: not part of a longer run of letters and digits, so `v6mesh-api`, `v6mesh_key` and `/v6mesh/` count, while a longer word that merely contains `v6mesh` stays as it is), and so does every mention of those names elsewhere in the configuration (for example a resource name inside a policy); inside documents such as policies, container definitions and environment values, every whole-word occurrence of `v6mesh` that stands for it comes from it too; This includes the `PROJECT` value in every launch template's user data, project fields in the SSM catalogs and bootstrap objects, and the project token in alarm namespaces and dimensions.
- `environment` (`string`, `"prod"`): every whole-word occurrence of `prod` in a resource name, identifier or tag value today, and the `ENVIRONMENT` value in every launch template's user data, the environment fields in the SSM catalogs and bootstrap objects, and the environment token in alarm namespaces and dimensions, comes from it (whole word: not part of a longer run of letters and digits, so `prod-api`, `prod_key` and `/prod/` count, while a longer word that merely contains `prod` stays as it is), and so does every mention of those names elsewhere in the configuration (for example a resource name inside a policy); inside documents such as policies, container definitions and environment values, every whole-word occurrence of `prod` that stands for it comes from it too.
- `primary_vpc_cidr` (`string`, `"172.20.0.0/16"`): the alpha cluster VPC's IPv4 CIDR and its control-plane API security-group rule.
- `secondary_vpc_cidr` (`string`, `"172.21.0.0/16"`): the beta cluster VPC's IPv4 CIDR and its control-plane API security-group rule.
- `availability_zones`: `map(object({ order = number, primary_public_cidr = string, primary_workload_cidr = string, secondary_public_cidr = string, secondary_workload_cidr = string }))`, keyed by AZ name, defaulting to today's three AZs, their stable collection order and all four subnet CIDRs. It is the only source of AZ membership, AZ order and subnet CIDRs.
- `worker_pools`: `map(object({ order = number, instance_type = string, disk_size = number, min_size = number, max_size = number, desired_size = number }))`, keyed by pool name, defaulting to today's gateway, system and mesh pools, their stable collection order, instance type, root disk size and scaling bounds. It is the only source of worker-pool membership, order and sizing.
- `tags` (`map(string)`, `{ Owner = "soloio-platform", CostCenter = "cc-6204", ManagedBy = "terraform" }`): the shared tags (`Owner`, `CostCenter` and `ManagedBy`) that tagged resources carry today. Wherever the configuration writes them out today, in any form, they come from this variable, so that a different map (other keys, other values) reaches every one of those places; a resource's other tags stay as they are, and resources that are untagged today stay untagged.
- `node_ami_id` (`string`, `"ami-0009de7aaac3fdbb1"`): the AMI of every control-plane and worker launch template.
- `master_instance_type` (`string`, `"t3.medium"`): the instance type of both control-plane launch templates.
- `log_retention_days` (`number`, `30`): the retention period of every control-plane and worker CloudWatch log group.
- `bootstrap_version_retention_days` (`number`, `30`): the bootstrap bucket's noncurrent-version retention period.
- `alarm_period_seconds` (`number`, `60`): the metric period of every worker-pool capacity alarm.
- Changing `primary_vpc_cidr`, `secondary_vpc_cidr`, `node_ami_id`, `master_instance_type`, `log_retention_days`, `bootstrap_version_retention_days` and `alarm_period_seconds` changes only what each one's line above says it controls: every other setting keeps today's value, including a setting that merely has the same value today.

**Root outputs.** Keep `primary_vpc_id`, `secondary_vpc_id`, `bootstrap_bucket_name` and `alerts_topic_arn` with their current values. `primary_workload_subnet_ids` becomes a map from the AZ name to the `id` of that availability zone's `aws_subnet.primary_workload`. `secondary_workload_subnet_ids` becomes a map from the AZ name to the `id` of that availability zone's `aws_subnet.secondary_workload`. `primary_nat64_public_ips` becomes a map from the AZ name to the `public_ip` of that availability zone's `aws_eip.primary_nat64`. `secondary_nat64_public_ips` becomes a map from the AZ name to the `public_ip` of that availability zone's `aws_eip.secondary_nat64`. `primary_worker_asg_names` becomes a map from the pool name to the `name` of that worker pool's `aws_autoscaling_group.primary_worker`. `secondary_worker_asg_names` becomes a map from the pool name to the `name` of that worker pool's `aws_autoscaling_group.secondary_worker`. `bootstrap_object_keys` is a new output: a map from the pool name to the `key` of that worker pool's `aws_s3_object.pool_bootstrap`. Each output passes through outputs of the module that owns the resource (network for `primary_vpc_id`, `secondary_vpc_id`, `primary_workload_subnet_ids`, `secondary_workload_subnet_ids`, `primary_nat64_public_ips` and `secondary_nat64_public_ips`; bootstrap for `bootstrap_bucket_name` and `bootstrap_object_keys`; platform for `primary_worker_asg_names` and `secondary_worker_asg_names`; observability for `alerts_topic_arn`): the root output is a plain reference to an output of that module, and that module output is a plain reference to the resource. A plain reference is a reference such as `module.network.<output>` or `<resource type>.<name>.<attribute>`, a local that holds one, or a `for` expression that only re-keys one (`{ for k, v in <reference> : k => v.id }`) or iterates a plain reference and looks each key up in one (`{ for k, v in var.<map> : k => <reference>[k].id }`); no literals, function calls, conditionals or string templates anywhere along the way.

**Not allowed anywhere in the configuration:** `ignore_changes`, `prevent_destroy` and `replace_triggered_by`, `removed` and `import` blocks, provisioners, `external` data sources, backend or cloud blocks, provider blocks other than the one in `providers.tf`, override files and `.tf.json` files.

</div>
</details>

#### Average reward

| Model | Graded runs | Average reward |
|---|---:|---:|
| google/gemini-4-argon | 2 | 0% |
| z-ai/glm-5.3-flash | 5 | 40% |

#### Environment

![How the task works](assets/env-dualipv6-module-refactor.svg)

### Example 2: Cloud infra: AWS platform stacks (Terraform)

| Field | Value |
|---|---|
| Task id | [`centralwatch-module-refactor`](https://drive.google.com/file/d/18b23bcb7ot9dDpaMF3nvcUVTGvYhg3aA/view) |
| Final category | Infrastructure as code |
| Domain | Cloud infrastructure & IaC |
| Sub-domain | Cloud infra: AWS platform stacks |
| Language | HCL (Terraform) |
| Seniority | Senior |
| Turn count | 140 (z-ai/glm-5.3-flash), 70 (google/gemini-4-argon) |
| Long horizon | no |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

The Terraform for our centralwatch production alert-routing stack in `/workspace/infra` has grown into one flat root module: everything is declared at the top level, the per-team resources are `count`-indexed by list position, and names, settings and tags are hard-coded all over the files. Split it into three local modules (eventing, messaging and processing) without touching the running infrastructure: against the current state, the plan has to come out as nothing but moves.

There is no AWS access from this machine. `terraform init` works offline from the local provider mirror, `terraform.tfstate` is a copy of the production state, and `scripts/ci-plan.sh` runs what CI runs: a `terraform plan -refresh=false` against the state followed by the guardrail policies in `policies/`.

###### Detailed Constraints

**How CI judges the change.** CI takes the repository alone and plans it with `terraform plan -refresh=false` against its own copy of the production state. Local `terraform state` commands and edits to `terraform.tfstate` never reach it, so the whole migration has to be expressed in the configuration. That plan must:
- still manage every resource that is in the state today, and
- contain no create, update, replace, destroy or forget: only resources moving to new addresses.

The guardrail policies in `policies/` must pass on that plan, and `providers.tf` and everything in `policies/` stay exactly as they are, byte for byte.

**Layout.**
- The root module calls `module "eventing"`, `module "messaging"` and `module "processing"`, with sources `./modules/eventing`, `./modules/messaging` and `./modules/processing` and one instance each, calls no other module and declares no resources of its own.
- Which module owns what (every instance of the resources described, wherever they are declared today):
  - eventing: the KMS key and alias, the central EventBridge bus, the EventBridge service role, the per-source event rules, log groups, dead-letter queues, age and backlog alarms, filter parameters, and the shared source-map and default-source parameters;
  - messaging: the central alarm queue and central dead-letter queue with the alarm queue policy, the per-source queue and log targets with the EventBridge role's inline policy, every per-team SNS topic, topic policy and email subscription, delivery dead-letter queue and queue policy, team log group, both delivery alarms and routing parameter, the shared team-map and default-team parameters, every per-severity SNS topic, topic policy and subscription, queue and queue policy, log group, both queue alarms and routing parameter, the shared severity-map and default-severity parameters, every per-channel SNS topic, topic policy, SQS queue and dead-letter queue, queue policy and subscription, the deployment parameter, and the operations escalation topic, topic policy and subscription;
  - processing: the enricher Lambda function and its archive, event source mapping, log group, IAM role and inline policy, the queue-depth, Lambda-error and Lambda-throttle alarms, every per-channel log group, backlog alarm, age alarm and route parameter, and the shared channel-map, routing-inventory and default-channel parameters.
- Each of these modules declares the resources it owns itself and calls no other module.
- Modules get each other's IDs and ARNs through module outputs and variables. Never paste an ID, ARN, IP address or DNS name of an existing resource, or any part of one (such as an ARN suffix), into the `.tf` files or templates. The configuration reads files only through literal paths inside its own module (such as `"${path.module}/templates/..."`; in a child module a path starts with `${path.module}/`, because Terraform resolves any other relative path from the root directory, not from the module): no computed paths, no `terraform_remote_state` data sources, and never the state or a plan file.

**Keys.**
- Everything that exists once per notification team today is a `for_each` resource keyed by the team name (for example `["payments"]`), including each instance of a list that also holds things that belong to no single notification team.
- The default-team parameter and `primary_team_topic_arn` choose `operations` while that team exists; removing it destroys only its keyed team resources, leaves the separate operations escalation topic, policy and subscription unchanged, and makes both defaults choose the lexicographically first remaining team rather than a list position.
- Everything that exists once per event source today is a `for_each` resource keyed by the source name (for example `["backup"]`), including each instance of a list that also holds things that belong to no single event source.
- The default-source parameter and `primary_source_rule_arn` choose `rds` while that source exists; removing it destroys its keyed source resources and makes both defaults choose the lexicographically first remaining source rather than a list position.
- Everything that exists once per severity route today is a `for_each` resource keyed by the severity name (for example `["critical"]`), including each instance of a list that also holds things that belong to no single severity route.
- The default-severity parameter and `primary_severity_topic_arn` choose `critical` while that severity exists; removing it destroys its keyed severity resources and makes both defaults choose the lexicographically first remaining severity rather than a list position.
- Everything that exists once per delivery channel today is a `for_each` resource keyed by the channel name (for example `["chatops"]`), including each instance of a list that also holds things that belong to no single delivery channel.
- The default-channel parameter and `primary_channel_queue_arn` choose `webhook` while that channel exists; removing it destroys only its keyed channel resources and makes both defaults choose the lexicographically first remaining channel rather than a list position.
- Don't use `count` anywhere. Other repeated resources use `for_each` with string keys that are not numbers (a name such as `["assets"]`, never `["0"]`).
- Each existing notification team's entry in `teams` is the only source of its values: changing an entry changes, for that notification team alone, exactly the settings the entry provides, and changes nothing else.
- Adding a notification team to `teams` must plan only the creation of that notification team's resources, each configured exactly like its counterparts in the existing notification teams apart from the notification team itself and the values its entry in `teams` gives it (same settings, names and tags), and removing one only the destruction of that notification team's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every notification team today (wherever a setting holds a part of every notification team: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that notification team's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing event source's entry in `sources` is the only source of its values: changing an entry changes, for that event source alone, exactly the settings the entry provides, and changes nothing else.
- Adding an event source to `sources` must plan only the creation of that event source's resources, each configured exactly like its counterparts in the existing event sources apart from the event source itself and the values its entry in `sources` gives it (same settings, names and tags), and removing one only the destruction of that event source's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every event source today (wherever a setting holds a part of every event source: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that event source's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing severity route's entry in `severities` is the only source of its values: changing an entry changes, for that severity route alone, exactly the settings the entry provides, and changes nothing else.
- Adding a severity route to `severities` must plan only the creation of that severity route's resources, each configured exactly like its counterparts in the existing severity routes apart from the severity route itself and the values its entry in `severities` gives it (same settings, names and tags), and removing one only the destruction of that severity route's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every severity route today (wherever a setting holds a part of every severity route: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that severity route's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing delivery channel's entry in `channels` is the only source of its values: changing an entry changes, for that delivery channel alone, exactly the settings the entry provides, and changes nothing else.
- Adding a delivery channel to `channels` must plan only the creation of that delivery channel's resources, each configured exactly like its counterparts in the existing delivery channels apart from the delivery channel itself and the values its entry in `channels` gives it (same settings, names and tags), and removing one only the destruction of that delivery channel's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every delivery channel today (wherever a setting holds a part of every delivery channel: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that delivery channel's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.

**Root variables.** Declare these in the root module, each defaulting to today's value:
- `project` (`string`, `"centralwatch"`): every whole-word occurrence of `centralwatch` in a resource name, identifier or tag value today comes from it (whole word: not part of a longer run of letters and digits, so `centralwatch-api`, `centralwatch_key` and `/centralwatch/` count, while a longer word that merely contains `centralwatch` stays as it is), and so does every mention of those names elsewhere in the configuration (for example a resource name inside a policy); inside documents such as policies, container definitions and environment values, every whole-word occurrence of `centralwatch` that stands for it comes from it too.
- `environment` (`string`, `"prod"`): every whole-word occurrence of `prod` in a resource name, identifier or tag value today comes from it (whole word: not part of a longer run of letters and digits, so `prod-api`, `prod_key` and `/prod/` count, while a longer word that merely contains `prod` stays as it is), and so does every mention of those names elsewhere in the configuration (for example a resource name inside a policy); inside documents such as policies, container definitions and environment values, every whole-word occurrence of `prod` that stands for it comes from it too.
- `tags` (`map(string)`, `{ Owner = "monitoring-team", CostCenter = "cc-4170", ManagedBy = "terraform" }`): the shared tags (`Owner`, `CostCenter` and `ManagedBy`) that tagged resources carry today. Wherever the configuration writes them out today, in any form, they come from this variable, so that a different map (other keys, other values) reaches every one of those places; a resource's other tags stay as they are, and resources that are untagged today stay untagged.
- `teams`: `map(object({ email = string, retention_days = number, delivery_threshold = number, dlq_visibility_seconds = number, dlq_delay_seconds = number, dlq_receive_wait_seconds = number, dlq_max_message_size = number, dlq_age_threshold_seconds = number }))`, keyed by team name, defaulting to today's ten teams, their primary notification email, team log retention, failed-delivery threshold, delivery-queue visibility timeout, delay, receive wait, maximum message size and oldest-message threshold. It is the only source of team names and those per-team settings.
- `sources`: `map(object({ detail_type = string, log_retention_days = number, age_threshold_seconds = number, dlq_visibility_seconds = number, dlq_retention_seconds = number, dlq_delay_seconds = number, dlq_receive_wait_seconds = number, backlog_threshold = number }))`, keyed by source name, defaulting to today's seven event sources, their EventBridge detail type, source log retention, oldest-message and backlog thresholds, and dead-letter-queue visibility timeout, retention, delay and receive wait. It is the only source of source names and those per-source settings.
- `kms_deletion_window_days` (`number`, `20`): the KMS key's deletion window in days.
- `queue_visibility_timeout_seconds` (`number`, `90`): the visibility timeout of the central alarm queue.
- `queue_message_retention_seconds` (`number`, `345600`): the message retention of the central alarm queue.
- `dlq_message_retention_seconds` (`number`, `1209600`): the message retention of the central dead-letter queue and every team delivery dead-letter queue.
- `lambda_memory_size` (`number`, `256`): the enricher Lambda function's memory in MiB.
- `lambda_timeout_seconds` (`number`, `20`): the enricher Lambda function's timeout in seconds.
- `lambda_reserved_concurrency` (`number`, `25`): the enricher Lambda function's reserved concurrency.
- `enricher_log_retention_days` (`number`, `120`): the enricher Lambda log group's retention in days.
- `alarm_period_seconds` (`number`, `300`): the metric period of every CloudWatch alarm in the stack.
- `alarm_evaluation_periods` (`number`, `2`): the evaluation periods of every CloudWatch alarm in the stack.
- `severities`: `map(object({ email = string, log_retention_days = number, queue_visibility_seconds = number, queue_retention_seconds = number, backlog_threshold = number, queue_delay_seconds = number, queue_receive_wait_seconds = number, age_threshold_seconds = number }))`, keyed by severity name, defaulting to today's five severity routes, their notification email, log retention, queue visibility timeout, retention, delay and receive wait, and backlog and oldest-message thresholds. It is the only source of severity names and those per-severity settings.
- `kms_enable_key_rotation` (`bool`, `true`): whether automatic rotation is enabled for the KMS key.
- `event_target_maximum_event_age_seconds` (`number`, `3600`): the maximum event age in seconds for every EventBridge queue and log target.
- `event_target_maximum_retry_attempts` (`number`, `8`): the maximum retry attempts for every EventBridge queue and log target.
- `central_dlq_visibility_timeout_seconds` (`number`, `120`): the visibility timeout of the central dead-letter queue.
- `central_queue_delay_seconds` (`number`, `5`): the delivery delay of the central alarm queue.
- `lambda_batch_size` (`number`, `10`): the enricher event source mapping's batch size.
- `lambda_batching_window_seconds` (`number`, `5`): the enricher event source mapping's maximum batching window in seconds.
- `queue_depth_threshold` (`number`, `100`): the central queue-depth alarm's threshold.
- `lambda_error_threshold` (`number`, `5`): the enricher Lambda error alarm's threshold.
- `lambda_throttle_threshold` (`number`, `3`): the enricher Lambda throttle alarm's threshold.
- `alarm_datapoints_to_alarm` (`number`, `2`): the datapoints-to-alarm setting of every CloudWatch alarm in the stack.
- `operations_email` (`string`, `"operations-escalation@example.com"`): the operations escalation topic subscription's email endpoint.
- `channels`: `map(object({ queue_visibility_seconds = number, queue_retention_seconds = number, queue_delay_seconds = number, queue_receive_wait_seconds = number, queue_max_message_size = number, dlq_retention_seconds = number, log_retention_days = number, backlog_threshold = number, age_threshold_seconds = number }))`, keyed by channel name, defaulting to today's four delivery channels, their queue visibility timeout, retention, delay, receive wait and maximum message size, dead-letter retention, log retention, backlog threshold and oldest-message threshold. It is the only source of channel names and those per-channel settings.
- Changing `kms_deletion_window_days`, `queue_visibility_timeout_seconds`, `queue_message_retention_seconds`, `dlq_message_retention_seconds`, `lambda_memory_size`, `lambda_timeout_seconds`, `lambda_reserved_concurrency`, `enricher_log_retention_days`, `alarm_period_seconds`, `alarm_evaluation_periods`, `kms_enable_key_rotation`, `event_target_maximum_event_age_seconds`, `event_target_maximum_retry_attempts`, `central_dlq_visibility_timeout_seconds`, `central_queue_delay_seconds`, `lambda_batch_size`, `lambda_batching_window_seconds`, `queue_depth_threshold`, `lambda_error_threshold`, `lambda_throttle_threshold`, `alarm_datapoints_to_alarm` and `operations_email` changes only what each one's line above says it controls: every other setting keeps today's value, including a setting that merely has the same value today.

**Root outputs.** Keep `event_bus_arn`, `alerts_queue_arn`, `enricher_function_arn`, `kms_key_arn`, `primary_team_topic_arn`, `primary_source_rule_arn`, `primary_severity_topic_arn` and `primary_channel_queue_arn` with their current values. `team_topic_arns` becomes a map from the team name to the `arn` of that notification team's `aws_sns_topic.this`. `team_route_parameter_names` becomes a map from the team name to the `name` of that notification team's `aws_ssm_parameter.team_route`. `source_rule_arns` becomes a map from the source name to the `arn` of that event source's `aws_cloudwatch_event_rule.source`. `source_log_group_names` becomes a map from the source name to the `name` of that event source's `aws_cloudwatch_log_group.event_rule`. `severity_topic_arns` becomes a map from the severity name to the `arn` of that severity route's `aws_sns_topic.severity`. `severity_queue_arns` becomes a map from the severity name to the `arn` of that severity route's `aws_sqs_queue.severity`. `channel_topic_arns` becomes a map from the channel name to the `arn` of that delivery channel's `aws_sns_topic.channel`. `channel_queue_arns` becomes a map from the channel name to the `arn` of that delivery channel's `aws_sqs_queue.channel`. `channel_route_parameter_names` becomes a map from the channel name to the `name` of that delivery channel's `aws_ssm_parameter.channel_route`. Each output passes through outputs of the module that owns the resource (eventing for `event_bus_arn`, `kms_key_arn`, `source_rule_arns`, `source_log_group_names` and `primary_source_rule_arn`; messaging for `alerts_queue_arn`, `team_topic_arns`, `team_route_parameter_names`, `severity_topic_arns`, `severity_queue_arns`, `channel_topic_arns`, `channel_queue_arns`, `primary_team_topic_arn`, `primary_severity_topic_arn` and `primary_channel_queue_arn`; processing for `enricher_function_arn` and `channel_route_parameter_names`): the root output is a plain reference to an output of that module, and that module output is a plain reference to the resource. A plain reference is a reference such as `module.eventing.<output>` or `<resource type>.<name>.<attribute>`, a local that holds one, or a `for` expression that only re-keys one (`{ for k, v in <reference> : k => v.id }`) or iterates a plain reference and looks each key up in one (`{ for k, v in var.<map> : k => <reference>[k].id }`); no literals, function calls, conditionals or string templates anywhere along the way.

**Not allowed anywhere in the configuration:** `ignore_changes`, `prevent_destroy` and `replace_triggered_by`, `removed` and `import` blocks, provisioners, `external` data sources, backend or cloud blocks, provider blocks other than the one in `providers.tf`, override files and `.tf.json` files.

</div>
</details>

#### Average reward

| Model | Graded runs | Average reward |
|---|---:|---:|
| z-ai/glm-5.3-flash | 16 | 19% |
| google/gemini-4-argon | 2 | 0% |

#### Environment

![How the task works](assets/env-centralwatch-module-refactor.svg)

### Example 3: Cloud infra: AWS platform stacks (Terraform)

| Field | Value |
|---|---|
| Task id | [`modelrouter-module-refactor`](https://drive.google.com/file/d/1VrmncKJo_ub16T50JNG8Ep_0vONojAMq/view) |
| Final category | Infrastructure as code |
| Domain | Cloud infrastructure & IaC |
| Sub-domain | Cloud infra: AWS platform stacks |
| Language | HCL (Terraform) |
| Seniority | Senior |
| Turn count | 177 (z-ai/glm-5.3-flash), 58 (google/gemini-4-argon) |
| Long horizon | no |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

The Terraform for our multi-model router production stack in `/workspace/infra` has grown into one flat root module: everything is declared at the top level, the per-AZ resources are `count`-indexed by list position, and names, settings and tags are hard-coded all over the files. Split it into eight local modules (network, security, identity, artifacts, compute, routing, observability and queues) without touching the running infrastructure: against the current state, the plan has to come out as nothing but moves.

There is no AWS access from this machine. `terraform init` works offline from the local provider mirror, `terraform.tfstate` is a copy of the production state, and `scripts/ci-plan.sh` runs what CI runs: a `terraform plan -refresh=false` against the state followed by the guardrail policies in `policies/`.

###### Detailed Constraints

**How CI judges the change.** CI takes the repository alone and plans it with `terraform plan -refresh=false` against its own copy of the production state. Local `terraform state` commands and edits to `terraform.tfstate` never reach it, so the whole migration has to be expressed in the configuration. That plan must:
- still manage every resource that is in the state today, and
- contain no create, update, replace, destroy or forget: only resources moving to new addresses.

The guardrail policies in `policies/` must pass on that plan, and `providers.tf` and everything in `policies/` stay exactly as they are, byte for byte.

**Layout.**
- The root module calls `module "network"`, `module "security"`, `module "identity"`, `module "artifacts"`, `module "compute"`, `module "routing"`, `module "observability"` and `module "queues"`, with sources `./modules/network`, `./modules/security`, `./modules/identity`, `./modules/artifacts`, `./modules/compute`, `./modules/routing`, `./modules/observability` and `./modules/queues` and one instance each, calls no other module and declares no resources of its own.
- Which module owns what (every instance of the resources described, wherever they are declared today):
  - network: the VPC and internet gateway, public and private subnets, NAT gateways and their Elastic IPs, public and private route tables and associations, private network ACLs and their rules, the S3 gateway endpoint and its route table associations, per-AZ network metadata parameters and the all-AZ catalog, the task role's network-parameter access policy, and the VPC flow log together with its log group, IAM role and inline policy;
  - security: the load balancer and ECS task security groups, every entrypoint ingress rule, all shared egress rules, and every model-specific inference-port rule;
  - identity: the central ECS infrastructure, instance, task execution and task IAM roles, their managed policy attachments, the infrastructure role's pass-role policy, and the ECS instance profile; it does not own resource-specific access policies;
  - artifacts: the per-model ECR repositories and lifecycle policies, artifact buckets and every one of their settings resources, runtime, route and deployment parameters, the all-model catalog, per-model artifact-reader policies, the task role's model-data inline policy, and the ALB access-log bucket with all of its settings resources and bucket policy;
  - compute: the ECS cluster, every model task definition, and both operational and audit log groups for every model;
  - routing: the application load balancer, every model target group and path-routing rule, every entrypoint listener and configuration parameter, the all-entrypoint catalog, and the primary-entrypoint parameter;
  - observability: every model alert and deployment topic, every model target, CPU, memory, error and latency alarm, every per-AZ network operations log group and NAT gateway alarm, every entrypoint log group, alert topic and request and error alarm, and the task role's entrypoint-observability inline policy;
  - queues: every asynchronous inference queue and dead-letter queue, its redrive policy, configuration parameter, log group, alert topic and age, depth and dead-letter error alarms, its worker role and inline policy and publisher policy, the all-queue catalog parameter, and the task role's queue-access inline policy.
- Modules get each other's IDs and ARNs through module outputs and variables. Never paste an ID, ARN, IP address or DNS name of an existing resource, or any part of one (such as an ARN suffix), into the `.tf` files or templates. The configuration reads files only through literal paths inside its own module (such as `"${path.module}/templates/..."`): no computed paths, no `terraform_remote_state` data sources, and never the state or a plan file.

**Keys.**
- Everything that exists once per availability zone today is a `for_each` resource keyed by the AZ name (for example `["us-east-1a"]`), including each instance of a list that also holds things that belong to no single availability zone (the S3 gateway endpoint's associations with private route tables; its association with the public route table is not per AZ).
- Everything that exists once per model service today is a `for_each` resource keyed by the short model key (for example `["opt"]`), including each instance of a list that also holds things that belong to no single model service.
- Exactly one model has network_alert_role equal to "primary" today, and every probe-supplied model map that changes the designation also has exactly one primary. NAT alarms use that model's alert topic; if the primary entry is removed and no remaining entry has that role, their alarm-action lists become empty, and changing the roles switches them to the newly primary model.
- Everything that exists once per asynchronous inference queue today is a `for_each` resource keyed by the queue key (for example `["interactive"]`), including each instance of a list that also holds things that belong to no single asynchronous inference queue.
- Everything that exists once per public entrypoint today is a `for_each` resource keyed by the entrypoint key (for example `["operations"]`), including each instance of a list that also holds things that belong to no single public entrypoint.
- Exactly one entrypoint has purpose "routes" today and model path rules attach to that entrypoint's listener. Exactly one has purpose "primary" today; the primary-entrypoint parameter's value is that entrypoint key, or the literal string "none" when no remaining entry has that purpose. Probe-supplied updates preserve exactly one "routes" and one "primary" purpose while moving both roles to different entries.
- Don't use `count` anywhere. Other repeated resources use `for_each` with string keys that are not numbers (a name such as `["assets"]`, never `["0"]`).
- Each existing availability zone's entry in `availability_zones` is the only source of its values: changing an entry changes, for that availability zone alone, exactly the settings the entry provides, and changes nothing else.
- Adding an availability zone to `availability_zones` must plan only the creation of that availability zone's resources, each configured exactly like its counterparts in the existing availability zones apart from the availability zone itself and the values its entry in `availability_zones` gives it (same settings, names and tags), and removing one only the destruction of that availability zone's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every availability zone today (wherever a setting holds a part of every availability zone: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that availability zone's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing model service's entry in `models` is the only source of its values: changing an entry changes, for that model service alone, exactly the settings the entry provides, and changes nothing else.
- Adding a model service to `models` must plan only the creation of that model service's resources, each configured exactly like its counterparts in the existing model services apart from the model service itself and the values its entry in `models` gives it (same settings, names and tags), and removing one only the destruction of that model service's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every model service today (wherever a setting holds a part of every model service: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that model service's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing asynchronous inference queue's entry in `queues` is the only source of its values: changing an entry changes, for that asynchronous inference queue alone, exactly the settings the entry provides, and changes nothing else.
- Adding an asynchronous inference queue to `queues` must plan only the creation of that asynchronous inference queue's resources, each configured exactly like its counterparts in the existing asynchronous inference queues apart from the asynchronous inference queue itself and the values its entry in `queues` gives it (same settings, names and tags), and removing one only the destruction of that asynchronous inference queue's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every asynchronous inference queue today (wherever a setting holds a part of every asynchronous inference queue: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that asynchronous inference queue's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.
- Each existing public entrypoint's entry in `entrypoints` is the only source of its values: changing an entry changes, for that public entrypoint alone, exactly the settings the entry provides, and changes nothing else.
- Adding a public entrypoint to `entrypoints` must plan only the creation of that public entrypoint's resources, each configured exactly like its counterparts in the existing public entrypoints apart from the public entrypoint itself and the values its entry in `entrypoints` gives it (same settings, names and tags), and removing one only the destruction of that public entrypoint's resources. Beyond that, the only change either may plan is an in-place update of the settings that collect something from every public entrypoint today (wherever a setting holds a part of every public entrypoint: their names, IDs, ARNs, subnets or CIDRs, say, in a list, a policy document or an environment value): each of them must take in, or drop, exactly that public entrypoint's part where it belongs, in the same form as today (today's parts keep their order; where a new part goes is up to you), and change nothing else. No other resource may be created, updated, replaced or destroyed.

**Root variables.** Declare these in the root module, each defaulting to today's value:
- `project` (`string`, `"modelrouter"`): every whole-word occurrence of `modelrouter` in a resource name, identifier or tag value today comes from it (whole word: not part of a longer run of letters and digits, so `modelrouter-api`, `modelrouter_key` and `/modelrouter/` count, while a longer word that merely contains `modelrouter` stays as it is), and so does every mention of those names elsewhere in the configuration (for example a resource name inside a policy); inside documents such as policies, container definitions and environment values, every whole-word occurrence of `modelrouter` that stands for it comes from it too.
- `environment` (`string`, `"prod"`): every whole-word occurrence of `prod` in a resource name, identifier or tag value today comes from it (whole word: not part of a longer run of letters and digits, so `prod-api`, `prod_key` and `/prod/` count, while a longer word that merely contains `prod` stays as it is), and so does every mention of those names elsewhere in the configuration (for example a resource name inside a policy); inside documents such as policies, container definitions and environment values, every whole-word occurrence of `prod` that stands for it comes from it too.
- `tags` (`map(string)`, `{ Owner = "ai-platform", CostCenter = "cc-7310", ManagedBy = "terraform" }`): the shared tags (`Owner`, `CostCenter` and `ManagedBy`) that tagged resources carry today. Wherever the configuration writes them out today, in any form, they come from this variable, so that a different map (other keys, other values) reaches every one of those places; a resource's other tags stay as they are, and resources that are untagged today stay untagged.
- `vpc_cidr` (`string`, `"10.60.0.0/16"`): the VPC's address range; subnet CIDRs remain controlled by the availability-zone map.
- `availability_zones`: `map(object({ public_cidr = string, private_cidr = string, acl_rule_number = number, nat_error_threshold = number, nat_packet_threshold = number, ingress_from_port = number, egress_to_port = number }))`, keyed by AZ name, defaulting to today's three AZs and their public and private subnet CIDRs, private network ACL rule number, NAT error and packet thresholds, ingress start port and egress end port. It is the only source of AZ names and all seven per-AZ settings.
- `models`: `map(object({ cpu = string, memory = string, desired_count = number, priority = number, port = number, health_path = string, error_limit = number, latency_limit = number, runtime_mode = string, network_alert_role = string, cpu_alarm_threshold = number, memory_alarm_threshold = number, health_timeout = number }))`, keyed by short model name, defaulting to today's three models and their task CPU, task memory, desired-capacity metadata, listener priority, inference port, health path, error and latency thresholds, runtime mode, network-alert role, CPU and memory alarm thresholds and health timeout. It is the only source of model keys and all thirteen per-model settings.
- `log_retention_days` (`number`, `30`): the retention of every CloudWatch log group, including VPC flow, per-AZ network, per-model operational and audit, per-queue and per-entrypoint groups.
- `health_check_interval` (`number`, `30`): the health-check interval of every model target group.
- `deregistration_delay` (`number`, `120`): the deregistration delay of every model target group.
- `alarm_period` (`number`, `60`): the period of every CloudWatch metric alarm.
- `alarm_evaluation_periods` (`number`, `2`): the evaluation-period count of every CloudWatch metric alarm.
- `bucket_expiration_days` (`number`, `365`): the expiration in every model-artifact lifecycle rule and the access-log lifecycle rule.
- `bucket_noncurrent_days` (`number`, `90`): the noncurrent-version expiration in every model-artifact lifecycle rule.
- `force_destroy_buckets` (`bool`, `false`): the force-destroy setting of every model-artifact bucket and the access-log bucket.
- `alb_idle_timeout` (`number`, `60`): the application load balancer's idle timeout.
- `enable_deletion_protection` (`bool`, `false`): the application load balancer's deletion-protection setting.
- `task_ephemeral_storage` (`number`, `50`): the ephemeral storage size in every model task definition.
- `ecr_scan_on_push` (`bool`, `true`): the image scan-on-push setting of every model repository.
- `queues`: `map(object({ visibility_timeout_seconds = number, message_retention_seconds = number, max_receive_count = number, age_alarm_threshold = number, depth_alarm_threshold = number, delay_seconds = number, dlq_retention_seconds = number, error_alarm_threshold = number }))`, keyed by queue name, defaulting to today's three asynchronous inference queues and their visibility timeout, message retention, maximum receive count, oldest-message and visible-depth alarm thresholds, delivery delay, dead-letter retention and dead-letter error threshold. It is the only source of queue keys and all eight per-queue settings.
- `queue_long_poll_seconds` (`number`, `20`): the long-poll wait time of every asynchronous inference queue.
- `alarm_actions_enabled` (`bool`, `true`): whether actions are enabled on every CloudWatch metric alarm.
- `entrypoints`: `map(object({ port = number, cidr_blocks = list(string), purpose = string, response_prefix = string, status_code = string, request_threshold = number, error_threshold = number }))`, keyed by entrypoint name, defaulting to today's partner, public and operations entrypoints and their listener port, ingress CIDR list, purpose, fixed-response prefix and status code, request threshold and error threshold. It is the only source of entrypoint keys and all seven per-entrypoint settings.
- `alarm_datapoints_to_alarm` (`number`, `2`): the datapoints-to-alarm count of every CloudWatch metric alarm.
- `ecr_images_to_keep` (`number`, `20`): the retained image count in every model repository lifecycle policy.
- `queue_max_message_size` (`number`, `262144`): the maximum message size of every asynchronous inference queue and dead-letter queue.
- `flow_log_aggregation_interval` (`number`, `600`): the VPC flow log's maximum aggregation interval.
- Changing `vpc_cidr`, `log_retention_days`, `health_check_interval`, `deregistration_delay`, `alarm_period`, `alarm_evaluation_periods`, `bucket_expiration_days`, `bucket_noncurrent_days`, `force_destroy_buckets`, `alb_idle_timeout`, `enable_deletion_protection`, `task_ephemeral_storage`, `ecr_scan_on_push`, `queue_long_poll_seconds`, `alarm_actions_enabled`, `alarm_datapoints_to_alarm`, `ecr_images_to_keep`, `queue_max_message_size` and `flow_log_aggregation_interval` changes only what each one's line above says it controls: every other setting keeps today's value, including a setting that merely has the same value today.

**Root outputs.** Keep `vpc_id`, `cluster_name`, `alb_name`, `alb_dns_name`, `access_logs_bucket_name` and `task_role_arn` with their current values. `public_subnet_ids` becomes a map from the AZ name to the `id` of that availability zone's `aws_subnet.public`. `private_subnet_ids` becomes a map from the AZ name to the `id` of that availability zone's `aws_subnet.private`. `nat_public_ips` becomes a map from the AZ name to the `public_ip` of that availability zone's `aws_eip.nat`. `model_bucket_names` becomes a map from the short model key to the `bucket` of that model service's `aws_s3_bucket.model`. `model_repository_urls` becomes a map from the short model key to the `repository_url` of that model service's `aws_ecr_repository.model`. `target_group_arns` becomes a map from the short model key to the `arn` of that model service's `aws_lb_target_group.model`. `log_group_names` becomes a map from the short model key to the `name` of that model service's `aws_cloudwatch_log_group.model`. `alert_topic_arns` becomes a map from the short model key to the `arn` of that model service's `aws_sns_topic.model_alerts`. `queue_urls` becomes a map from the queue key to the `url` of that asynchronous inference queue's `aws_sqs_queue.inference`. `queue_alert_topic_arns` becomes a map from the queue key to the `arn` of that asynchronous inference queue's `aws_sns_topic.queue_alerts`. `az_network_parameter_names` becomes a map from the AZ name to the `name` of that availability zone's `aws_ssm_parameter.az_network`. `entrypoint_listener_arns` becomes a map from the entrypoint key to the `arn` of that public entrypoint's `aws_lb_listener.entrypoint`. `entrypoint_alert_topic_arns` becomes a map from the entrypoint key to the `arn` of that public entrypoint's `aws_sns_topic.entrypoint_alerts`. Each output passes through outputs of the module that owns the resource (network for `vpc_id`, `public_subnet_ids`, `private_subnet_ids`, `nat_public_ips` and `az_network_parameter_names`; identity for `task_role_arn`; artifacts for `model_bucket_names`, `model_repository_urls` and `access_logs_bucket_name`; compute for `log_group_names` and `cluster_name`; routing for `target_group_arns`, `alb_name`, `alb_dns_name` and `entrypoint_listener_arns`; observability for `alert_topic_arns` and `entrypoint_alert_topic_arns`; queues for `queue_urls` and `queue_alert_topic_arns`): the root output is a plain reference to an output of that module, and that module output is a plain reference to the resource. A plain reference is a reference such as `module.network.<output>` or `<resource type>.<name>.<attribute>`, a local that holds one, or a `for` expression that only re-keys one (`{ for k, v in <reference> : k => v.id }`) or iterates a plain reference and looks each key up in one (`{ for k, v in var.<map> : k => <reference>[k].id }`); no literals, function calls, conditionals or string templates anywhere along the way.

**Not allowed anywhere in the configuration:** `ignore_changes`, `prevent_destroy` and `replace_triggered_by`, `removed` and `import` blocks, provisioners, `external` data sources, backend or cloud blocks, provider blocks other than the one in `providers.tf`, override files and `.tf.json` files.

</div>
</details>

#### Average reward

| Model | Graded runs | Average reward |
|---|---:|---:|
| z-ai/glm-5.3-flash | 5 | 80% |
| google/gemini-4-argon | 2 | 50% |

#### Environment

![How the task works](assets/env-modelrouter-module-refactor.svg)

### Example 4: Cloud infra: containers & self-hosted platforms (TypeScript)

| Field | Value |
|---|---|
| Task id | [`atlasgrid-pulumi-migration`](https://drive.google.com/file/d/1l8nNQLGUM8GbW_dp8HFuPQb2nHNGh6J-/view) |
| Final category | Infrastructure as code |
| Domain | Cloud infrastructure & IaC |
| Sub-domain | Cloud infra: containers & self-hosted platforms |
| Language | TypeScript |
| Seniority | Senior |
| Turn count | 210 (google/gemini-3.8-flash), 89 (google/gemini-4-argon) |
| Long horizon | no |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

##### Pulumi program for AtlasGrid's imported `dev` stack

AtlasGrid's production ECS platform is managed with Terraform (`/workspace/terraform`; `terraform.tfstate` is production). The platform team bulk-imported every production resource into stack `dev` of the Pulumi project `/workspace/pulumi`, but its entry point `index.ts` declares nothing, so a preview would delete everything. We need the matching TypeScript program.

###### What we need

- Each module call is a `pulumi.ComponentResource` under the stack, named after the module and typed `atlasgrid:modules:<Module>` (`Network`, `Identity`, `Edge`, `Cluster`, `Workloads`, `Observability`).
- Each Terraform resource instance is one `@pulumi/aws` resource under its module's component, named after the Terraform resource plus `-<key>` for `for_each` instances (`ecs-us-east-1a`).
- Each variable in `variables.tf` is a same-named config key (`atlasgrid-ecs:project`, …) holding its value as plain YAML (integers, strings, mappings); unset keys take the Terraform default.
- For any values Terraform and AWS accept, `pulumi preview` plans the same creates, updates, replacements, deletions, settings and outputs as `terraform plan` with those values.
- Values Terraform reads from another resource's attribute come from that attribute's output (unknown in preview exactly where unknown in Terraform's plan).
- Lists built from maps use sorted key order, and later maps win in `merge()`.
- If the stack state drifts, the preview reverts the drift as Terraform would.
- Stack outputs match `outputs.tf`: same names and values (maps as objects).
- Default `aws` provider only; no `protect`, `ignoreChanges`, `retainOnDelete`, `deletedWith`, `import`, `aliases`, `replaceOnChanges`, `replaceWith`, `customTimeouts`, `transforms` or `hooks` options, stack transforms, remote components, `.get()` lookups, `StackReference`s or provider functions like `aws.getRegion()`.
- No production-generated IDs, ARNs, account ID, IPs or DNS names anywhere in `/workspace/pulumi`, even partly or in notes; constants from the Terraform code are fine.
- The program runs offline from the regular files in `/workspace/pulumi` alone (no symlinks).

###### Keep working

- Production: `pulumi preview --refresh=false` on `dev` shows no changes
- A clean `npx tsc --noEmit`
- `Pulumi.yaml`, `Pulumi.dev.yaml`, `package.json`, `tsconfig.json`, `templates/`, byte for byte (undo any `pulumi config set`)

###### Setup

No AWS access; `pulumi preview --refresh=false` works offline (backend `/workspace/pulumi-state` and passphrase preset) and `pulumi stack export` shows every URN. In `/workspace/terraform`, `terraform init -input=false` and `terraform plan -refresh=false` work offline from a provider mirror, including with `-var`/`-var-file`. `node_modules` links to the image's packages (Node.js 22, versions per `package.json`; `@pulumi/aws` 6.83.0 is built on Terraform's AWS provider 5.100.0); nothing can be installed. `templates/userdata.sh.tpl` copies the cluster module's template.

</div>
</details>

#### Average reward

| Model | Graded runs | Average reward |
|---|---:|---:|
| google/gemini-3.8-flash | 3 | 67% |
| google/gemini-4-argon | 2 | 50% |

#### Environment

![How the task works](assets/env-atlasgrid-pulumi-migration.svg)

<div data-chart-runtime>
<style>.cx{margin:30px 0 36px;max-width:940px;min-width:0}
.cx .fig-box{position:relative}
.cx-chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.cx-chip{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid var(--ink);background:var(--card);cursor:pointer;font:500 13px/1.3 var(--sans);color:var(--ink)}
.cx-chip[aria-pressed=false]{border-color:var(--line);color:var(--faint);background:transparent}
.cx-dot{width:10px;height:10px;background:var(--ink)}.cx-chip[aria-pressed=false] .cx-dot{background:var(--line)}
.cx-n{font:11px var(--mono);color:var(--muted)}
.cx-strip{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 12px;padding:8px 10px;background:var(--soft);font-size:13px}
.cx-strip-lab{font:600 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cx-filter{border:1px solid var(--red);background:var(--card);color:var(--red-ink);padding:3px 9px;cursor:pointer;font:500 13px var(--sans)}
.cx-clearall{border:0;background:none;color:var(--muted);text-decoration:underline;cursor:pointer;font:13px var(--sans)}
.cx-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin:0 0 12px;font-size:13px}
.cx-seg{display:inline-flex;border:1px solid var(--ink)}.cx-seg button{border:0;background:transparent;padding:5px 11px;cursor:pointer;font:500 13px var(--sans);color:var(--ink)}
.cx-seg button+button{border-left:1px solid var(--ink)}.cx-seg button[aria-pressed=true]{background:var(--ink);color:#fff}
.cx-hint-inline{color:var(--muted)}
.cx-slider{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2)}.cx-slider input{accent-color:var(--red);width:120px}
.cx-check{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--ink-2);margin:0 0 6px;cursor:pointer}.cx-check input{accent-color:var(--red)}
.cx-summary{font-size:15px;margin:0 0 6px;color:var(--ink)}
.cx-svg{display:block;width:100%;height:auto;touch-action:none;user-select:none}
.cx-tick{font:11px var(--sans);fill:var(--muted)}.cx-axis{font:12px var(--sans);fill:var(--muted)}
.cx-rowlab{font:600 13px var(--sans);fill:var(--ink)}.cx-collab{font:600 12px var(--sans);fill:var(--ink-2)}
.cx-cellv{font:600 15px var(--sans)}.cx-cells{font:10.5px var(--sans)}.cx-cell{cursor:pointer}.cx-cell:hover{stroke:var(--ink)}
.cx-mean{font:600 12px var(--sans);fill:var(--ink)}.cx-thr{font:600 12px var(--sans);fill:var(--red-ink)}.cx-band{font:600 11px var(--sans);fill:var(--teal)}
.cx-col{fill:var(--ink);cursor:pointer}.cx-col:hover,.cx-col:focus-visible{fill:var(--teal);outline:none}.cx-col.is-on{fill:var(--red)}
.cx-pt{fill:var(--red);fill-opacity:.38;cursor:pointer}.cx-pt:hover{fill-opacity:1}.cx-pt.is-on{fill-opacity:1;stroke:var(--ink);stroke-width:1.5}
.cx-handle{cursor:ew-resize;outline:none}.cx-handle:focus-visible circle{stroke:var(--ink)}
.cx-hint{font-size:13px;color:var(--muted);margin:6px 0 0}
.cx-cap{font-size:14px;font-weight:600;margin:18px 0 0}.cx-link{border:0;background:none;padding:0 0 0 8px;color:var(--red-ink);text-decoration:underline;cursor:pointer;font:inherit;font-weight:500}
.cx-grid{margin-top:8px;font-size:14px;font-variant-numeric:tabular-nums}.cx-row{display:grid;grid-template-columns:minmax(0,1fr) 130px 120px 130px;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
.cx-row>span:not(:first-child){text-align:right;white-space:nowrap}.cx-head{color:var(--muted);font-size:13px;font-weight:600;border-bottom-color:var(--ink)}
.cx-grid5 .cx-row{grid-template-columns:minmax(0,1fr) 70px 110px 95px 95px 105px}
.cx-meter{display:inline-block;width:70px;height:8px;background:var(--line-2);margin-right:8px;vertical-align:middle}.cx-meter span{display:block;height:100%;background:var(--ink)}
.cx-panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px 40px}
.cx-panel-title{font:600 13px var(--sans);color:var(--muted);margin:0 0 6px}.cx-panel-foot{font-size:12px;color:var(--muted);margin-top:6px}
.cx-bar{display:grid;grid-template-columns:minmax(120px,42%) 1fr 52px;align-items:center;gap:10px;padding:4px 4px;cursor:pointer;font-size:14px;line-height:1.3}
.cx-bar:hover{background:var(--soft)}.cx-bar:focus-visible{outline:2px solid var(--red)}
.cx-bar-lab{display:flex;align-items:center;gap:4px;color:var(--ink);min-width:0;overflow-wrap:anywhere}
.cx-bar-track{height:16px;background:transparent}.cx-bar-fill{display:block;height:100%;background:var(--ink);min-width:1px}
.cx-bar-val{text-align:right;font:600 13px var(--sans);font-variant-numeric:tabular-nums;color:var(--ink)}
.cx-bar.is-on .cx-bar-fill{background:var(--red)}.cx-bar.is-on .cx-bar-lab{font-weight:600}
.cx-bar.is-child{font-size:13px}.cx-bar.is-child .cx-bar-lab{padding-left:24px;color:var(--ink-2)}.cx-bar.is-child .cx-bar-fill{background:var(--teal)}.cx-bar.is-child.is-on .cx-bar-fill{background:var(--red)}
.cx-expand{border:0;background:none;padding:0 4px 0 0;cursor:pointer;color:var(--muted);font-size:12px;width:16px}
.cx-tip{position:absolute;z-index:5;pointer-events:none;background:var(--ink);color:#fff;font:12.5px/1.45 var(--sans);padding:8px 10px;max-width:300px}
.cx-detail{margin-top:14px;padding:12px 14px;background:var(--card);border:1px solid var(--line-2);border-left:3px solid var(--red);font-size:14px;line-height:1.6}
.cx-mini{display:flex;align-items:flex-end;gap:6px;height:150px;margin:12px 0 4px}.cx-mini-col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;text-align:center}
.cx-mini-bar{background:var(--ink);min-height:1px}.cx-mini-n{font:600 11px var(--sans);color:var(--ink);margin-top:3px}.cx-mini-lab{font:10px var(--sans);color:var(--muted)}
@media (max-width:640px){.cx-row{grid-template-columns:minmax(0,1fr) 64px 64px 80px}.cx-grid5 .cx-row{grid-template-columns:minmax(0,1fr) 44px 60px 52px 52px 56px}.cx-meter{display:none}.cx-bar{grid-template-columns:minmax(90px,45%) 1fr 46px}}
</style>
<script type="application/json" data-chart-data>{"cross":true,"models":["z-ai/glm-5.3-flash","google/gemini-4-argon","google/gemini-3.8-flash"],"dims":{"g":["Cloud infrastructure & IaC","Security"],"c":["Cloud infra: AWS platform stacks","Cloud infra: containers & self-hosted platforms","Cloud infra: serverless & event-driven","Cloud security & compliance"],"l":["HCL (Terraform)","Python","TypeScript"],"s":["Senior","Staff+"]},"tasks":[[0,0,0,0,{"0":[1,0,1,0,0]},{"0":[365,5]}],[0,2,0,0,{"0":[1,1,0,0,0]},{"0":[601,5]}],[0,0,0,0,{"0":[0,1,0,1,0]},{"0":[372,5]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[493,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[790,5]}],[0,1,0,0,{"0":[1,0,0,1,0]},{"0":[721,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[350,5]}],[0,0,0,0,{"0":[1,1,0,1,0]},{"0":[450,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[599,5]}],[0,1,0,0,{"1":[1,1],"0":[1,1,1,0,1]},{"1":[59,2],"0":[309,5]}],[0,0,0,0,{"0":[1,1,1,1,0,0,0,0,0.8864]},{"0":[2303,9]}],[0,1,0,0,{"0":[1,0,1,0,1]},{"0":[546,5]}],[0,2,0,0,{"0":[1,1,1,0,1]},{"0":[1356,5]}],[0,0,0,0,{"0":[0,1,1,1,1,0]},{"0":[537,6]}],[0,2,0,0,{"0":[1,1,0,1,1]},{"0":[499,5]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[439,5]}],[0,1,0,0,{"0":[1,0.9268,1,0]},{"0":[608,4]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[607,5]}],[0,0,0,0,{"1":[1,0],"0":[1,0,1,1,1]},{"1":[117,2],"0":[887,5]}],[0,2,0,0,{"0":[1,0.931,0.931,1,0,0,1,0,0,0,0,0,0,0]},{"0":[1363,14]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[396,5]}],[0,0,0,0,{"0":[1,1,0,1,0]},{"0":[488,5]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[458,5]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[1067,5]}],[0,0,0,0,{"0":[1,0,1,1,0]},{"0":[994,5]}],[0,1,0,0,{"0":[1,0,1,1]},{"0":[252,4]}],[0,1,0,0,{"0":[0,1,1,1]},{"0":[264,4]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[560,5]}],[0,0,0,0,{"0":[1,1,0,1,0.9318]},{"0":[1182,5]}],[0,0,0,0,{"0":[1,0,0.9355,0,0,0,1]},{"0":[839,7]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[889,5]}],[0,2,0,0,{"1":[1,1],"0":[1,0,1,1,0]},{"1":[120,2],"0":[484,5]}],[0,1,0,0,{"0":[1,0,0,1,1]},{"0":[524,5]}],[0,0,0,0,{"0":[1,1,0.8846,1,1]},{"0":[546,5]}],[0,2,0,0,{"0":[1,0,1,1,1]},{"0":[1148,5]}],[0,0,0,0,{"0":[1,0,1,1,0.98]},{"0":[1035,5]}],[0,1,0,0,{"0":[0,1,0,1,1]},{"0":[480,5]}],[0,2,0,0,{"0":[1,1,1,1,0]},{"0":[435,5]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[559,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[432,5]}],[0,1,0,0,{"0":[1,1,0,1,1]},{"0":[439,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[500,5]}],[0,0,0,0,{"1":[1,1],"0":[1,1,1,1,0]},{"1":[115,2],"0":[273,5]}],[0,1,0,0,{"0":[1,0,1,1,0]},{"0":[578,5]}],[0,0,0,0,{"0":[0,0,0,1,0]},{"0":[373,5]}],[0,0,0,0,{"0":[1,0,1,1,0.96]},{"0":[614,5]}],[0,0,0,0,{"0":[1,0,1,0,1]},{"0":[445,5]}],[0,1,0,0,{"1":[1,1],"0":[0,1,1,1,0]},{"1":[95,2],"0":[432,5]}],[0,0,0,0,{"0":[1,0,0,0,0,0,0,0,0.875,0,0.975,1,0,0,0]},{"0":[1700,15]}],[0,1,0,0,{"0":[0,1,0,0,1,0,1,0]},{"0":[1050,8]}],[0,1,2,0,{"1":[1,0],"2":[1,0,1]},{"1":[178,2],"2":[629,3]}],[0,0,0,0,{"0":[1,1,0,0,0,0,0]},{"0":[802,7]}],[0,0,0,0,{"0":[0,1,1,0]},{"0":[553,4]}],[0,1,0,0,{"0":[0,1,0,1,1]},{"0":[478,5]}],[0,2,0,0,{"0":[1,1,1,0,0]},{"0":[478,5]}],[0,0,0,0,{"0":[1,1,0,1]},{"0":[373,4]}],[0,0,0,0,{"0":[1,1,0,0,0,1,0.825,0,1]},{"0":[1545,9]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[555,5]}],[0,1,0,0,{"0":[0,0,1,0,1,0,1]},{"0":[884,7]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[358,5]}],[0,0,0,0,{"0":[0,1,1,1,0]},{"0":[462,5]}],[0,0,0,0,{"0":[0,1,0,1,0,0.8571,0,0,0,1]},{"0":[1808,10]}],[0,1,0,0,{"0":[1,0,0,0,1]},{"0":[820,5]}],[0,1,0,0,{"0":[1,1,0,0,1]},{"0":[651,5]}],[0,2,0,0,{"0":[0,1,1,1,1]},{"0":[578,5]}],[0,2,0,0,{"0":[1,1,0,0,1]},{"0":[599,5]}],[0,0,0,0,{"0":[1,0,0,0.92,0]},{"0":[433,5]}],[0,0,0,0,{"0":[1,1,0,1]},{"0":[282,4]}],[0,0,0,0,{"0":[1,1,0,0,0]},{"0":[681,5]}],[0,2,0,0,{"0":[1,1,0,1]},{"0":[287,4]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[575,5]}],[0,0,0,0,{"0":[1,0,1,0,0,0,0,0]},{"0":[872,8]}],[0,0,0,0,{"0":[1,0,0,0,1]},{"0":[656,5]}],[0,1,0,0,{"0":[0,1,1,0,1,0]},{"0":[436,6]}],[0,1,0,0,{"0":[1,1,0.9545,1,1]},{"0":[620,5]}],[0,0,0,0,{"0":[1,0,0,1,1]},{"0":[369,5]}],[0,0,0,0,{"0":[0,1,1,1]},{"0":[481,4]}],[0,2,0,0,{"0":[0,1,1,1,1]},{"0":[420,5]}],[0,2,0,0,{"0":[1,1,0,1,0,1]},{"0":[934,6]}],[0,1,0,0,{"1":[1,1],"0":[0,1,0,1,1]},{"1":[132,2],"0":[364,5]}],[0,0,0,0,{"0":[1,1,0,0,1,0]},{"0":[707,6]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[683,5]}],[0,2,0,0,{"2":[1,0,1],"0":[0,0,1,1,0,0,0,0,0.9429]},{"2":[435,3],"0":[1135,9]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[313,5]}],[0,2,0,0,{"0":[1,0,0,1,1]},{"0":[886,5]}],[0,1,0,0,{"0":[0,1,0,1,1]},{"0":[456,5]}],[0,0,0,0,{"0":[1,1,1,0]},{"0":[366,4]}],[0,0,2,0,{"1":[1,1]},{"1":[198,2]}],[0,1,0,0,{"0":[1,0,1,1,0]},{"0":[818,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[239,5]}],[0,1,0,0,{"0":[0,1,0,1,1]},{"0":[409,5]}],[0,0,0,0,{"0":[0,0,0,0,0]},{"0":[589,5]}],[0,2,0,0,{"0":[1,1,0,0.9787,1]},{"0":[660,5]}],[0,0,0,0,{"0":[1,1,1,0.9756,0]},{"0":[576,5]}],[0,0,0,0,{"1":[1,1],"0":[0.9714,0.9714,0.9714,1,1]},{"1":[82,2],"0":[319,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[482,5]}],[0,0,0,0,{"0":[1,1,1,0,0]},{"0":[313,5]}],[0,2,0,0,{"0":[1,0,1,0]},{"0":[574,4]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[387,5]}],[0,0,0,0,{"0":[1,0.9672,1,1,0.9672,1]},{"0":[845,6]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[389,5]}],[0,0,0,0,{"0":[1,1,0,0,0]},{"0":[816,5]}],[0,0,0,0,{"0":[1,0.9535,1,0,1]},{"0":[932,5]}],[0,0,0,0,{"0":[1,1,0.8,1]},{"0":[511,4]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[480,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[265,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[739,5]}],[0,2,0,0,{"0":[1,0,0.9231,1,0.8462]},{"0":[854,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[588,5]}],[0,0,0,0,{"0":[1,0,1,1]},{"0":[544,4]}],[0,0,0,0,{"0":[0,1,0,0,0]},{"0":[326,5]}],[0,1,0,0,{"1":[0,0],"0":[0,0,1,0,1]},{"1":[93,2],"0":[501,5]}],[0,0,2,0,{"1":[1,1]},{"1":[290,2]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[514,5]}],[0,0,0,0,{"1":[1,1],"0":[0.9273,0,1,1]},{"1":[129,2],"0":[712,4]}],[0,1,0,0,{"0":[1,1,0,1,1]},{"0":[363,5]}],[0,1,0,0,{"0":[1,0,1,0,0,0,1]},{"0":[728,7]}],[0,1,0,0,{"0":[1,1,1,0,0]},{"0":[554,5]}],[0,1,0,0,{"0":[1,1,0,0,1]},{"0":[421,5]}],[0,1,0,0,{"0":[1,0,1,0,1]},{"0":[426,5]}],[0,1,0,0,{"0":[1,1,1,1,0]},{"0":[419,5]}],[0,2,0,0,{"0":[1,1,1,0,1]},{"0":[452,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[269,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[353,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[686,5]}],[0,2,0,0,{"0":[1,1,1,0.96,1,0]},{"0":[1026,6]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[503,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[364,5]}],[0,1,0,0,{"0":[1,1,1,0,0]},{"0":[284,5]}],[0,0,0,0,{"0":[0,0,0,0,0]},{"0":[670,5]}],[0,2,0,0,{"0":[0,0,1,0,1]},{"0":[367,5]}],[0,0,0,0,{"1":[0,0],"0":[0,0,0,0,1,0,0,1,1,0,0,0,0,0,0,0]},{"1":[140,2],"0":[2245,16]}],[0,0,0,0,{"0":[1,0,1,1]},{"0":[472,4]}],[0,1,0,0,{"0":[0.9318,0,1,1,0,0,0,0,1]},{"0":[1554,9]}],[0,0,0,0,{"0":[1,1,0,0,0]},{"0":[742,5]}],[0,0,0,0,{"0":[0.9583,1,1,1,0.9583]},{"0":[549,5]}],[0,1,0,0,{"0":[1,1,1,0,0]},{"0":[602,5]}],[0,1,0,0,{"0":[0,0,0,1,1]},{"0":[464,5]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[397,5]}],[0,1,0,0,{"0":[1,0,1,1,1]},{"0":[482,5]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[546,5]}],[0,0,0,0,{"0":[0,0,1,1,0]},{"0":[427,5]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[685,5]}],[0,0,0,0,{"0":[1,1,0.9787,1,1]},{"0":[606,5]}],[0,1,0,0,{"0":[1,1,0,0,1]},{"0":[425,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[468,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[441,5]}],[0,0,0,0,{"0":[1,0,0,0,1]},{"0":[542,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[509,5]}],[0,0,0,0,{"0":[0,0,1,1,1]},{"0":[522,5]}],[0,2,0,0,{"0":[0,1,1,1,0]},{"0":[610,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[776,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[528,5]}],[0,0,0,0,{"0":[1,1,0.9583,1,1]},{"0":[413,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[487,5]}],[0,2,0,0,{"0":[0.9143,1,1,1,0.9429]},{"0":[454,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[714,5]}],[0,1,0,0,{"0":[1,1,0,1,1]},{"0":[415,5]}],[0,1,0,0,{"0":[0.931,1,1,1,0,0,0,0,0,1,0]},{"0":[854,11]}],[0,1,0,0,{"0":[0.9688,1,1,0,1]},{"0":[586,5]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[921,5]}],[0,0,0,0,{"0":[0,1,0.7097,1,0.7097,0,0,0,0,0]},{"0":[1325,10]}],[0,0,0,0,{"0":[1,0.9792,1,1,1]},{"0":[861,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[539,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[874,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[412,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[698,5]}],[0,0,0,0,{"0":[0,1,0.975,0,1,1,0,0,0,0]},{"0":[1999,10]}],[0,0,0,0,{"0":[1,1,0,0,0,1,1]},{"0":[1281,7]}],[0,0,0,0,{"0":[1,0,0,1,0]},{"0":[550,5]}],[0,1,0,0,{"0":[1,1,0.9643,1,1]},{"0":[310,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[555,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[390,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[654,5]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[522,5]}],[0,0,0,0,{"0":[1,0,1,1,0]},{"0":[488,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[741,5]}],[0,1,0,0,{"0":[1,1,1,0,0,1,0,0]},{"0":[1020,8]}],[0,0,0,0,{"0":[1,1,0.9643,0,0.9643]},{"0":[455,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[585,5]}],[0,0,0,0,{"0":[1,0,0,1,1]},{"0":[548,5]}],[0,1,0,0,{"0":[0,0,0,0,0]},{"0":[394,5]}],[0,0,0,0,{"0":[0,1,0,1,1]},{"0":[827,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[551,5]}],[0,0,0,0,{"0":[1,1,1,0.96,1]},{"0":[467,5]}],[0,0,0,0,{"0":[1,0,1,1,0]},{"0":[394,5]}],[0,0,0,0,{"0":[0,1,1,1,0]},{"0":[546,5]}],[0,0,1,0,{"1":[1,1],"2":[1,1,1]},{"1":[576,2],"2":[780,3]}],[0,1,0,0,{"0":[0,1,0,0,1]},{"0":[587,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[407,5]}],[0,2,0,0,{"0":[1,0,1,1,0,1]},{"0":[945,6]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[503,5]}],[0,0,0,0,{"1":[1,1],"0":[1,0,0,1,0,0,1]},{"1":[132,2],"0":[705,7]}],[0,1,0,0,{"0":[1,1,0,1,1]},{"0":[312,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[623,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[526,5]}],[0,1,0,0,{"0":[0,0,0,0,0]},{"0":[489,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[531,5]}],[0,0,0,0,{"0":[1,1,0.931,0,1]},{"0":[527,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[670,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[772,5]}],[0,0,0,0,{"0":[0,1,1,1,0]},{"0":[333,5]}],[0,1,0,0,{"2":[1,1,1],"0":[0,0,0,0,0]},{"2":[317,3],"0":[430,5]}],[0,0,0,0,{"0":[0,1,1,0,0,0,1,0]},{"0":[921,8]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[585,5]}],[0,2,0,0,{"0":[1,1,0,1,1]},{"0":[568,5]}],[0,1,0,0,{"0":[1,0,1,1,1]},{"0":[703,5]}],[0,2,0,0,{"0":[1,1,1,1,0]},{"0":[546,5]}],[0,0,0,0,{"0":[0,0,0,0,0.9714,0,0,0,0,0.9429,0,0.9143,0,0,0]},{"0":[2180,15]}],[0,1,0,0,{"0":[0,1,1,0,1]},{"0":[585,5]}],[0,2,0,0,{"0":[0,1,1,1,0]},{"0":[404,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[511,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[539,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[351,5]}],[0,0,0,0,{"0":[0,0,0,0,0]},{"0":[476,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[1046,5]}],[0,2,0,0,{"1":[1,1],"0":[1,1,0,0,1]},{"1":[112,2],"0":[945,5]}],[1,3,0,0,{"0":[0,0,1,1,0]},{"0":[1458,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[571,5]}],[0,1,0,0,{"0":[1,1,0,1,1]},{"0":[443,5]}],[0,1,0,0,{"0":[1,0,1,0,1]},{"0":[329,5]}],[0,1,0,0,{"0":[0,1,1,1,1]},{"0":[324,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[360,5]}],[0,1,0,0,{"0":[1,1,0,1,0]},{"0":[761,5]}],[0,0,0,0,{"0":[0.9773,1,1,1,1]},{"0":[1076,5]}],[0,0,0,0,{"0":[0,0,0,0,1,0,0,0,1,0,0,1,0.9643,0,0]},{"0":[1876,15]}],[0,1,0,0,{"0":[0,1,1,0,0,0,0,0,1,1,0]},{"0":[1808,11]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[505,5]}],[0,0,0,0,{"0":[0.96,1,1,1,1]},{"0":[535,5]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[714,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[370,5]}],[0,1,0,0,{"0":[0,0,1,1,1]},{"0":[631,5]}],[0,2,0,0,{"0":[1,1,0,1,1]},{"0":[516,5]}],[0,0,0,0,{"0":[1,0,1,0,0,0.9773,0,1,0,0,0,0.9318]},{"0":[1851,12]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[482,5]}],[0,2,0,0,{"0":[1,1,0,1,1]},{"0":[604,5]}],[0,1,0,0,{"0":[1,1,1,1,0]},{"0":[463,5]}],[0,0,0,0,{"1":[0,0],"0":[1,1,1,1,0]},{"1":[140,2],"0":[722,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[479,5]}],[0,2,0,0,{"0":[1,1,0,0,0,1,0,0,1,0]},{"0":[1236,10]}],[0,1,0,0,{"1":[1,1],"0":[1,1,0,1,1]},{"1":[112,2],"0":[489,5]}],[0,2,0,0,{"0":[0,1,1,1,1]},{"0":[552,5]}],[0,0,0,0,{"0":[1,1,1,0.9778]},{"0":[771,4]}],[0,0,0,0,{"0":[0,1,0.8519,1,1]},{"0":[672,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[561,5]}],[0,0,0,0,{"0":[1,0,1,1]},{"0":[266,4]}],[0,1,0,0,{"0":[0,0.9778,0,1,0,0,0,0,1,1]},{"0":[2107,10]}],[0,0,0,0,{"0":[1,1,0.9444,1,1]},{"0":[537,5]}],[0,0,0,0,{"2":[1,1,1],"0":[0,0,0,0,0]},{"2":[274,3],"0":[682,5]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[730,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[759,5]}],[0,0,0,0,{"0":[0.8966,0.931,1,1,1]},{"0":[510,5]}],[0,0,0,0,{"0":[1,1,1,0,1]},{"0":[605,5]}],[0,0,0,0,{"0":[1,0,1,0]},{"0":[390,4]}],[0,2,0,0,{"0":[1,1,0,0,0]},{"0":[683,5]}],[0,1,0,0,{"0":[1,1,1,0.9286,0,1,0,0,0]},{"0":[664,9]}],[0,0,0,0,{"0":[0,1,0,0,1]},{"0":[281,5]}],[0,1,0,0,{"0":[1,1,0,1,0]},{"0":[350,5]}],[0,0,0,0,{"0":[0,1,1,1,1]},{"0":[701,5]}],[0,0,0,0,{"0":[0,1,0,0,1,0.9167,0,0,0]},{"0":[1059,9]}],[0,0,0,0,{"0":[1,1,1,0,0]},{"0":[691,5]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[380,5]}],[0,0,0,0,{"0":[1,0,1,1]},{"0":[424,4]}],[1,3,0,0,{"0":[1,1,0,1,1]},{"0":[1197,5]}],[0,0,0,0,{"0":[0.96,1,0.96,1,1]},{"0":[265,5]}],[0,0,0,0,{"1":[0,1],"0":[0,0,0,0,0]},{"1":[71,2],"0":[497,5]}],[0,1,0,0,{"0":[1,1,0,1,1]},{"0":[359,5]}],[0,0,0,0,{"0":[0,0,1,1]},{"0":[668,4]}],[0,0,0,0,{"0":[1,1,0,1,1]},{"0":[461,5]}],[0,0,0,0,{"0":[1,1,1,0]},{"0":[461,4]}],[0,0,0,0,{"0":[1,1,0,1,0]},{"0":[552,5]}],[1,3,0,0,{"2":[0,1,1]},{"2":[623,3]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[366,5]}],[0,1,0,0,{"0":[1,1,1,0,0]},{"0":[400,5]}],[0,1,0,0,{"0":[0,1,0,0,1]},{"0":[554,5]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[346,5]}],[0,1,0,0,{"2":[0,0,0],"0":[0,0,0,0]},{"2":[234,3],"0":[332,4]}],[0,0,0,0,{"1":[1,1],"0":[1,1,0,0,0]},{"1":[93,2],"0":[563,5]}],[0,1,0,0,{"0":[0,1,1,1,0]},{"0":[340,5]}],[0,2,0,0,{"0":[0,1,0,1,1]},{"0":[664,5]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[669,5]}],[0,0,0,0,{"0":[1,1,1,1,0.9412]},{"0":[855,5]}],[0,0,0,0,{"0":[0,1,0,0,1]},{"0":[403,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[570,5]}],[0,2,0,0,{"0":[1,1,1,0,1]},{"0":[408,5]}],[0,0,0,0,{"0":[1,1,0,0,1]},{"0":[578,5]}],[0,2,0,0,{"0":[0.9167,0.9583,0.9583,0.9583,0.9583]},{"0":[561,5]}],[0,0,0,0,{"0":[1,0,1,0,1]},{"0":[553,5]}],[0,0,0,0,{"0":[1,1,0,1]},{"0":[156,4]}],[0,0,0,0,{"0":[0,1,1,0,1]},{"0":[726,5]}],[0,0,0,0,{"0":[0.9677,1,1,1,1]},{"0":[620,5]}],[0,1,0,0,{"0":[1,1,0,1]},{"0":[320,4]}],[0,1,0,0,{"0":[0,1,1,0,1]},{"0":[507,5]}],[0,0,0,0,{"0":[1,1,1,1,0]},{"0":[458,5]}],[0,0,0,0,{"0":[1,0,1,1,1]},{"0":[514,5]}],[0,1,0,0,{"0":[1,1,0.8462,1,1]},{"0":[497,5]}],[0,1,0,0,{"0":[0,0,1,1,1]},{"0":[792,5]}],[0,0,0,0,{"0":[1,0,1,1,0]},{"0":[773,5]}],[0,1,0,0,{"0":[0,1,1,0,1]},{"0":[466,5]}],[0,1,0,0,{"0":[1,1,1,0,1]},{"0":[500,5]}],[1,3,0,1,{"2":[0,1,0]},{"2":[801,3]}]],"minTasks":5,"sat":0.8,"bin":50,"xmax":1000,"threshold":200}</script>
<script>// Interactive charts for the catalog site. Each page carries one JSON data block; charts on a page share a store,
// so a click in one chart can filter the others. No element ids are used (the single-file build prefixes them),
// everything is found through data attributes inside the page's own view.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var fmt = function (n) { return Math.round(n).toLocaleString('en-US'); };
  var half = function (r) { var f = Math.floor(r), d = r - f; return Math.abs(d - 0.5) < 1e-9 ? (f % 2 ? f + 1 : f) : Math.round(r); };  // round half to even, like the tables
  var pc = function (v) { return v === null || isNaN(v) ? 'n/a' : (v > 0 && v < 0.005 ? '<1%' : half(100 * v) + '%'); };
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, parent, html) {
    var e = document.createElement(tag); if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
  function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : NaN; }
  function quant(s, q) { if (!s.length) return NaN; var p = (s.length - 1) * q, lo = Math.floor(p), hi = Math.ceil(p); return s[lo] + (s[hi] - s[lo]) * (p - lo); }
  function svgX(svg, clientX) { var p = svg.createSVGPoint(); p.x = clientX; p.y = 0; return p.matrixTransform(svg.getScreenCTM().inverse()).x; }
  function jitter(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x) - 0.5; }
  function chips(parent, items, onToggle) {  // items: [{label, note, on}]
    var wrap = h('div', 'cx-chips', parent);
    items.forEach(function (it, i) {
      var b = h('button', 'cx-chip', wrap, '<span class="cx-dot"></span>' + esc(it.label) + (it.note ? ' <span class="cx-n">' + esc(it.note) + '</span>' : ''));
      b.type = 'button'; b.setAttribute('aria-pressed', String(it.on));
      b.addEventListener('click', function () { if (onToggle(i)) b.setAttribute('aria-pressed', String(items[i].on)); });
    });
    return wrap;
  }
  function tip(box) {
    var t = h('div', 'cx-tip', box); t.hidden = true;
    return {
      show: function (html, ev) {
        t.innerHTML = html; t.hidden = false;
        var r = box.getBoundingClientRect(), x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
        if (x + t.offsetWidth > r.width) x = Math.max(0, ev.clientX - r.left - t.offsetWidth - 10);
        t.style.left = x + 'px'; t.style.top = y + 'px';
      },
      hide: function () { t.hidden = true; }
    };
  }
  // ---- store: tasks, cross-filters and subscribers, one per page ----
  function makeStore(D) {
    var S = { D: D, tasks: D.tasks, filters: {}, order: [], subs: [] };
    S.visible = function (except) {
      var keys = S.order.filter(function (k) { return S.filters[k] && (except || []).indexOf(k) < 0; }), out = [];
      for (var i = 0; i < S.tasks.length; i++) {
        var ok = true;
        for (var j = 0; j < keys.length && ok; j++) ok = S.filters[keys[j]].test(i);
        if (ok) out.push(i);
      }
      return out;
    };
    S.set = function (key, f) {
      if (f) { S.filters[key] = f; if (S.order.indexOf(key) < 0) S.order.push(key); }
      else { delete S.filters[key]; S.order = S.order.filter(function (k) { return k !== key; }); }
      S.subs.forEach(function (fn) { fn(); });
    };
    S.strip = function (parent) {  // the active filters, shown at the top of every chart on the page
      var s = h('div', 'cx-strip', parent);
      S.subs.push(function () {
        clear(s); var keys = S.order.filter(function (k) { return S.filters[k]; }); s.hidden = !keys.length;
        if (!keys.length) return;
        h('span', 'cx-strip-lab', s, 'Showing');
        keys.forEach(function (k) {
          var b = h('button', 'cx-filter', s, esc(S.filters[k].label) + ' <span aria-hidden="true">&times;</span>'); b.type = 'button';
          b.title = 'Remove this filter'; b.addEventListener('click', function () { S.set(k, null); });
        });
        if (keys.length > 1) { var a = h('button', 'cx-clearall', s, 'Clear all'); a.type = 'button'; a.addEventListener('click', function () { S.order.slice().forEach(function (k) { delete S.filters[k]; }); S.order = []; S.subs.forEach(function (fn) { fn(); }); }); }
      });
      return s;
    };
    return S;
  }
  // ---- bar panels (domain with sub-domains; language; seniority) ----
  function bars(fig, S) {
    var box = fig.querySelector('[data-body]'), specs = fig.dataset.dims.split(','), mode = 'pct', open = {};
    if (S.D.cross) S.strip(box);
    var bar = h('div', 'cx-toolbar', box), seg = h('div', 'cx-seg', bar);
    [['pct', '% of tasks'], ['n', 'Tasks']].forEach(function (m) {
      var b = h('button', '', seg, m[1]); b.type = 'button'; b.setAttribute('aria-pressed', String(mode === m[0]));
      b.addEventListener('click', function () { mode = m[0]; seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); });
    });
    h('span', 'cx-hint-inline', bar, fig.dataset.hint || 'Click a bar to filter the charts on this page.');
    var panels = h('div', 'cx-panels', box);
    var P = specs.map(function (sp) {
      var m = sp.match(/^(\w)(?:>(\w))?(?::(\d+))?(?:=(.*))?$/);
      var p = { key: m[1], child: m[2], top: m[3] ? +m[3] : 0, title: m[4] || '', el: h('div', 'cx-panel', panels) };
      var all = {}; S.tasks.forEach(function (t) { all[t[p.key]] = (all[t[p.key]] || 0) + 1; });
      p.order = Object.keys(all).map(Number).sort(function (a, b) { return all[b] - all[a]; });
      if (p.top && p.order.length > p.top + 1) { p.rest = p.order.slice(p.top); p.order = p.order.slice(0, p.top).concat(['rest']); }
      return p;
    });
    function row(parent, p, label, n, tot, max, active, onClick, cls, toggle) {
      var r = h('div', 'cx-bar' + (active ? ' is-on' : '') + (cls ? ' ' + cls : ''), parent), v = mode === 'pct' ? (tot ? n / tot : 0) : n;
      var lab = h('span', 'cx-bar-lab', r);
      if (toggle) { var t = h('button', 'cx-expand', lab, toggle.open ? '&#9662;' : '&#9656;'); t.type = 'button'; t.title = toggle.open ? 'Hide sub-domains' : 'Show sub-domains'; t.addEventListener('click', function (e) { e.stopPropagation(); toggle.fn(); }); }
      h('span', '', lab, esc(label));
      var tr = h('span', 'cx-bar-track', r); h('span', 'cx-bar-fill', tr).style.width = (max ? 100 * v / max : 0) + '%';
      h('span', 'cx-bar-val', r, mode === 'pct' ? (tot ? (100 * n / tot).toFixed(n && 100 * n / tot < 10 ? 1 : 0) + '%' : 'n/a') : fmt(n));
      r.tabIndex = 0; r.setAttribute('role', 'button'); r.setAttribute('aria-pressed', String(!!active));
      r.addEventListener('click', onClick); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } });
      return v;
    }
    function draw() {
      P.forEach(function (p) {
        clear(p.el); if (p.title) h('div', 'cx-panel-title', p.el, esc(p.title));
        var V = S.visible([p.key, p.child].filter(Boolean)), cnt = {}, sub = {};
        V.forEach(function (i) { var t = S.tasks[i]; cnt[t[p.key]] = (cnt[t[p.key]] || 0) + 1; if (p.child) { var k = t[p.key] + ':' + t[p.child]; sub[k] = (sub[k] || 0) + 1; } });
        var val = function (k) { return k === 'rest' ? p.rest.reduce(function (a, r) { return a + (cnt[r] || 0); }, 0) : (cnt[k] || 0); };
        var tot = V.length, max = 0;
        p.order.forEach(function (k) { var n = val(k); max = Math.max(max, mode === 'pct' ? (tot ? n / tot : 0) : n); });
        var names = S.D.dims[p.key], F = S.filters[p.key];
        p.order.forEach(function (k) {
          var label = k === 'rest' ? 'Other (' + p.rest.length + ' languages)' : names[k], active = F && F.v === String(k);
          var click = function () {
            if (active) { S.set(p.key, null); return; }
            if (p.child) S.set(p.child, null);
            S.set(p.key, { v: String(k), label: (p.title || 'Domain') + ': ' + label, test: k === 'rest' ? function (i) { return p.rest.indexOf(S.tasks[i][p.key]) >= 0; } : function (i) { return S.tasks[i][p.key] === k; } });
          };
          row(p.el, p, label, val(k), tot, max, active, click, '', p.child ? { open: !!open[k], fn: function () { open[k] = !open[k]; draw(); } } : null);
          if (p.child && open[k]) {
            var kids = Object.keys(sub).filter(function (s) { return s.split(':')[0] === String(k); }).map(function (s) { return +s.split(':')[1]; })
              .sort(function (a, b) { return sub[k + ':' + b] - sub[k + ':' + a]; });
            kids.forEach(function (c) {
              var CF = S.filters[p.child], on = CF && CF.v === String(c);
              row(p.el, p, S.D.dims[p.child][c], sub[k + ':' + c], tot, max, on, function () {
                if (on) { S.set(p.child, null); return; }
                S.set(p.child, { v: String(c), label: 'Sub-domain: ' + S.D.dims[p.child][c], test: function (i) { return S.tasks[i][p.child] === c; } });
              }, 'is-child');
            });
          }
        });
        h('div', 'cx-panel-foot', p.el, fmt(tot) + ' tasks' + (tot < S.tasks.length ? ' after filters' : ''));
      });
    }
    S.subs.push(draw);
  }
  // ---- turns per task histogram ----
  function turns(fig, S) {
    var D = S.D, box = fig.querySelector('[data-body]'), W = 940, H = 330, L = 52, R = 18, T = 34, B = 44, BIN = D.bin, XMAX = D.xmax;
    var models = D.models.map(function (m, i) { var n = 0; S.tasks.forEach(function (t) { if (t.t[i]) n++; }); return { label: m, note: fmt(n) + ' tasks', on: n > 0, n: n }; }).filter(function (m) { return m.n; });
    var sel = function (name) { return models.some(function (m) { return m.on && m.label === name; }); };
    var thr = D.threshold, pick = null, gname = fig.dataset.group || 'Domain';
    if (D.cross) S.strip(box);
    chips(box, models, function (i) { if (models[i].on && models.filter(function (m) { return m.on; }).length === 1) return false; models[i].on = !models[i].on; pick = null; if (S.filters.turns) S.set('turns', null); else draw(); return true; });
    var sum = h('p', 'cx-summary', box), svg = el('svg', { 'class': 'cx-svg', viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Histogram of average turns per task' }, box);
    h('p', 'cx-hint', box, 'Toggle models to recompute each task from their runs only. Drag the red line to move the long-horizon threshold. Click a bar to break it down by ' + gname.toLowerCase() + (D.cross ? ' and filter the other charts' : '') + '.');
    var panel = h('div', '', box), t = tip(box);
    var x = function (v) { return L + (W - L - R) * v / XMAX; };
    var gS = el('g', {}, svg), gGrid = el('g', {}, svg), gBars = el('g', {}, svg), gL = el('g', {}, svg);
    var wash = el('rect', { y: T, height: H - T - B, fill: 'var(--red)', 'fill-opacity': 0.07 }, gS);
    for (var v = 0; v <= XMAX; v += 100) el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gS, fmt(v));
    el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: 'var(--ink)' }, gS);
    el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gS, 'Average turns per task');
    el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', 'class': 'cx-axis', transform: 'rotate(-90 14 ' + (T + H - B) / 2 + ')' }, gS, 'Tasks');
    var mLine = el('line', { y1: T, y2: H - B, stroke: 'var(--ink)', 'stroke-width': 1.2, 'stroke-dasharray': '4 4' }, gL), mText = el('text', { y: T + 14, 'class': 'cx-mean' }, gL);
    var hg = el('g', { 'class': 'cx-handle', tabindex: 0, role: 'slider', 'aria-label': 'Long-horizon threshold in turns', 'aria-valuemin': 0, 'aria-valuemax': XMAX }, gL);
    var hHit = el('rect', { y: T - 20, height: H - B - T + 20, width: 24, fill: 'transparent' }, hg), hLine = el('line', { y1: T - 6, y2: H - B, stroke: 'var(--red)', 'stroke-width': 2 }, hg);
    var hKnob = el('circle', { cy: T - 6, r: 7, fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 2 }, hg), hText = el('text', { y: T - 18, 'class': 'cx-thr' }, hg);
    function means(V) {
      var out = [];
      V.forEach(function (i) { var tk = S.tasks[i], s = 0, n = 0; for (var m in tk.t) if (sel(D.models[m])) { s += tk.t[m][0]; n += tk.t[m][1]; } if (n) out.push([i, s / n]); });
      return out;
    }
    function draw() {
      var M = means(S.visible(['turns'])), nb = Math.ceil(XMAX / BIN), bins = [];
      for (var i = 0; i < nb; i++) bins.push([]);
      M.forEach(function (m) { bins[Math.min(nb - 1, Math.floor(m[1] / BIN))].push(m[0]); });
      var top = Math.max.apply(null, bins.map(function (b) { return b.length; })) || 1, step = top > 200 ? 50 : top > 80 ? 20 : top > 30 ? 10 : top > 12 ? 5 : top > 5 ? 2 : 1;
      top = Math.ceil(top / step) * step;
      var y = function (n) { return H - B - (H - B - T) * n / top; };
      clear(gGrid); clear(gBars);
      for (var g = 0; g <= top; g += step) { el('line', { x1: L, x2: W - R, y1: y(g), y2: y(g), stroke: 'var(--line-2)' }, gGrid); el('text', { x: L - 8, y: y(g) + 4, 'text-anchor': 'end', 'class': 'cx-tick' }, gGrid, fmt(g)); }
      var F = S.filters.turns; if (D.cross && !F) pick = null;
      bins.forEach(function (b, i) {
        var lo = i * BIN, on = pick === i, r = el('rect', { x: x(lo) + 1, width: x(lo + BIN) - x(lo) - 2, y: y(b.length), height: Math.max(0, H - B - y(b.length)), 'class': 'cx-col' + (on ? ' is-on' : ''), tabindex: b.length ? 0 : -1, role: 'button' }, gBars);
        var go = function () {
          if (!b.length) return; pick = on ? null : i;
          if (D.cross) { var set = {}; b.forEach(function (k) { set[k] = 1; }); S.set('turns', pick === null ? null : { label: 'Turns: ' + fmt(lo) + '-' + fmt(lo + BIN - 1), test: function (k) { return !!set[k]; } }); } else draw();
        };
        r.addEventListener('click', go); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
        r.addEventListener('mousemove', function (e) { t.show('<b>' + fmt(lo) + '-' + fmt(lo + BIN - 1) + ' turns</b><br>' + fmt(b.length) + ' tasks (' + pc(M.length ? b.length / M.length : 0) + ')', e); });
        r.addEventListener('mouseleave', t.hide);
      });
      var mu = mean(M.map(function (m) { return m[1]; })) || 0, tx = x(thr);
      mLine.setAttribute('x1', x(mu)); mLine.setAttribute('x2', x(mu));
      var left = x(mu) > tx - 90 && x(mu) < tx; mText.setAttribute('x', left ? x(mu) - 6 : x(mu) + 6); mText.setAttribute('text-anchor', left ? 'end' : 'start'); mText.textContent = 'mean ' + fmt(mu);
      wash.setAttribute('x', tx); wash.setAttribute('width', Math.max(0, W - R - tx));
      hHit.setAttribute('x', tx - 12); hLine.setAttribute('x1', tx); hLine.setAttribute('x2', tx); hKnob.setAttribute('cx', tx);
      var flip = tx > W - R - 190; hText.setAttribute('x', flip ? tx - 12 : tx + 12); hText.setAttribute('text-anchor', flip ? 'end' : 'start'); hText.textContent = 'long horizon, ' + fmt(thr) + '+ turns';
      hg.setAttribute('aria-valuenow', thr);
      var long = M.filter(function (m) { return m[1] >= thr; });
      sum.innerHTML = '<strong>' + fmt(long.length) + '</strong> of ' + fmt(M.length) + ' tasks (' + pc(M.length ? long.length / M.length : 0) + ') average ' + fmt(thr) + ' turns or more. Mean ' + fmt(mu) + ' turns per task.';
      // breakdown table: long-horizon tasks by group, or the picked bar's tasks by group
      var names = D.dims.g, rows, cap, head;
      var byG = function (list) { var c = {}; list.forEach(function (k) { var gg = S.tasks[k].g; c[gg] = (c[gg] || 0) + 1; }); return c; };
      var allC = byG(M.map(function (m) { return m[0]; }));
      var order = Object.keys(allC).map(Number).sort(function (a, b) { return allC[b] - allC[a]; });
      if (pick === null) {
        cap = 'Long-horizon tasks (' + fmt(thr) + '+ turns) by ' + gname.toLowerCase(); head = [gname, 'Long-horizon tasks', 'Tasks with runs', 'Share'];
        var lc = byG(long.map(function (m) { return m[0]; }));
        rows = order.map(function (gg) { return [names[gg], lc[gg] || 0, allC[gg], (lc[gg] || 0) / allC[gg]]; });
      } else {
        var bc = byG(bins[pick]); cap = 'Tasks averaging ' + fmt(pick * BIN) + '-' + fmt(pick * BIN + BIN - 1) + ' turns, by ' + gname.toLowerCase(); head = [gname, 'Tasks in this bar', 'Tasks with runs', 'Share of bar'];
        rows = order.map(function (gg) { return [names[gg], bc[gg] || 0, allC[gg], bins[pick].length ? (bc[gg] || 0) / bins[pick].length : 0]; });
      }
      clear(panel); grid(panel, cap + (pick === null ? '. Click a bar to break it down.' : '.'), head, rows, pick === null ? null : function () { pick = null; if (D.cross) S.set('turns', null); else draw(); });
    }
    var drag = false;
    hg.addEventListener('pointerdown', function (e) { drag = true; hg.setPointerCapture(e.pointerId); e.preventDefault(); });
    hg.addEventListener('pointermove', function (e) { if (!drag) return; var v = Math.max(0, Math.min(XMAX, Math.round((svgX(svg, e.clientX) - L) / (W - L - R) * XMAX / 10) * 10)); if (v !== thr) { thr = v; draw(); } });
    hg.addEventListener('pointerup', function () { drag = false; });
    hg.addEventListener('keydown', function (e) { var d = { ArrowLeft: -10, ArrowDown: -10, ArrowRight: 10, ArrowUp: 10, PageDown: -100, PageUp: 100 }[e.key]; if (d) { e.preventDefault(); thr = Math.max(0, Math.min(XMAX, thr + d)); draw(); } });
    S.subs.push(draw);
  }
  function grid(parent, cap, head, rows, back) {  // a small table drawn with divs, with a share meter in the last column
    var c = h('p', 'cx-cap', parent, esc(cap));
    if (back) { var b = h('button', 'cx-link', c, 'Back to the long-horizon view'); b.type = 'button'; b.addEventListener('click', back); }
    var g = h('div', 'cx-grid', parent); g.setAttribute('role', 'table');
    var hr = h('div', 'cx-row cx-head', g); hr.setAttribute('role', 'row'); head.forEach(function (x) { h('span', '', hr, esc(x)).setAttribute('role', 'columnheader'); });
    rows.forEach(function (r) {
      var rr = h('div', 'cx-row', g); rr.setAttribute('role', 'row');
      h('span', '', rr, esc(r[0])); h('span', '', rr, fmt(r[1])); h('span', '', rr, fmt(r[2]));
      h('span', '', rr, '<span class="cx-meter"><span style="width:' + (100 * r[3]).toFixed(1) + '%"></span></span>' + Math.round(100 * r[3]) + '%');
      rr.querySelectorAll(':scope > span').forEach(function (s) { s.setAttribute('role', 'cell'); });
    });
  }
  // ---- per-task average reward by model: box plot with one dot per task ----
  function reward(fig, S) {
    var D = S.D, box = fig.querySelector('[data-body]'), W = 940, L = 210, R = 24, T = 40, B = 44, ROW = 58;
    var lo = 0.2, hi = 0.8, same = false, focus = null;
    var stats = D.models.map(function (m, k) {
      var pt = []; S.tasks.forEach(function (t) { var s = t.r[k]; if (s && s.length) pt.push(mean(s)); });
      return { k: k, n: pt.length, full: pt.filter(function (v) { return v >= 1; }).length };
    }).filter(function (s) { return s.n; });
    var items = stats.map(function (s) {
      var sat = s.full / s.n >= D.sat, few = s.n < D.minTasks;
      return { k: s.k, label: D.models[s.k], note: fmt(s.n) + ' tasks' + (sat ? ', saturated' : few ? ', few tasks' : ''), on: !sat && !few };
    });
    if (!items.some(function (i) { return i.on; }) && items.length) items[0].on = true;
    if (D.cross) S.strip(box);
    chips(box, items, function (i) { if (items[i].on && items.filter(function (x) { return x.on; }).length === 1) return false; items[i].on = !items[i].on; draw(); return true; });
    var opts = h('label', 'cx-check', box, '<input type="checkbox"> Same tasks only: keep the tasks every selected model ran');
    opts.querySelector('input').addEventListener('change', function (e) { same = e.target.checked; draw(); });
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Per-task average reward by model' }, box);
    h('p', 'cx-hint', box, 'Each dot is one task: its average grader score over a model\'s graded runs. Boxes span the middle half of tasks, the line is the median and the diamond the average. Drag the edges of the shaded band to change it. Hover a dot for its runs; click it for the task.');
    var detail = h('div', 'cx-detail', box), summary = h('div', '', box), t = tip(box);
    var x = function (v) { return L + (W - L - R) * v; };
    var gBand = el('rect', { y: T - 10, fill: 'var(--teal)', 'fill-opacity': 0.09 }, svg), gC = el('g', {}, svg), lastH = T + ROW + B, H0;
    var hd = ['lo', 'hi'].map(function (which) {
      var g = el('g', { 'class': 'cx-handle', tabindex: 0, role: 'slider', 'aria-label': which === 'lo' ? 'Lower edge of the band' : 'Upper edge of the band' }, svg);
      var o = { which: which, g: g, hit: el('rect', { y: T - 26, width: 20, fill: 'transparent' }, g), line: el('line', { y1: T - 16, stroke: 'var(--teal)', 'stroke-width': 2 }, g),
        knob: el('circle', { cy: T - 16, r: 6.5, fill: 'var(--teal)', stroke: 'var(--paper)', 'stroke-width': 2 }, g), lab: el('text', { y: T - 27, 'text-anchor': 'middle', 'class': 'cx-band' }, g) };
      var setv = function (v) { v = Math.round(v * 20) / 20; if (which === 'lo') lo = Math.max(0, Math.min(v, hi - 0.05)); else hi = Math.min(1, Math.max(v, lo + 0.05)); };
      var dragging = false;
      g.addEventListener('pointerdown', function (ev) { dragging = true; g.setPointerCapture(ev.pointerId); ev.preventDefault(); });
      g.addEventListener('pointermove', function (ev) { if (!dragging) return; var old = lo + ':' + hi; setv((svgX(svg, ev.clientX) - L) / (W - L - R)); if (old !== lo + ':' + hi) { place(); tally(); } });
      g.addEventListener('pointerup', function () { dragging = false; });
      g.addEventListener('keydown', function (ev) { var d = { ArrowLeft: -0.05, ArrowDown: -0.05, ArrowRight: 0.05, ArrowUp: 0.05 }[ev.key]; if (d) { ev.preventDefault(); setv((which === 'lo' ? lo : hi) + d); place(); tally(); } });
      return o;
    });
    function place() {  // band and handles follow lo, hi and the chart height
      gBand.setAttribute('x', x(lo)); gBand.setAttribute('width', x(hi) - x(lo)); gBand.setAttribute('height', lastH - T - B + 10);
      hd.forEach(function (o) {
        var v = o.which === 'lo' ? lo : hi;
        o.hit.setAttribute('x', x(v) - 10); o.hit.setAttribute('height', lastH - B - T + 26);
        o.line.setAttribute('x1', x(v)); o.line.setAttribute('x2', x(v)); o.line.setAttribute('y2', lastH - B); o.knob.setAttribute('cx', x(v));
        o.lab.setAttribute('x', x(v)); o.lab.textContent = Math.round(100 * v) + '%'; o.g.setAttribute('aria-valuenow', Math.round(100 * v));
      });
    }
    var lastRows = [];
    function draw() {
      var V = S.visible([]), on = items.filter(function (i) { return i.on; });
      if (same) V = V.filter(function (i) { return on.every(function (m) { var s = S.tasks[i].r[m.k]; return s && s.length; }); });
      var rows = on.map(function (m) {
        var pts = []; V.forEach(function (i) { var s = S.tasks[i].r[m.k]; if (s && s.length) pts.push({ i: i, v: mean(s), runs: s }); });
        var vs = pts.map(function (p) { return p.v; }).sort(function (a, b) { return a - b; });
        return { m: m, pts: pts, vs: vs, q1: quant(vs, 0.25), q2: quant(vs, 0.5), q3: quant(vs, 0.75), mu: mean(vs) };
      }).filter(function (r) { return r.pts.length; });
      rows.sort(function (a, b) { return (b.q3 - a.q3) || (b.q2 - a.q2) || (b.mu - a.mu); });
      var H = T + Math.max(1, rows.length) * ROW + B; svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(gC); lastH = H; place();
      for (var v = 0; v <= 1.0001; v += 0.1) { el('line', { x1: x(v), x2: x(v), y1: T - 10, y2: H - B, stroke: 'var(--line-2)' }, gC); el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gC, Math.round(100 * v) + '%'); }
      el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'Per-task average reward');
      if (!rows.length) el('text', { x: (L + W - R) / 2, y: T + 30, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'No graded runs for the selected models and filters');
      rows.forEach(function (r, j) {
        var cy = T + j * ROW + ROW / 2, g = el('g', {}, gC);
        el('text', { x: L - 14, y: cy - 2, 'text-anchor': 'end', 'class': 'cx-rowlab' }, g, r.m.label);
        el('text', { x: L - 14, y: cy + 14, 'text-anchor': 'end', 'class': 'cx-tick' }, g, fmt(r.pts.length) + ' tasks, average ' + pc(r.mu));
        var iqr = r.q3 - r.q1, wl = Math.max(r.vs[0], r.q1 - 1.5 * iqr), wh = Math.min(r.vs[r.vs.length - 1], r.q3 + 1.5 * iqr);
        el('line', { x1: x(wl), x2: x(r.q1), y1: cy, y2: cy, stroke: 'var(--ink)' }, g); el('line', { x1: x(r.q3), x2: x(wh), y1: cy, y2: cy, stroke: 'var(--ink)' }, g);
        el('rect', { x: x(r.q1), width: Math.max(1, x(r.q3) - x(r.q1)), y: cy - 14, height: 28, fill: 'var(--card)', stroke: 'var(--ink)' }, g);
        el('line', { x1: x(r.q2), x2: x(r.q2), y1: cy - 14, y2: cy + 14, stroke: 'var(--ink)', 'stroke-width': 2 }, g);
        r.pts.forEach(function (p) {
          var c = el('circle', { cx: x(p.v), cy: cy + jitter(p.i * 7 + r.m.k) * 26, r: focus === p.i ? 5 : 3.2, 'class': 'cx-pt' + (focus === p.i ? ' is-on' : '') }, g);
          c.addEventListener('mousemove', function (e) { t.show('<b>' + esc(r.m.label) + '</b><br>' + p.runs.length + ' graded run' + (p.runs.length > 1 ? 's' : '') + ': ' + p.runs.map(function (s) { return +s.toFixed(2); }).join(', ') + '<br>Average ' + pc(p.v), e); });
          c.addEventListener('mouseleave', t.hide);
          c.addEventListener('click', function () { focus = focus === p.i ? null : p.i; draw(); });
        });
        el('path', { d: 'M' + x(r.mu) + ' ' + (cy - 7) + 'l6 7l-6 7l-6 -7z', fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 1.5 }, g);
      });
      lastRows = rows; tally();
      clear(detail); detail.hidden = focus === null;
      if (focus !== null) {
        var tk = S.tasks[focus], tu = 0, tn = 0; for (var m in tk.t) { tu += tk.t[m][0]; tn += tk.t[m][1]; }
        var parts = ['<b>Selected task</b>', 'Domain: ' + esc(D.dims.g[tk.g]), 'Sub-domain: ' + esc(D.dims.c[tk.c]), 'Language: ' + esc(D.dims.l[tk.l]), 'Seniority: ' + esc(D.dims.s[tk.s]), tn ? 'Average turns: ' + fmt(tu / tn) + ' over ' + tn + ' completed runs' : 'No completed runs with a turn count'];
        D.models.forEach(function (name, k) { var s = tk.r[k]; if (s && s.length) parts.push(esc(name) + ': ' + s.map(function (v) { return +v.toFixed(2); }).join(', ') + ' (average ' + pc(mean(s)) + ')'); });
        detail.innerHTML = parts.join('<br>');
        var x0 = h('button', 'cx-link', detail, 'Close'); x0.type = 'button'; x0.addEventListener('click', function () { focus = null; draw(); });
      }
    }
    function tally() {  // the table under the chart, recomputed for the band
      var rows = lastRows; clear(summary);
      var cap = h('p', 'cx-cap', summary, 'Tasks by per-task average reward, with the band at ' + Math.round(100 * lo) + '-' + Math.round(100 * hi) + '%');
      var gtab = h('div', 'cx-grid cx-grid5', summary); gtab.setAttribute('role', 'table');
      var hr = h('div', 'cx-row cx-head', gtab); ['Model', 'Tasks', 'Average reward', 'Tasks at 0%', 'In the band', 'Tasks at 100%'].forEach(function (s) { h('span', '', hr, s); });
      rows.forEach(function (r) {
        var n = r.vs.length, z = r.vs.filter(function (v) { return v === 0; }).length, f = r.vs.filter(function (v) { return v >= 1; }).length, b = r.vs.filter(function (v) { return v >= lo - 1e-9 && v <= hi + 1e-9; }).length;
        var rr = h('div', 'cx-row', gtab); h('span', '', rr, esc(r.m.label)); h('span', '', rr, fmt(n)); h('span', '', rr, pc(r.mu)); h('span', '', rr, pc(z / n)); h('span', '', rr, pc(b / n)); h('span', '', rr, pc(f / n));
      });
    }
    S.subs.push(draw);
  }
  // ---- overview heatmap: models by catalogs ----
  function heat(fig, S) {
    var D = S.D.heat, box = fig.querySelector('[data-body]'), metric = 'reward', minT = D.minTasks, pick = null;
    var M = {
      reward: { label: 'Average reward', f: function (c) { return mean(c.pt); }, txt: pc },
      t0: { label: 'Tasks at 0%', f: function (c) { return c.pt.filter(function (v) { return v === 0; }).length / c.pt.length; }, txt: pc },
      band: { label: 'Tasks at 20-80%', f: function (c) { return c.pt.filter(function (v) { return v >= 0.2 && v <= 0.8; }).length / c.pt.length; }, txt: pc },
      t100: { label: 'Tasks at 100%', f: function (c) { return c.pt.filter(function (v) { return v >= 1; }).length / c.pt.length; }, txt: pc },
      runs: { label: 'Graded runs', f: function (c) { return c.graded; }, txt: fmt }
    };
    var bar = h('div', 'cx-toolbar', box), seg = h('div', 'cx-seg', bar);
    Object.keys(M).forEach(function (k) { var b = h('button', '', seg, M[k].label); b.type = 'button'; b.setAttribute('aria-pressed', String(k === metric)); b.addEventListener('click', function () { metric = k; seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); }); });
    var sl = h('label', 'cx-slider', bar, 'Hide cells with fewer than <input type="range" min="1" max="20" value="' + minT + '"> <b>' + minT + '</b> tasks');
    sl.querySelector('input').addEventListener('input', function (e) { minT = +e.target.value; sl.querySelector('b').textContent = minT; draw(); });
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Heatmap of models by catalog' }, box);
    h('p', 'cx-hint', box, 'Hover a cell for its numbers; click it for the spread of per-task rewards.');
    var detail = h('div', 'cx-detail', box), t = tip(box); detail.hidden = true;
    var links = fig.querySelectorAll('[data-links] a');
    var C = {}; D.cells.forEach(function (c) { C[c[0] + ':' + c[1]] = { graded: c[2], pt: c[3] }; });
    function color(v) {  // paper -> sage -> ink
      var s = [[251, 249, 244], [127, 179, 170], [17, 72, 78]], a = v < 0.5 ? s[0] : s[1], b = v < 0.5 ? s[1] : s[2], u = v < 0.5 ? v * 2 : (v - 0.5) * 2;
      return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * u); }).join(',') + ')';
    }
    function draw() {
      var W = 940, L = 200, T = 70, CW = (W - L - 10) / D.catalogs.length, CH = 54, H = T + D.models.length * CH + 10, m = M[metric];
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(svg);
      var vmax = 1; if (metric === 'runs') { vmax = 1; D.cells.forEach(function (c) { if (c[3].length >= minT) vmax = Math.max(vmax, c[2]); }); }
      D.catalogs.forEach(function (name, j) {
        var words = name.split(' '), lines = [], cur = '';
        words.forEach(function (w) { if ((cur + ' ' + w).trim().length > 16) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w; }); lines.push(cur.trim());
        lines.slice(0, 3).forEach(function (ln, k) { el('text', { x: L + j * CW + CW / 2, y: T - 12 - (Math.min(lines.length, 3) - 1 - k) * 14, 'text-anchor': 'middle', 'class': 'cx-collab' }, svg, ln); });
      });
      D.models.forEach(function (mname, i) {
        el('text', { x: L - 12, y: T + i * CH + CH / 2 + 4, 'text-anchor': 'end', 'class': 'cx-rowlab' }, svg, mname);
        D.catalogs.forEach(function (cn, j) {
          var c = C[j + ':' + i], ok = c && c.pt.length >= minT, gx = L + j * CW, gy = T + i * CH;
          var r = el('rect', { x: gx + 2, y: gy + 2, width: CW - 4, height: CH - 4, fill: ok ? color(metric === 'runs' ? c.graded / vmax : m.f(c)) : 'var(--paper)', stroke: pick === j + ':' + i ? 'var(--red)' : 'var(--line-2)', 'stroke-width': pick === j + ':' + i ? 2.5 : 1, 'class': ok ? 'cx-cell' : '' }, svg);
          if (!ok) { if (c) el('text', { x: gx + CW / 2, y: gy + CH / 2 + 4, 'text-anchor': 'middle', 'class': 'cx-tick' }, svg, c.pt.length + ' task' + (c.pt.length > 1 ? 's' : '')); return; }
          var v = metric === 'runs' ? c.graded / vmax : m.f(c), ink = v > 0.55 ? '#fff' : 'var(--ink)';
          el('text', { x: gx + CW / 2, y: gy + CH / 2 - 1, 'text-anchor': 'middle', 'class': 'cx-cellv', fill: ink }, svg, m.txt(m.f(c)));
          el('text', { x: gx + CW / 2, y: gy + CH / 2 + 15, 'text-anchor': 'middle', 'class': 'cx-cells', fill: ink }, svg, c.pt.length + ' tasks');
          r.addEventListener('mousemove', function (e) {
            var s = c.pt.slice().sort(function (a, b) { return a - b; });
            t.show('<b>' + esc(mname) + '</b><br>' + esc(cn) + '<br>' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs<br>Average reward ' + pc(mean(c.pt)) + '<br>Middle half of tasks: ' + pc(quant(s, 0.25)) + ' to ' + pc(quant(s, 0.75)), e);
          });
          r.addEventListener('mouseleave', t.hide);
          r.addEventListener('click', function () { pick = pick === j + ':' + i ? null : j + ':' + i; draw(); });
        });
      });
      clear(detail); detail.hidden = pick === null;
      if (pick !== null) {
        var jj = +pick.split(':')[0], ii = +pick.split(':')[1], c = C[pick], bins = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        c.pt.forEach(function (v) { bins[Math.min(9, Math.floor(v * 10))]++; });
        var mx = Math.max.apply(null, bins);
        h('p', 'cx-cap', detail, esc(D.models[ii]) + ' in ' + esc(D.catalogs[jj]) + ': ' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs, average reward ' + pc(mean(c.pt)));
        var hist = h('div', 'cx-mini', detail);
        bins.forEach(function (n, k) { var col = h('div', 'cx-mini-col', hist); var b = h('div', 'cx-mini-bar', col); b.style.height = (mx ? 100 * n / mx : 0) + '%'; b.title = n + ' tasks'; h('div', 'cx-mini-n', col, String(n)); h('div', 'cx-mini-lab', col, (k * 10) + '-' + (k === 9 ? 100 : k * 10 + 9) + '%'); });
        var foot = h('p', 'cx-hint', detail, 'Tasks by per-task average reward. ');
        if (links[jj]) { var a = links[jj].cloneNode(true); a.textContent = 'Open the ' + D.catalogs[jj] + ' page'; foot.appendChild(a); }
      }
    }
    draw();
  }
  // ---- wiring ----
  function init(scope) {
    var dataEl = scope.querySelector('script[data-chart-data]');
    if (!dataEl || dataEl.dataset.ready) return; dataEl.dataset.ready = '1';
    var D = JSON.parse(dataEl.textContent), S = makeStore(D);
    S.tasks = D.tasks.map(function (r) { return { g: r[0], c: r[1], l: r[2], s: r[3], r: r[4] || {}, t: r[5] || {} }; });
    scope.querySelectorAll('[data-chart]').forEach(function (fig) {
      var kind = fig.dataset.chart;
      if (kind === 'bars') bars(fig, S); else if (kind === 'turns') turns(fig, S); else if (kind === 'reward') reward(fig, S); else if (kind === 'heat') heat(fig, S);
    });
    S.subs.forEach(function (fn) { fn(); });
  }
  var me = document.currentScript, scope = (me && me.closest('.view')) || document;
  init(scope);
})();
</script>
</div>
