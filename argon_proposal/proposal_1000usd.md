# Gemini 4 Argon run proposal: $1,000 budget

28 Oct 2026 · Carlos

Run Gemini 4 Argon (`google/gemini-4-argon`, `umbra`) on 84 new catalog tasks, 2 runs each: 168 runs at an estimated $890, with $110 in reserve. Argon then appears in the pass-rate plots of all seven catalogs. Repo upgrades stay out, so ProgramBench still reflects only its reimplementation tasks. Task list: `argon_task_selection_1000usd.csv`.

## Cost basis

Argon's 64 existing runs (System design, effort `high`, `typhoon`) cost $410.81 in total: $6.42 per run on average ($5.90 median, $15.64 max), or $0.0174 per turn. Each task's estimate is 2 runs × that task's average turns across all existing runs (catalog average if it has none) × $0.0174. The full 1,060-run plan in `proposal.md` would cost about $6,900.

## Allocation

| Catalog | Catalog tasks | Argon tasks after | Shortlisted | Runs | Est. cost | Pooled pass rate ± | Share at 0% ± |
|---|---:|---:|---:|---:|---:|---:|---:|
| ProgramBench (reimplementation) | 435 | 10 | 4 | 20 | $269 | 10 pp | 15 pp |
| System design | 56 | 15 (already run) | 0 | 0 | $0 | existing | existing |
| Debugging | 378 | 15 | 14 | 30 | $251 | 21 pp | 23 pp |
| Feature implementation | 120 | 10 | 2 | 20 | $114 | up to 20 pp | up to 25 pp |
| Infrastructure as code | 300 | 20 | 13 | 40 | $78 | 14 pp | 12 pp |
| Data engineering | 17 | 17 (all) | 10 | 34 | $47 | full coverage | full coverage |
| Migration | 36 | 12 | 4 | 24 | $130 | 17 pp | 24 pp |
| **Total** | | **99** | **47** | **168** | **$890** | | |

Each margin is a 95% interval, from resampling 2 runs per task of each catalog's most-run model. The Feature implementation reference model passes almost nothing, so its margin is a worst-case bound.

Within each catalog, tasks are spread over domains in proportion to the catalog (largest remainder), shortlisted tasks first, then tasks other models have already run. Seed 20261028.

## What the budget leaves out

- **ProgramBench repo upgrades** (353 tasks, never run by any model). A 3-task, 1-run smoke test costs roughly $40 and fits in the reserve; 10 tasks × 2 runs would be about $250 more.
- **Precision.** These numbers are enough to place Argon in the plots and the model tables. They are not enough to rank it closely against models within about 15 points.
- **System design** gets no new runs; its 15 existing Argon tasks already clear the plot threshold.

## Launch steps

1. Launch the 84 tasks in `argon_task_selection_1000usd.csv`: 2 runs each, `typhoon`, effort `high`, at the CSV's task version.
2. Check spend after the first 40 runs against the estimate; stop at $1,000.
3. Re-pull runs and turn counts and rebuild the catalog site.
