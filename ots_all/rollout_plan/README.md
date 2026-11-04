# Rollout plan

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

| Setting | Value | How it is set |
|---|---|---|
| Agent | Terminus V2 | `agent_type: typhoon` (Typhoon is Horizon's codename for TerminusV2Agent, the agent the existing runs used) |
| Turn limit | 1,200 | `max_turns: 1200`. The CLI only accepts up to 1,000, so submit through `POST /api/v1/evaluations` (it accepts up to 10,000) |
| Effort | max | `effort: "max"`. Validated per model when you submit |
| Max output tokens | 32,000 | `max_tokens: 32000` (the most allowed) |
| Agent timeout | 43,200 s | Not a submit option. It is `[agent] timeout_sec` in each task's `task.toml`, so it needs new task versions or a platform-side override. **Open** |

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
