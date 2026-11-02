# Checkpoint the budget sync log

We need the sync server to compact a budget's history from a client-built snapshot while keeping its sync group stable, so long-lived budgets stay small without offline devices losing edits; the server cannot inspect encrypted changes. Today it retains every change indefinitely, and resetting sync shrinks a budget only by replacing its group, which makes offline devices lose edits they have not uploaded.

## What we need

- Configure the message-count threshold with `ACTUAL_SYNC_CHECKPOINT_THRESHOLD` (use 300 for this workload); below it no checkpoint is taken. After repeated transaction edits exceed it, two `sync()` calls leave no more than 300 server messages. A fresh download has the same transactions, payees, categories and budget amounts, and its local CRDT log contains at most one message per distinct cell.
- Extend `SyncRequest` with `checkpointId` (protobuf field 7) and `SyncResponse` with `checkpointWanted`, `checkpointRequired` and `checkpointBase` (fields 3, 4 and 6); retain the existing protobuf fields. File info exposes `messageCount`, `checkpointId` and `checkpointBase`; its `checkpointBase` is the current receive base as a decimal string, the value a client sends in `X-ACTUAL-CHECKPOINT-BASE` to checkpoint everything received so far. The receive base tracks received changes, including late arrivals with older timestamps. A client builds a compact snapshot after syncing and commits it with `POST /sync/commit-checkpoint`, sending `X-ACTUAL-FILE-ID`, `X-ACTUAL-GROUP-ID`, `X-ACTUAL-CHECKPOINT-BASE`, `X-ACTUAL-CHECKPOINT-ID`, `X-ACTUAL-CHECKPOINT-MERKLE` and an `application/encrypted-file` body. A successful commit replaces the downloadable file with the snapshot and updates the checkpoint ID; the commit succeeds only when its receive base and prior checkpoint still match, otherwise it returns 409. A malformed receive base returns 400. A successful commit removes every change the checkpoint covers, and only those.
- A disconnected device's unsent edits survive rejoining after a checkpoint, and its data converges with active and newly downloaded devices after two syncs. Repeated syncs after late, older-timestamp arrivals do not error, reset the group or discard changes. Concurrent checkpoint proposals install only one snapshot without surfacing a sync error.
- A truncated or interrupted checkpoint body leaves both the message log and downloadable file unchanged; a later valid checkpoint can succeed. Old-format requests needing pruned history receive HTTP 400 with `file-has-reset`, not partial data; old-format requests already past the checkpoint continue normal sync. New clients needing the checkpoint receive `checkpointRequired` without losing unsent work.

## Keep working

Existing `/sync/sync`, `/sync/upload-user-file`, `/sync/download-user-file`, `/sync/get-user-file-info` and password login remain usable.

## Setup

Work in `/app` (Node 22, Yarn 4); build the affected packages with `yarn workspace @actual-app/crdt build && yarn workspace @actual-app/core build && yarn workspace @actual-app/sync-server build && yarn workspace @actual-app/api build`. Grading runs the packages as you leave them built in `/app`, without rebuilding, so rebuild after your last change. The sync server runs via `node packages/sync-server/build/app.js`, with SQLite files in `ACTUAL_DATA_DIR` and `ACTUAL_USER_FILES`. No Docker daemon or internet access is available inside the container.
