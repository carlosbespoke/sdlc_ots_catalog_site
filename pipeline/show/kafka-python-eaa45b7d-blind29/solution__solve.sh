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
      "file": "kafka/admin/_groups.py",
      "function": "_async_delete_groups"
    },
    {
      "file": "kafka/net/compat.py",
      "function": "least_loaded_node"
    },
    {
      "file": "kafka/producer/transaction_manager.py",
      "function": "is_valid"
    },
    {
      "file": "kafka/metrics/stats/avg.py",
      "function": "combine"
    },
    {
      "file": "kafka/net/sasl/msk.py",
      "function": "receive"
    },
    {
      "file": "kafka/partitioner/sticky.py",
      "function": "_pick_sticky_locked"
    },
    {
      "file": "kafka/net/backend/asyncio_backend.py",
      "function": "call_at"
    },
    {
      "file": "kafka/util.py",
      "function": "timeout_secs"
    },
    {
      "file": "kafka/protocol/admin/topics.py",
      "function": "encode"
    },
    {
      "file": "kafka/metrics/metrics.py",
      "function": "add_metric"
    },
    {
      "file": "kafka/record/memory_records.py",
      "function": "__init__"
    },
    {
      "file": "kafka/consumer/subscription_state.py",
      "function": "update_preferred_read_replica"
    },
    {
      "file": "kafka/coordinator/assignors/cooperative_sticky.py",
      "function": "assign"
    },
    {
      "file": "kafka/coordinator/assignors/sticky/partition_movements.py",
      "function": "_has_cycles"
    },
    {
      "file": "kafka/admin/_partitions.py",
      "function": "_async_delete_records"
    },
    {
      "file": "kafka/net/compat.py",
      "function": "in_flight_request_count"
    },
    {
      "file": "kafka/producer/kafka.py",
      "function": "__init__"
    },
    {
      "file": "kafka/metrics/stats/histogram.py",
      "function": "from_bin"
    },
    {
      "file": "kafka/partitioner/sticky.py",
      "function": "partition"
    },
    {
      "file": "kafka/net/backend/asyncio_backend.py",
      "function": "_fail_pending_waiters"
    },
    {
      "file": "kafka/cluster.py",
      "function": "expand_to_canonical_bootstrap_hosts"
    },
    {
      "file": "kafka/metrics/metrics.py",
      "function": "metric_name"
    },
    {
      "file": "kafka/consumer/subscription_state.py",
      "function": "subscribe"
    },
    {
      "file": "kafka/coordinator/assignors/cooperative_sticky.py",
      "function": "parse_member_metadata"
    },
    {
      "file": "kafka/admin/_cluster.py",
      "function": "_async_describe_features"
    },
    {
      "file": "kafka/net/connection.py",
      "function": "close"
    },
    {
      "file": "kafka/producer/kafka.py",
      "function": "send"
    },
    {
      "file": "kafka/net/backend/transport.py",
      "function": "write"
    },
    {
      "file": "kafka/admin/_groups.py",
      "function": "_remove_group_members_batch_request"
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
