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
../pipeline/.venv/bin/python bin/gh_plots.py              # catalog/assets/*.svg
~/code/horizon_env/bin/python3 bin/gh_md.py               # catalog/*.md and the CSV's example column
cd catalog && ../../pipeline/.venv/bin/python build_site.py --verify && python3 build_single.py && cd ..
~/code/horizon_env/bin/python3 bin/check_consistency.py      # recomputes every number on the pages from ro3/ and turns/
```

Data source: one snapshot. `ro3/` holds every task's runs at the version the 2 Nov sheet selects, and `turns/` holds the turn count of every completed Gemini run, both pulled at the time in `SNAPSHOT`. To refresh, delete both folders, fetch them again, and rebuild.

Write-ups for samples that are not OTS catalog examples are in `cat/samples_text.json`. A new sample needs an entry there.

## Rules

- **Gemini-hard:** Argon pass rate under 80% (passes over graded runs).
- **Proven:** Argon has run the task and is under 80%.
- **Likely:** no Argon runs, at least one graded run from some model, and a predicted chance of 50% or more. The prediction is the catalog's Argon share, adjusted by GLM-5.3 Flash and Gemini 3.8 Flash results on the task (naive Bayes, `bin/universe.py`).
- **Main samples:** shortlisted ("Updated selection 120" tab), in the catalog, run by Argon, 4 or more Gemini runs, pooled Gemini pass rate of 25% or less, and one per catalog.
- **Attached samples:** shortlisted, run by Argon, pooled Gemini pass rate of 50% or less, lowest first, and at most 3 per task group.
- **Catalog merges:** for presentation only, three task groups move into other catalogs, each as one domain. Migration goes to ProgramBench as "Cross-language migration", Infrastructure as code goes to System design as "State-preserving infrastructure changes", and Data engineering goes to Feature implementation as "Data pipelines" (`MERGE` in `bin/gh_stats.py`). Selection and estimates still use each group's own Argon share.
