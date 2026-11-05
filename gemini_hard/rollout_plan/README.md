# Argon rollout plan (5 Nov)

Gemini 4 Argon runs on 331 tasks that have none, run adaptively in waves from our side. Horizon's own adaptive mode is switched
off globally (admin setting, test allowlist only) and needs a binary-graded project; `alpharecon` grades partially.

## Tasks (`plan.csv`, built by `bin/rollout5_plan.py`)

| Set | Why | ProgramBench | System design | Feature impl. | Debugging | Total |
|---|---|---|---|---|---|---|
| refill | Green tasks not in the report; added if Argon stays at or below 60% | 41 | 116 | | | 157 |
| confirm | in the report, every GLM-5.3 Flash / Grok 4.7 run failed and no model ever passed | 134 | 12 | 18 | 10 | 174 |

Refill evidence: GLM-5.3 Flash 10-30% or 30-50%, only Grok 4.7 runs that almost always fail (0 or 1 of 8), or no runs at all
(ProgramBench repo upgrade). Every task's active version is the 5 Nov sheet's selected version (checked 5 Nov).

## Adaptive rule (`bin/rollout5_wave.py`)

Each wave submits 1 Argon run for every task that still needs one: no passed run yet, fewer than 3 graded runs, nothing pending,
fewer than 3 errored attempts. A run that scores 1 (passed) stops the task. Outcomes per task: 1/1, 1/2, 1/3 or 0/3.
Priority order: refill ProgramBench, refill System design (GLM 10-30% first), then the confirm set.

## Settings (`runs.csv`, `bin/rollout5_settings.py`, from each task's `task.toml` in `toml/` -> `task_infra.json`)

Same rules as the 4 Nov rollout (`../ots_all/rollout_plan/README.md`): Terminus V2 (`typhoon`), 1,200 turns, 32,000 output tokens,
effort tier 3 (`high` for Argon), Cloud Batch with the smallest VM covering the agent container plus a separate verifier
(272 tasks on 8 CPU / 16 GB). Timeouts and network are the task's own.

## Cost

Argon cost on the 4 Nov rollout: about $8.30 a run on ProgramBench, $5.50 elsewhere. Expected about 830 runs and $6,000 in model
cost, ceiling 993 runs and about $7,000; VMs extra (under about $500 at real run lengths).

## Order of work

1. Pilot: 1 run on 2 refill tasks (one ProgramBench, one System design). Check settings are accepted, runs grade, and cost per run.
2. Wave 1: every task. 3. Waves 2 and 3: tasks with no pass. 4. Re-pull the 5 Nov runs (`ro5/`), rerun `bin/select5.py` and rebuild.

Logs: `waves.json` (every submission), `results.json` (every evaluation's runs, from `--collect`).
