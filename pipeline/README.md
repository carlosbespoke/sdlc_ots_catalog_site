# Catalog pipeline

Everything that builds `../catalogs/` (the Markdown pages, the site and the packaged `ots-catalogs.html`).

## Rebuild

From this folder (Horizon key needed only for the fetch steps):

```bash
export HORIZON_API_KEY="$(security find-generic-password -a "$USER" -s HORIZON_API_KEY -w)"
P=$PWD
~/code/horizon_env/bin/python3 bin/fetch_all_runs.py $P   # optional: refresh runs (ro2/) and turn counts (turns_all/); delete a task's files there to refetch it
~/code/horizon_env/bin/python3 bin/cat_stats.py            # cat/stats.json
.venv/bin/python bin/cat_plots.py $P                       # ../catalogs/assets/*.svg plots
python3 bin/d2gen.py $P                                    # only if the task diagrams change (needs `d2`)
python3 bin/cat_md.py $P                                   # ../catalogs/*.md
cd ../catalogs && ../pipeline/.venv/bin/python build_site.py && python3 build_single.py   # site/ and ots-catalogs.html
```

## What is here

| Path | Contents |
|---|---|
| `bin/` | Scripts. `cat_common.py` holds the catalog list, the Green filter (`green`) and dedupe. |
| `fullcat/` | The "Task candidates - OTS" sheet export; `full.json` is the "Full catalogue" tab (Green = shippable). |
| `rfc/` | Task metadata and classifications for the alpharecon tasks. |
| `ro/`, `ro2/` | Per-task runs. `ro2/` is the current pull at the sheet's selected version and overrides `ro/`. |
| `turns_all/` | Turn count of every completed run. `turns_s/`, `turns_x/`, `turns/` are older samples. |
| `cat/` | `stats.json` and the per-catalog prose (`<slug>_text.json`) and diagram specs. |
| `show/` | Downloaded task files for the example tasks. Untrusted data: read, never run. |
| `d2/` | Diagram icons and sources. |
| `ro_models.json` | Horizon codename to model name. |
| `argon_*.json` | Gemini 4 Argon cost basis, task resource requests, selection summary. |
| `backups/` | `backup_pre_green/` (before the Green rebase), `pre_argon/` (before the Argon runs). |
| `.venv/` | Python 3.9 environment for plots and the site builder (seaborn, matplotlib, markdown-it). |

The Argon run plan, task list and launch record are in `../argon_proposal/`.
