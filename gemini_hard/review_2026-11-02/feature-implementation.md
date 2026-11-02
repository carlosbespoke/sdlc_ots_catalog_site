# Feature implementation

## Executive summary

| KPI cards: 101 Tasks |<div class="kpi"><div class="kpi-value">11%</div><div class="kpi-label">Gemini 4 Argon pass rate</div></div><div class="kpi"><div class="kpi-value">0%</div><div class="kpi-label">Gemini 3.8 Flash pass rate</div></div></div>

Each task asks the agent to add a capability to an existing open-source library or service, specified the way a series of pull requests would be, while every existing behaviour keeps working. The data pipeline tasks extend data libraries so pipelines keep producing correct results after an upstream format or schema change. Hidden tests check the new behaviour and the old behaviour together.

Gemini 4 Argon passes 11% of its runs on these tasks, and it fails every run on 85% of the tasks. Gemini 3.8 Flash passes 0%, and it fails every run on 98% of the tasks. The main languages are Go (68%), Python (32%) and C# (1%).

| Domain | What the tasks do | % of catalog |
|---|---|---:|
| Languages & developer tooling | Add features to command-line tools, compilers and API tooling. | 22% |
| Systems, hardware & accelerators | Add features to networking and HTTP libraries and to smart-home device integrations. | 16% |
| Data engineering & databases | Add features to serialization formats and storage engines. | 14% |
| Applications & business domains | Add features to web applications and media processing libraries. | 14% |
| Scientific & ML software | Add features to ML, agent and geospatial libraries. | 10% |
| Cloud infrastructure & IaC | Add features to container platforms and configuration-management tools. | 8% |
| Security | Add features to cryptography and secrets libraries. | 5% |
| Data pipelines | Extend data libraries so pipelines keep correct results when upstream data changes. | 5% |
| Observability & reliability | Add features to monitoring and observability tooling. | 4% |
| Distributed systems & coordination | Add features to messaging and calendaring libraries. | 3% |

## Why this catalog

### Problems engineers face

Maintainers add a capability that runs through many code paths of an unfamiliar library or service, while existing callers must see no change. Typical requests add an opt-in mode or policy, keep information the library currently drops, or make a subsystem safe under concurrency and failure. Data engineers face a related problem: after an upstream format or schema change, a pipeline keeps running but produces wrong results, and the library has to handle the new data while old inputs still work.

### How the tasks reproduce them

Each task pins an open-source repository, mostly Go or Python, in an offline container and gives a written specification of the new behaviour, with the public types and functions to deliver. The agent's edits are collected as a diff against the base commit. After the session, hidden acceptance tests check the new behaviour and the project's existing tests check that nothing else changed. The data pipeline tasks also provide sample inputs in `/data`.

### Typical prompts

- A capability gap stated as "X cannot Y", then dense paragraphs on the behaviour to add and the behaviour to preserve.
- A bullet list of required exported names, constants and signatures, with a research and plan file due before any code change.
- A first-person data problem after an upstream change, with sample files in `/data` and a request to keep existing results unchanged.

## Domain breakdown

![Share of tasks by domain](assets/feature-implementation_domain.svg)

## Language and seniority

![Primary language and seniority](assets/feature-implementation_metadata.svg)

### Primary language

| Primary language | % of catalog |
|---|---:|
| Go | 67.6% |
| Python | 31.5% |
| C# | 0.9% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Senior | 92.6% |
| Mid-Senior | 4.6% |
| Staff+ | 2.8% |

## Gemini pass rates across the catalog

| Model | Pass rate | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|
| google/gemini-4-argon | 11% | 85% | 15% | 0% |
| google/gemini-3.8-flash | 0% | 98% | 0% | 0% |

![Per-task pass rate by Gemini model](assets/feature-implementation_per_task.svg)

## Turn counts and long-horizon tasks

A task's turn count is the average over its Gemini runs. A task is long horizon when that average is 200 or more turns.

| Measure | Value |
|---|---:|
| Average turn count | 347.9 |
| Median turn count | 321.7 |
| Range | 79 to 956 |
| Long-horizon tasks (200+ turns) | 72% of tasks |

![Turns per task](assets/feature-implementation_turns.svg)

| Model | % of tasks | Mean turns | % with 200+ turns |
|---|---:|---:|---:|
| google/gemini-3.8-flash | 94% | 345.5 | 69% |
| google/gemini-4-argon | 13% | 229.6 | 63% |

## Example tasks from the shortlist

These examples are attached samples. All of them come from the shortlist and have Gemini runs that pass at most half the time.

### Example 1: Data formats & serialization (Python)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Data engineering |
| Domain | Data pipelines |
| Sub-domain | Data formats & serialization |
| Language | Python |
| Seniority | Mid-Senior |
| Turn count | 84 (google/gemini-4-argon) |
| Long horizon | no |

Prompt shape: A feature request for a widely used library, written as a list of behaviors per option with compatibility constraints for existing behavior.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 50% | 0.50 |

#### Environment

![How the task works](assets/env-feature-implementation-ex1.svg)

#### How it maps to the work

A data engineer ingests partner XML that now carries explicit nulls and whitespace that matters. They extend a parser and writer with opt-in options, keep defaults unchanged and make a document round trip without losing null positions.

### Example 2: Databases & storage engines (Python)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Data engineering |
| Domain | Data pipelines |
| Sub-domain | Databases & storage engines |
| Language | Python |
| Seniority | Mid-Senior |
| Turn count | 236 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: A production symptom with several schema change causes, then a list of invariants the migration must satisfy including idempotence and error cases.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-pdk-sqlite-history-json-schema.svg)

#### How it maps to the work

A data engineer owns audit history for SQLite tables whose schema later changed through ALTER TABLE. They must repair the stored history in an upgrade path so restore and history queries work again, with a safe dry run and no change on a second run.

### Example 3: Data pipelines & ETL (Python)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Data engineering |
| Domain | Data pipelines |
| Sub-domain | Data pipelines & ETL |
| Language | Python |
| Seniority | Mid-Senior |
| Turn count | 248 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: An export format switch with a failing command given verbatim and an equivalence requirement between two input formats.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-feature-implementation-ex3.svg)

#### How it maps to the work

A data engineer's nightly pipeline switched its export from JSON to CSV, so validation fails and totals are wrong. They fix the library so a CSV source gives the same records and results as JSON, including CSV written by an earlier job.
