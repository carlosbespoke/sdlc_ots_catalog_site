# System design

## Executive summary

<div class="kpis"><div class="kpi"><div class="kpi-value">85</div><div class="kpi-label">Tasks</div></div><div class="kpi"><div class="kpi-value">85</div><div class="kpi-label">Tasks with graded runs</div></div><div class="kpi"><div class="kpi-value">36%</div><div class="kpi-label">z-ai/glm-5.3-flash pass rate</div></div></div>

Each task changes a production service that must keep running. The agent makes a multi-process service hold its guarantees through crashes, retries, races and returning stale writers, and delivers the change as a patch. The main languages are Python (34%), TypeScript (27%) and Go (22%).

Every task has graded runs. The model with the most runs here, z-ai/glm-5.3-flash, passes 36% of its 393 graded runs and fails every run on 12% of the 75 tasks it ran.

## Why this catalog

### Problems engineers face

Production systems fail in specific ways when they change while running. In services where several processes share state and any of them can stop, the failures are duplicate effects after retries, lost notifications, stale writers returning after a takeover, limits that hold in one process but not across instances, and partial state after a crash.

### How the tasks reproduce them

Each task pins an open-source repository at a base commit, with a short specification that often sets time limits. The agent runs the needed databases, caches or brokers locally and delivers a patch. After the session, hidden tests kill or pause processes, cut connections and confirm that existing behaviour still works.

### Typical prompts

- A capability gap stated as "X cannot do Y", followed by measurable requirements, many with time limits.
- A closing paragraph with the repository path, how to start each service and the build command.

## Domain breakdown

The tasks span ten domains. The largest, Applications & business domains, makes up 44% of the catalog.

![Share of tasks by domain](assets/system-design_domain.svg)

## Language and seniority

![Primary language and seniority](assets/system-design_metadata.svg)

### Primary language

| Primary language | % of catalog |
|---|---:|
| Python | 34.1% |
| TypeScript | 27.1% |
| Go | 22.4% |
| C# | 16.5% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Staff+ | 100.0% |

## Model pass rates across the catalog

A model's pass rate is its passed runs over its graded runs, pooled across the tasks it ran; runs that errored are left out. Models are listed by number of runs, and a model needs graded runs on five or more tasks for a row.

| Model | Tasks run | Graded runs | Pass rate | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|---:|---:|
| z-ai/glm-5.3-flash | 75 | 393 | 36% | 12% | 71% | 3% |
| google/gemini-4-argon | 20 | 99 | 47% | 25% | 55% | 20% |
| google/gemini-3.8-flash | 12 | 80 | 1% | 92% | 0% | 0% |

![Per-task pass rate by model](assets/system-design_per_task.svg)

## Turn counts and long-horizon tasks

A task's turn count is the average over its completed runs, from every model. A task is long horizon when that average is 200 or more turns. 85 of the 85 tasks have a completed run.

| Measure | Value |
|---|---:|
| Average turn count | 480.0 |
| Median turn count | 461.1 |
| Range | 107 to 948 |
| Long-horizon tasks (200+ turns) | 93% of tasks |

![Turns per task](assets/system-design_turns.svg)

| Model | % of tasks | Mean turns | % of runs with 200+ turns |
|---|---:|---:|---:|
| z-ai/glm-5.3-flash | 88% | 534.9 | 93% |
| google/gemini-4-argon | 24% | 349.9 | 89% |
| google/gemini-3.8-flash | 14% | 276.7 | 56% |

## Sample tasks

### Example 1: Payments & banking (TypeScript)

| Field | Value |
|---|---|
| Task id | [`actual-sync-compaction`](https://drive.google.com/file/d/1_sEAFRDztsqj6IIzgfOQ4KVr7m7Ff0-0/view) |
| Final category | System design |
| Domain | Applications & business domains |
| Sub-domain | Payments & banking |
| Language | TypeScript |
| Seniority | Staff+ |
| Turn count | 670 (z-ai/glm-5.3-flash), 414 (google/gemini-4-argon) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

##### Checkpoint the budget sync log

We need the sync server to compact a budget's history from a client-built snapshot while keeping its sync group stable, so long-lived budgets stay small without offline devices losing edits; the server cannot inspect encrypted changes. Today it retains every change indefinitely, and resetting sync shrinks a budget only by replacing its group, which makes offline devices lose edits they have not uploaded.

###### What we need

- Configure the message-count threshold with `ACTUAL_SYNC_CHECKPOINT_THRESHOLD` (use 300 for this workload); below it no checkpoint is taken. After repeated transaction edits exceed it, two `sync()` calls leave no more than 300 server messages. A fresh download has the same transactions, payees, categories and budget amounts, and its local CRDT log contains at most one message per distinct cell.
- Extend `SyncRequest` with `checkpointId` (protobuf field 7) and `SyncResponse` with `checkpointWanted`, `checkpointRequired` and `checkpointBase` (fields 3, 4 and 6); retain the existing protobuf fields. File info exposes `messageCount`, `checkpointId` and `checkpointBase`; its `checkpointBase` is the current receive base as a decimal string, the value a client sends in `X-ACTUAL-CHECKPOINT-BASE` to checkpoint everything received so far. The receive base tracks received changes, including late arrivals with older timestamps. A client builds a compact snapshot after syncing and commits it with `POST /sync/commit-checkpoint`, sending `X-ACTUAL-FILE-ID`, `X-ACTUAL-GROUP-ID`, `X-ACTUAL-CHECKPOINT-BASE`, `X-ACTUAL-CHECKPOINT-ID`, `X-ACTUAL-CHECKPOINT-MERKLE` and an `application/encrypted-file` body. A successful commit replaces the downloadable file with the snapshot and updates the checkpoint ID; the commit succeeds only when its receive base and prior checkpoint still match, otherwise it returns 409. A malformed receive base returns 400. A successful commit removes every change the checkpoint covers, and only those.
- A disconnected device's unsent edits survive rejoining after a checkpoint, and its data converges with active and newly downloaded devices after two syncs. Repeated syncs after late, older-timestamp arrivals do not error, reset the group or discard changes. Concurrent checkpoint proposals install only one snapshot without surfacing a sync error.
- A truncated or interrupted checkpoint body leaves both the message log and downloadable file unchanged; a later valid checkpoint can succeed. Old-format requests needing pruned history receive HTTP 400 with `file-has-reset`, not partial data; old-format requests already past the checkpoint continue normal sync. New clients needing the checkpoint receive `checkpointRequired` without losing unsent work.

###### Keep working

Existing `/sync/sync`, `/sync/upload-user-file`, `/sync/download-user-file`, `/sync/get-user-file-info` and password login remain usable.

###### Setup

Work in `/app` (Node 22, Yarn 4); build the affected packages with `yarn workspace @actual-app/crdt build && yarn workspace @actual-app/core build && yarn workspace @actual-app/sync-server build && yarn workspace @actual-app/api build`. Grading runs the packages as you leave them built in `/app`, without rebuilding, so rebuild after your last change. The sync server runs via `node packages/sync-server/build/app.js`, with SQLite files in `ACTUAL_DATA_DIR` and `ACTUAL_USER_FILES`. No Docker daemon or internet access is available inside the container.

</div>
</details>

#### Pass rates

| Model | Graded runs | Pass rate |
|---|---:|---:|
| z-ai/glm-5.3-flash | 6 | 17% |
| google/gemini-4-argon | 5 | 20% |

#### Environment

![How the task works](assets/env-actual-sync-compaction.svg)

### Example 2: Secrets & access control (Go)

| Field | Value |
|---|---|
| Task id | [`harbor-scanner-credentials`](https://drive.google.com/file/d/1aHmGorPxaObXqhuZbCDJxOM00L7U6V0m/view) |
| Final category | System design |
| Domain | Security |
| Sub-domain | Secrets & access control |
| Language | Go |
| Seniority | Staff+ |
| Turn count | 365 (google/gemini-4-argon), 624 (z-ai/glm-5.3-flash) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

Harbor's vulnerability scans currently create nonexpiring, project-wide scanner robots and submit their secrets in jobservice parameters, which remain in Redis job stats. Replace that lifecycle for `IMAGE_SCAN` jobs started by the artifact scan API and scan-on-push.

- A scanner's credential, used directly (Basic) or exchanged at `/service/token` for a bearer token, gives only pull access to the scanned artifact's repository: no push anywhere, and no pull or push on any other repository in the same or another project. Scans started concurrently through two core instances each get a credential limited to their own repository.
- A credential keeps working while a scan runs for three minutes, and successful scans still publish their vulnerability reports to the artifact. Existing scanner adapters using Basic or Bearer registry authorization continue to work.
- After the task becomes final, Basic authentication using its credential is rejected with 401 or 403 by `/v2/` and `/service/token` within 30 seconds. If jobservice is killed mid-scan without a final hook, within two minutes the credential is rejected with 401 or 403 by `/v2/` and any robot account created for it is deleted. A scan requested through the artifact scan API while jobservice is down leaves no robot account behind.
- Neither Redis keys and values nor `GET /api/v1/jobs/{id}` expose a scanner credential secret during or after a scan. Job parameters and the core and jobservice logs must not carry it either.
- Preserve the existing artifact scan response and jobservice status API.

Work in `/app` (`src/` is the Go module). PostgreSQL and Redis are installed; start them with `sudo service postgresql start` and `sudo service redis-server start`. Build offline from `/app/src` with `GOPROXY=off go build ./core ./jobservice`; generated Swagger server packages are present. Docker is unavailable inside the agent container. SBOM, scan-all, scanner registration and proxy-cache scanning are outside this change.

</div>
</details>

#### Pass rates

| Model | Graded runs | Pass rate |
|---|---:|---:|
| google/gemini-4-argon | 5 | 20% |
| z-ai/glm-5.3-flash | 4 | 0% |

#### Environment

![How the task works](assets/env-harbor-scanner-credentials.svg)

### Example 3: Software supply chain (C#)

| Field | Value |
|---|---|
| Task id | [`bagetter-fenced-writes`](https://drive.google.com/file/d/1yHr7nw0bfAZG5xO4uxrn_gH3GXffUFla/view) |
| Final category | System design |
| Domain | Build, release & supply chain |
| Sub-domain | Software supply chain |
| Language | C# |
| Seniority | Staff+ |
| Turn count | 509 (z-ai/glm-5.3-flash), 203 (google/gemini-4-argon) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

Two BaGetter instances sharing PostgreSQL and an S3 bucket can accept conflicting package-version writes: the database describes one upload while the bucket serves another. An interrupted push leaves unowned objects, and a failed prerelease overwrite can remove the previous package.

To close this out:
- Coordinate version writes across instances so one of two different simultaneous pushes receives 201, while the loser does not; downloads, nuspecs, registration metadata and the flat-container index agree with the winner. A delayed S3 PUT from a writer whose database claim has expired must never replace the winner's served bytes or delete its objects. `Storage:WriteClaimTimeoutSeconds` defines the maximum database-disconnection window (3 seconds in the deployment).
- An interrupted push remains invisible; a failed overwrite keeps the old prerelease bytes and metadata available until a successful replacement commits. Hard deletion must return 204 only when the version ends absent with no objects under `packages/{id}/{version}/`, or 404 when it remains downloadable. Concurrent cold mirror requests for the same upstream version both download successfully without duplicate indexed versions or objects.
- Add API-key-protected `POST /api/v2/admin/reconcile`, returning JSON that identifies removed orphan objects and hidden versions missing a nupkg. It reclaims expired writes, removes unowned objects even if no claim or row exists, and removes broken versions from flat-container, registration and database search listings without affecting healthy versions. Recovery of expired uploads permits a fresh push. A deleted version leaves no version-prefix objects.

Keep existing packages from the old bucket layout (`{id}.{version}.nupkg` and `{id}.nuspec` under the same version prefix) readable, deletable and overwritable without reupload. Existing push, v3 download, registration, relist and hard-delete routes remain available. An existing PostgreSQL schema must upgrade in place, treating its rows as committed. A duplicate push of a non-overwritable version returns 409; push and delete routes, including relist, retain API-key protection (401 without a valid key). For a package containing only a nuspec, a committed version has exactly one owned nupkg and one owned nuspec object under its version prefix, including after a successful overwrite or reconciliation; abandoned attempts must not leave extra objects there.

The source is at `/app`. Build and run with `dotnet build src/BaGetter/BaGetter.csproj -p:NuGetAudit=false` from `/app`. PostgreSQL is `postgres:5432`, S3 is `s3:4566` (S3-compatible LocalStack with path-style requests); both are provided as sidecars and the container has no Docker daemon. The deployment uses `Database__Type=PostgreSql`, `Storage__Type=AwsS3`, `Search__Type=Database`, `AllowPackageOverwrites=PrereleaseOnly`, and `PackageDeletionBehavior=HardDelete`; cold-mirror requests use `Mirror__Enabled=true` with a configured `Mirror__PackageSource`. Application settings use `Database__ConnectionString`, `Storage__Endpoint`, `Storage__Bucket`, `Storage__AccessKey`, `Storage__SecretKey`, `Storage__ForcePathStyle`, and `ApiKey`. The deployment database is `sd` with app-role credentials `app`/`app`; the S3 bucket is `packages` with credentials `test`/`test`, path-style access enabled, and the API key is `secret` (sent as `X-NuGet-ApiKey`). The app has no internet access.

</div>
</details>

#### Pass rates

| Model | Graded runs | Pass rate |
|---|---:|---:|
| z-ai/glm-5.3-flash | 6 | 50% |
| google/gemini-4-argon | 5 | 20% |

#### Environment

![How the task works](assets/env-bagetter-fenced-writes.svg)

### Example 4: Web applications (TypeScript)

| Field | Value |
|---|---|
| Task id | [`dittofeed-user-deletion`](https://drive.google.com/file/d/1cxE8Is6I9_6PCr0kAZZnMWp-ao9Z--xN/view) |
| Final category | System design |
| Domain | Applications & business domains |
| Sub-domain | Web applications |
| Language | TypeScript |
| Seniority | Staff+ |
| Turn count | 430 (google/gemini-4-argon), 608 (z-ai/glm-5.3-flash) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

Deleting a user currently starts asynchronous ClickHouse deletes and removes Postgres assignments, but activity already in flight can put that user back into a segment. A delayed journey can still send a message after erasure. The user ID must remain reusable for genuinely new activity.

To close this out:
- `DELETE /api/users` and `DELETE /api/users/v2` erase users within their workspace and return only after recording a durable deletion watermark. Previously stored user events are removed. A deleted user disappears from `POST /api/users` (the existing listing route), its segment memberships and user properties within 10 seconds after the delete returns, and stays absent at least 60 seconds after deletion across two computation cycles, including when a computation read their old state before the deletion and publishes afterward.
- `/identify`, `/track` and `/batch` accept events as before, but events whose timestamps are at or before that user's deletion watermark cannot revive the old user, even when they arrive after the delete. Events timestamped later create a fresh incarnation with only the new properties. This also applies to in-flight assignments and segment-entry triggers.
- A journey already waiting at a delay must still reach and record its message step, but must not send the webhook message to an erased user, including a send already scheduled when deletion occurs. Other users' journey deliveries continue.
- Deleting an unknown ID succeeds without affecting other users. An identical ID in another workspace is unaffected. Existing identify/track/batch responses and ordinary journey deliveries remain intact.

The repository is at `/app`. The API and worker use PostgreSQL (`DATABASE_URL`), ClickHouse (`CLICKHOUSE_HOST`, `CLICKHOUSE_USER`, `CLICKHOUSE_PASSWORD`), and Temporal (`TEMPORAL_ADDRESS`); services are supplied by the environment. Implement the change in the existing TypeScript services and include any schema migration needed for persistence. Build from `/app` with `yarn workspace backend-lib build && yarn workspace api build && yarn workspace worker build`.

</div>
</details>

#### Pass rates

| Model | Graded runs | Pass rate |
|---|---:|---:|
| google/gemini-4-argon | 4 | 75% |
| z-ai/glm-5.3-flash | 4 | 0% |

#### Environment

![How the task works](assets/env-dittofeed-user-deletion.svg)

### Example 5: Media processing (TypeScript)

| Field | Value |
|---|---|
| Task id | [`immich-storage-quotas`](https://drive.google.com/file/d/1iooMPQxDSF99aj7XHO7rn2HfRhoZEiYJ/view) |
| Final category | System design |
| Domain | Applications & business domains |
| Sub-domain | Media processing |
| Language | TypeScript |
| Seniority | Staff+ |
| Turn count | 252 (google/gemini-4-argon), 383 (z-ai/glm-5.3-flash) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

Concurrent asset uploads can each pass the quota check using the same old usage value, after their files have already been written. A terminated API leaves an unfinished original on disk. The quota needs to remain a hard limit even while requests are still streaming.

To close this out:
- Make the per-user quota a hard limit across separate API processes, including uploads through shared links. Count bytes while multipart `POST /api/assets` bodies are arriving, including bodies without a declared file size. Refuse an upload that would exceed committed usage plus in-flight bytes with a quota error (HTTP 400 or 413), leaving no asset or rejected file. An active slow stream retains its space.
- Return space and remove unfinished originals on client abort within 5 seconds, and after an API process dies within 45 seconds, without requiring another request. Completing an upload charges its original once. `GET /api/users/me` reports committed usage, not in-flight bytes.
- Permanent deletion, whether requested repeatedly by emptying trash or through duplicate `AssetDelete` jobs on the `backgroundTask` queue, releases the original's usage exactly once; trash and restore leave it charged. Uploads whose checksum matches an existing asset return the existing id without charging twice. Users with no quota remain unrestricted.
- Admin quota updates and `UserSyncUsage` jobs cannot erase in-flight space; finishing concurrent uploads charges their accepted bytes exactly.

Work in `/app` (Immich at the pinned revision). PostgreSQL with VectorChord, Valkey/Redis and the shared `/data` upload directory are available through `DB_HOSTNAME=postgres`, `DB_USERNAME=postgres`, `DB_PASSWORD=postgres`, `DB_DATABASE_NAME=immich`, and `REDIS_HOSTNAME=redis`. Build with `pnpm --filter immich build` from `/app`. `api` and `microservices` run as separate workers via `IMMICH_WORKERS_INCLUDE`; Docker is unavailable inside the agent container.

</div>
</details>

#### Pass rates

| Model | Graded runs | Pass rate |
|---|---:|---:|
| google/gemini-4-argon | 5 | 80% |
| z-ai/glm-5.3-flash | 4 | 25% |

#### Environment

![How the task works](assets/env-immich-storage-quotas.svg)

### Example 6: Payments & banking (TypeScript)

| Field | Value |
|---|---|
| Task id | [`medusa-cart-completion`](https://drive.google.com/file/d/1U6jZxHDbr-NnxBgwRvkZQplrsuJlpWCD/view) |
| Final category | System design |
| Domain | Applications & business domains |
| Sub-domain | Payments & banking |
| Language | TypeScript |
| Seniority | Staff+ |
| Turn count | 412 (google/gemini-4-argon), 783 (z-ai/glm-5.3-flash) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

##### Crash-safe cart completion

Customers must not receive two orders for the same cart when a store API process dies during checkout. Fix `POST /store/carts/:id/complete` in `/app` so completing a cart across separate server processes creates at most one order, one payment authorization and one reservation per inventory-managed line item. Repeating completion on another instance after success returns HTTP 200 with the same `{type: "order", order}` and order ID. Ten simultaneous requests split across two servers must all return that order or HTTP 409 while completion is genuinely in progress; once settled, a retry returns the order. Keep the existing error response for an unknown payment provider without creating an order.

If a server is SIGKILLed after order creation but before the cart is linked, another running process (the other server or one of the two workers) must finish or compensate its abandoned execution without any client request: within 45 seconds the cart has exactly one linked order and its effects, or it remains uncompleted with no order or reservations. A subsequent retry must complete once. A retry on another server must not be blocked for more than 15 seconds by the dead holder's lock. Live completions must not lose their lock to another execution. Preserve the store response, the admin reservations list, and the admin workflow-executions list.

Work in `/app`; the checked-out Medusa workspace is TypeScript. PostgreSQL and Redis are local (`DATABASE_URL=postgres://postgres:postgres@localhost:5432/sdmedusa`, `REDIS_URL=redis://localhost:6379`). The canonical application command is `node /app/packages/cli/medusa-cli/cli.js start --port 9121` from `/app/sd-project`, with `MEDUSA_WORKER_MODE=server` or `worker`. Start local services with `sudo service postgresql start` and `sudo service redis-server start` as needed.

</div>
</details>

#### Pass rates

| Model | Graded runs | Pass rate |
|---|---:|---:|
| google/gemini-4-argon | 5 | 80% |
| z-ai/glm-5.3-flash | 4 | 50% |

#### Environment

![How the task works](assets/env-medusa-cart-completion.svg)
