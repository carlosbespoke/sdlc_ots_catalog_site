# Coding OTS RL Envs

| KPI cards: 605 Tasks |<div class="kpi"><div class="kpi-value">23%</div><div class="kpi-label">Gemini 4 Argon pass rate</div></div><div class="kpi"><div class="kpi-value">2%</div><div class="kpi-label">Gemini 3.8 Flash pass rate</div></div></div>

These are coding environments for reinforcement learning, grouped into 4 catalogs. Each task puts the agent in a real open-source codebase or program, gives it a written request of the kind an engineer would receive, and grades the result with hidden tests. Gemini 4 Argon passes 23% of its runs on these tasks and Gemini 3.8 Flash passes 2%. Every pass rate and plot on these pages covers Gemini models only: Gemini 4 Argon (`google/gemini-4-argon`) and Gemini 3.8 Flash (`google/gemini-3.8-flash`).

| Catalog | Tasks | What the tasks do | % of all tasks | Average turn count |
|---|---:|---|---:|---:|
| [ProgramBench and Migration](programbench.md) | 283 | Rebuild or upgrade programs to match a reference exactly, or port libraries to another language. | 46.8% | 420 |
| [System design & IaC](system-design.md) | 123 | Keep running services and live infrastructure correct through failures and refactors. | 20.3% | 265 |
| [Diagnosis, Debugging, and Bug Fixing](debugging.md) | 98 | Find and fix faults in real codebases from symptoms or documentation. | 16.2% | 417 |
| [Feature implementation](feature-implementation.md) | 101 | Add capabilities to existing libraries and services without breaking current behaviour. | 16.7% | 348 |
| **Total** | **605** |  | **100%** |  |

## Gemini pass rates

![Gemini pass rates by catalog](assets/overview_gemini.svg)

| Model | Pass rate |
|---|---:|
| google/gemini-4-argon | 23% |
| google/gemini-3.8-flash | 2% |
| google/gemini-3.7-flash | 0% |

## Samples

3 main samples go into the catalog and 12 are attached. All come from the shortlist. Main samples pass at most 25% of their Gemini runs. Attached samples pass at most half their Gemini runs. Each example is written up on its catalog page.

| Sample | Catalog | Example | Gemini 4 Argon | Gemini 3.8 Flash |
|---|---|---|---:|---:|
| Main | ProgramBench and Migration | [Example 1: Statistics & numerical methods (Go)](programbench.md) | 33% | 0% |
| Main | System design & IaC | [Example 1: Payments & banking (TypeScript)](system-design.md) | 20% |  |
| Main | Diagnosis, Debugging, and Bug Fixing | [Example 1: Logic programming (Go)](debugging.md) | 50% | 0% |
| Attached | ProgramBench and Migration | [Example 2: Graph algorithms (Go)](programbench.md) | 50% |  |
| Attached | System design & IaC | [Example 2: Identity and security boundaries (Go)](system-design.md) | 20% |  |
| Attached | System design & IaC | [Example 3: Storage and publication integrity (C#)](system-design.md) | 20% |  |
| Attached | System design & IaC | [Example 4: Cloud infra: containers & self-hosted platforms (HCL (Terraform))](system-design.md) | 0% |  |
| Attached | System design & IaC | [Example 5: Cloud infra: AWS platform stacks (HCL (Terraform))](system-design.md) | 50% |  |
| Attached | System design & IaC | [Example 6: Cloud infra: AWS platform stacks (HCL (Terraform))](system-design.md) | 0% |  |
| Attached | Diagnosis, Debugging, and Bug Fixing | [Example 2: Compilers & language runtimes (Python)](debugging.md) | 0% |  |
| Attached | Diagnosis, Debugging, and Bug Fixing | [Example 3: Medical imaging & healthcare (Python)](debugging.md) | 0% |  |
| Attached | Diagnosis, Debugging, and Bug Fixing | [Example 4: Machine learning & MLOps (Python)](debugging.md) | 0% |  |
| Attached | Feature implementation | [Example 1: Data formats & serialization (Python)](feature-implementation.md) | 50% |  |
| Attached | Feature implementation | [Example 2: Databases & storage engines (Python)](feature-implementation.md) | 0% |  |
| Attached | Feature implementation | [Example 3: Data pipelines & ETL (Python)](feature-implementation.md) | 0% |  |


![Turns per task, all catalogs](assets/all_turns.svg)
