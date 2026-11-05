# Rollout plan

## Result (5 Nov)

All 40 task and model pairs finished with 4 or more graded runs on the first pass, counting the three graded pilot runs. No run errored, so the top-up step was not needed. Five runs ended without a grade (`no_progress`), and every task still reached 4 graded runs without them. Total model cost was $1,018, against $1,145 expected. Every kept model now has graded runs on 5 or more tasks in every catalog. Per-run results are in `launch_results.json`, and the runs are merged into the report by `bin/merge_rollouts.py`.

| Catalog | Model | Tasks | Runs | Graded | Average reward | Mean turns | Cost |
|---|---|---|---|---|---|---|---|
| ProgramBench | Gemini 4 Argon | 12 | 67 | 64 | 37% | 369 | $559 |
| IaC | Gemini 3.8 Flash | 8 | 37 | 37 | 70% | 123 | $108 |
| Data engineering | GLM 5.3 Flash | 5 | 21 | 20 | 80% | 213 | $18 |
| Data engineering | Gemini 3.8 Flash | 5 | 24 | 24 | 58% | 324 | $166 |
| Migration | GLM 5.3 Flash | 1 | 5 | 4 | 0% | 954 | $13 |
| Migration | Gemini 3.8 Flash | 1 | 5 | 5 | 0% | 443 | $43 |
| Optimization | GLM 5.3 Flash | 3 | 13 | 13 | 38% | 424 | $22 |
| Optimization | Gemini 4 Argon | 5 | 29 | 29 | 45% | 174 | $89 |

Average reward here is the mean grader score over this run's graded runs only, pooled over runs. The report's per-catalog figures average per task and include the earlier runs.

## Plan

Goal: every kept model (GLM 5.3 Flash, Gemini 3.8 Flash, Gemini 4 Argon) has graded runs on at least 5% of each catalog's tasks, and on at least 5 tasks, so it gets a row in that catalog's tables and a cell in the overview heatmap. 4 graded runs per task. Built by `bin/rollout_plan.py`; the task list is `plan.csv` (40 tasks), the numbers are in `summary.json`.

## What to run

| Catalog | Model | Has now | Target | Tasks to add | Runs to start | Expected | Ceiling |
|---|---|---|---|---|---|---|---|
| ProgramBench (434) | Gemini 4 Argon | 10 | 22 | 12 | 68 | $379 | $1,422 |
| IaC (300) | Gemini 3.8 Flash | 7 | 15 | 8 | 38 | $254 | $1,942 |
| Data engineering (17) | GLM 5.3 Flash | 0 | 5 | 5 | 22 | $22 | $150 |
| Data engineering | Gemini 3.8 Flash | 0 | 5 | 5 | 24 | $177 | $1,227 |
| Migration (18) | GLM 5.3 Flash | 4 | 5 | 1 | 5 | $34 | $34 |
| Migration | Gemini 3.8 Flash | 4 | 5 | 1 | 5 | $110 | $256 |
| Optimization (9) | GLM 5.3 Flash | 2 | 5 | 3 | 13 | $14 | $89 |
| Optimization | Gemini 4 Argon | 0 | 5 | 5 | 29 | $155 | $607 |
| **Total** | | | | **40** | **204** | **$1,145** | **$5,727** |

Every other catalog and model pair already meets the target.

- **Runs to start:** 4 graded runs per task, grossed up by each model's error rate in the snapshot (GLM 5.3 Flash 6%, Gemini 3.8 Flash 16%, Gemini 4 Argon 29%).
- **Expected cost:** dollars per turn for the model (Horizon cost ledger, divided by that model's mean turns) times the expected turns in that catalog under a 1,200-turn limit. Runs that hit their old limit are counted at 1,200 turns.
- **Ceiling:** every run goes the full 1,200 turns.
- **Effort:** the Gemini runs behind the cost basis ran at `high`, and this plan uses `max`. Thinking costs at `max` are not measured. Allowing 30% more on the Gemini groups puts the budget at about $1,470.

## Settings

Settings come from each task's own `task.toml` at the plan version (parsed into `task_infra.json`) and from Horizon's evaluation config. `bin/rollout_settings.py` writes them per task and model to `runs.csv`, which is what gets submitted.

**Same for every run**

| Setting | Value | Source |
|---|---|---|
| Agent | Terminus V2 (`typhoon`) | the agent behind the existing runs |
| Turn limit | 1,200 | submitted through the API (the CLI stops at 1,000) |
| Max output tokens | 32,000 | Horizon's limit |
| Effort | top tier (`effort_tier: 3`) | Horizon maps it per model: `max` for GLM 5.3 Flash, `high` for both Gemini models, which offer no `max` |
| Sandbox | Cloud Batch, named explicitly | all 34 Dockerfiles install ca-certificates, which the tensorlake backend can refuse (HRZN-835 item 19); only Cloud Batch takes a machine type |
| Network, GPU | none, none | every task sets no network and 0 GPUs |

**Set by the task**

| Catalog | Model | Tasks | VM | Agent container | Verifier | Agent timeout | Verifier timeout |
|---|---|---|---|---|---|---|---|
| ProgramBench | Gemini 4 Argon | 12 | 8 CPU / 16 GB | 2 CPU / 8 GB | separate, same size | 6 h | 2 h |
| IaC | Gemini 3.8 Flash | 8 | 8 CPU / 16 GB | 4 CPU / 8 GB | separate, 2 CPU / 4 GB | 6 h (one task 3 h) | 30-60 min |
| Data engineering | GLM 5.3 Flash, Gemini 3.8 Flash | 5 each | 8 CPU / 16 GB | 4 CPU / 8 GB | separate, same size | 6 h | 30 min |
| Migration | GLM 5.3 Flash, Gemini 3.8 Flash | 1 each | 8 CPU / 16 GB | 2 CPU / 8 GB | separate, same size | 6 h | 40 min |
| Optimization | GLM 5.3 Flash (3), Gemini 4 Argon (5) | 6 distinct | 8 CPU / 16 GB, or 2 CPU / 4 GB for the two fasthttp tasks | 4 CPU / 16 GB, or 2 CPU / 4 GB | shared (runs in the agent container) | 4 h, or 3 h for fasthttp | 4 h, or 40 min for fasthttp |

- **VM size rule:** the smallest allowed VM whose CPUs cover the largest container and whose memory covers the agent container plus a separate verifier container. Horizon's default VM is 2 CPU / 4 GB and does not follow `task.toml`; a container asking for more CPUs than the VM has fails before the first turn, which is what broke the first Flash pilots. 8 CPU / 16 GB is the size the Flash retries passed on.
- **Agent timeout** is whatever the task sets (3, 4 or 6 hours). It is not a submit option.
- **VM cost** is extra to the model cost. At GCE list price an 8 CPU / 16 GB VM is about $0.22 an hour. If every run used its full build, agent and verifier time, VMs would add about $340 over the 204 runs; real runs finish much sooner.

## Task choice

Among report tasks the model has no graded run on:

1. The catalog's sample tasks first: 11 picks are samples (the three Data engineering samples for both models, dagre for both Migration models, three IaC samples for Gemini 3.8 Flash).
2. Then domains in proportion to the catalog's domain mix.
3. Inside a domain: tasks other kept models already graded (so results compare on the same tasks), then the healthiest tasks (fewest errored runs), then a seeded shuffle that keeps languages varied.
4. Only tasks whose active version is the version the report uses. Horizon runs the active version and the submit call takes no version, so this keeps the new runs joinable with the old ones. 357 report tasks have a newer active version than the one the report uses and are skipped (`active_versions.json`).

## Order of work

1. **Pilot.** Pick one task per model (the first row of each model in `plan.csv`) and start 1 run each with the settings above. Check that `effort: max` and `max_turns: 1200` are accepted, then read the cost and turns. If cost per turn is more than 1.5 times the plan's figure, stop and re-price.
2. **Main run.** 4 runs on every task in `plan.csv`, by model.
3. **Top-up.** Rerun only the errored runs until each task has 4 graded runs, up to 3 extra rounds. Flag tasks that keep erroring.
4. **Refresh.** Re-snapshot (`bin/fetch.py`), rebuild the stats, plots and pages, and rerun `bin/check.py`.
