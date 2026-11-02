# Gemini 4 Argon run proposal

28 Oct 2026 · Carlos

Run Gemini 4 Argon (`google/gemini-4-argon`, Horizon codename `umbra`) on 227 catalog tasks: every Green shortlisted task plus a domain-stratified sample of each catalog. That is 212 new tasks and 1,060 runs. With these runs Argon appears in every catalog's pass-rate plot, model table and turn table. Today it appears only in System design.

The task list is in `argon_task_selection.csv`, next to this file.

## What we run

| Catalog | Catalog tasks | Selected | Shortlist | Already run by Argon | Sampled | New tasks | New runs |
|---|---:|---:|---:|---:|---:|---:|---:|
| ProgramBench | 435 | 40 | 7 | 0 | 33 | 40 | 200 |
| System design | 56 | 30 | 9 | 14 | 7 | 15 | 75 |
| Diagnosis, Debugging, and Bug Fixing | 378 | 44 | 34 | 0 | 10 | 44 | 220 |
| Feature implementation | 120 | 30 | 2 | 0 | 28 | 30 | 150 |
| Infrastructure as code | 300 | 30 | 16 | 0 | 14 | 30 | 150 |
| Data engineering | 17 | 17 | 10 | 0 | 7 | 17 | 85 |
| Migration | 36 | 36 | 7 | 0 | 29 | 36 | 180 |
| **Total** | **1,342** | **227** | **85** | **14** | **128** | **212** | **1,060** |

One of the 15 System design tasks that Argon has already run is also on the shortlist. It is counted under Shortlist.

A model enters a catalog's plots once it has graded runs on at least 5 tasks. Every catalog clears that bar with room to spare.

## How the tasks were picked

1. **Shortlist.** All 85 shortlisted tasks that are Green in the "Full catalogue" tab.
2. **Existing Argon runs.** The 15 System design tasks Argon has already run stay in the sample and are not rerun.
3. **Sample size.** Catalogs with 40 tasks or fewer are run in full (Data engineering, Migration). Larger catalogs get the larger of 30 tasks or the shortlist plus 10. ProgramBench gets 40, as explained below.
4. **Domain stratification.** The rest of each catalog's quota is spread over its domains in proportion to their share of the catalog, after counting the tasks already picked. Within a domain, the picks favour tasks that other models have already run, so Argon can be compared with them on the same tasks. The picks are otherwise random, with seed 20261028.

The resulting domain mix tracks the catalog closely. Debugging's domains are all within 1 point of their catalog share, and Feature implementation's within 2 points. Infrastructure as code is the exception (see Known skews).

## Run settings

| Setting | Value | Why |
|---|---|---|
| Model | `google/gemini-4-argon` (`umbra`) | |
| Agent | `typhoon` | Same agent as every existing catalog run |
| Effort | `high` | Highest effort Argon supports (`low`, `medium`, `high`); matches its existing 75 System design runs |
| Runs per task | 5 | Matches the existing Argon runs; other models have a median of 4 to 8 per task |
| Task version | The version selected in the "Full catalogue" tab | Listed per task in the CSV |

Expected volume: about 400,000 agent turns if Argon matches each catalog's average turn count. On the 15 System design tasks it already ran, Argon averaged 350 turns per run, against 586 for GLM-5.3 Flash on the same tasks. So the real figure is likely lower.

## Expected precision

These are 95% intervals, from resampling the existing runs of each catalog's most-run model at the same sample sizes. "Pooled pass rate" is all passes over all graded runs. "Share at 0%" is the share of tasks where no run passes.

| Catalog | Tasks run | Pooled pass rate | Share of tasks at 0% |
|---|---:|---:|---:|
| ProgramBench | 40 | ±6 pp | ±13 pp |
| System design | 30 of 56 | ±6 pp | ±9 pp |
| Debugging | 44 | ±11 pp | ±14 pp |
| Feature implementation | 30 | ±1 to ±9 pp | ±3 to ±18 pp |
| Infrastructure as code | 30 | ±8 pp | ±5 pp |
| Data engineering | 17 of 17 | full coverage | full coverage |
| Migration | 36 of 36 | full coverage | full coverage |

For Feature implementation the reference model passes almost nothing, which makes the interval look artificially narrow. The upper bound is the worst case for a 50% pass rate. Fully covered catalogs only have run-to-run noise.

## ProgramBench repo upgrades

No model has ever run any of the 353 repo-upgrade tasks (81% of ProgramBench, all in batch `alpharecon-programbench-upgrade`). Today's ProgramBench plot reflects only the 81 reimplementation tasks.

The sample therefore splits ProgramBench into two quotas of 20:

- **20 reimplementation tasks**: the 7 shortlisted ones plus 13 sampled, all already run by GLM-5.3 Flash, so the comparison is paired.
- **20 repo-upgrade tasks**, sampled across their domains. These would be the first runs on this half of the catalog.

Because these tasks have never run, launch 3 of them with 1 run each first. Confirm the environment builds, the agent runs and the grader returns scores before launching the other 97 upgrade runs.

## Known skews and decisions to confirm

- **IaC leans on the shortlist.** The shortlist brings in every Pulumi port, policy remediation and CDK task (7 tasks), so Terraform module refactors are 77% of the IaC sample against 98% of the catalog. Options: accept it and note it on the page, or add about 70 more Terraform refactor tasks (350 runs) to bring the sample within 5 points.
- **Debugging leans on the shortlist too.** 34 of its 44 tasks are shortlisted. The domain mix still matches the catalog. 6 of the shortlisted tasks have no runs from any other model, so they add Argon-only data.
- **ProgramBench repo upgrades.** Confirm that we want Argon to be the first model on them, rather than also running GLM-5.3 Flash on the same 20 so the comparison is paired.
- **Five runs per task.** Dropping to 3 saves 424 runs. The pooled rates hold up, but per-task rates become coarse (0, 33, 67, 100%), which weakens the "tasks at 20-80%" column.

## Launch steps

1. Smoke test: 3 ProgramBench repo-upgrade tasks from the CSV, 1 run each.
2. Launch the 192 tasks that are not ProgramBench repo upgrades: 5 runs each, `typhoon`, effort `high`, at the CSV's task version.
3. Launch the 20 ProgramBench repo-upgrade tasks once the smoke test passes.
4. Re-pull the runs and turn counts, then rebuild the catalog site.
