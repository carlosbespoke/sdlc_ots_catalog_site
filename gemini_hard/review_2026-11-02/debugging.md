# Diagnosis, Debugging, and Bug Fixing

## Executive summary

| KPI cards: 98 Tasks |<div class="kpi"><div class="kpi-value">25%</div><div class="kpi-label">Gemini 4 Argon pass rate</div></div><div class="kpi"><div class="kpi-value">7%</div><div class="kpi-label">Gemini 3.8 Flash pass rate</div></div></div>

Each task gives the agent a codebase that misbehaves and a description of the symptoms or the documentation it should follow. The agent finds the faulty code, fixes it without breaking what already works, and in some tasks writes a report naming each root cause. Hidden tests check both the fixes and the code that was already correct.

Gemini 4 Argon passes 25% of its runs on these tasks, and it fails every run on 71% of the tasks. Gemini 3.8 Flash passes 7%, and it fails every run on 67% of the tasks. The main languages are Python (60%) and Go (40%).

| Domain | What the tasks do | % of catalog |
|---|---|---:|
| Languages & developer tooling | Find and fix faults in command-line tools, a compiler, a logic-programming engine and a utility library. | 47% |
| Scientific & ML software | Bring ML tracking, medical imaging and agent libraries back in line with their documentation. | 20% |
| Data engineering & databases | Fix SQL tooling and data validation libraries. | 13% |
| Applications & business domains | Fix a web crawler and a collaborative documents application. | 13% |
| Distributed systems & coordination | Fix a calendaring and recurrence library. | 7% |

## Why this catalog

### Problems engineers face

Maintainers are handed code that is wrong in several places and must find the causes without a test suite to lean on. In the diagnosis tasks, many undocumented edits break unrelated features at once. In the documentation-drift tasks, the code still runs but contradicts its own documentation. One task starts from a single production symptom with a hidden root cause. In all of them the engineer reproduces the symptom, finds the faulty function and repairs it without breaking neighbouring behaviour.

### How the tasks reproduce them

Each task ships a pinned checkout of an open-source project, with the tests withheld and no network. The prompt describes the symptoms or names the documentation in scope, never the location of the faults. Most diagnosis tasks also ask for `/app/rca.json`, which lists the file and function of each edit and is compared with an answer key. Drift tasks treat the documentation as the authority and forbid editing it. Hidden tests check the repairs and the behaviour that was already correct.

### Typical prompts

- A first-person list of symptoms grouped by feature, with no file or function named, ending in a request to fix and report.
- A stated number of undocumented edits and a JSON schema for the root-cause report.
- A library description with the source paths and documentation pages in scope, and the rule that documentation outranks code.

## Domain breakdown

![Share of tasks by domain](assets/debugging_domain.svg)

## Language and seniority

![Primary language and seniority](assets/debugging_metadata.svg)

### Primary language

| Primary language | % of catalog |
|---|---:|
| Python | 60.0% |
| Go | 40.0% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Senior | 93.3% |
| Mid-Senior | 6.7% |

## Gemini pass rates across the catalog

| Model | Pass rate | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|
| google/gemini-4-argon | 25% | 71% | 29% | 0% |
| google/gemini-3.8-flash | 7% | 67% | 0% | 8% |

![Per-task pass rate by Gemini model](assets/debugging_per_task.svg)

## Turn counts and long-horizon tasks

A task's turn count is the average over its Gemini runs. A task is long horizon when that average is 200 or more turns.

| Measure | Value |
|---|---:|
| Average turn count | 417.5 |
| Median turn count | 433.0 |
| Range | 54 to 916 |
| Long-horizon tasks (200+ turns) | 73% of tasks |

![Turns per task](assets/debugging_turns.svg)

| Model | % of tasks | Mean turns | % with 200+ turns |
|---|---:|---:|---:|
| google/gemini-3.8-flash | 80% | 539.5 | 86% |
| google/gemini-4-argon | 47% | 280.6 | 67% |

## Example tasks from the shortlist

The first example is a main sample for the catalog; the others are attached samples. All of them come from the shortlist and have Gemini runs that pass at most half the time.

### Example 1: Logic programming (Go)

| Field | Value |
|---|---|
| Sample | Main sample for the catalog |
| Final category | Diagnosis, Debugging, and Bug Fixing |
| Domain | Languages & developer tooling |
| Sub-domain | Logic programming |
| Language | Go |
| Seniority | Senior |
| Turn count | 582 (google/gemini-4-argon), 658 (google/gemini-3.8-flash) |
| Long horizon | yes |

Prompt shape: A first-person symptom report grouped by subsystem and written in user terms without function names, followed by a request to restore the behavior, a JSON schema for `/app/rca.json` with one file and function per edit, and a requirement to write `/app/RESEARCH_AND_PLANNING.md` before touching code.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 50% | 0.50 |
| google/gemini-3.8-flash | 0% | 0.00 |

#### Environment

![How the task works](assets/env-mangle-8edad8d3-blind30.svg)

#### How it maps to the work

A maintainer of a Datalog engine receives a user report that undocumented single-line edits have broken parsing, type checking, evaluation, provenance and temporal arithmetic, and no test suite is available. The maintainer starts from the faulted source tree and the written symptoms only. The hard part is tracing each symptom to the function that holds the edit, including symptoms that need two separate fixes before they disappear, and then naming exactly those functions in a root-cause report.

### Example 2: Compilers & language runtimes (Python)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Diagnosis, Debugging, and Bug Fixing |
| Domain | Languages & developer tooling |
| Sub-domain | Compilers & language runtimes |
| Language | Python |
| Seniority | Senior |
| Turn count | 280 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: A repository summary, an exact in-scope code and documentation list, and the instruction to change the implementation and never the documentation.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-exo-canonical-ots.svg)

#### How it maps to the work

A compiler engineer working on a scheduling language finds that primitives, cursors or code generation behave differently from the documentation pages and docstring examples. The engineer treats the docs as the contract and repairs the compiler code without touching the docs. This is the documentation-drift repair family.

### Example 3: Medical imaging & healthcare (Python)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Diagnosis, Debugging, and Bug Fixing |
| Domain | Scientific & ML software |
| Sub-domain | Medical imaging & healthcare |
| Language | Python |
| Seniority | Senior |
| Turn count | 312 (google/gemini-4-argon) |
| Long horizon | yes |

Prompt shape: A short description of the library, a one-line directive to fix implementation drift from the documentation, an explicit list of in-scope source paths and documentation pages, a rule that documentation outranks code and comments, and a note on the installed offline environment.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-torchio-canonical.svg)

#### How it maps to the work

A maintainer of a medical imaging library treats the documentation as the specification and repairs the places where the code has drifted from it. The engineer starts from the source tree with its pages, docstrings and examples, and has no list of the discrepancies. The hard part is reading a large documented surface of transforms, data containers and patch sampling closely enough to find each behavioral mismatch, fixing the code rather than the docs, and leaving every behavior that already matches untouched.

### Example 4: Machine learning & MLOps (Python)

| Field | Value |
|---|---|
| Sample | Attached sample |
| Final category | Diagnosis, Debugging, and Bug Fixing |
| Domain | Scientific & ML software |
| Sub-domain | Machine learning & MLOps |
| Language | Python |
| Seniority | Mid-Senior |
| Turn count | 54 (google/gemini-4-argon) |
| Long horizon | no |

Prompt shape: A production complaint written as a ticket (diverged runs sort first in a sweep CSV while the live view shows NaN), with no module named, asking for a source-level fix, a regression test and a root-cause note in `rca.json`.

#### Prompt

| [verbatim task prompt omitted: task content, not authored text] |

#### Pass rates

| Model | Pass rate | Mean score |
|---|---:|---:|
| google/gemini-4-argon | 0% | 0.00 |

#### Environment

![How the task works](assets/env-debugging-ex4.svg)

#### How it maps to the work

A machine learning engineer maintains an experiment tracker and receives a complaint that diverged sweep runs rank first in the exported CSV. The engineer has to follow the NaN from the CSV plugin back to where the value is lost, repair it in the library so every consumer is fixed, add a regression test, and write down where the defect starts. The work mirrors an incident ticket against a shared tool.
