#!/usr/bin/env bash
# Reference solution. Undoes each edit and writes the expected report.
# Proves the task is solvable. Never present in the agent image.
set -euo pipefail
cd /workspace/repo
git apply --whitespace=nowarn /solution/solution.patch
mkdir -p /app
cat > /app/rca.json <<'RCA'
{
  "causes": [
    {
      "file": "job.go",
      "function": "weeklyJob.next"
    },
    {
      "file": "logger.go",
      "function": "logger.Error"
    },
    {
      "file": "util.go",
      "function": "convertAtTimesToDateTime"
    },
    {
      "file": "scheduler.go",
      "function": "scheduler.selectExecJobsOutForRescheduling"
    },
    {
      "file": "logger.go",
      "function": "logger.Debug"
    },
    {
      "file": "util.go",
      "function": "scheduledTimeForRun"
    },
    {
      "file": "job.go",
      "function": "dailyJob.nextDay"
    },
    {
      "file": "executor.go",
      "function": "executor.start"
    },
    {
      "file": "scheduler.go",
      "function": "scheduler.stopScheduler"
    },
    {
      "file": "logger.go",
      "function": "logger.Info"
    },
    {
      "file": "util.go",
      "function": "requestJobCtx"
    },
    {
      "file": "scheduler.go",
      "function": "NewScheduler"
    },
    {
      "file": "logger.go",
      "function": "logFormatArgs"
    },
    {
      "file": "job.go",
      "function": "weeklyJob.nextWeekDayAtTime"
    },
    {
      "file": "executor.go",
      "function": "executor.runJob"
    },
    {
      "file": "scheduler.go",
      "function": "scheduler.RemoveJob"
    }
  ]
}
RCA
mkdir -p "$(dirname /app/RESEARCH_AND_PLANNING.md)"
cat > /app/RESEARCH_AND_PLANNING.md <<'PLAN'
# Research and plan

## What I investigated
I read the reported misbehaviours and traced each one to the function whose output
changed, comparing the broken areas against neighbouring code that still works to localise
the edits rather than guessing from names.

## Constraints that shape the change
Each defect is a single-line edit inside one function. The fix must restore the original
behaviour at that site without touching unrelated code, and must be reachable from the same
call paths the reports describe.

## How I will carry it out
Restore each identified site to the behaviour the reports expect, record every edited
function in /app/rca.json, then verify by re-exercising the affected behaviours and
confirming the previously-wrong outputs are correct again while the working neighbours stay
working.
PLAN
