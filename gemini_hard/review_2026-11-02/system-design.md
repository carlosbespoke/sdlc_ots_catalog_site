# System design & IaC

## Executive summary

| KPI cards: 123 Tasks |<div class="kpi"><div class="kpi-value">20%</div><div class="kpi-label">Gemini 4 Argon pass rate</div></div><div class="kpi"><div class="kpi-value">10%</div><div class="kpi-label">Gemini 3.8 Flash pass rate</div></div></div>

Each task changes a production system that must keep running. In the system design tasks the agent makes a multi-process service hold its guarantees through crashes, retries, races and returning stale writers, and hidden tests kill or pause processes to check them. In the infrastructure tasks the agent restructures live Terraform or Pulumi code so that the plan against production state changes nothing that is deployed.

Gemini 4 Argon passes 20% of its runs on these tasks, and it fails every run on 44% of the tasks. Gemini 3.8 Flash passes 10%, and it fails every run on 73% of the tasks. The main languages are HCL (Terraform) (33%), Go (31%) and Python (13%).

| Domain | What the tasks do | % of catalog |
|---|---|---:|
| State-preserving infrastructure changes | Split flat Terraform stacks into modules, or port them to Pulumi, without replacing any deployed resource. | 36% |
| Applications & business domains | Keep bookings, payments, uploads and documents consistent in web and payment services when instances fail. | 20% |
| Scientific & ML software | Keep agent and graph services correct when workers stop or restart. | 8% |
| Distributed systems & coordination | Deliver messages and run scheduled jobs correctly across instances and restarts. | 8% |
| Not yet classified | Newly added services: short-lived scanner credentials, deletion of in-flight user data and safe package writes. | 8% |
| Build, release & supply chain | Keep build pipelines and package supply chains correct when steps fail or race. | 5% |
| Cloud infrastructure & IaC | Keep self-hosted platform services correct when nodes fail or restart. | 5% |
| Data engineering & databases | Keep data pipelines from losing or duplicating records across failures. | 5% |
| Security | Keep secrets and access grants correct across failures. | 3% |
| Languages & developer tooling | Keep API tooling state consistent across instances. | 3% |

## Why this catalog

### Problems engineers face

Engineers here change production systems that must keep running. In services where several processes share state and any of them can stop, the failures are duplicate effects after retries, lost notifications, stale writers returning after a takeover, limits that hold in one process but not across instances, and partial state after a crash. In infrastructure code, a flat Terraform stack has to become modules with stable keys, or move to Pulumi, while every deployed resource stays exactly as it is.

### How the tasks reproduce them

Service tasks pin an open-source repository at a base commit and give a short specification, often with time limits. The agent runs the databases, caches or brokers it needs locally and delivers a patch. Hidden tests then kill or pause processes and confirm that existing behaviour still works. Infrastructure tasks ship the stack with its recorded production state and an offline toolchain. A separate verifier plans the result with refresh disabled and expects moves only, then plans hidden changes such as an added key.

### Typical prompts

- A capability gap stated as "X cannot do Y", followed by measurable requirements, many with time limits.
- A closing paragraph with the repository path, how to start each service and the build command.
- A first-person request to modularize a named production Terraform stack, followed by rules for modules, `for_each` keys, variables, outputs and banned constructs.

## Domain breakdown

![Share of tasks by domain](assets/system-design_domain.svg)

## Language and seniority

![Primary language and seniority](assets/system-design_metadata.svg)

### Primary language

| Primary language | % of catalog |
|---|---:|
| HCL (Terraform) | 33.3% |
| Go | 30.8% |
| Python | 12.8% |
| TypeScript | 12.8% |
| C# | 10.3% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Staff+ | 56.4% |
| Senior | 35.9% |
| Not yet classified | 7.7% |

## Gemini pass rates across the catalog

| Model | Pass rate | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|
| google/gemini-4-argon | 20% | 44% | 56% | 0% |
| google/gemini-3.8-flash | 10% | 73% | 7% | 13% |

![Per-task pass rate by Gemini model](assets/system-design_per_task.svg)

## Turn counts and long-horizon tasks

A task's turn count is the average over its Gemini runs. A task is long horizon when that average is 200 or more turns.

| Measure | Value |
|---|---:|
| Average turn count | 264.6 |
| Median turn count | 241.0 |
| Range | 36 to 931 |
| Long-horizon tasks (200+ turns) | 62% of tasks |

![Turns per task](assets/system-design_turns.svg)

| Model | % of tasks | Mean turns | % with 200+ turns |
|---|---:|---:|---:|
| google/gemini-3.8-flash | 47% | 259.7 | 52% |
| google/gemini-4-argon | 56% | 313.2 | 79% |

## Example tasks from the shortlist

The first example is a main sample for the catalog; the others are attached samples. All of them come from the shortlist and have Gemini runs that pass at most half the time.

### Example 1: Payments & banking (TypeScript)

| Field | Value |
|---|---|
| Sample | Main sample for the catalog |
| Final category | System design |
| Domain | Applications & business domains |
| Sub-domain | Payments & banking |
| Language | TypeScript |
| Seniority | Staff+ |
| Turn count | 414 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: A product-style problem statement followed by `What we need`, `Keep working` and `Setup` sections that fix the environment variable, protobuf field numbers, HTTP headers, endpoint and status codes, and the build commands.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 20% | 0.20 |

#### Environment

![How the task works](assets/env-pdk-actual-sync-log-checkpoint-compaction.svg)

#### How it maps to the work

A backend engineer on a self-hosted budgeting app needs the sync server to compact each budget's change log from a client-built snapshot without breaking offline devices. The engineer starts from the sync server, CRDT and client packages, and the server cannot read the encrypted changes it stores. The hard part is the protocol: a conditional checkpoint commit tied to a receive base, correct handling of late messages with older timestamps, and compatibility for old clients, all checked across several simulated devices.

### Example 2: Identity and security boundaries (Go)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | System design |
| Domain | Not yet classified |
| Sub-domain | Identity and security boundaries |
| Language | Go |
| Seniority | Not yet classified |
| Turn count | 365 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: A paragraph stating the current insecure behavior, a bullet list of observable requirements with time limits and HTTP status codes, and a closing paragraph on services, the offline build command and what is out of scope.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 20% | 0.20 |

#### Environment

![How the task works](assets/env-pdk-harbor-scan-ephemeral-credentials.svg)

#### How it maps to the work

A maintainer of a container registry replaces long-lived, project-wide scanner robot accounts with short-lived credentials scoped to one repository. The engineer starts from Harbor's core and jobservice code for scan jobs, robot accounts and registry authorization. The hard part is the lifecycle across processes: keeping secrets out of Redis job records and logs, keeping the credential valid during long scans, and revoking it when a job ends or when jobservice dies without a final hook.

### Example 3: Storage and publication integrity (C#)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | System design |
| Domain | Not yet classified |
| Sub-domain | Storage and publication integrity |
| Language | C# |
| Seniority | Not yet classified |
| Turn count | 203 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: A two-sentence problem statement, a bullet list of required behaviors with HTTP status codes and a new admin endpoint, a compatibility paragraph, and a closing paragraph giving the build command, sidecar hosts, configuration keys and credentials.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 20% | 0.20 |

#### Environment

![How the task works](assets/env-pdk-bagetter-fenced-package-writes.svg)

#### How it maps to the work

A backend engineer running a NuGet server as several replicas over shared PostgreSQL and S3 must make package-version writes safe under races, partitions and crashes. The engineer starts from BaGetter's push, delete, mirror and storage code. The hard part is fencing: a writer whose database claim has expired must not overwrite or delete the winner's objects, and a new reconcile endpoint must clean up orphans while old-layout packages and an existing schema keep working.

### Example 4: Cloud infra: containers & self-hosted platforms (HCL (Terraform))

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Infrastructure as code |
| Domain | State-preserving infrastructure changes |
| Sub-domain | Cloud infra: containers & self-hosted platforms |
| Language | HCL (Terraform) |
| Seniority | Senior |
| Turn count | 46 (google/gemini-4-argon) |
| Long horizon | no |

Prompt shape: A refactor request for an IPv6 Kubernetes stack that names four target modules and constrains the result to a plan of moves against recorded state.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-system-design-ex4.svg)

#### How it maps to the work

A platform engineer maintains the Terraform for two test Kubernetes clusters whose VPCs, NAT64 gateways, auto scaling groups and worker pools were written with positional count. The engineer needs to restructure it into four modules and make clusters, zones and pools data-driven, without any resource being replaced. The check is the plan against the recorded production state.

### Example 5: Cloud infra: AWS platform stacks (HCL (Terraform))

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Infrastructure as code |
| Domain | State-preserving infrastructure changes |
| Sub-domain | Cloud infra: AWS platform stacks |
| Language | HCL (Terraform) |
| Seniority | Senior |
| Turn count | 58 (google/gemini-4-argon) |
| Long horizon | no |

Prompt shape: A refactor request for a model-serving stack that names eight modules and their ownership and requires a moves-only plan against recorded state.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 50% | 0.50 |

#### Environment

![How the task works](assets/env-terraform-multi-model-router-module-refactor.svg)

#### How it maps to the work

A platform engineer is asked to bring a production ML routing stack up to the team's module standard. The work spans eight modules with several independent keys, so each resource must land in the right module and keep its state address through a move. The engineer relies on the recorded state and the CI plan.

### Example 6: Cloud infra: AWS platform stacks (HCL (Terraform))

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Infrastructure as code |
| Domain | State-preserving infrastructure changes |
| Sub-domain | Cloud infra: AWS platform stacks |
| Language | HCL (Terraform) |
| Seniority | Senior |
| Turn count | 70 (google/gemini-4-argon) |
| Long horizon | no |

Prompt shape: A first-person request to modularize a named Terraform stack without changing running infrastructure, followed by long constraint sections on how CI judges the change, module layout and ownership, `for_each` keys, root variables, root outputs and banned constructs.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-terraform-centralwatch-alert-routing-module-refactor.svg)

#### How it maps to the work

A platform engineer inherits a production alert-routing stack written as one flat root module with list-indexed resources and hard-coded settings. The engineer must split it into eventing, messaging and processing modules keyed by team, source, severity and channel, with generalized variables and outputs. The hard part is expressing every address change in configuration so the plan against the live state contains only moves, while passing IDs between modules through outputs instead of literals.
