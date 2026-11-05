# Gemini-hard catalogs

The OTS catalogs narrowed to tasks where Gemini 4 Argon passes, or is likely to pass, under 80% of its runs, with Gemini-only numbers. Output: `catalog/gemini-hard-catalogs.html` (same structure as `../catalogs/ots-catalogs.html`) and `gemini_hard_universe.csv` (every selected task, its tier and its catalog example, if any).

## Rebuild

From this folder (Horizon key needed only for the fetch steps):

```bash
export HORIZON_API_KEY="$(security find-generic-password -a "$USER" -s HORIZON_API_KEY -w)"
~/code/horizon_env/bin/python3 bin/fetch_runs.py          # runs at the 2 Nov sheet's selected versions (ro3/)
~/code/horizon_env/bin/python3 bin/universe.py            # estimate, selection, samples, CSV
~/code/horizon_env/bin/python3 bin/fetch_turns.py         # turn counts of Gemini runs (turns/)
~/code/horizon_env/bin/python3 bin/fetch_files.py         # task files for samples without a local copy (show/; untrusted, never run)
~/code/horizon_env/bin/python3 bin/gh_stats.py            # cat/stats.json
~/code/horizon_env/bin/python3 bin/gh_md.py               # catalog/*.md and the CSV's example column
cd catalog && ../../pipeline/.venv/bin/python build_site.py --verify && python3 build_single.py && cd ..
~/code/horizon_env/bin/python3 bin/check_consistency.py      # recomputes every number on the pages from ro3/ and turns/
~/code/horizon_env/bin/python3 bin/check_samples.py          # each sample's heading, fields, prompt, write-up, diagram, overview row and CSV row
~/code/horizon_env/bin/python3 bin/verify_samples_live.py    # optional, needs the key: samples' pass rates and turn counts re-pulled live from Horizon
```

Data source: one snapshot. `ro3/` holds every task's runs at the version the 2 Nov sheet selects, and `turns/` holds the turn count of every completed Gemini run, both pulled at the time in `SNAPSHOT`. To refresh, delete both folders, fetch them again, and rebuild.

Write-ups for samples that are not OTS catalog examples are in `cat/samples_text.json`. A new sample needs an entry there.

## Rules

- **Gemini-hard:** Argon pass rate under 80% (passes over graded runs).
- **Charts:** the figures are interactive, built by `bin/charts.js` and `bin/charts.css`, ported from the all-models report (`../ots_all/bin/charts.js`) with pass rate in place of average reward. `gh_md.py` embeds one JSON data block per page from `task_rows` in `cat/stats.json`. A task's value is its share of passed Gemini runs, and a model's rate pools its runs across tasks, so the charts give the same numbers as the tables. Bar-chart counts are of the selected tasks; the headline task counts are estimates.
- **Argon failure modes:** the overview's failure-mode section is the 4 Nov supplement on the 22 samples (`cat/failure_modes.json`). `gh_md.py` computes the run totals and pass@1/pass@2 from the snapshot and stops if the supplement's counts do not add up to them.
- **Models shown:** Gemini 4 Argon and Gemini 3.8 Flash. Gemini 3.7 Flash is left out of every page, plot, turn count and CSV column (`DROPPED` in `bin/common.py`). Its runs still count as evidence when predicting Likely tasks, so the selection is unchanged.
- **Proven:** Argon has run the task and is under 80%.
- **Likely:** no Argon runs, at least one graded run from some model, and a predicted chance of 50% or more. The prediction is the catalog's Argon share, adjusted by GLM-5.3 Flash and Gemini 3.8 Flash results on the task (naive Bayes, `bin/universe.py`).
- **Attached samples:** 10 from the shortlist with Argon runs that are not main samples, Gemini-hard tasks first, then lowest Argon pass rate. Only 8 such tasks are Gemini-hard; the other 2 sit exactly at Argon 80%. They appear only in the overview's samples table and `samples.csv` (every sample, main and attached, with task id and version).
- **Main samples:** `mangle-8edad8d3-blind30` is excluded by reviewer decision (`NOT_SAMPLE` in `bin/universe.py`). Up to 3 per catalog page and at least one per task group, except System design & IaC, whose samples come from System design only (`SAMPLE_GROUPS`), all in the selection and run by Argon. The strongest earlier sample (4+ Gemini runs, 25% or less) anchors each page. A task group without a sample gets its lowest-pass-rate shortlisted task, or one from the original catalog's shortlist when it has none on the current one (ProgramBench). Remaining slots go to shortlisted tasks at 50% or less, lowest Gemini pass rate first (`bin/universe.py`).
- **Catalog merges:** for presentation only, three task groups move into other catalogs, each as one domain. Migration goes to ProgramBench as "Cross-language migration", Infrastructure as code goes to System design as "State-preserving infrastructure changes", and Data engineering goes to Feature implementation as "Data pipelines" (`MERGE` in `bin/gh_stats.py`). Selection and estimates still use each group's own Argon share.
