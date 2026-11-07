# OTS catalogs, all models

The OTS catalogs with every task and every model. The report has 1,305 tasks in 7 catalogs: the 2 Nov sheet's catalog plus five new System design tasks (1,356), plus 25 tasks of the 'Updated selection 120' tab that were missing (`cat/extra_tasks.json`: 23 System design, one IaC, one System design schema migration), less 76 tasks with no graded run from a kept model before the snapshot (`EXCLUDED_TASKS` in `bin/common_drop.py`). Output: `catalog/ots-catalogs-all-models.html`, `ots_tasks.csv` (every task with its per-model results) and `samples.csv` (the 24 samples, with Drive and Horizon links).

It keeps the structure of the original 7-catalog version (`../catalogs/`) and the later work from the Gemini-hard version (`../gemini_hard/`): the overview, executive summaries, sample tasks with renamed ids, Drive links, checked prompts and the hand-drawn diagrams.

## Rebuild

From this folder (Horizon key needed only for the fetch step):

```bash
export HORIZON_API_KEY="$(security find-generic-password -a "$USER" -s HORIZON_API_KEY -w)"
~/code/horizon_env/bin/python3 bin/merge_rollouts.py  # adds the campaigns' runs (rollout_plan/ and ../gemini_hard/rollout_plan/) to ro/
~/code/horizon_env/bin/python3 bin/merge_late.py     # adds later runs and newer-version runs, up to LATE_CUTOFF, to ro/
~/code/horizon_env/bin/python3 bin/fetch.py      # fills ro/ (runs) and turns/ (turn counts) where missing
~/code/horizon_env/bin/python3 bin/stats.py      # cat/stats.json
../pipeline/.venv/bin/python bin/plots.py        # catalog/assets/*.svg
~/code/horizon_env/bin/python3 bin/md.py         # catalog/*.md, ots_tasks.csv, samples.csv
cd catalog && ../../pipeline/.venv/bin/python build_site.py --verify && python3 build_single.py && cd ..
~/code/horizon_env/bin/python3 bin/check.py      # recomputes every number from ro/ and turns/, checks samples and writing rules
~/code/horizon_env/bin/python3 bin/horizon_check.py  # compares ro/ with live Horizon -> audit/horizon_check.json
```

## Data

- **Snapshot:** the base snapshot is at the time in `SNAPSHOT` (2 Nov). Later runs are added up to the time in `LATE_CUTOFF` (7 Nov).
  - `ro/` is a copy of `../gemini_hard/ro3/`, the runs at each task's version selected on the 2 Nov sheet, plus 9 tasks first catalogued as Optimization, fetched at their selected versions and counted as System design.
  - `turns/` has the turn count of every completed run of every model.
  - **Rollout campaign (5 Nov):** the runs started by the rollout plan in `rollout_plan/` are added on top of the snapshot by `bin/merge_rollouts.py`. That covers 212 runs on 34 tasks: the 201-run main run plus the pilot, retry and diagnostic runs. Each run is at the task's report version and is listed in `campaign_rollouts` in its `ro/` file. The 5 Nov Argon rollout run for the Gemini-hard catalog (`../gemini_hard/rollout_plan/`) adds 308 Gemini 4 Argon runs on 172 of this report's tasks the same way.
  - **Later runs (7 Nov):** `bin/merge_late.py` adds every run made after the snapshot at a task's report version, and every run at a newer version of a task, up to `LATE_CUTOFF`. A task with runs at a newer version counts both versions; the newer versions are listed in `extra_versions` in its `ro/` file and in the `Newer versions included` column of `ots_tasks.csv`. That adds 250 runs at the report version (140 Gemini 4 Argon, 110 Gemini 3.8 Flash) and 293 at newer versions on 43 tasks (151 Gemini 3.8 Flash, 86 Gemini 4 Argon, 56 GLM-5.3 Flash), 543 runs on 82 tasks in all, listed in `late_rollouts`. 35 runs from three models the report does not map (`abyss`, `abyss-pro`, `levanter`) are left out.
  - The task list is a frozen copy of `../gemini_hard/universe.json` in `cat/universe.json`, because that file keeps changing.
- **Shared with `../gemini_hard/`:**
  - the task list, frozen in `cat/universe.json` (see above)
  - the sample task folders and zips
  - the checked prompts (`audit/instr/`)
  - the diagrams (`diagrams/<task id>/draw.py`, rendered with `diagrams/sd.py`)

## Rules

- **Average reward:** average@k. For each task, the mean grader score over graded runs, partial credit included (no pass/fail cut-off); then the mean over tasks. Errored runs are left out. A task with runs at more than one version pools them.
- **Model rows:** a model gets a row in a catalog's tables once it has graded runs on 5 or more tasks there. Models with fewer are listed in a sentence below the table.
- **Average reward cards:** every page opens with one card per model that has graded runs there, in the same order everywhere (most graded runs overall first). A card notes the task count when the model ran fewer than 5 tasks in that catalog.
- **Turn counts:** a task's turn count is the average over its completed runs from every model. A task is long horizon at 200 or more turns.
- **Models:** model names come from `../pipeline/ro_models.json`. Two came from the vendored Horizon model map: `helm` is cohere/command-a and `granola-plus` is meta/muse-spark-1.3. Eleven models are left out everywhere (`bin/common_drop.py`): Gemini 3.7 Flash, Cohere Command A, Grok 4.7, Claude Opus 5.5, GPT-6 Astra, Qwen 3.8 Max, GLM 5.2, GLM 5.3, Muse Wonder, Muse Spark 1.3 and Kimi K3.1 Pro.
- **Samples:** the 24 samples are the 12 earlier main samples, the 10 earlier attached ones and 2 super-samples (`super/`), all shown as sample tasks on their own catalog page. The super-samples run on their own pinned Horizon tasks, so they are not rows of `ots_tasks.csv`. 
- **Writing rules:**
  - no em or en dashes
  - no task names in prose (client-facing sample ids only)
  - no "How it maps to the work" paragraphs
  - The write-ups are in `cat/text.json`.
- **seaweedfs task:** its classification was added by hand in `cat/new_task_classes.json`.
