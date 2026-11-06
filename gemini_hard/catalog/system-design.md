# System design & IaC

## Executive summary

<div class="kpis"><div class="kpi"><div class="kpi-value">50</div><div class="kpi-label">Tasks</div></div><div class="kpi"><div class="kpi-value">28%</div><div class="kpi-label">Gemini 4 Argon pass rate</div></div><div class="kpi"><div class="kpi-value">16%</div><div class="kpi-label">Gemini 3.8 Flash pass rate</div></div></div>

Each task changes a production system that must keep running. In the system design tasks the agent makes a multi-process service hold its guarantees through crashes, retries, races and returning stale writers. In the infrastructure tasks the agent restructures live Terraform or Pulumi code so that the plan against production state changes nothing that is deployed. The main languages are HCL (Terraform) (28%), Go (26%) and TypeScript (20%).

Gemini 4 Argon passes 28% of its runs and fails every run on 40% of them. Gemini 3.8 Flash passes 16% of its runs and fails every run on 65% of them.

## Why this catalog

### Problems engineers face

Production systems fail in specific ways when they change while running. In services where several processes share state and any of them can stop, the failures are duplicate effects after retries, lost notifications, stale writers returning after a takeover, limits that hold in one process but not across instances, and partial state after a crash. In infrastructure code, a flat Terraform stack has to become modules with stable keys, or move to Pulumi, while every deployed resource stays exactly as it is.

### How the tasks reproduce them

Both kinds of task give the agent a working copy of the system and grade the result with hidden checks after the session. Service tasks pin an open-source repository at a base commit, with a short specification that often sets time limits. The agent runs the needed databases, caches or brokers locally and delivers a patch. Hidden tests then kill or pause processes and confirm existing behaviour still works. Infrastructure tasks ship the stack with its recorded production state. A verifier plans the result with refresh disabled, expects moves only, then plans hidden changes such as an added key.

### Typical prompts

- A capability gap stated as "X cannot do Y", followed by measurable requirements, many with time limits.
- A closing paragraph with the repository path, how to start each service and the build command.
- A first-person request to modularize a named production Terraform stack, followed by rules for modules, `for_each` keys, variables, outputs and banned constructs.

## Domain breakdown

The tasks span nine domains. The largest, State-preserving infrastructure changes, makes up 30% of the catalog.

<div class="cx" data-chart="bars" data-dims="g>c=Domain" data-hint="Click a domain to filter the charts on this page; use the arrow to see its sub-domains.">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Share of tasks by domain</h4></div>
<div class="fig-box" data-body></div>
</div>

## Language and seniority

<div class="cx" data-chart="bars" data-dims="l:8=Primary language,s=Seniority">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Primary language and seniority</h4></div>
<div class="fig-box" data-body></div>
</div>

### Primary language

| Primary language | % of catalog |
|---|---:|
| HCL (Terraform) | 28.0% |
| Go | 26.0% |
| TypeScript | 20.0% |
| Python | 14.0% |
| C# | 12.0% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Staff+ | 72.0% |
| Senior | 28.0% |

## Pass rates across the catalog

| Model | Pass rate | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|
| google/gemini-4-argon | 28% | 40% | 60% | 0% |
| google/gemini-3.8-flash | 16% | 65% | 20% | 10% |
| z-ai/glm-5.3-flash | 17% | 53% | 34% | 0% |

Tasks with pass rates between 0% and 20%, or between 80% and 100%, fall outside these three columns.

<div class="cx" data-chart="reward">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Per-task pass rate by model</h4></div>
<div class="fig-box" data-body></div>
</div>

## Turn counts and long-horizon tasks

A task's turn count is the average over its runs by Gemini 4 Argon, Gemini 3.8 Flash and GLM-5.3 Flash. A task is long horizon when that average is 200 or more turns.

| Measure | Value |
|---|---:|
| Average turn count | 344.4 |
| Median turn count | 302.6 |
| Range | 79 to 959 |
| Long-horizon tasks (200+ turns) | 68% of tasks |

<div class="cx" data-chart="turns" data-group="Domain">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Turns per task</h4></div>
<div class="fig-box" data-body></div>
</div>

| Model | % of tasks run | Mean turns per task | % of its tasks at 200+ turns |
|---|---:|---:|---:|
| z-ai/glm-5.3-flash | 76% | 425.5 | 68% |
| google/gemini-3.8-flash | 40% | 236.2 | 55% |
| google/gemini-4-argon | 50% | 289.5 | 72% |

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
| Turn count | 414 (google/gemini-4-argon) |
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

| Model | Pass rate |
|---|---:|
| google/gemini-4-argon | 20% |

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
| Turn count | 365 (google/gemini-4-argon) |
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

| Model | Pass rate |
|---|---:|
| google/gemini-4-argon | 20% |

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
| Turn count | 203 (google/gemini-4-argon) |
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

| Model | Pass rate |
|---|---:|
| google/gemini-4-argon | 20% |

#### Environment

![How the task works](assets/env-bagetter-fenced-writes.svg)

<div data-chart-runtime>
<style>.cx{margin:30px 0 36px;max-width:940px;min-width:0}
.cx .fig-box{position:relative}
.cx-chips{display:flex;flex-wrap:wrap;gap:8px;margin:0 0 12px}
.cx-chip{display:inline-flex;align-items:center;gap:8px;padding:6px 12px;border:1px solid var(--ink);background:var(--card);cursor:pointer;font:500 13px/1.3 var(--sans);color:var(--ink)}
.cx-chip[aria-pressed=false]{border-color:var(--line);color:var(--faint);background:transparent}
.cx-dot{width:10px;height:10px;background:var(--ink)}.cx-chip[aria-pressed=false] .cx-dot{background:var(--line)}
.cx-n{font:11px var(--mono);color:var(--muted)}
.cx-strip{display:flex;flex-wrap:wrap;align-items:center;gap:8px;margin:0 0 12px;padding:8px 10px;background:var(--soft);font-size:13px}
.cx-strip-lab{font:600 11px var(--mono);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.cx-filter{border:1px solid var(--red);background:var(--card);color:var(--red-ink);padding:3px 9px;cursor:pointer;font:500 13px var(--sans)}
.cx-clearall{border:0;background:none;color:var(--muted);text-decoration:underline;cursor:pointer;font:13px var(--sans)}
.cx-toolbar{display:flex;flex-wrap:wrap;align-items:center;gap:10px 16px;margin:0 0 12px;font-size:13px}
.cx-seg{display:inline-flex;border:1px solid var(--ink)}.cx-seg button{border:0;background:transparent;padding:5px 11px;cursor:pointer;font:500 13px var(--sans);color:var(--ink)}
.cx-seg button+button{border-left:1px solid var(--ink)}.cx-seg button[aria-pressed=true]{background:var(--ink);color:#fff}
.cx-hint-inline{color:var(--muted)}
.cx-slider{display:inline-flex;align-items:center;gap:8px;color:var(--ink-2)}.cx-slider input{accent-color:var(--red);width:120px}
.cx-check{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--ink-2);margin:0 0 6px;cursor:pointer}.cx-check input{accent-color:var(--red)}
.cx-summary{font-size:15px;margin:0 0 6px;color:var(--ink)}
.cx-svg{display:block;width:100%;height:auto;touch-action:none;user-select:none}
.cx-tick{font:11px var(--sans);fill:var(--muted)}.cx-axis{font:12px var(--sans);fill:var(--muted)}
.cx-rowlab{font:600 13px var(--sans);fill:var(--ink)}.cx-collab{font:600 12px var(--sans);fill:var(--ink-2)}
.cx-cellv{font:600 15px var(--sans)}.cx-cells{font:10.5px var(--sans)}.cx-cell{cursor:pointer}.cx-cell:hover{stroke:var(--ink)}
.cx-mean{font:600 12px var(--sans);fill:var(--ink)}.cx-thr{font:600 12px var(--sans);fill:var(--red-ink)}.cx-band{font:600 11px var(--sans);fill:var(--teal)}
.cx-col{fill:var(--ink);cursor:pointer}.cx-col:hover,.cx-col:focus-visible{fill:var(--teal);outline:none}.cx-col.is-on{fill:var(--red)}
.cx-pt{fill:var(--red);fill-opacity:.38;cursor:pointer}.cx-pt:hover{fill-opacity:1}.cx-pt.is-on{fill-opacity:1;stroke:var(--ink);stroke-width:1.5}
.cx-handle{cursor:ew-resize;outline:none}.cx-handle:focus-visible circle{stroke:var(--ink)}
.cx-hint{font-size:13px;color:var(--muted);margin:6px 0 0}
.cx-cap{font-size:14px;font-weight:600;margin:18px 0 0}.cx-link{border:0;background:none;padding:0 0 0 8px;color:var(--red-ink);text-decoration:underline;cursor:pointer;font:inherit;font-weight:500}
.cx-grid{margin-top:8px;font-size:14px;font-variant-numeric:tabular-nums}.cx-row{display:grid;grid-template-columns:minmax(0,1fr) 130px 120px 130px;gap:10px;padding:7px 0;border-bottom:1px solid var(--line)}
.cx-row>span:not(:first-child){text-align:right;white-space:nowrap}.cx-head{color:var(--muted);font-size:13px;font-weight:600;border-bottom-color:var(--ink)}
.cx-grid5 .cx-row{grid-template-columns:minmax(0,1fr) 70px 110px 95px 95px 105px}
.cx-meter{display:inline-block;width:70px;height:8px;background:var(--line-2);margin-right:8px;vertical-align:middle}.cx-meter span{display:block;height:100%;background:var(--ink)}
.cx-panels{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px 40px}
.cx-panel-title{font:600 13px var(--sans);color:var(--muted);margin:0 0 6px}.cx-panel-foot{font-size:12px;color:var(--muted);margin-top:6px}
.cx-bar{display:grid;grid-template-columns:minmax(120px,42%) 1fr 52px;align-items:center;gap:10px;padding:4px 4px;cursor:pointer;font-size:14px;line-height:1.3}
.cx-bar:hover{background:var(--soft)}.cx-bar:focus-visible{outline:2px solid var(--red)}
.cx-bar-lab{display:flex;align-items:center;gap:4px;color:var(--ink);min-width:0;overflow-wrap:anywhere}
.cx-bar-track{height:16px;background:transparent}.cx-bar-fill{display:block;height:100%;background:var(--ink);min-width:1px}
.cx-bar-val{text-align:right;font:600 13px var(--sans);font-variant-numeric:tabular-nums;color:var(--ink)}
.cx-bar.is-on .cx-bar-fill{background:var(--red)}.cx-bar.is-on .cx-bar-lab{font-weight:600}
.cx-bar.is-child{font-size:13px}.cx-bar.is-child .cx-bar-lab{padding-left:24px;color:var(--ink-2)}.cx-bar.is-child .cx-bar-fill{background:var(--teal)}.cx-bar.is-child.is-on .cx-bar-fill{background:var(--red)}
.cx-expand{border:0;background:none;padding:0 4px 0 0;cursor:pointer;color:var(--muted);font-size:12px;width:16px}
.cx-tip{position:absolute;z-index:5;pointer-events:none;background:var(--ink);color:#fff;font:12.5px/1.45 var(--sans);padding:8px 10px;max-width:300px}
.cx-detail{margin-top:14px;padding:12px 14px;background:var(--card);border:1px solid var(--line-2);border-left:3px solid var(--red);font-size:14px;line-height:1.6}
.cx-mini{display:flex;align-items:flex-end;gap:6px;height:150px;margin:12px 0 4px}.cx-mini-col{flex:1;display:flex;flex-direction:column;justify-content:flex-end;height:100%;text-align:center}
.cx-mini-bar{background:var(--ink);min-height:1px}.cx-mini-n{font:600 11px var(--sans);color:var(--ink);margin-top:3px}.cx-mini-lab{font:10px var(--sans);color:var(--muted)}
@media (max-width:640px){.cx-row{grid-template-columns:minmax(0,1fr) 64px 64px 80px}.cx-grid5 .cx-row{grid-template-columns:minmax(0,1fr) 44px 60px 52px 52px 56px}.cx-meter{display:none}.cx-bar{grid-template-columns:minmax(90px,45%) 1fr 46px}}
</style>
<script type="application/json" data-chart-data>{"cross":true,"models":["google/gemini-4-argon","google/gemini-3.8-flash","z-ai/glm-5.3-flash"],"dims":{"g":["Applications & business domains","Build, release & supply chain","Cloud infrastructure & IaC","Data engineering & databases","Distributed systems & coordination","Languages & developer tooling","Scientific & ML software","Security","State-preserving infrastructure changes"],"c":["AI agents & retrieval","API tooling","CI/CD","Cloud infra: AWS platform stacks","Cloud infra: containers & self-hosted platforms","Cloud infra: serverless & event-driven","Cloud security & compliance","Data pipelines & ETL","Graph algorithms","Job scheduling","Media processing","Messaging & event streaming","Payments & banking","Secrets & access control","Software supply chain","Web applications","Workflow automation"],"l":["C#","Go","HCL (Terraform)","Python","TypeScript"],"s":["Senior","Staff+"]},"tasks":[[6,8,1,1,{"1":[0,0,0,0,0,0,0,0,0,0,0]},{"1":[1209,11]}],[0,15,3,1,{"1":[0,0,0,0,0,0]},{"1":[3231,6]}],[8,3,2,0,{"1":[1,1,1,1,1],"0":[1,0],"2":[1,0,1,1,1]},{"1":[507,5],"0":[117,2],"2":[887,5]}],[0,15,1,1,{"0":[0],"1":[0,0,0,0,1,0]},{"0":[559,1],"1":[1956,6]}],[6,0,3,1,{"1":[0,0,0,0,0,0]},{"1":[1549,6]}],[0,12,3,1,{"1":[0,0,0,0,0,0,0,0,0,0,0,0]},{"1":[1848,12]}],[8,4,4,0,{"0":[1,0],"1":[1,0,1]},{"0":[178,2],"1":[629,3]}],[7,13,3,1,{"1":[0,0,0,0,0,0],"2":[0,0,0,0,0,0]},{"2":[1708,6],"1":[1352,6]}],[0,12,4,1,{"0":[1,0,0,0,0],"2":[0,1,0,0,0,1]},{"0":[2128,5],"2":[4253,6]}],[4,9,1,1,{"0":[0,0,0,0,0],"2":[0,0,0,0]},{"0":[3616,5],"2":[4000,4]}],[0,10,1,1,{"0":[0,0,0,0,0],"2":[0,0,0,0]},{"0":[1736,5],"2":[3246,4]}],[8,5,2,0,{"1":[1,0,1],"2":[0,0,1,1,0,0,0,0,1]},{"1":[435,3],"2":[1135,9]}],[4,11,1,1,{"1":[0,0,0,0,0,0]},{"1":[1546,6]}],[8,3,2,0,{"2":[0,0,0,0,0]},{"2":[589,5]}],[0,15,0,1,{"0":[0,0,0,0,1],"2":[0,0,1,0]},{"0":[1718,5],"2":[1668,4]}],[0,12,4,1,{"0":[0,0,0,0,1],"2":[0,0,0,1,0,0]},{"0":[2068,5],"2":[4021,6]}],[8,4,2,0,{"1":[0,0,0,0,0],"0":[0,0],"2":[0,0,1,0,1]},{"1":[421,5],"0":[93,2],"2":[501,5]}],[4,11,0,1,{"2":[0,0,0,0]},{"2":[1181,4]}],[8,3,2,0,{"2":[0,0,0,0,0]},{"2":[670,5]}],[8,3,2,0,{"1":[1,1,1,1,1],"0":[0,0],"2":[0,0,0,0,1,0,0,1,1,0,0,0,0,0,0,0]},{"1":[925,5],"0":[140,2],"2":[2245,16]}],[0,15,0,1,{"0":[0,0,0,0,0],"2":[0,0,0,0]},{"0":[1375,5],"2":[2775,4]}],[1,14,1,1,{"0":[0,0,0,0,0],"2":[0,1,0,0]},{"0":[1176,5],"2":[1860,4]}],[1,2,1,1,{"2":[0,0,0,0]},{"2":[1913,4]}],[2,4,1,1,{"1":[0,0,0,0,0,0],"2":[0,0,0,0,0,0]},{"2":[2803,6],"1":[1260,6]}],[8,4,2,0,{"2":[0,0,0,0,0]},{"2":[394,5]}],[8,4,2,0,{"2":[0,0,0,0,0]},{"2":[489,5]}],[3,7,1,1,{"1":[0,0,0,0,0,0]},{"1":[641,6]}],[8,3,2,0,{"2":[0,0,0,0,0]},{"2":[476,5]}],[0,10,4,1,{"0":[0,1,1,1,1],"2":[0,0,0,1]},{"0":[1258,5],"2":[1532,4]}],[5,1,4,1,{"0":[0,0,0,0,0],"2":[0,0,0,1]},{"0":[1439,5],"2":[1521,4]}],[8,3,2,0,{"1":[0,0,0,0],"0":[0,0],"2":[1,1,1,1,0]},{"1":[329,4],"0":[140,2],"2":[722,5]}],[6,0,1,1,{"1":[0,0,0,0,0,0]},{"1":[1481,6]}],[3,7,3,1,{"0":[0,1,1,0,1],"2":[1,0,0,0,0,0,0]},{"0":[1681,5],"2":[5557,7]}],[8,3,2,0,{"0":[0,1],"2":[0,0,0,0,0]},{"0":[71,2],"2":[497,5]}],[8,6,2,0,{"1":[0,1,1]},{"1":[623,3]}],[8,4,2,0,{"1":[0,0,0],"2":[0,0,0,0]},{"1":[234,3],"2":[332,4]}],[2,4,1,1,{"1":[0,0,0,0,0,0]},{"1":[5588,6]}],[7,13,1,1,{"0":[0,0,0,1,0],"2":[0,0,0,0]},{"0":[1826,5],"2":[2496,4]}],[0,15,4,1,{"0":[0,1,1,1],"2":[0,0,0,0]},{"0":[1721,4],"2":[2432,4]}],[1,14,0,1,{"0":[1,0,0,0,0],"2":[1,0,1,0,1,0]},{"0":[1014,5],"2":[3053,6]}],[0,12,4,1,{"0":[1,1,1,0,1],"2":[1,0,1,0]},{"0":[2060,5],"2":[3133,4]}],[8,13,2,1,{"1":[0,1,0]},{"1":[801,3]}],[4,11,3,1,{"0":[0,1,0,1,0],"2":[0]},{"0":[1020,5],"2":[392,1]}],[4,9,3,1,{"0":[0,1,0,1,0],"2":[0,0,0,1,0,0]},{"0":[918,5],"2":[2749,6]}],[4,11,4,1,{"0":[0,0,0,0,0],"2":[0,1,0,0,1,0]},{"0":[2558,5],"2":[3018,6]}],[4,9,1,1,{"2":[0,0,0,0]},{"2":[3836,4]}],[4,11,4,1,{"0":[1,0,1,1,0],"2":[0,1,0,0]},{"0":[1808,5],"2":[1788,4]}],[4,11,0,1,{"2":[0,0,0,0]},{"2":[2576,4]}],[4,16,0,1,{"2":[0,0,0,0]},{"2":[3171,4]}],[7,13,4,1,{"2":[0,0,0,1,0,0,0,0,0,0,0,0]},{"2":[2479,12]}]],"minTasks":5,"sat":0.8,"bin":50,"xmax":1000,"threshold":200}</script>
<script>// Interactive charts for the Gemini-hard catalog site, ported from ../ots_all/bin/charts.js with pass rate in place of average reward:
// bar counts are of the selected tasks; each run is 1 (passed) or 0, a task's value is its share of passed runs, and a model's rate pools runs across tasks, as in the tables.
// Interactive charts for the catalog site. Each page carries one JSON data block; charts on a page share a store,
// so a click in one chart can filter the others. No element ids are used (the single-file build prefixes them),
// everything is found through data attributes inside the page's own view.
(function () {
  var NS = 'http://www.w3.org/2000/svg';
  var fmt = function (n) { return Math.round(n).toLocaleString('en-US'); };
  var half = function (r) { var f = Math.floor(r), d = r - f; return Math.abs(d - 0.5) < 1e-9 ? (f % 2 ? f + 1 : f) : Math.round(r); };  // round half to even, like the tables
  var pc = function (v) { return v === null || isNaN(v) ? 'n/a' : (v > 0 && v < 0.005 ? '<1%' : half(100 * v) + '%'); };
  var esc = function (s) { return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;'); };
  function el(tag, attrs, parent, text) {
    var e = document.createElementNS(NS, tag);
    for (var k in attrs) e.setAttribute(k, attrs[k]);
    if (text !== undefined) e.textContent = text;
    if (parent) parent.appendChild(e);
    return e;
  }
  function h(tag, cls, parent, html) {
    var e = document.createElement(tag); if (cls) e.className = cls;
    if (html !== undefined) e.innerHTML = html;
    if (parent) parent.appendChild(e);
    return e;
  }
  function clear(e) { while (e.firstChild) e.removeChild(e.firstChild); }
  function pool(pts) { var p = 0, n = 0; pts.forEach(function (x) { x.runs.forEach(function (v) { p += v; n++; }); }); return n ? p / n : NaN; }
  function passes(s) { var p = s.filter(function (v) { return v >= 1; }).length; return p + ' of ' + s.length + ' run' + (s.length > 1 ? 's' : '') + ' passed'; }
  function mean(a) { return a.length ? a.reduce(function (x, y) { return x + y; }, 0) / a.length : NaN; }
  function quant(s, q) { if (!s.length) return NaN; var p = (s.length - 1) * q, lo = Math.floor(p), hi = Math.ceil(p); return s[lo] + (s[hi] - s[lo]) * (p - lo); }
  function svgX(svg, clientX) { var p = svg.createSVGPoint(); p.x = clientX; p.y = 0; return p.matrixTransform(svg.getScreenCTM().inverse()).x; }
  function jitter(i) { var x = Math.sin(i * 12.9898 + 78.233) * 43758.5453; return x - Math.floor(x) - 0.5; }
  function chips(parent, items, onToggle) {  // items: [{label, note, on}]
    var wrap = h('div', 'cx-chips', parent);
    items.forEach(function (it, i) {
      var b = h('button', 'cx-chip', wrap, '<span class="cx-dot"></span>' + esc(it.label) + (it.note ? ' <span class="cx-n">' + esc(it.note) + '</span>' : ''));
      b.type = 'button'; b.setAttribute('aria-pressed', String(it.on));
      b.addEventListener('click', function () { if (onToggle(i)) b.setAttribute('aria-pressed', String(items[i].on)); });
    });
    return wrap;
  }
  function tip(box) {
    var t = h('div', 'cx-tip', box); t.hidden = true;
    return {
      show: function (html, ev) {
        t.innerHTML = html; t.hidden = false;
        var r = box.getBoundingClientRect(), x = ev.clientX - r.left + 14, y = ev.clientY - r.top + 14;
        if (x + t.offsetWidth > r.width) x = Math.max(0, ev.clientX - r.left - t.offsetWidth - 10);
        t.style.left = x + 'px'; t.style.top = y + 'px';
      },
      hide: function () { t.hidden = true; }
    };
  }
  // ---- store: tasks, cross-filters and subscribers, one per page ----
  function makeStore(D) {
    var S = { D: D, tasks: D.tasks, filters: {}, order: [], subs: [] };
    S.visible = function (except) {
      var keys = S.order.filter(function (k) { return S.filters[k] && (except || []).indexOf(k) < 0; }), out = [];
      for (var i = 0; i < S.tasks.length; i++) {
        var ok = true;
        for (var j = 0; j < keys.length && ok; j++) ok = S.filters[keys[j]].test(i);
        if (ok) out.push(i);
      }
      return out;
    };
    S.set = function (key, f) {
      if (f) { S.filters[key] = f; if (S.order.indexOf(key) < 0) S.order.push(key); }
      else { delete S.filters[key]; S.order = S.order.filter(function (k) { return k !== key; }); }
      S.subs.forEach(function (fn) { fn(); });
    };
    S.strip = function (parent) {  // the active filters, shown at the top of every chart on the page
      var s = h('div', 'cx-strip', parent);
      S.subs.push(function () {
        clear(s); var keys = S.order.filter(function (k) { return S.filters[k]; }); s.hidden = !keys.length;
        if (!keys.length) return;
        h('span', 'cx-strip-lab', s, 'Showing');
        keys.forEach(function (k) {
          var b = h('button', 'cx-filter', s, esc(S.filters[k].label) + ' <span aria-hidden="true">&times;</span>'); b.type = 'button';
          b.title = 'Remove this filter'; b.addEventListener('click', function () { S.set(k, null); });
        });
        if (keys.length > 1) { var a = h('button', 'cx-clearall', s, 'Clear all'); a.type = 'button'; a.addEventListener('click', function () { S.order.slice().forEach(function (k) { delete S.filters[k]; }); S.order = []; S.subs.forEach(function (fn) { fn(); }); }); }
      });
      return s;
    };
    return S;
  }
  // ---- bar panels (domain with sub-domains; language; seniority) ----
  function bars(fig, S) {
    var box = fig.querySelector('[data-body]'), specs = fig.dataset.dims.split(','), mode = 'pct', open = {};
    if (S.D.cross) S.strip(box);
    var bar = h('div', 'cx-toolbar', box), seg = h('div', 'cx-seg', bar);
    [['pct', '% of tasks'], ['n', 'Tasks']].forEach(function (m) {
      var b = h('button', '', seg, m[1]); b.type = 'button'; b.setAttribute('aria-pressed', String(mode === m[0]));
      b.addEventListener('click', function () { mode = m[0]; seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); });
    });
    h('span', 'cx-hint-inline', bar, fig.dataset.hint || 'Click a bar to filter the charts on this page.');
    var panels = h('div', 'cx-panels', box);
    var P = specs.map(function (sp) {
      var m = sp.match(/^(\w)(?:>(\w))?(?::(\d+))?(?:=(.*))?$/);
      var p = { key: m[1], child: m[2], top: m[3] ? +m[3] : 0, title: m[4] || '', el: h('div', 'cx-panel', panels) };
      var all = {}; S.tasks.forEach(function (t) { all[t[p.key]] = (all[t[p.key]] || 0) + 1; });
      p.order = Object.keys(all).map(Number).sort(function (a, b) { return all[b] - all[a]; });
      if (p.top && p.order.length > p.top + 1) { p.rest = p.order.slice(p.top); p.order = p.order.slice(0, p.top).concat(['rest']); }
      return p;
    });
    function row(parent, p, label, n, tot, max, active, onClick, cls, toggle) {
      var r = h('div', 'cx-bar' + (active ? ' is-on' : '') + (cls ? ' ' + cls : ''), parent), v = mode === 'pct' ? (tot ? n / tot : 0) : n;
      var lab = h('span', 'cx-bar-lab', r);
      if (toggle) { var t = h('button', 'cx-expand', lab, toggle.open ? '&#9662;' : '&#9656;'); t.type = 'button'; t.title = toggle.open ? 'Hide sub-domains' : 'Show sub-domains'; t.addEventListener('click', function (e) { e.stopPropagation(); toggle.fn(); }); }
      h('span', '', lab, esc(label));
      var tr = h('span', 'cx-bar-track', r); h('span', 'cx-bar-fill', tr).style.width = (max ? 100 * v / max : 0) + '%';
      h('span', 'cx-bar-val', r, mode === 'pct' ? (tot ? (100 * n / tot).toFixed(n && 100 * n / tot < 10 ? 1 : 0) + '%' : 'n/a') : fmt(n));
      r.tabIndex = 0; r.setAttribute('role', 'button'); r.setAttribute('aria-pressed', String(!!active));
      r.addEventListener('click', onClick); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onClick(); } });
      return v;
    }
    function draw() {
      P.forEach(function (p) {
        clear(p.el); if (p.title) h('div', 'cx-panel-title', p.el, esc(p.title));
        var V = S.visible([p.key, p.child].filter(Boolean)), cnt = {}, sub = {};
        V.forEach(function (i) { var t = S.tasks[i]; cnt[t[p.key]] = (cnt[t[p.key]] || 0) + 1; if (p.child) { var k = t[p.key] + ':' + t[p.child]; sub[k] = (sub[k] || 0) + 1; } });
        var val = function (k) { return k === 'rest' ? p.rest.reduce(function (a, r) { return a + (cnt[r] || 0); }, 0) : (cnt[k] || 0); };
        var tot = V.length, max = 0;
        p.order.forEach(function (k) { var n = val(k); max = Math.max(max, mode === 'pct' ? (tot ? n / tot : 0) : n); });
        var names = S.D.dims[p.key], F = S.filters[p.key];
        p.order.forEach(function (k) {
          var label = k === 'rest' ? 'Other (' + p.rest.length + ' languages)' : names[k], active = F && F.v === String(k);
          var click = function () {
            if (active) { S.set(p.key, null); return; }
            if (p.child) S.set(p.child, null);
            S.set(p.key, { v: String(k), label: (p.title || 'Domain') + ': ' + label, test: k === 'rest' ? function (i) { return p.rest.indexOf(S.tasks[i][p.key]) >= 0; } : function (i) { return S.tasks[i][p.key] === k; } });
          };
          row(p.el, p, label, val(k), tot, max, active, click, '', p.child ? { open: !!open[k], fn: function () { open[k] = !open[k]; draw(); } } : null);
          if (p.child && open[k]) {
            var kids = Object.keys(sub).filter(function (s) { return s.split(':')[0] === String(k); }).map(function (s) { return +s.split(':')[1]; })
              .sort(function (a, b) { return sub[k + ':' + b] - sub[k + ':' + a]; });
            kids.forEach(function (c) {
              var CF = S.filters[p.child], on = CF && CF.v === String(c);
              row(p.el, p, S.D.dims[p.child][c], sub[k + ':' + c], tot, max, on, function () {
                if (on) { S.set(p.child, null); return; }
                S.set(p.child, { v: String(c), label: 'Sub-domain: ' + S.D.dims[p.child][c], test: function (i) { return S.tasks[i][p.child] === c; } });
              }, 'is-child');
            });
          }
        });
        h('div', 'cx-panel-foot', p.el, fmt(tot) + ' selected tasks' + (tot < S.tasks.length ? ' after filters' : ''));
      });
    }
    S.subs.push(draw);
  }
  // ---- turns per task histogram ----
  function turns(fig, S) {
    var D = S.D, box = fig.querySelector('[data-body]'), W = 940, H = 330, L = 52, R = 18, T = 34, B = 44, BIN = D.bin, XMAX = D.xmax;
    var models = D.models.map(function (m, i) { var n = 0; S.tasks.forEach(function (t) { if (t.t[i]) n++; }); return { label: m, note: fmt(n) + ' tasks', on: n > 0, n: n }; }).filter(function (m) { return m.n; });
    var sel = function (name) { return models.some(function (m) { return m.on && m.label === name; }); };
    var thr = D.threshold, pick = null, gname = fig.dataset.group || 'Domain';
    if (D.cross) S.strip(box);
    chips(box, models, function (i) { if (models[i].on && models.filter(function (m) { return m.on; }).length === 1) return false; models[i].on = !models[i].on; pick = null; if (S.filters.turns) S.set('turns', null); else draw(); return true; });
    var sum = h('p', 'cx-summary', box), svg = el('svg', { 'class': 'cx-svg', viewBox: '0 0 ' + W + ' ' + H, role: 'img', 'aria-label': 'Histogram of average turns per task' }, box);
    h('p', 'cx-hint', box, 'Toggle models to recompute each task from their runs only. Drag the red line to move the long-horizon threshold. Click a bar to break it down by ' + gname.toLowerCase() + (D.cross ? ' and filter the other charts' : '') + '.');
    var panel = h('div', '', box), t = tip(box);
    var x = function (v) { return L + (W - L - R) * v / XMAX; };
    var gS = el('g', {}, svg), gGrid = el('g', {}, svg), gBars = el('g', {}, svg), gL = el('g', {}, svg);
    var wash = el('rect', { y: T, height: H - T - B, fill: 'var(--red)', 'fill-opacity': 0.07 }, gS);
    for (var v = 0; v <= XMAX; v += 100) el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gS, fmt(v));
    el('line', { x1: L, x2: W - R, y1: H - B, y2: H - B, stroke: 'var(--ink)' }, gS);
    el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gS, 'Average turns per task');
    el('text', { x: 14, y: (T + H - B) / 2, 'text-anchor': 'middle', 'class': 'cx-axis', transform: 'rotate(-90 14 ' + (T + H - B) / 2 + ')' }, gS, 'Tasks');
    var mLine = el('line', { y1: T, y2: H - B, stroke: 'var(--ink)', 'stroke-width': 1.2, 'stroke-dasharray': '4 4' }, gL), mText = el('text', { y: T + 14, 'class': 'cx-mean' }, gL);
    var hg = el('g', { 'class': 'cx-handle', tabindex: 0, role: 'slider', 'aria-label': 'Long-horizon threshold in turns', 'aria-valuemin': 0, 'aria-valuemax': XMAX }, gL);
    var hHit = el('rect', { y: T - 20, height: H - B - T + 20, width: 24, fill: 'transparent' }, hg), hLine = el('line', { y1: T - 6, y2: H - B, stroke: 'var(--red)', 'stroke-width': 2 }, hg);
    var hKnob = el('circle', { cy: T - 6, r: 7, fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 2 }, hg), hText = el('text', { y: T - 18, 'class': 'cx-thr' }, hg);
    function means(V) {
      var out = [];
      V.forEach(function (i) { var tk = S.tasks[i], s = 0, n = 0; for (var m in tk.t) if (sel(D.models[m])) { s += tk.t[m][0]; n += tk.t[m][1]; } if (n) out.push([i, s / n]); });
      return out;
    }
    function draw() {
      var M = means(S.visible(['turns'])), nb = Math.ceil(XMAX / BIN), bins = [];
      for (var i = 0; i < nb; i++) bins.push([]);
      M.forEach(function (m) { bins[Math.min(nb - 1, Math.floor(m[1] / BIN))].push(m[0]); });
      var top = Math.max.apply(null, bins.map(function (b) { return b.length; })) || 1, step = top > 200 ? 50 : top > 80 ? 20 : top > 30 ? 10 : top > 12 ? 5 : top > 5 ? 2 : 1;
      top = Math.ceil(top / step) * step;
      var y = function (n) { return H - B - (H - B - T) * n / top; };
      clear(gGrid); clear(gBars);
      for (var g = 0; g <= top; g += step) { el('line', { x1: L, x2: W - R, y1: y(g), y2: y(g), stroke: 'var(--line-2)' }, gGrid); el('text', { x: L - 8, y: y(g) + 4, 'text-anchor': 'end', 'class': 'cx-tick' }, gGrid, fmt(g)); }
      var F = S.filters.turns; if (D.cross && !F) pick = null;
      bins.forEach(function (b, i) {
        var lo = i * BIN, on = pick === i, r = el('rect', { x: x(lo) + 1, width: x(lo + BIN) - x(lo) - 2, y: y(b.length), height: Math.max(0, H - B - y(b.length)), 'class': 'cx-col' + (on ? ' is-on' : ''), tabindex: b.length ? 0 : -1, role: 'button' }, gBars);
        var go = function () {
          if (!b.length) return; pick = on ? null : i;
          if (D.cross) { var set = {}; b.forEach(function (k) { set[k] = 1; }); S.set('turns', pick === null ? null : { label: 'Turns: ' + fmt(lo) + '-' + fmt(lo + BIN - 1), test: function (k) { return !!set[k]; } }); } else draw();
        };
        r.addEventListener('click', go); r.addEventListener('keydown', function (e) { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); go(); } });
        r.addEventListener('mousemove', function (e) { t.show('<b>' + fmt(lo) + '-' + fmt(lo + BIN - 1) + ' turns</b><br>' + fmt(b.length) + ' tasks (' + pc(M.length ? b.length / M.length : 0) + ')', e); });
        r.addEventListener('mouseleave', t.hide);
      });
      var mu = mean(M.map(function (m) { return m[1]; })) || 0, tx = x(thr);
      mLine.setAttribute('x1', x(mu)); mLine.setAttribute('x2', x(mu));
      var left = x(mu) > tx - 90 && x(mu) < tx; mText.setAttribute('x', left ? x(mu) - 6 : x(mu) + 6); mText.setAttribute('text-anchor', left ? 'end' : 'start'); mText.textContent = 'mean ' + fmt(mu);
      wash.setAttribute('x', tx); wash.setAttribute('width', Math.max(0, W - R - tx));
      hHit.setAttribute('x', tx - 12); hLine.setAttribute('x1', tx); hLine.setAttribute('x2', tx); hKnob.setAttribute('cx', tx);
      var flip = tx > W - R - 190; hText.setAttribute('x', flip ? tx - 12 : tx + 12); hText.setAttribute('text-anchor', flip ? 'end' : 'start'); hText.textContent = 'long horizon, ' + fmt(thr) + '+ turns';
      hg.setAttribute('aria-valuenow', thr);
      var long = M.filter(function (m) { return m[1] >= thr; });
      sum.innerHTML = '<strong>' + fmt(long.length) + '</strong> of ' + fmt(M.length) + ' tasks (' + pc(M.length ? long.length / M.length : 0) + ') average ' + fmt(thr) + ' turns or more. Mean ' + fmt(mu) + ' turns per task.';
      // breakdown table: long-horizon tasks by group, or the picked bar's tasks by group
      var names = D.dims.g, rows, cap, head;
      var byG = function (list) { var c = {}; list.forEach(function (k) { var gg = S.tasks[k].g; c[gg] = (c[gg] || 0) + 1; }); return c; };
      var allC = byG(M.map(function (m) { return m[0]; }));
      var order = Object.keys(allC).map(Number).sort(function (a, b) { return allC[b] - allC[a]; });
      if (pick === null) {
        cap = 'Long-horizon tasks (' + fmt(thr) + '+ turns) by ' + gname.toLowerCase(); head = [gname, 'Long-horizon tasks', 'Tasks with runs', 'Share'];
        var lc = byG(long.map(function (m) { return m[0]; }));
        rows = order.map(function (gg) { return [names[gg], lc[gg] || 0, allC[gg], (lc[gg] || 0) / allC[gg]]; });
      } else {
        var bc = byG(bins[pick]); cap = 'Tasks averaging ' + fmt(pick * BIN) + '-' + fmt(pick * BIN + BIN - 1) + ' turns, by ' + gname.toLowerCase(); head = [gname, 'Tasks in this bar', 'Tasks with runs', 'Share of bar'];
        rows = order.map(function (gg) { return [names[gg], bc[gg] || 0, allC[gg], bins[pick].length ? (bc[gg] || 0) / bins[pick].length : 0]; });
      }
      clear(panel); grid(panel, cap + (pick === null ? '. Click a bar to break it down.' : '.'), head, rows, pick === null ? null : function () { pick = null; if (D.cross) S.set('turns', null); else draw(); });
    }
    var drag = false;
    hg.addEventListener('pointerdown', function (e) { drag = true; hg.setPointerCapture(e.pointerId); e.preventDefault(); });
    hg.addEventListener('pointermove', function (e) { if (!drag) return; var v = Math.max(0, Math.min(XMAX, Math.round((svgX(svg, e.clientX) - L) / (W - L - R) * XMAX / 10) * 10)); if (v !== thr) { thr = v; draw(); } });
    hg.addEventListener('pointerup', function () { drag = false; });
    hg.addEventListener('keydown', function (e) { var d = { ArrowLeft: -10, ArrowDown: -10, ArrowRight: 10, ArrowUp: 10, PageDown: -100, PageUp: 100 }[e.key]; if (d) { e.preventDefault(); thr = Math.max(0, Math.min(XMAX, thr + d)); draw(); } });
    S.subs.push(draw);
  }
  function grid(parent, cap, head, rows, back) {  // a small table drawn with divs, with a share meter in the last column
    var c = h('p', 'cx-cap', parent, esc(cap));
    if (back) { var b = h('button', 'cx-link', c, 'Back to the long-horizon view'); b.type = 'button'; b.addEventListener('click', back); }
    var g = h('div', 'cx-grid', parent); g.setAttribute('role', 'table');
    var hr = h('div', 'cx-row cx-head', g); hr.setAttribute('role', 'row'); head.forEach(function (x) { h('span', '', hr, esc(x)).setAttribute('role', 'columnheader'); });
    rows.forEach(function (r) {
      var rr = h('div', 'cx-row', g); rr.setAttribute('role', 'row');
      h('span', '', rr, esc(r[0])); h('span', '', rr, fmt(r[1])); h('span', '', rr, fmt(r[2]));
      h('span', '', rr, '<span class="cx-meter"><span style="width:' + (100 * r[3]).toFixed(1) + '%"></span></span>' + Math.round(100 * r[3]) + '%');
      rr.querySelectorAll(':scope > span').forEach(function (s) { s.setAttribute('role', 'cell'); });
    });
  }
  // ---- per-task pass rate by model: box plot with one dot per task ----
  function reward(fig, S) {
    var D = S.D, box = fig.querySelector('[data-body]'), W = 940, L = 210, R = 24, T = 40, B = 44, ROW = 58;
    var lo = 0.2, hi = 0.8, same = false, focus = null;
    var stats = D.models.map(function (m, k) {
      var pt = []; S.tasks.forEach(function (t) { var s = t.r[k]; if (s && s.length) pt.push(mean(s)); });
      return { k: k, n: pt.length, full: pt.filter(function (v) { return v >= 1; }).length };
    }).filter(function (s) { return s.n; });
    var items = stats.map(function (s) {
      var sat = s.full / s.n >= D.sat, few = s.n < D.minTasks;
      return { k: s.k, label: D.models[s.k], note: fmt(s.n) + ' tasks' + (sat ? ', saturated' : few ? ', few tasks' : ''), on: !sat && !few };
    });
    if (!items.some(function (i) { return i.on; }) && items.length) items[0].on = true;
    if (D.cross) S.strip(box);
    chips(box, items, function (i) { if (items[i].on && items.filter(function (x) { return x.on; }).length === 1) return false; items[i].on = !items[i].on; draw(); return true; });
    var opts = h('label', 'cx-check', box, '<input type="checkbox"> Same tasks only: keep the tasks every selected model ran');
    opts.querySelector('input').addEventListener('change', function (e) { same = e.target.checked; draw(); });
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Per-task pass rate by model' }, box);
    h('p', 'cx-hint', box, 'Each dot is one task: the share of a model\'s graded runs on it that passed. Boxes span the middle half of tasks, the line is the median and the diamond the model\'s pass rate over all its runs. Drag the edges of the shaded band to change it. Hover a dot for its runs; click it for the task.');
    var detail = h('div', 'cx-detail', box), summary = h('div', '', box), t = tip(box);
    var x = function (v) { return L + (W - L - R) * v; };
    var gBand = el('rect', { y: T - 10, fill: 'var(--teal)', 'fill-opacity': 0.09 }, svg), gC = el('g', {}, svg), lastH = T + ROW + B, H0;
    var hd = ['lo', 'hi'].map(function (which) {
      var g = el('g', { 'class': 'cx-handle', tabindex: 0, role: 'slider', 'aria-label': which === 'lo' ? 'Lower edge of the band' : 'Upper edge of the band' }, svg);
      var o = { which: which, g: g, hit: el('rect', { y: T - 26, width: 20, fill: 'transparent' }, g), line: el('line', { y1: T - 16, stroke: 'var(--teal)', 'stroke-width': 2 }, g),
        knob: el('circle', { cy: T - 16, r: 6.5, fill: 'var(--teal)', stroke: 'var(--paper)', 'stroke-width': 2 }, g), lab: el('text', { y: T - 27, 'text-anchor': 'middle', 'class': 'cx-band' }, g) };
      var setv = function (v) { v = Math.round(v * 20) / 20; if (which === 'lo') lo = Math.max(0, Math.min(v, hi - 0.05)); else hi = Math.min(1, Math.max(v, lo + 0.05)); };
      var dragging = false;
      g.addEventListener('pointerdown', function (ev) { dragging = true; g.setPointerCapture(ev.pointerId); ev.preventDefault(); });
      g.addEventListener('pointermove', function (ev) { if (!dragging) return; var old = lo + ':' + hi; setv((svgX(svg, ev.clientX) - L) / (W - L - R)); if (old !== lo + ':' + hi) { place(); tally(); } });
      g.addEventListener('pointerup', function () { dragging = false; });
      g.addEventListener('keydown', function (ev) { var d = { ArrowLeft: -0.05, ArrowDown: -0.05, ArrowRight: 0.05, ArrowUp: 0.05 }[ev.key]; if (d) { ev.preventDefault(); setv((which === 'lo' ? lo : hi) + d); place(); tally(); } });
      return o;
    });
    function place() {  // band and handles follow lo, hi and the chart height
      gBand.setAttribute('x', x(lo)); gBand.setAttribute('width', x(hi) - x(lo)); gBand.setAttribute('height', lastH - T - B + 10);
      hd.forEach(function (o) {
        var v = o.which === 'lo' ? lo : hi;
        o.hit.setAttribute('x', x(v) - 10); o.hit.setAttribute('height', lastH - B - T + 26);
        o.line.setAttribute('x1', x(v)); o.line.setAttribute('x2', x(v)); o.line.setAttribute('y2', lastH - B); o.knob.setAttribute('cx', x(v));
        o.lab.setAttribute('x', x(v)); o.lab.textContent = Math.round(100 * v) + '%'; o.g.setAttribute('aria-valuenow', Math.round(100 * v));
      });
    }
    var lastRows = [];
    function draw() {
      var V = S.visible([]), on = items.filter(function (i) { return i.on; });
      if (same) V = V.filter(function (i) { return on.every(function (m) { var s = S.tasks[i].r[m.k]; return s && s.length; }); });
      var rows = on.map(function (m) {
        var pts = []; V.forEach(function (i) { var s = S.tasks[i].r[m.k]; if (s && s.length) pts.push({ i: i, v: mean(s), runs: s }); });
        var vs = pts.map(function (p) { return p.v; }).sort(function (a, b) { return a - b; });
        return { m: m, pts: pts, vs: vs, q1: quant(vs, 0.25), q2: quant(vs, 0.5), q3: quant(vs, 0.75), mu: pool(pts) };
      }).filter(function (r) { return r.pts.length; });
      rows.sort(function (a, b) { return (b.q3 - a.q3) || (b.q2 - a.q2) || (b.mu - a.mu); });
      var H = T + Math.max(1, rows.length) * ROW + B; svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(gC); lastH = H; place();
      for (var v = 0; v <= 1.0001; v += 0.1) { el('line', { x1: x(v), x2: x(v), y1: T - 10, y2: H - B, stroke: 'var(--line-2)' }, gC); el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gC, Math.round(100 * v) + '%'); }
      el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'Per-task pass rate');
      if (!rows.length) el('text', { x: (L + W - R) / 2, y: T + 30, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'No graded runs for the selected models and filters');
      rows.forEach(function (r, j) {
        var cy = T + j * ROW + ROW / 2, g = el('g', {}, gC);
        el('text', { x: L - 14, y: cy - 2, 'text-anchor': 'end', 'class': 'cx-rowlab' }, g, r.m.label);
        el('text', { x: L - 14, y: cy + 14, 'text-anchor': 'end', 'class': 'cx-tick' }, g, fmt(r.pts.length) + ' tasks, pass rate ' + pc(r.mu));
        var iqr = r.q3 - r.q1, wl = Math.max(r.vs[0], r.q1 - 1.5 * iqr), wh = Math.min(r.vs[r.vs.length - 1], r.q3 + 1.5 * iqr);
        el('line', { x1: x(wl), x2: x(r.q1), y1: cy, y2: cy, stroke: 'var(--ink)' }, g); el('line', { x1: x(r.q3), x2: x(wh), y1: cy, y2: cy, stroke: 'var(--ink)' }, g);
        el('rect', { x: x(r.q1), width: Math.max(1, x(r.q3) - x(r.q1)), y: cy - 14, height: 28, fill: 'var(--card)', stroke: 'var(--ink)' }, g);
        el('line', { x1: x(r.q2), x2: x(r.q2), y1: cy - 14, y2: cy + 14, stroke: 'var(--ink)', 'stroke-width': 2 }, g);
        r.pts.forEach(function (p) {
          var c = el('circle', { cx: x(p.v), cy: cy + jitter(p.i * 7 + r.m.k) * 26, r: focus === p.i ? 5 : 3.2, 'class': 'cx-pt' + (focus === p.i ? ' is-on' : '') }, g);
          c.addEventListener('mousemove', function (e) { t.show('<b>' + esc(r.m.label) + '</b><br>' + passes(p.runs) + '<br>Task pass rate ' + pc(p.v), e); });
          c.addEventListener('mouseleave', t.hide);
          c.addEventListener('click', function () { focus = focus === p.i ? null : p.i; draw(); });
        });
        el('path', { d: 'M' + x(r.mu) + ' ' + (cy - 7) + 'l6 7l-6 7l-6 -7z', fill: 'var(--red)', stroke: 'var(--paper)', 'stroke-width': 1.5 }, g);
      });
      lastRows = rows; tally();
      clear(detail); detail.hidden = focus === null;
      if (focus !== null) {
        var tk = S.tasks[focus], tu = 0, tn = 0; for (var m in tk.t) { tu += tk.t[m][0]; tn += tk.t[m][1]; }
        var parts = ['<b>Selected task</b>', 'Domain: ' + esc(D.dims.g[tk.g]), 'Sub-domain: ' + esc(D.dims.c[tk.c]), 'Language: ' + esc(D.dims.l[tk.l]), 'Seniority: ' + esc(D.dims.s[tk.s]), tn ? 'Average turns: ' + fmt(tu / tn) + ' over ' + tn + ' completed runs' : 'No completed runs with a turn count'];
        D.models.forEach(function (name, k) { var s = tk.r[k]; if (s && s.length) parts.push(esc(name) + ': ' + passes(s) + ' (' + pc(mean(s)) + ')'); });
        detail.innerHTML = parts.join('<br>');
        var x0 = h('button', 'cx-link', detail, 'Close'); x0.type = 'button'; x0.addEventListener('click', function () { focus = null; draw(); });
      }
    }
    function tally() {  // the table under the chart, recomputed for the band
      var rows = lastRows; clear(summary);
      var cap = h('p', 'cx-cap', summary, 'Tasks by per-task pass rate, with the band at ' + Math.round(100 * lo) + '-' + Math.round(100 * hi) + '%');
      var gtab = h('div', 'cx-grid cx-grid5', summary); gtab.setAttribute('role', 'table');
      var hr = h('div', 'cx-row cx-head', gtab); ['Model', 'Tasks', 'Pass rate', 'Tasks at 0%', 'In the band', 'Tasks at 100%'].forEach(function (s) { h('span', '', hr, s); });
      rows.forEach(function (r) {
        var n = r.vs.length, z = r.vs.filter(function (v) { return v === 0; }).length, f = r.vs.filter(function (v) { return v >= 1; }).length, b = r.vs.filter(function (v) { return v >= lo - 1e-9 && v <= hi + 1e-9; }).length;
        var rr = h('div', 'cx-row', gtab); h('span', '', rr, esc(r.m.label)); h('span', '', rr, fmt(n)); h('span', '', rr, pc(r.mu)); h('span', '', rr, pc(z / n)); h('span', '', rr, pc(b / n)); h('span', '', rr, pc(f / n));
      });
    }
    S.subs.push(draw);
  }
  // ---- overview heatmap: models by catalogs ----
  function heat(fig, S) {
    var D = S.D.heat, box = fig.querySelector('[data-body]'), metric = 'reward', minT = D.minTasks, pick = null;
    var M = {
      reward: { label: 'Pass rate', f: function (c) { return c.passed / c.graded; }, txt: pc },
      t0: { label: 'Tasks at 0%', f: function (c) { return c.pt.filter(function (v) { return v === 0; }).length / c.pt.length; }, txt: pc },
      band: { label: 'Tasks at 20-80%', f: function (c) { return c.pt.filter(function (v) { return v >= 0.2 && v <= 0.8; }).length / c.pt.length; }, txt: pc },
      t100: { label: 'Tasks at 100%', f: function (c) { return c.pt.filter(function (v) { return v >= 1; }).length / c.pt.length; }, txt: pc },
      runs: { label: 'Graded runs', f: function (c) { return c.graded; }, txt: fmt }
    };
    var bar = h('div', 'cx-toolbar', box), seg = h('div', 'cx-seg', bar);
    Object.keys(M).forEach(function (k) { var b = h('button', '', seg, M[k].label); b.type = 'button'; b.setAttribute('aria-pressed', String(k === metric)); b.addEventListener('click', function () { metric = k; seg.querySelectorAll('button').forEach(function (x) { x.setAttribute('aria-pressed', String(x === b)); }); draw(); }); });
    var sl = h('label', 'cx-slider', bar, 'Hide cells with fewer than <input type="range" min="1" max="20" value="' + minT + '"> <b>' + minT + '</b> tasks');
    sl.querySelector('input').addEventListener('input', function (e) { minT = +e.target.value; sl.querySelector('b').textContent = minT; draw(); });
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Heatmap of models by catalog' }, box);
    h('p', 'cx-hint', box, 'Hover a cell for its numbers; click it for the spread of per-task pass rates.');
    var detail = h('div', 'cx-detail', box), t = tip(box); detail.hidden = true;
    var links = fig.querySelectorAll('[data-links] a');
    var C = {}; D.cells.forEach(function (c) { C[c[0] + ':' + c[1]] = { graded: c[2], pt: c[3], passed: c[4] }; });
    function color(v) {  // paper -> sage -> ink
      var s = [[251, 249, 244], [127, 179, 170], [17, 72, 78]], a = v < 0.5 ? s[0] : s[1], b = v < 0.5 ? s[1] : s[2], u = v < 0.5 ? v * 2 : (v - 0.5) * 2;
      return 'rgb(' + [0, 1, 2].map(function (i) { return Math.round(a[i] + (b[i] - a[i]) * u); }).join(',') + ')';
    }
    function draw() {
      var W = 940, L = 200, T = 70, CW = (W - L - 10) / D.catalogs.length, CH = 54, H = T + D.models.length * CH + 10, m = M[metric];
      svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(svg);
      var vmax = 1; if (metric === 'runs') { vmax = 1; D.cells.forEach(function (c) { if (c[3].length >= minT) vmax = Math.max(vmax, c[2]); }); }
      D.catalogs.forEach(function (name, j) {
        var words = name.split(' '), lines = [], cur = '';
        words.forEach(function (w) { if ((cur + ' ' + w).trim().length > 16) { lines.push(cur.trim()); cur = w; } else cur += ' ' + w; }); lines.push(cur.trim());
        lines.slice(0, 3).forEach(function (ln, k) { el('text', { x: L + j * CW + CW / 2, y: T - 12 - (Math.min(lines.length, 3) - 1 - k) * 14, 'text-anchor': 'middle', 'class': 'cx-collab' }, svg, ln); });
      });
      D.models.forEach(function (mname, i) {
        el('text', { x: L - 12, y: T + i * CH + CH / 2 + 4, 'text-anchor': 'end', 'class': 'cx-rowlab' }, svg, mname);
        D.catalogs.forEach(function (cn, j) {
          var c = C[j + ':' + i], ok = c && c.pt.length >= minT, gx = L + j * CW, gy = T + i * CH;
          var r = el('rect', { x: gx + 2, y: gy + 2, width: CW - 4, height: CH - 4, fill: ok ? color(metric === 'runs' ? c.graded / vmax : m.f(c)) : 'var(--paper)', stroke: pick === j + ':' + i ? 'var(--red)' : 'var(--line-2)', 'stroke-width': pick === j + ':' + i ? 2.5 : 1, 'class': ok ? 'cx-cell' : '' }, svg);
          if (!ok) { if (c) el('text', { x: gx + CW / 2, y: gy + CH / 2 + 4, 'text-anchor': 'middle', 'class': 'cx-tick' }, svg, c.pt.length + ' task' + (c.pt.length > 1 ? 's' : '')); return; }
          var v = metric === 'runs' ? c.graded / vmax : m.f(c), ink = v > 0.55 ? '#fff' : 'var(--ink)';
          el('text', { x: gx + CW / 2, y: gy + CH / 2 - 1, 'text-anchor': 'middle', 'class': 'cx-cellv', fill: ink }, svg, m.txt(m.f(c)));
          el('text', { x: gx + CW / 2, y: gy + CH / 2 + 15, 'text-anchor': 'middle', 'class': 'cx-cells', fill: ink }, svg, c.pt.length + ' tasks');
          r.addEventListener('mousemove', function (e) {
            var s = c.pt.slice().sort(function (a, b) { return a - b; });
            t.show('<b>' + esc(mname) + '</b><br>' + esc(cn) + '<br>' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs<br>Pass rate ' + pc(c.passed / c.graded) + '<br>Middle half of tasks: ' + pc(quant(s, 0.25)) + ' to ' + pc(quant(s, 0.75)), e);
          });
          r.addEventListener('mouseleave', t.hide);
          r.addEventListener('click', function () { pick = pick === j + ':' + i ? null : j + ':' + i; draw(); });
        });
      });
      clear(detail); detail.hidden = pick === null;
      if (pick !== null) {
        var jj = +pick.split(':')[0], ii = +pick.split(':')[1], c = C[pick], bins = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0];
        c.pt.forEach(function (v) { bins[Math.min(9, Math.floor(v * 10))]++; });
        var mx = Math.max.apply(null, bins);
        h('p', 'cx-cap', detail, esc(D.models[ii]) + ' in ' + esc(D.catalogs[jj]) + ': ' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs, pass rate ' + pc(c.passed / c.graded));
        var hist = h('div', 'cx-mini', detail);
        bins.forEach(function (n, k) { var col = h('div', 'cx-mini-col', hist); var b = h('div', 'cx-mini-bar', col); b.style.height = (mx ? 100 * n / mx : 0) + '%'; b.title = n + ' tasks'; h('div', 'cx-mini-n', col, String(n)); h('div', 'cx-mini-lab', col, (k * 10) + '-' + (k === 9 ? 100 : k * 10 + 9) + '%'); });
        var foot = h('p', 'cx-hint', detail, 'Tasks by per-task pass rate. ');
        if (links[jj]) { var a = links[jj].cloneNode(true); a.textContent = 'Open the ' + D.catalogs[jj] + ' page'; foot.appendChild(a); }
      }
    }
    draw();
  }
  // ---- wiring ----
  function init(scope) {
    var dataEl = scope.querySelector('script[data-chart-data]');
    if (!dataEl || dataEl.dataset.ready) return; dataEl.dataset.ready = '1';
    var D = JSON.parse(dataEl.textContent), S = makeStore(D);
    S.tasks = D.tasks.map(function (r) { return { g: r[0], c: r[1], l: r[2], s: r[3], r: r[4] || {}, t: r[5] || {} }; });
    scope.querySelectorAll('[data-chart]').forEach(function (fig) {
      var kind = fig.dataset.chart;
      if (kind === 'bars') bars(fig, S); else if (kind === 'turns') turns(fig, S); else if (kind === 'reward') reward(fig, S); else if (kind === 'heat') heat(fig, S);
    });
    S.subs.forEach(function (fn) { fn(); });
  }
  var me = document.currentScript, scope = (me && me.closest('.view')) || document;
  init(scope);
})();
</script>
</div>
