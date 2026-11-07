# Coding OTS RL Envs

<div class="kpis"><div class="kpi"><div class="kpi-value">1,305</div><div class="kpi-label">Tasks</div></div><div class="kpi"><div class="kpi-value">40%</div><div class="kpi-label">z-ai/glm-5.3-flash average reward</div></div><div class="kpi"><div class="kpi-value">4%</div><div class="kpi-label">google/gemini-3.8-flash average reward</div></div><div class="kpi"><div class="kpi-value">59%</div><div class="kpi-label">google/gemini-4-argon average reward</div></div></div>

## Executive summary

This OTS catalog helps AI coding agents develop capabilities on long, senior-level software work: rebuilding whole programs, fixing faults in real codebases and changing live systems without breaking them.

The tasks fall into seven catalogs. In ProgramBench (434 tasks) the agent rebuilds a program from how it behaves. In Debugging (324) it finds and fixes faults, and in Infrastructure as code (301) it restructures deployed Terraform without changing what runs. Feature implementation (117) adds capabilities to existing libraries, and System design (94) keeps running services correct through crashes and retries. Data engineering (17) and Migration (18) cover data pipelines and ports to another language.

Almost all tasks are senior engineering work in a few languages. Senior engineers are the target for 86% of tasks and staff engineers for 13%. Go, Terraform and Python account for 67% of tasks, and Rust, C and C++ for another 22%.

The catalogs include long-horizon coding tasks. An agent averages 353 turns (one model reply plus its tool calls) on a task, and 66% of tasks average 200 turns or more. ProgramBench and System design run longest, at about 450 turns. Infrastructure as code tasks are the shortest, at 113 turns.

## Catalogs

| Catalog | Tasks | What the tasks do | Average turn count |
|---|---:|---|---:|
| [ProgramBench](programbench.md) | 434 | Rebuild or upgrade programs so they behave exactly like a reference version. | 459 |
| [System design](system-design.md) | 94 | Keep multi-process services correct through crashes, retries and races. | 443 |
| [Diagnosis, Debugging, and Bug Fixing](debugging.md) | 324 | Find and fix faults in real codebases from symptoms or documentation. | 420 |
| [Feature implementation](feature-implementation.md) | 117 | Add capabilities to existing libraries and services without breaking current behaviour. | 342 |
| [Infrastructure as code](infrastructure-as-code.md) | 301 | Restructure live Terraform, CDK and Pulumi code without touching deployed resources. | 113 |
| [Data engineering](data-engineering.md) | 17 | Repair pipelines and data libraries after an upstream format or schema change. | 192 |
| [Migration](migration.md) | 18 | Port Java and Rust libraries to Go or C++ with identical behaviour. | 375 |
| **Total** | **1,305** |  |  |

## Benchmarks each catalog lifts

Our catalogs enable models to climb on different benchmarks, including but not limited to the following:

| Catalog | ProgramBench | DeepSWE | FrontierCode | CursorBench | Terminal-Bench 4.0 |
|---|:---:|:---:|:---:|:---:|:---:|
| ProgramBench | ✓ |  |  |  | ✓ |
| System design |  | ✓ | ✓ |  |  |
| Diagnosis, Debugging, and Bug Fixing |  |  | ✓ |  | ✓ |
| Feature implementation |  | ✓ | ✓ | ✓ |  |
| Infrastructure as code |  |  |  |  | ✓ |
| Data engineering |  |  |  |  | ✓ |

## Model average reward

Each cell is a model's average reward in one catalog (average@k): on each task, the mean grader score over its graded runs, partial credit included; then the mean over the tasks it ran there.

<div class="cx" data-chart="heat">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Average reward by model and catalog</h4></div>
<div class="fig-box" data-body></div>
<span data-links hidden><a href="programbench.html">ProgramBench</a><a href="system-design.html">System design</a><a href="debugging.html">Diagnosis, Debugging, and Bug Fixing</a><a href="feature-implementation.html">Feature implementation</a><a href="infrastructure-as-code.html">Infrastructure as code</a><a href="data-engineering.html">Data engineering</a><a href="migration.html">Migration</a></span>
</div>

| Model | Tasks run | Graded runs | Average reward |
|---|---:|---:|---:|
| z-ai/glm-5.3-flash | 800 | 4,246 | 40% |
| google/gemini-3.8-flash | 575 | 3,796 | 4% |
| google/gemini-4-argon | 350 | 866 | 59% |

## Samples

Each sample is a full task, downloadable from its task id. The average reward is that of the model with the most graded runs on the task.

| Catalog | Example | Task id | Model with most graded runs | Average reward |
|---|---|---|---|---:|
| ProgramBench | [Example 1: Media processing (Agent's choice)](programbench.md#example-1-media-processing-agents-choice) | [`svtav1-encoder-rebuild`](https://drive.google.com/file/d/1JmlCRxmj-7RJ9yZ698lASh-GGDr2N9Je/view) | z-ai/glm-5.3-flash | 7% of 5 |
| ProgramBench | [Example 2: Build systems (Agent's choice)](programbench.md#example-2-build-systems-agents-choice) | `bazel-gazelle-rebuild` | google/gemini-4-argon | 27% of 5 |
| System design | [Example 1: Payments & banking (TypeScript)](system-design.md#example-1-payments-banking-typescript) | [`actual-sync-compaction`](https://drive.google.com/file/d/1_sEAFRDztsqj6IIzgfOQ4KVr7m7Ff0-0/view) | z-ai/glm-5.3-flash | 17% of 6 |
| System design | [Example 2: Secrets & access control (Go)](system-design.md#example-2-secrets-access-control-go) | [`harbor-scanner-credentials`](https://drive.google.com/file/d/1aHmGorPxaObXqhuZbCDJxOM00L7U6V0m/view) | google/gemini-4-argon | 20% of 5 |
| System design | [Example 3: Software supply chain (C#)](system-design.md#example-3-software-supply-chain-c) | [`bagetter-fenced-writes`](https://drive.google.com/file/d/1yHr7nw0bfAZG5xO4uxrn_gH3GXffUFla/view) | z-ai/glm-5.3-flash | 50% of 6 |
| System design | [Example 4: Web applications (TypeScript)](system-design.md#example-4-web-applications-typescript) | [`dittofeed-user-deletion`](https://drive.google.com/file/d/1cxE8Is6I9_6PCr0kAZZnMWp-ao9Z--xN/view) | google/gemini-4-argon | 75% of 4 |
| System design | [Example 5: Media processing (TypeScript)](system-design.md#example-5-media-processing-typescript) | [`immich-storage-quotas`](https://drive.google.com/file/d/1iooMPQxDSF99aj7XHO7rn2HfRhoZEiYJ/view) | google/gemini-4-argon | 80% of 5 |
| System design | [Example 6: Payments & banking (TypeScript)](system-design.md#example-6-payments-banking-typescript) | [`medusa-cart-completion`](https://drive.google.com/file/d/1U6jZxHDbr-NnxBgwRvkZQplrsuJlpWCD/view) | google/gemini-4-argon | 80% of 5 |
| Diagnosis, Debugging, and Bug Fixing | [Example 1: Compilers & language runtimes (Python)](debugging.md#example-1-compilers-language-runtimes-python) | [`exo-canonical-ots`](https://drive.google.com/file/d/1hqLtS09dPnqztGyE15JRg9AZ0pS3fdAD/view) | z-ai/glm-5.3-flash | 0% of 5 |
| Diagnosis, Debugging, and Bug Fixing | [Example 2: Medical imaging & healthcare (Python)](debugging.md#example-2-medical-imaging-healthcare-python) | [`torchio-canonical-ots`](https://drive.google.com/file/d/1dAuRMjByz3IKD2Q7Qux8ZUoDjKNsHrvc/view) | z-ai/glm-5.3-flash | 0% of 5 |
| Diagnosis, Debugging, and Bug Fixing | [Example 3: Machine learning & MLOps (Python)](debugging.md#example-3-machine-learning-mlops-python) | [`swanlab-nanpair-ots`](https://drive.google.com/file/d/1ycCPNxGlpkKdgs2MHARCrZvTi6koSwwP/view) | google/gemini-4-argon | 0% of 1 |
| Diagnosis, Debugging, and Bug Fixing | [Example 4: Web crawling (Python)](debugging.md#example-4-web-crawling-python) | [`scrapy-pdk-ots`](https://drive.google.com/file/d/1REQsLCXJtRnoruzB2WlCUywZX56GZX8F/view) | google/gemini-4-argon | 69% of 13 |
| Feature implementation | [Example 1: Databases & storage engines (Go)](feature-implementation.md#example-1-databases-storage-engines-go) | [`memdb-txn-ots`](https://drive.google.com/file/d/1M3HCkXFdoznYOiY4yc3LlI8olgAA1K15/view) | z-ai/glm-5.3-flash | 0% of 4 |
| Feature implementation | [Example 2: Networking & HTTP (Go)](feature-implementation.md#example-2-networking-http-go) | `hertz-buffer-leases` | google/gemini-4-argon | 0% of 3 |
| Infrastructure as code | [Example 1: Cloud infra: containers & self-hosted platforms (Terraform)](infrastructure-as-code.md#example-1-cloud-infra-containers-self-hosted-platforms-terraform) | [`dualipv6-module-refactor`](https://drive.google.com/file/d/1Yg1iLWpltsqLdJS0jpUj4v3Wb3K4JlE-/view) | google/gemini-3.8-flash | 0% of 5 |
| Infrastructure as code | [Example 2: Cloud infra: AWS platform stacks (Terraform)](infrastructure-as-code.md#example-2-cloud-infra-aws-platform-stacks-terraform) | [`centralwatch-module-refactor`](https://drive.google.com/file/d/18b23bcb7ot9dDpaMF3nvcUVTGvYhg3aA/view) | z-ai/glm-5.3-flash | 19% of 16 |
| Infrastructure as code | [Example 3: Cloud infra: AWS platform stacks (Terraform)](infrastructure-as-code.md#example-3-cloud-infra-aws-platform-stacks-terraform) | [`modelrouter-module-refactor`](https://drive.google.com/file/d/1VrmncKJo_ub16T50JNG8Ep_0vONojAMq/view) | google/gemini-3.8-flash | 100% of 10 |
| Infrastructure as code | [Example 4: Cloud infra: containers & self-hosted platforms (TypeScript)](infrastructure-as-code.md#example-4-cloud-infra-containers-self-hosted-platforms-typescript) | [`atlasgrid-pulumi-migration`](https://drive.google.com/file/d/1l8nNQLGUM8GbW_dp8HFuPQb2nHNGh6J-/view) | google/gemini-3.8-flash | 62% of 8 |
| Data engineering | [Example 1: Databases & storage engines (Python)](data-engineering.md#example-1-databases-storage-engines-python) | [`sqlite-history-repair`](https://drive.google.com/file/d/146Un1dIq2RerHMbYpd5aWBnrQ6VpXLLV/view) | google/gemini-3.8-flash | 47% of 15 |
| Data engineering | [Example 2: Data pipelines & ETL (Python)](data-engineering.md#example-2-data-pipelines-etl-python) | [`etlplus-csv-pipeline`](https://drive.google.com/file/d/1j76u3l7Bo5yUlUhQCeFMMRASnZxfB8WD/view) | google/gemini-3.8-flash | 60% of 15 |
| Data engineering | [Example 3: Data formats & serialization (Python)](data-engineering.md#example-3-data-formats-serialization-python) | [`xmltodict-nulls-etl`](https://drive.google.com/file/d/1seIRx1v4KsVyJvkEOHKyRWaV64otchUF/view) | google/gemini-3.8-flash | 67% of 15 |
| Migration | [Example 1: Statistics & numerical methods (Go)](migration.md#example-1-statistics-numerical-methods-go) | [`dynahist-go-port`](https://drive.google.com/file/d/1ChoekorIF6oHhZTUyDkKJex0iPC334b8/view) | google/gemini-4-argon | 33% of 3 |
| Migration | [Example 2: Graph algorithms (Go)](migration.md#example-2-graph-algorithms-go) | [`dagre-go-port`](https://drive.google.com/file/d/1LEUYx_W7eOkFA8s4EEXnSfVbyYqMdLiD/view) | google/gemini-3.8-flash | 0% of 5 |
| Migration | [Example 3: Probabilistic data structures (Go)](migration.md#example-3-probabilistic-data-structures-go) | [`heavykeeper-go-port`](https://drive.google.com/file/d/13JG9-uLtmoWpJ6xDy7VUyn2UjxIfHsyo/view) | google/gemini-4-argon | 75% of 4 |

## Turn counts

A task's turn count is the average over its completed runs, from every model. Across all catalogs the average is 353 turns, and 66% of tasks average 200 turns or more.

<div class="cx" data-chart="turns" data-group="Catalog">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Turns per task, all catalogs</h4></div>
<div class="fig-box" data-body></div>
</div>

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
<script type="application/json" data-chart-data>{"cross":false,"models":["z-ai/glm-5.3-flash","google/gemini-3.8-flash","google/gemini-4-argon"],"dims":{"g":["ProgramBench","System design","Diagnosis, Debugging, and Bug Fixing","Feature implementation","Infrastructure as code","Data engineering","Migration"]},"tasks":[[0,0,0,0,{},{"0":[2155,5],"2":[272,1]}],[4,0,0,0,{},{"0":[365,5]}],[2,0,0,0,{},{"0":[2499,5]}],[1,0,0,0,{},{"2":[676,5],"0":[796,4]}],[2,0,0,0,{},{"0":[3499,6]}],[4,0,0,0,{},{"0":[601,5],"2":[68,1]}],[0,0,0,0,{},{"0":[3697,5],"2":[3595,6]}],[1,0,0,0,{},{"0":[3790,4],"2":[517,1]}],[0,0,0,0,{},{"1":[2097,6]}],[3,0,0,0,{},{"0":[1027,4]}],[4,0,0,0,{},{"0":[372,5],"2":[68,2]}],[1,0,0,0,{},{"0":[2665,4],"2":[247,1]}],[4,0,0,0,{},{"0":[493,5]}],[3,0,0,0,{},{"1":[3000,6]}],[1,0,0,0,{},{"1":[1209,11]}],[4,0,0,0,{},{"0":[790,5]}],[4,0,0,0,{},{"0":[721,5],"2":[172,3]}],[0,0,0,0,{},{"1":[1552,6]}],[4,0,0,0,{},{"0":[350,5]}],[2,0,0,0,{},{"1":[2328,6]}],[0,0,0,0,{},{"0":[4036,5],"2":[547,1]}],[0,0,0,0,{},{"1":[1215,8]}],[0,0,0,0,{},{"1":[1509,6]}],[0,0,0,0,{},{"0":[2174,3],"2":[2238,3]}],[3,0,0,0,{},{"0":[4415,6],"1":[4435,6],"2":[1377,3]}],[0,0,0,0,{},{"0":[1975,3],"2":[348,2]}],[4,0,0,0,{},{"0":[450,5]}],[0,0,0,0,{},{"1":[2521,6]}],[0,0,0,0,{},{"0":[1422,6],"1":[879,6]}],[2,0,0,0,{},{"0":[660,6]}],[2,0,0,0,{},{"1":[5155,6]}],[0,0,0,0,{},{"1":[1414,6]}],[0,0,0,0,{},{"1":[1523,6]}],[4,0,0,0,{},{"0":[599,5]}],[1,0,0,0,{},{"0":[2596,4]}],[4,0,0,0,{},{"2":[59,2],"0":[309,5]}],[4,0,0,0,{},{"0":[2303,9]}],[4,0,0,0,{},{"0":[546,5]}],[0,0,0,0,{},{"1":[10892,18]}],[1,0,0,0,{},{"1":[3231,6]}],[0,0,0,0,{},{"1":[1637,6]}],[2,0,0,0,{},{"1":[5435,6]}],[4,0,0,0,{},{"0":[1356,5]}],[0,0,0,0,{},{"1":[1514,6]}],[2,0,0,0,{},{"1":[271,1],"2":[169,1],"0":[3909,5]}],[1,0,0,0,{},{"0":[15375,28]}],[4,0,0,0,{},{"0":[537,6]}],[3,0,0,0,{},{"1":[555,6]}],[0,0,0,0,{},{"0":[4147,5],"2":[1662,6]}],[2,0,0,0,{},{"0":[650,6]}],[0,0,0,0,{},{"1":[4925,11]}],[0,0,0,0,{},{"1":[1111,6]}],[4,0,0,0,{},{"0":[499,5]}],[4,0,0,0,{},{"0":[439,5]}],[4,0,0,0,{},{"0":[608,4]}],[4,0,0,0,{},{"0":[607,5]}],[4,0,0,0,{},{"2":[418,7],"0":[887,5],"1":[903,10]}],[4,0,0,0,{},{"0":[1363,14],"2":[44,1]}],[1,0,0,0,{},{"0":[1618,4],"2":[459,1]}],[0,0,0,0,{},{"1":[5604,6]}],[0,0,0,0,{},{"1":[903,6]}],[4,0,0,0,{},{"0":[396,5]}],[4,0,0,0,{},{"0":[488,5]}],[2,0,0,0,{},{"0":[1405,6],"1":[2598,6],"2":[1256,3]}],[4,0,0,0,{},{"0":[458,5]}],[2,0,0,0,{},{"0":[579,6]}],[4,0,0,0,{},{"0":[1067,5]}],[4,0,0,0,{},{"0":[994,5]}],[3,0,0,0,{},{"1":[1930,6]}],[4,0,0,0,{},{"0":[252,4]}],[2,0,0,0,{},{"0":[1890,6]}],[2,0,0,0,{},{"0":[3433,5]}],[4,0,0,0,{},{"0":[264,4]}],[4,0,0,0,{},{"0":[560,5]}],[4,0,0,0,{},{"0":[1182,5]}],[4,0,0,0,{},{"0":[839,7],"2":[38,1]}],[1,0,0,0,{},{"1":[4218,15],"2":[3165,6]}],[0,0,0,0,{},{"1":[1561,6]}],[3,0,0,0,{},{"1":[1401,11]}],[0,0,0,0,{},{"1":[1020,6]}],[2,0,0,0,{},{"0":[1012,5]}],[2,0,0,0,{},{"2":[1163,2],"1":[9205,14]}],[0,0,0,0,{},{"1":[3042,14]}],[4,0,0,0,{},{"0":[889,5]}],[1,0,0,0,{},{"0":[2779,4],"2":[514,1]}],[4,0,0,0,{},{"2":[120,2],"0":[484,5]}],[0,0,0,0,{},{"0":[1295,6],"1":[1550,6],"2":[646,3]}],[2,0,0,0,{},{"1":[3831,6],"0":[1451,6],"2":[530,3]}],[2,0,0,0,{},{"0":[1588,6]}],[0,0,0,0,{},{"0":[2592,6],"1":[2919,6]}],[0,0,0,0,{},{"1":[2605,9]}],[0,0,0,0,{},{"1":[945,6]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"1":[4959,6]}],[1,0,0,0,{},{"0":[5538,8],"2":[634,1]}],[2,0,0,0,{},{"0":[1271,5]}],[0,0,0,0,{},{"1":[3215,6]}],[4,0,0,0,{},{"0":[524,5]}],[2,0,0,0,{},{"2":[131,2],"0":[561,6]}],[0,0,0,0,{},{"0":[1174,6],"1":[1256,6]}],[2,0,0,0,{},{"0":[1772,6]}],[2,0,0,0,{},{"1":[1892,6]}],[4,0,0,0,{},{"0":[546,5]}],[0,0,0,0,{},{"1":[1336,6]}],[0,0,0,0,{},{"1":[1756,6]}],[4,0,0,0,{},{"0":[1148,5]}],[2,0,0,0,{},{"0":[1718,8]}],[6,0,0,0,{},{"2":[611,2],"0":[3814,4],"1":[2216,5]}],[0,0,0,0,{},{"1":[2292,10],"0":[1835,6]}],[4,0,0,0,{},{"0":[1035,5]}],[2,0,0,0,{},{"0":[2599,6]}],[2,0,0,0,{},{"0":[1086,6]}],[0,0,0,0,{},{"1":[1010,6]}],[4,0,0,0,{},{"0":[480,5]}],[0,0,0,0,{},{"0":[1226,6],"1":[2932,11]}],[0,0,0,0,{},{"1":[2337,5]}],[2,0,0,0,{},{"1":[4564,6]}],[3,0,0,0,{},{"1":[1208,11]}],[0,0,0,0,{},{"2":[175,2],"0":[1934,5]}],[0,0,0,0,{},{"0":[1167,6],"1":[1634,6]}],[4,0,0,0,{},{"0":[435,5]}],[4,0,0,0,{},{"0":[559,5]}],[0,0,0,0,{},{"1":[11999,12],"0":[2641,6]}],[2,0,0,0,{},{"1":[5437,6]}],[4,0,0,0,{},{"0":[432,5]}],[2,0,0,0,{},{"0":[1170,6]}],[0,0,0,0,{},{"1":[5966,6]}],[3,0,0,0,{},{"0":[491,6],"1":[1404,11],"2":[498,3]}],[0,0,0,0,{},{"1":[887,6]}],[2,0,0,0,{},{"1":[2489,6]}],[0,0,0,0,{},{"2":[976,2],"0":[2835,4]}],[4,0,0,0,{},{"0":[439,5]}],[0,0,0,0,{},{"1":[6000,6]}],[0,0,0,0,{},{"0":[1796,4],"2":[223,1]}],[0,0,0,0,{},{"1":[3495,6]}],[2,0,0,0,{},{"0":[2299,5]}],[4,0,0,0,{},{"0":[500,5]}],[0,0,0,0,{},{"1":[1725,6]}],[3,0,0,0,{},{"0":[1225,6],"1":[1199,6],"2":[406,3]}],[2,0,0,0,{},{"0":[2263,7]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[1308,6]}],[6,0,0,0,{},{"1":[381,1],"2":[351,1]}],[0,0,0,0,{},{"0":[2083,6],"1":[2597,6]}],[4,0,0,0,{},{"2":[115,2],"0":[273,5],"1":[359,5]}],[0,0,0,0,{},{"1":[2463,6]}],[2,0,0,0,{},{"1":[3597,6]}],[0,0,0,0,{},{"1":[1345,6]}],[0,0,0,0,{},{"1":[683,6]}],[0,0,0,0,{},{"1":[2904,12]}],[2,0,0,0,{},{"0":[1983,9],"2":[163,1]}],[5,0,0,0,{},{"2":[256,2]}],[4,0,0,0,{},{"0":[578,5]}],[1,0,0,0,{},{"1":[1549,6]}],[2,0,0,0,{},{"2":[366,2],"0":[823,5]}],[0,0,0,0,{},{"0":[3806,5],"2":[936,5]}],[2,0,0,0,{},{"0":[1600,6]}],[3,0,0,0,{},{"1":[2653,6]}],[4,0,0,0,{},{"0":[373,5],"2":[49,1]}],[2,0,0,0,{},{"0":[1010,5]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[614,5]}],[2,0,0,0,{},{"0":[1847,5]}],[0,0,0,0,{},{"1":[7246,11]}],[6,0,0,0,{},{"1":[642,1],"2":[949,3]}],[2,0,0,0,{},{"0":[1750,5]}],[2,0,0,0,{},{"1":[355,1],"2":[141,1],"0":[2306,8]}],[4,0,0,0,{},{"0":[445,5]}],[2,0,0,0,{},{"1":[2353,6]}],[0,0,0,0,{},{"1":[5171,12]}],[0,0,0,0,{},{"1":[1388,6]}],[0,0,0,0,{},{"1":[2523,6],"2":[453,2]}],[0,0,0,0,{},{"1":[5586,6]}],[2,0,0,0,{},{"1":[5154,6]}],[2,0,0,0,{},{"0":[1558,6]}],[0,0,0,0,{},{"1":[1746,6]}],[0,0,0,0,{},{"0":[1952,4],"2":[243,1]}],[1,0,0,0,{},{"0":[6986,8]}],[2,0,0,0,{},{"0":[1761,6]}],[1,0,0,0,{},{"1":[1848,12]}],[0,0,0,0,{},{"0":[3488,5],"2":[528,3]}],[0,0,0,0,{},{"1":[685,6]}],[0,0,0,0,{},{"1":[1077,6],"2":[102,1]}],[2,0,0,0,{},{"0":[949,6]}],[4,0,0,0,{},{"2":[95,2],"0":[432,5],"1":[299,4]}],[3,0,0,0,{},{"1":[2969,6]}],[4,0,0,0,{},{"0":[1700,15],"2":[119,2]}],[2,0,0,0,{},{"0":[1065,6]}],[4,0,0,0,{},{"0":[1050,8],"2":[46,1]}],[0,0,0,0,{},{"1":[1683,6]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"2":[697,6],"1":[1673,8]}],[4,0,0,0,{},{"0":[802,7],"2":[54,1]}],[2,0,0,0,{},{"0":[1690,6]}],[6,0,0,0,{},{"2":[202,1]}],[4,0,0,0,{},{"0":[553,4],"2":[43,1]}],[0,0,0,0,{},{"0":[3668,5],"2":[1391,3]}],[2,0,0,0,{},{"0":[2446,5]}],[5,0,0,0,{},{"2":[252,2]}],[0,0,0,0,{},{"1":[1385,6]}],[2,0,0,0,{},{"0":[2109,13]}],[0,0,0,0,{},{"1":[7990,9]}],[0,0,0,0,{},{"0":[1012,3],"2":[156,1]}],[5,0,0,0,{},{"2":[145,2],"1":[608,5]}],[0,0,0,0,{},{"1":[1971,6]}],[4,0,0,0,{},{"0":[478,5]}],[0,0,0,0,{},{"1":[606,6]}],[2,0,0,0,{},{"2":[54,1]}],[0,0,0,0,{},{"1":[1027,8]}],[0,0,0,0,{},{"2":[802,2],"0":[3761,5]}],[0,0,0,0,{},{"1":[3161,6]}],[4,0,0,0,{},{"0":[478,5]}],[4,0,0,0,{},{"0":[373,4]}],[0,0,0,0,{},{"1":[1100,6]}],[4,0,0,0,{},{"0":[1545,9]}],[4,0,0,0,{},{"0":[555,5]}],[0,0,0,0,{},{"1":[1855,6]}],[4,0,0,0,{},{"0":[884,7],"2":[39,1]}],[4,0,0,0,{},{"0":[358,5]}],[2,0,0,0,{},{"1":[5508,6]}],[2,0,0,0,{},{"0":[2417,5]}],[0,0,0,0,{},{"2":[645,2],"0":[4000,4]}],[2,0,0,0,{},{"0":[1670,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[857,6]}],[4,0,0,0,{},{"0":[462,5]}],[4,0,0,0,{},{"0":[1808,10],"2":[137,2]}],[0,0,0,0,{},{"1":[2510,6]}],[2,0,0,0,{},{"0":[2404,5]}],[4,0,0,0,{},{"0":[820,5],"2":[48,1]}],[4,0,0,0,{},{"0":[651,5]}],[0,0,0,0,{},{"0":[2268,6],"1":[5999,6]}],[4,0,0,0,{},{"0":[578,5]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[2879,6]}],[4,0,0,0,{},{"0":[599,5]}],[1,0,0,0,{},{"0":[1708,6],"1":[1352,6],"2":[561,3]}],[4,0,0,0,{},{"0":[433,5],"2":[49,1]}],[3,0,0,0,{},{"1":[3297,6]}],[2,0,0,0,{},{"0":[2030,5]}],[0,0,0,0,{},{"0":[1513,6],"1":[2737,6]}],[4,0,0,0,{},{"0":[282,4]}],[0,0,0,0,{},{"1":[4125,5]}],[0,0,0,0,{},{"1":[2004,6],"2":[1352,3]}],[2,0,0,0,{},{"1":[5881,6]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"1":[2815,6]}],[4,0,0,0,{},{"0":[681,5],"2":[56,1]}],[3,0,0,0,{},{"1":[1101,8]}],[1,0,0,0,{},{"1":[1387,6]}],[2,0,0,0,{},{"0":[2659,6]}],[2,0,0,0,{},{"0":[2293,6],"2":[688,3]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[287,4]}],[4,0,0,0,{},{"0":[575,5]}],[4,0,0,0,{},{"0":[872,8],"2":[121,2]}],[0,0,0,0,{},{"1":[2464,6]}],[2,0,0,0,{},{"0":[1157,6]}],[0,0,0,0,{},{"1":[1406,6]}],[2,0,0,0,{},{"0":[1805,6],"2":[630,3]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[3315,5]}],[0,0,0,0,{},{"0":[4269,5],"2":[2280,3]}],[1,0,0,0,{},{"2":[2128,5],"0":[4253,6]}],[2,0,0,0,{},{"1":[1430,6]}],[0,0,0,0,{},{"0":[1585,3],"2":[1417,3]}],[2,0,0,0,{},{"1":[3258,6]}],[4,0,0,0,{},{"0":[656,5],"2":[42,1]}],[0,0,0,0,{},{"1":[2468,6]}],[0,0,0,0,{},{"1":[1069,6]}],[3,0,0,0,{},{"0":[1047,4],"2":[157,1]}],[2,0,0,0,{},{"0":[1193,5]}],[1,0,0,0,{},{"0":[2542,4],"2":[352,1]}],[0,0,0,0,{},{"0":[3264,6],"1":[5312,6]}],[4,0,0,0,{},{"0":[436,6],"2":[56,1]}],[4,0,0,0,{},{"0":[620,5]}],[2,0,0,0,{},{"0":[2492,5]}],[2,0,0,0,{},{"0":[3618,5]}],[4,0,0,0,{},{"0":[369,5]}],[6,0,0,0,{},{"1":[606,1],"2":[138,1]}],[0,0,0,0,{},{"0":[2785,4],"2":[469,1]}],[2,0,0,0,{},{"1":[1130,6]}],[0,0,0,0,{},{"1":[2748,6]}],[3,0,0,0,{},{"1":[2653,6]}],[0,0,0,0,{},{"1":[1676,6],"2":[570,3]}],[0,0,0,0,{},{"1":[4138,6]}],[2,0,0,0,{},{"1":[3504,6]}],[0,0,0,0,{},{"1":[2367,6]}],[0,0,0,0,{},{"1":[2462,6]}],[2,0,0,0,{},{"1":[765,6]}],[3,0,0,0,{},{"1":[2596,6]}],[4,0,0,0,{},{"0":[481,4]}],[3,0,0,0,{},{"1":[2993,6]}],[0,0,0,0,{},{"2":[377,2],"0":[3879,5]}],[3,0,0,0,{},{"1":[1880,6]}],[0,0,0,0,{},{"1":[2102,6]}],[1,0,0,0,{},{"0":[1171,6],"1":[1537,6],"2":[957,6]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"0":[3999,4],"2":[1954,3]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[2500,5],"2":[99,1]}],[4,0,0,0,{},{"0":[420,5]}],[2,0,0,0,{},{"1":[857,6]}],[6,0,0,0,{},{"2":[599,3]}],[0,0,0,0,{},{"0":[3425,5],"2":[2515,3]}],[6,0,0,0,{},{"0":[3000,5],"2":[587,1]}],[4,0,0,0,{},{"0":[934,6]}],[0,0,0,0,{},{"2":[761,1],"0":[2883,4]}],[2,0,0,0,{},{"0":[722,6]}],[2,0,0,0,{},{"0":[2017,6]}],[1,0,0,0,{},{"2":[3616,5],"0":[4000,4]}],[2,0,0,0,{},{"0":[1904,6],"2":[555,3]}],[2,0,0,0,{},{"1":[1717,6]}],[0,0,0,0,{},{"1":[1334,9]}],[0,0,0,0,{},{"1":[1596,6]}],[3,0,0,0,{},{"1":[2768,6]}],[2,0,0,0,{},{"0":[2265,5]}],[4,0,0,0,{},{"2":[132,2],"0":[364,5]}],[4,0,0,0,{},{"0":[707,6],"2":[197,3]}],[1,0,0,0,{},{"0":[6556,10]}],[1,0,0,0,{},{"0":[2352,4],"2":[259,1]}],[3,0,0,0,{},{"1":[1284,8]}],[3,0,0,0,{},{"1":[1185,6],"2":[101,1]}],[0,0,0,0,{},{"1":[2007,6],"2":[682,3]}],[1,0,0,0,{},{"2":[1736,5],"0":[3246,4]}],[2,0,0,0,{},{"2":[108,1],"0":[1202,6],"1":[938,6]}],[4,0,0,0,{},{"0":[683,5]}],[4,0,0,0,{},{"1":[435,3],"0":[1135,9]}],[3,0,0,0,{},{"1":[3157,6]}],[2,0,0,0,{},{"0":[1432,5]}],[4,0,0,0,{},{"0":[313,5]}],[3,0,0,0,{},{"1":[2410,6]}],[0,0,0,0,{},{"1":[2374,6]}],[0,0,0,0,{},{"0":[1481,6],"1":[2643,6]}],[2,0,0,0,{},{"0":[626,6]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[886,5]}],[4,0,0,0,{},{"0":[456,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"0":[1576,6],"1":[1972,6]}],[0,0,0,0,{},{"1":[5768,10]}],[0,0,0,0,{},{"1":[1665,6]}],[2,0,0,0,{},{"0":[1475,5]}],[1,0,0,0,{},{"0":[1500,4]}],[0,0,0,0,{},{"1":[4496,6]}],[6,0,0,0,{},{"2":[902,2],"0":[3000,5]}],[3,0,0,0,{},{"0":[2304,6],"1":[1287,6],"2":[650,3]}],[0,0,0,0,{},{"1":[1152,6]}],[0,0,0,0,{},{"1":[2512,5]}],[2,0,0,0,{},{"0":[1712,5]}],[0,0,0,0,{},{"1":[5944,6],"2":[543,1]}],[0,0,0,0,{},{"1":[1980,6]}],[0,0,0,0,{},{"1":[3300,6]}],[0,0,0,0,{},{"1":[1998,6],"2":[1784,3]}],[2,0,0,0,{},{"2":[412,3],"0":[2500,5]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[366,4]}],[4,0,0,0,{},{"2":[198,2]}],[1,0,0,0,{},{"0":[2778,4]}],[4,0,0,0,{},{"0":[818,5]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[239,5]}],[1,0,0,0,{},{"1":[1546,6]}],[5,0,0,0,{},{"2":[481,2]}],[4,0,0,0,{},{"0":[409,5]}],[1,0,0,0,{},{"1":[1735,6],"0":[1588,4]}],[0,0,0,0,{},{"1":[3594,6]}],[0,0,0,0,{},{"0":[1934,5],"1":[2507,6]}],[4,0,0,0,{},{"0":[589,5],"2":[58,1]}],[4,0,0,0,{},{"0":[660,5]}],[2,0,0,0,{},{"0":[2368,5]}],[4,0,0,0,{},{"0":[576,5]}],[0,0,0,0,{},{"1":[3218,6]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"0":[525,4]}],[3,0,0,0,{},{"2":[348,2],"1":[938,6]}],[4,0,0,0,{},{"2":[82,2],"0":[319,5]}],[2,0,0,0,{},{"0":[2500,5]}],[1,0,0,0,{},{"2":[1718,5],"0":[1668,4]}],[2,0,0,0,{},{"1":[3544,6]}],[0,0,0,0,{},{"1":[3836,6]}],[0,0,0,0,{},{"1":[5922,6]}],[0,0,0,0,{},{"1":[1528,8]}],[0,0,0,0,{},{"0":[3187,4],"2":[831,6]}],[0,0,0,0,{},{"1":[1386,6]}],[4,0,0,0,{},{"0":[482,5]}],[0,0,0,0,{},{"0":[3887,4],"2":[2314,3]}],[4,0,0,0,{},{"0":[313,5]}],[4,0,0,0,{},{"0":[574,4],"2":[46,1]}],[0,0,0,0,{},{"1":[5830,6]}],[3,0,0,0,{},{"1":[1454,6]}],[2,0,0,0,{},{"0":[2159,5]}],[4,0,0,0,{},{"0":[387,5]}],[0,0,0,0,{},{"1":[2726,6]}],[0,0,0,0,{},{"1":[4200,6]}],[4,0,0,0,{},{"0":[845,6]}],[0,0,0,0,{},{"1":[1550,5],"2":[1695,3]}],[1,0,0,0,{},{"2":[2068,5],"0":[4021,6]}],[0,0,0,0,{},{"1":[4288,6]}],[4,0,0,0,{},{"0":[389,5]}],[3,0,0,0,{},{"1":[4135,6]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"1":[2603,6]}],[0,0,0,0,{},{"0":[3866,5],"2":[2932,5]}],[2,0,0,0,{},{"0":[2500,5]}],[5,0,0,0,{},{"2":[2485,12],"1":[4650,15],"0":[1206,4]}],[4,0,0,0,{},{"0":[816,5],"2":[49,1]}],[2,0,0,0,{},{"0":[1861,6]}],[0,0,0,0,{},{"1":[5300,6]}],[4,0,0,0,{},{"0":[932,5]}],[4,0,0,0,{},{"0":[511,4]}],[0,0,0,0,{},{"0":[1891,3],"2":[960,3]}],[0,0,0,0,{},{"1":[1299,6]}],[0,0,0,0,{},{"0":[1820,6],"1":[7053,10]}],[5,0,0,0,{},{"2":[418,2]}],[0,0,0,0,{},{"0":[2645,5],"2":[1712,3]}],[3,0,0,0,{},{"0":[459,5]}],[2,0,0,0,{},{"1":[3928,6]}],[2,0,0,0,{},{"0":[1666,5]}],[3,0,0,0,{},{"2":[921,2],"1":[2944,6]}],[0,0,0,0,{},{"0":[2931,5],"2":[1326,6]}],[0,0,0,0,{},{"1":[1733,6]}],[0,0,0,0,{},{"1":[5998,6]}],[2,0,0,0,{},{"0":[611,6]}],[2,0,0,0,{},{"0":[2428,5]}],[4,0,0,0,{},{"0":[480,5]}],[2,0,0,0,{},{"0":[2250,6]}],[2,0,0,0,{},{"0":[2036,5]}],[0,0,0,0,{},{"0":[2801,4],"2":[412,1]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[265,5]}],[0,0,0,0,{},{"1":[1927,6]}],[4,0,0,0,{},{"0":[739,5]}],[2,0,0,0,{},{"1":[2265,6]}],[4,0,0,0,{},{"0":[854,5]}],[4,0,0,0,{},{"0":[588,5]}],[3,0,0,0,{},{"0":[1380,6],"1":[1511,6],"2":[366,3]}],[0,0,0,0,{},{"0":[1685,4],"1":[4746,6]}],[2,0,0,0,{},{"0":[571,6]}],[6,0,0,0,{},{"0":[3000,5],"2":[239,1]}],[0,0,0,0,{},{"1":[2741,6]}],[0,0,0,0,{},{"1":[4758,6],"2":[1569,3]}],[3,0,0,0,{},{"1":[1258,8]}],[6,0,0,0,{},{"2":[628,3]}],[0,0,0,0,{},{"1":[782,6]}],[1,0,0,0,{},{"0":[2185,4]}],[0,0,0,0,{},{"1":[1862,6]}],[0,0,0,0,{},{"1":[2253,6]}],[0,0,0,0,{},{"1":[556,6]}],[0,0,0,0,{},{"1":[1728,6]}],[1,0,0,0,{},{"0":[3013,6],"2":[309,1]}],[5,0,0,0,{},{"2":[244,2]}],[0,0,0,0,{},{"1":[2361,6]}],[2,0,0,0,{},{"2":[625,2],"0":[2500,5]}],[0,0,0,0,{},{"1":[2425,6]}],[3,0,0,0,{},{"1":[836,6]}],[4,0,0,0,{},{"0":[544,4]}],[0,0,0,0,{},{"1":[1652,6]}],[0,0,0,0,{},{"1":[753,6]}],[2,0,0,0,{},{"2":[1707,11],"1":[9191,16]}],[2,0,0,0,{},{"0":[1113,6]}],[4,0,0,0,{},{"0":[326,5],"2":[30,1]}],[0,0,0,0,{},{"0":[2759,3],"2":[315,1]}],[2,0,0,0,{},{"0":[2500,5],"2":[391,1]}],[0,0,0,0,{},{"0":[2766,5],"2":[1960,5]}],[0,0,0,0,{},{"0":[3483,4],"2":[2225,3]}],[4,0,0,0,{},{"2":[93,2],"0":[501,5],"1":[421,5]}],[3,0,0,0,{},{"1":[2258,6]}],[0,0,0,0,{},{"1":[6000,6]}],[2,0,0,0,{},{"0":[4629,5]}],[0,0,0,0,{},{"1":[1009,6]}],[4,0,0,0,{},{"2":[290,2],"1":[1360,5]}],[0,0,0,0,{},{"1":[1638,12]}],[0,0,0,0,{},{"1":[1566,6]}],[3,0,0,0,{},{"1":[1687,6]}],[4,0,0,0,{},{"0":[514,5]}],[4,0,0,0,{},{"2":[129,2],"0":[712,4]}],[0,0,0,0,{},{"1":[3440,6],"2":[643,3]}],[5,0,0,0,{},{"2":[361,2]}],[1,0,0,0,{},{"0":[1181,4],"2":[988,3]}],[2,0,0,0,{},{"0":[1513,6]}],[0,0,0,0,{},{"0":[1934,2],"2":[1643,3]}],[0,0,0,0,{},{"1":[1249,6]}],[0,0,0,0,{},{"1":[10389,12],"0":[1389,6]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"2":[462,1],"1":[3439,6]}],[4,0,0,0,{},{"0":[363,5]}],[2,0,0,0,{},{"0":[2110,5]}],[0,0,0,0,{},{"1":[3757,6]}],[1,0,0,0,{},{"0":[4905,6]}],[2,0,0,0,{},{"1":[4214,7]}],[4,0,0,0,{},{"0":[728,7],"2":[44,1]}],[0,0,0,0,{},{"2":[373,2],"0":[2645,3]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[1822,6]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[6725,15]}],[3,0,0,0,{},{"1":[5733,6]}],[0,0,0,0,{},{"1":[4285,6]}],[2,0,0,0,{},{"1":[3588,6]}],[0,0,0,0,{},{"1":[2381,6]}],[4,0,0,0,{},{"0":[554,5]}],[0,0,0,0,{},{"1":[961,6]}],[4,0,0,0,{},{"0":[421,5]}],[3,0,0,0,{},{"1":[3354,6]}],[3,0,0,0,{},{"1":[584,6]}],[0,0,0,0,{},{"0":[3470,5],"2":[2214,6]}],[2,0,0,0,{},{"0":[3233,5]}],[3,0,0,0,{},{"1":[3231,6]}],[6,0,0,0,{},{"2":[429,2]}],[0,0,0,0,{},{"1":[2423,6]}],[4,0,0,0,{},{"0":[426,5]}],[4,0,0,0,{},{"0":[419,5]}],[4,0,0,0,{},{"0":[452,5]}],[2,0,0,0,{},{"0":[2453,5]}],[4,0,0,0,{},{"0":[269,5]}],[4,0,0,0,{},{"0":[353,5]}],[0,0,0,0,{},{"0":[1578,4],"2":[618,1]}],[6,0,0,0,{},{"2":[837,2]}],[0,0,0,0,{},{"1":[3355,7]}],[0,0,0,0,{},{"0":[3995,5],"2":[184,1]}],[0,0,0,0,{},{"1":[8620,12]}],[3,0,0,0,{},{"1":[1314,6]}],[2,0,0,0,{},{"0":[2462,5]}],[0,0,0,0,{},{"0":[1692,6],"1":[1888,6]}],[4,0,0,0,{},{"0":[686,5]}],[4,0,0,0,{},{"0":[1026,6]}],[0,0,0,0,{},{"1":[2678,6]}],[0,0,0,0,{},{"1":[5300,7]}],[0,0,0,0,{},{"1":[1463,6]}],[4,0,0,0,{},{"0":[503,5]}],[0,0,0,0,{},{"1":[3657,6]}],[4,0,0,0,{},{"0":[364,5]}],[0,0,0,0,{},{"0":[3776,5],"2":[912,3]}],[4,0,0,0,{},{"0":[284,5]}],[0,0,0,0,{},{"0":[2296,6],"1":[5967,6]}],[2,0,0,0,{},{"0":[1569,6]}],[2,0,0,0,{},{"0":[990,6]}],[2,0,0,0,{},{"0":[1037,5],"2":[50,1]}],[0,0,0,0,{},{"1":[4778,12]}],[0,0,0,0,{},{"1":[4356,7]}],[4,0,0,0,{},{"0":[670,5],"2":[152,3]}],[2,0,0,0,{},{"0":[690,6]}],[3,0,0,0,{},{"0":[417,4],"2":[111,1]}],[2,0,0,0,{},{"0":[2374,5]}],[4,0,0,0,{},{"0":[367,5],"2":[37,1]}],[0,0,0,0,{},{"1":[1947,6]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"0":[1046,4]}],[0,0,0,0,{},{"1":[4016,6],"2":[300,1]}],[2,0,0,0,{},{"1":[4106,6]}],[2,0,0,0,{},{"0":[2120,5]}],[4,0,0,0,{},{"2":[473,7],"0":[2245,16],"1":[2094,10]}],[0,0,0,0,{},{"1":[2524,8]}],[1,0,0,0,{},{"2":[1236,5],"0":[1929,4]}],[2,0,0,0,{},{"1":[5790,6]}],[3,0,0,0,{},{"1":[3252,6]}],[0,0,0,0,{},{"0":[883,5],"1":[3428,6]}],[0,0,0,0,{},{"1":[1113,6]}],[4,0,0,0,{},{"0":[472,4]}],[2,0,0,0,{},{"1":[5804,6]}],[0,0,0,0,{},{"1":[2688,6]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[7163,16]}],[0,0,0,0,{},{"1":[2094,6]}],[2,0,0,0,{},{"1":[202,1],"2":[180,1],"0":[2242,5]}],[0,0,0,0,{},{"1":[1699,6]}],[4,0,0,0,{},{"0":[1554,9],"2":[146,3]}],[0,0,0,0,{},{"0":[1023,2],"2":[1568,3]}],[2,0,0,0,{},{"1":[1126,6]}],[0,0,0,0,{},{"0":[2858,6],"1":[3693,6]}],[3,0,0,0,{},{"0":[1003,4]}],[3,0,0,0,{},{"1":[674,6]}],[0,0,0,0,{},{"0":[1032,6],"1":[1451,6]}],[5,0,0,0,{},{"2":[373,2],"0":[653,4]}],[2,0,0,0,{},{"0":[688,6]}],[4,0,0,0,{},{"0":[742,5],"2":[42,1]}],[4,0,0,0,{},{"0":[549,5]}],[4,0,0,0,{},{"0":[602,5]}],[0,0,0,0,{},{"1":[3515,9],"2":[1717,3]}],[2,0,0,0,{},{"0":[3112,5]}],[2,0,0,0,{},{"0":[2272,5],"2":[222,1]}],[4,0,0,0,{},{"0":[464,5],"2":[36,1]}],[2,0,0,0,{},{"0":[2249,6]}],[4,0,0,0,{},{"0":[397,5]}],[2,0,0,0,{},{"0":[2500,5]}],[6,0,0,0,{},{"2":[1196,2]}],[0,0,0,0,{},{"1":[3578,6]}],[1,0,0,0,{},{"2":[1536,5],"0":[1995,5]}],[4,0,0,0,{},{"0":[482,5]}],[4,0,0,0,{},{"0":[546,5]}],[1,0,0,0,{},{"2":[1375,5],"0":[2775,4]}],[1,0,0,0,{},{"1":[1769,6],"2":[1163,5]}],[0,0,0,0,{},{"1":[1868,6],"2":[419,3]}],[0,0,0,0,{},{"1":[2437,6],"2":[793,3]}],[4,0,0,0,{},{"0":[427,5],"2":[70,1]}],[5,0,0,0,{},{"2":[612,2],"1":[1582,4]}],[2,0,0,0,{},{"0":[1692,6],"1":[3262,6],"2":[252,1]}],[3,0,0,0,{},{"0":[2296,6],"1":[1275,6],"2":[152,1]}],[4,0,0,0,{},{"0":[685,5]}],[0,0,0,0,{},{"2":[600,2],"0":[3753,5]}],[4,0,0,0,{},{"0":[606,5]}],[0,0,0,0,{},{"1":[879,6]}],[0,0,0,0,{},{"1":[8599,12]}],[1,0,0,0,{},{"2":[1176,5],"0":[1860,4]}],[3,0,0,0,{},{"1":[1754,6]}],[0,0,0,0,{},{"1":[1104,6]}],[0,0,0,0,{},{"1":[1555,6]}],[4,0,0,0,{},{"0":[425,5]}],[0,0,0,0,{},{"0":[4641,5],"2":[3368,5]}],[2,0,0,0,{},{"1":[2036,6]}],[4,0,0,0,{},{"0":[468,5]}],[0,0,0,0,{},{"1":[2237,6],"2":[1788,3]}],[2,0,0,0,{},{"0":[2372,5]}],[2,0,0,0,{},{"0":[2440,5]}],[2,0,0,0,{},{"0":[2500,5]}],[6,0,0,0,{},{"1":[433,1],"2":[732,3]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[5312,6]}],[0,0,0,0,{},{"0":[610,6],"1":[819,6]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[441,5]}],[0,0,0,0,{},{"0":[3292,4],"2":[387,1]}],[0,0,0,0,{},{"0":[1663,6],"1":[1818,6]}],[2,0,0,0,{},{"0":[3374,5]}],[0,0,0,0,{},{"1":[4405,6]}],[0,0,0,0,{},{"0":[734,2],"2":[1261,3]}],[0,0,0,0,{},{"1":[3155,6]}],[2,0,0,0,{},{"0":[2500,5]}],[5,0,0,0,{},{"2":[2377,12],"0":[1193,5],"1":[6994,15]}],[3,0,0,0,{},{"1":[1156,6]}],[4,0,0,0,{},{"0":[542,5],"2":[54,1]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"1":[2098,6]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[2513,6]}],[2,0,0,0,{},{"0":[1483,5]}],[2,0,0,0,{},{"0":[831,6]}],[0,0,0,0,{},{"0":[3211,5],"2":[2654,5]}],[0,0,0,0,{},{"0":[2207,4],"2":[456,1]}],[4,0,0,0,{},{"0":[509,5]}],[2,0,0,0,{},{"0":[668,6]}],[5,0,0,0,{},{"2":[202,2],"0":[855,4]}],[2,0,0,0,{},{"0":[2157,5]}],[0,0,0,0,{},{"1":[800,6],"2":[1723,3]}],[0,0,0,0,{},{"1":[5215,6]}],[4,0,0,0,{},{"0":[522,5]}],[2,0,0,0,{},{"0":[1310,6]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[610,5]}],[0,0,0,0,{},{"0":[1887,5],"2":[1077,6]}],[4,0,0,0,{},{"0":[776,5]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[1592,6]}],[2,0,0,0,{},{"0":[1681,5]}],[2,0,0,0,{},{"0":[1336,5]}],[4,0,0,0,{},{"0":[528,5]}],[3,0,0,0,{},{"0":[2596,6],"1":[1795,6],"2":[621,3]}],[0,0,0,0,{},{"1":[5234,6]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[413,5]}],[2,0,0,0,{},{"0":[1564,3]}],[2,0,0,0,{},{"0":[1401,6]}],[0,0,0,0,{},{"1":[1393,6]}],[3,0,0,0,{},{"1":[2017,6]}],[2,0,0,0,{},{"0":[1299,5]}],[0,0,0,0,{},{"1":[5947,6]}],[0,0,0,0,{},{"1":[4286,6]}],[1,0,0,0,{},{"2":[2393,5],"0":[2058,6]}],[2,0,0,0,{},{"0":[2381,5],"2":[177,1]}],[2,0,0,0,{},{"0":[1056,6]}],[4,0,0,0,{},{"0":[487,5]}],[0,0,0,0,{},{"1":[2291,6]}],[0,0,0,0,{},{"0":[3098,4],"2":[409,1]}],[1,0,0,0,{},{"0":[4545,6],"2":[368,1]}],[4,0,0,0,{},{"0":[454,5]}],[1,0,0,0,{},{"0":[1913,4],"2":[354,1]}],[2,0,0,0,{},{"1":[719,6]}],[3,0,0,0,{},{"1":[801,6]}],[2,0,0,0,{},{"0":[1094,6]}],[2,0,0,0,{},{"1":[5374,6]}],[4,0,0,0,{},{"0":[714,5]}],[0,0,0,0,{},{"1":[3713,6]}],[4,0,0,0,{},{"0":[415,5]}],[0,0,0,0,{},{"1":[3361,6]}],[0,0,0,0,{},{"0":[1552,3],"2":[1143,3]}],[4,0,0,0,{},{"0":[854,11],"2":[46,1]}],[0,0,0,0,{},{"1":[1085,6]}],[2,0,0,0,{},{"1":[4859,6]}],[1,0,0,0,{},{"0":[2803,6],"1":[1260,6],"2":[672,3]}],[1,0,0,0,{},{"1":[1406,6],"0":[1419,4],"2":[845,6]}],[2,0,0,0,{},{"0":[2536,5]}],[0,0,0,0,{},{"1":[2652,6]}],[0,0,0,0,{},{"1":[2047,6]}],[3,0,0,0,{},{"1":[5555,6]}],[0,0,0,0,{},{"1":[2544,6]}],[3,0,0,0,{},{"1":[3478,6]}],[2,0,0,0,{},{"0":[3098,5]}],[4,0,0,0,{},{"0":[586,5]}],[3,0,0,0,{},{"1":[817,6]}],[2,0,0,0,{},{"1":[4447,6]}],[0,0,0,0,{},{"0":[1781,6],"1":[3794,8]}],[2,0,0,0,{},{"0":[693,6]}],[3,0,0,0,{},{"1":[3397,6]}],[2,0,0,0,{},{"0":[1975,5]}],[2,0,0,0,{},{"0":[2266,5]}],[3,0,0,0,{},{"1":[5229,6]}],[0,0,0,0,{},{"1":[1046,6]}],[0,0,0,0,{},{"1":[3735,6]}],[0,0,0,0,{},{"0":[3000,4],"2":[402,1]}],[5,0,0,0,{},{"2":[517,2]}],[1,0,0,0,{},{"1":[1574,6]}],[2,0,0,0,{},{"0":[2468,5]}],[4,0,0,0,{},{"0":[921,5]}],[3,0,0,0,{},{"1":[1062,6]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[1964,5]}],[2,0,0,0,{},{"0":[3213,5]}],[2,0,0,0,{},{"0":[1773,6]}],[4,0,0,0,{},{"0":[1325,10],"2":[54,1]}],[0,0,0,0,{},{"1":[3800,6],"2":[674,2]}],[1,0,0,0,{},{"0":[733,4],"2":[173,1]}],[0,0,0,0,{},{"1":[1285,6]}],[2,0,0,0,{},{"1":[653,6]}],[0,0,0,0,{},{"1":[2606,6]}],[2,0,0,0,{},{"0":[2218,5]}],[2,0,0,0,{},{"0":[5557,10]}],[4,0,0,0,{},{"0":[861,5]}],[3,0,0,0,{},{"1":[1600,9]}],[0,0,0,0,{},{"0":[1441,6],"1":[1011,6]}],[4,0,0,0,{},{"0":[539,5]}],[4,0,0,0,{},{"0":[874,5]}],[0,0,0,0,{},{"1":[3599,12]}],[0,0,0,0,{},{"1":[691,6]}],[3,0,0,0,{},{"1":[3118,6]}],[4,0,0,0,{},{"0":[412,5]}],[0,0,0,0,{},{"1":[6000,6]}],[0,0,0,0,{},{"1":[11218,12],"2":[1388,3]}],[0,0,0,0,{},{"1":[2174,6]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"1":[127,1],"0":[2262,5]}],[4,0,0,0,{},{"0":[698,5]}],[2,0,0,0,{},{"0":[1815,5]}],[3,0,0,0,{},{"1":[1793,6]}],[0,0,0,0,{},{"1":[1378,6]}],[4,0,0,0,{},{"0":[1999,10],"2":[51,1]}],[4,0,0,0,{},{"0":[1281,7]}],[0,0,0,0,{},{"1":[2892,7]}],[3,0,0,0,{},{"1":[746,6]}],[0,0,0,0,{},{"0":[894,6],"1":[1194,6]}],[4,0,0,0,{},{"0":[550,5],"2":[45,1]}],[0,0,0,0,{},{"0":[1193,5],"1":[2109,6]}],[0,0,0,0,{},{"0":[2450,6],"1":[3755,6]}],[1,0,0,0,{},{"0":[1336,4],"2":[180,1]}],[0,0,0,0,{},{"1":[3004,6]}],[0,0,0,0,{},{"1":[3306,6],"2":[1701,3]}],[2,0,0,0,{},{"2":[251,1],"0":[1403,7]}],[5,0,0,0,{},{"2":[183,2]}],[2,0,0,0,{},{"0":[2518,6]}],[0,0,0,0,{},{"1":[1607,5]}],[2,0,0,0,{},{"0":[911,6]}],[4,0,0,0,{},{"0":[310,5]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"1":[2396,6]}],[4,0,0,0,{},{"0":[555,5]}],[4,0,0,0,{},{"0":[390,5]}],[3,0,0,0,{},{"0":[2143,9],"1":[1522,6],"2":[483,3]}],[4,0,0,0,{},{"0":[654,5]}],[0,0,0,0,{},{"1":[3156,7],"2":[486,2]}],[2,0,0,0,{},{"0":[671,6]}],[0,0,0,0,{},{"0":[2240,5],"2":[166,1]}],[4,0,0,0,{},{"0":[522,5]}],[4,0,0,0,{},{"0":[488,5]}],[2,0,0,0,{},{"1":[985,6]}],[4,0,0,0,{},{"0":[741,5]}],[4,0,0,0,{},{"0":[1020,8],"2":[55,1]}],[0,0,0,0,{},{"1":[1853,6]}],[4,0,0,0,{},{"0":[455,5]}],[1,0,0,0,{},{"0":[983,4]}],[4,0,0,0,{},{"0":[585,5]}],[2,0,0,0,{},{"0":[1029,6]}],[4,0,0,0,{},{"0":[548,5]}],[0,0,0,0,{},{"1":[2405,12]}],[4,0,0,0,{},{"0":[394,5],"2":[41,1]}],[0,0,0,0,{},{"1":[2827,6]}],[0,0,0,0,{},{"1":[1196,6]}],[0,0,0,0,{},{"1":[1268,6]}],[2,0,0,0,{},{"1":[1389,6]}],[2,0,0,0,{},{"0":[3132,5]}],[4,0,0,0,{},{"0":[827,5]}],[3,0,0,0,{},{"1":[2365,6]}],[2,0,0,0,{},{"0":[1301,6]}],[4,0,0,0,{},{"0":[551,5]}],[4,0,0,0,{},{"0":[467,5]}],[0,0,0,0,{},{"1":[1136,6]}],[2,0,0,0,{},{"0":[2389,5]}],[2,0,0,0,{},{"0":[2418,5]}],[2,0,0,0,{},{"0":[1417,6]}],[0,0,0,0,{},{"1":[6404,9]}],[2,0,0,0,{},{"0":[2762,5],"2":[287,1]}],[0,0,0,0,{},{"1":[1767,6]}],[4,0,0,0,{},{"0":[394,5]}],[0,0,0,0,{},{"1":[1796,6]}],[2,0,0,0,{},{"0":[1368,5]}],[0,0,0,0,{},{"0":[3628,5],"2":[1160,3]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"2":[777,2],"0":[3502,4]}],[4,0,0,0,{},{"0":[546,5]}],[0,0,0,0,{},{"0":[4070,5],"2":[2308,3]}],[2,0,0,0,{},{"0":[989,5]}],[2,0,0,0,{},{"0":[2700,6]}],[4,0,0,0,{},{"2":[576,2],"1":[780,3]}],[0,0,0,0,{},{"1":[3939,12]}],[0,0,0,0,{},{"1":[6029,11]}],[2,0,0,0,{},{"0":[1828,5]}],[3,0,0,0,{},{"2":[545,2],"1":[1661,6]}],[0,0,0,0,{},{"1":[5595,6]}],[2,0,0,0,{},{"0":[2329,5]}],[4,0,0,0,{},{"0":[587,5],"2":[38,1]}],[4,0,0,0,{},{"0":[407,5]}],[4,0,0,0,{},{"0":[945,6]}],[4,0,0,0,{},{"0":[503,5]}],[2,0,0,0,{},{"1":[5579,6]}],[3,0,0,0,{},{"1":[2980,6]}],[4,0,0,0,{},{"2":[132,2],"0":[705,7],"1":[475,5]}],[0,0,0,0,{},{"1":[1047,6]}],[0,0,0,0,{},{"0":[2971,5],"2":[249,1]}],[3,0,0,0,{},{"0":[1056,6],"1":[769,6],"2":[568,3]}],[2,0,0,0,{},{"0":[2000,7]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"1":[3914,6]}],[2,0,0,0,{},{"1":[564,6]}],[3,0,0,0,{},{"1":[2638,6]}],[0,0,0,0,{},{"1":[3264,7]}],[0,0,0,0,{},{"1":[990,6]}],[0,0,0,0,{},{"1":[5400,6]}],[2,0,0,0,{},{"0":[1120,6]}],[0,0,0,0,{},{"1":[2605,6]}],[4,0,0,0,{},{"0":[312,5]}],[3,0,0,0,{},{"2":[724,2],"1":[2979,6]}],[0,0,0,0,{},{"0":[1555,6],"1":[2741,6]}],[1,0,0,0,{},{"1":[1785,6],"0":[2511,5],"2":[819,6]}],[3,0,0,0,{},{"2":[1219,7],"1":[2626,16]}],[0,0,0,0,{},{"1":[1766,6]}],[3,0,0,0,{},{"0":[659,4]}],[0,0,0,0,{},{"1":[2014,6]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[2524,6]}],[0,0,0,0,{},{"1":[1809,6]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[623,5]}],[3,0,0,0,{},{"1":[3714,6]}],[2,0,0,0,{},{"0":[2500,5]}],[1,0,0,0,{},{"0":[1772,6],"2":[221,1]}],[4,0,0,0,{},{"0":[526,5]}],[0,0,0,0,{},{"1":[1374,5]}],[2,0,0,0,{},{"0":[1568,6]}],[0,0,0,0,{},{"0":[1360,6],"1":[1807,5]}],[0,0,0,0,{},{"1":[1441,6]}],[0,0,0,0,{},{"2":[585,2],"0":[4361,5]}],[4,0,0,0,{},{"0":[489,5],"2":[34,1]}],[0,0,0,0,{},{"0":[3949,4],"2":[240,1]}],[0,0,0,0,{},{"1":[1281,6]}],[4,0,0,0,{},{"0":[531,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"0":[2941,4],"2":[279,2]}],[4,0,0,0,{},{"0":[527,5]}],[3,0,0,0,{},{"1":[1836,11]}],[2,0,0,0,{},{"0":[4293,5]}],[0,0,0,0,{},{"0":[3129,4],"2":[1411,3]}],[2,0,0,0,{},{"2":[437,3],"0":[2377,5]}],[4,0,0,0,{},{"0":[670,5]}],[5,0,0,0,{},{"2":[394,2]}],[3,0,0,0,{},{"0":[4752,10],"1":[1952,6],"2":[813,3]}],[2,0,0,0,{},{"0":[1810,6]}],[0,0,0,0,{},{"1":[3587,6]}],[0,0,0,0,{},{"1":[5155,9]}],[2,0,0,0,{},{"1":[1098,6]}],[0,0,0,0,{},{"0":[1114,6],"1":[1161,6]}],[0,0,0,0,{},{"1":[5164,10],"2":[1667,3]}],[4,0,0,0,{},{"0":[772,5]}],[4,0,0,0,{},{"0":[333,5]}],[2,0,0,0,{},{"0":[2527,6]}],[0,0,0,0,{},{"1":[3447,6]}],[4,0,0,0,{},{"1":[317,3],"0":[430,5]}],[2,0,0,0,{},{"0":[2500,5]}],[1,0,0,0,{},{"2":[2206,5],"0":[2001,4]}],[3,0,0,0,{},{"2":[392,2],"1":[1099,6]}],[0,0,0,0,{},{"1":[2383,6]}],[4,0,0,0,{},{"0":[921,8],"2":[96,1]}],[2,0,0,0,{},{"2":[1447,10],"1":[10946,16]}],[2,0,0,0,{},{"0":[2251,5]}],[0,0,0,0,{},{"1":[3163,6]}],[0,0,0,0,{},{"1":[1213,6]}],[0,0,0,0,{},{"1":[2360,6]}],[0,0,0,0,{},{"0":[1345,3],"2":[758,2]}],[2,0,0,0,{},{"2":[519,3],"1":[2084,6]}],[0,0,0,0,{},{"1":[3343,6]}],[0,0,0,0,{},{"1":[2349,5],"2":[1073,3]}],[0,0,0,0,{},{"1":[1475,6]}],[2,0,0,0,{},{"1":[978,6]}],[3,0,0,0,{},{"2":[238,3],"0":[1050,4]}],[5,0,0,0,{},{"2":[801,12],"1":[2436,15],"0":[596,4]}],[4,0,0,0,{},{"0":[585,5]}],[0,0,0,0,{},{"1":[3832,9]}],[4,0,0,0,{},{"0":[568,5]}],[0,0,0,0,{},{"1":[2734,5]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"1":[216,1],"2":[188,1],"0":[2360,5]}],[0,0,0,0,{},{"1":[3257,6]}],[2,0,0,0,{},{"0":[2090,5]}],[4,0,0,0,{},{"0":[703,5]}],[0,0,0,0,{},{"0":[3342,5]}],[4,0,0,0,{},{"0":[546,5]}],[4,0,0,0,{},{"0":[2180,15],"2":[67,1]}],[0,0,0,0,{},{"0":[898,3],"2":[993,3]}],[0,0,0,0,{},{"1":[2500,6]}],[4,0,0,0,{},{"0":[585,5]}],[0,0,0,0,{},{"1":[5548,12]}],[3,0,0,0,{},{"1":[1714,6]}],[3,0,0,0,{},{"1":[1706,12]}],[0,0,0,0,{},{"1":[1198,5]}],[0,0,0,0,{},{"1":[3439,6]}],[0,0,0,0,{},{"1":[3700,6]}],[0,0,0,0,{},{"0":[2705,4],"2":[232,1]}],[0,0,0,0,{},{"1":[3691,6]}],[0,0,0,0,{},{"1":[2714,12]}],[2,0,0,0,{},{"0":[2500,5]}],[1,0,0,0,{},{"0":[2134,4]}],[0,0,0,0,{},{"1":[5971,6]}],[0,0,0,0,{},{"1":[1033,6]}],[0,0,0,0,{},{"1":[2783,6]}],[0,0,0,0,{},{"1":[2959,6]}],[1,0,0,0,{},{"0":[1145,6],"1":[1440,6],"2":[1262,6]}],[0,0,0,0,{},{"1":[1714,6]}],[0,0,0,0,{},{"0":[2092,4],"2":[1090,3]}],[1,0,0,0,{},{"0":[3338,6],"2":[534,1]}],[3,0,0,0,{},{"1":[2067,6]}],[2,0,0,0,{},{"1":[2907,6]}],[4,0,0,0,{},{"0":[404,5]}],[1,0,0,0,{},{"1":[641,6]}],[0,0,0,0,{},{"0":[2606,5],"2":[189,1]}],[0,0,0,0,{},{"1":[3512,6],"2":[1234,2]}],[3,0,0,0,{},{"0":[1417,6],"1":[808,5],"2":[499,3]}],[0,0,0,0,{},{"1":[5312,9]}],[1,0,0,0,{},{"0":[1180,4]}],[3,0,0,0,{},{"1":[1460,11]}],[4,0,0,0,{},{"0":[511,5]}],[0,0,0,0,{},{"0":[2015,6],"1":[1991,6]}],[4,0,0,0,{},{"0":[539,5]}],[4,0,0,0,{},{"0":[351,5]}],[4,0,0,0,{},{"0":[476,5],"2":[50,1]}],[6,0,0,0,{},{"0":[3000,5],"2":[513,1]}],[2,0,0,0,{},{"0":[2471,5]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[2500,5]}],[3,0,0,0,{},{"0":[1845,4]}],[4,0,0,0,{},{"0":[1046,5]}],[2,0,0,0,{},{"2":[1045,2],"0":[4515,6]}],[4,0,0,0,{},{"2":[112,2],"0":[945,5]}],[2,0,0,0,{},{"1":[4854,6]}],[0,0,0,0,{},{"1":[1788,6]}],[0,0,0,0,{},{"1":[2398,6]}],[3,0,0,0,{},{"0":[557,4]}],[2,0,0,0,{},{"0":[4319,5]}],[0,0,0,0,{},{"0":[2926,3],"2":[300,1]}],[6,0,0,0,{},{"2":[439,2]}],[2,0,0,0,{},{"1":[5991,6]}],[0,0,0,0,{},{"1":[2227,6]}],[2,0,0,0,{},{"1":[2368,6]}],[4,0,0,0,{},{"0":[1458,5]}],[0,0,0,0,{},{"0":[3690,5],"2":[347,1]}],[0,0,0,0,{},{"1":[3350,6]}],[4,0,0,0,{},{"0":[571,5]}],[4,0,0,0,{},{"0":[443,5]}],[1,0,0,0,{},{"2":[1258,5],"0":[1532,4]}],[3,0,0,0,{},{"1":[1633,8]}],[3,0,0,0,{},{"0":[2604,6],"1":[3800,6],"2":[672,3]}],[4,0,0,0,{},{"0":[329,5]}],[3,0,0,0,{},{"2":[636,2],"1":[2726,6]}],[2,0,0,0,{},{"0":[1405,6]}],[3,0,0,0,{},{"1":[2591,6]}],[2,0,0,0,{},{"0":[1388,6]}],[3,0,0,0,{},{"1":[1225,6]}],[3,0,0,0,{},{"1":[3495,6]}],[0,0,0,0,{},{"1":[3381,6]}],[0,0,0,0,{},{"1":[8999,14]}],[2,0,0,0,{},{"0":[2221,6]}],[2,0,0,0,{},{"0":[771,6],"1":[563,6]}],[1,0,0,0,{},{"2":[1439,5],"0":[1521,4]}],[0,0,0,0,{},{"1":[4129,6]}],[0,0,0,0,{},{"1":[2101,6],"2":[1469,3]}],[2,0,0,0,{},{"0":[2939,6]}],[3,0,0,0,{},{"1":[3634,6]}],[3,0,0,0,{},{"1":[2341,6]}],[0,0,0,0,{},{"1":[4327,6]}],[2,0,0,0,{},{"0":[3773,5]}],[1,0,0,0,{},{"1":[2463,6]}],[2,0,0,0,{},{"0":[2265,5]}],[3,0,0,0,{},{"2":[526,2],"1":[3000,6]}],[4,0,0,0,{},{"0":[324,5]}],[4,0,0,0,{},{"0":[360,5]}],[4,0,0,0,{},{"0":[761,5]}],[0,0,0,0,{},{"1":[757,7]}],[4,0,0,0,{},{"0":[1076,5]}],[4,0,0,0,{},{"0":[1876,15],"2":[55,1]}],[4,0,0,0,{},{"0":[1808,11],"2":[75,1]}],[0,0,0,0,{},{"1":[4652,6]}],[0,0,0,0,{},{"0":[4028,5],"2":[1199,3]}],[4,0,0,0,{},{"0":[505,5]}],[4,0,0,0,{},{"0":[535,5]}],[4,0,0,0,{},{"0":[714,5]}],[0,0,0,0,{},{"1":[2320,6]}],[2,0,0,0,{},{"0":[2098,5]}],[0,0,0,0,{},{"1":[2417,6]}],[0,0,0,0,{},{"0":[2531,3],"2":[485,1]}],[4,0,0,0,{},{"0":[370,5]}],[2,0,0,0,{},{"0":[2409,5]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[3148,6]}],[4,0,0,0,{},{"0":[631,5]}],[4,0,0,0,{},{"0":[516,5]}],[3,0,0,0,{},{"1":[2091,6]}],[2,0,0,0,{},{"0":[2272,5]}],[2,0,0,0,{},{"0":[2488,5],"2":[209,1]}],[3,0,0,0,{},{"1":[2266,6]}],[4,0,0,0,{},{"0":[1851,12],"2":[66,1]}],[0,0,0,0,{},{"1":[4196,6]}],[0,0,0,0,{},{"1":[815,6]}],[0,0,0,0,{},{"1":[1092,5]}],[0,0,0,0,{},{"1":[1588,5]}],[1,0,0,0,{},{"0":[1968,4]}],[4,0,0,0,{},{"0":[482,5]}],[4,0,0,0,{},{"0":[604,5]}],[4,0,0,0,{},{"0":[463,5]}],[4,0,0,0,{},{"2":[140,2],"0":[722,5],"1":[329,4]}],[3,0,0,0,{},{"1":[753,6]}],[2,0,0,0,{},{"0":[710,6]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"0":[1857,6],"1":[2896,6]}],[3,0,0,0,{},{"1":[1504,6]}],[3,0,0,0,{},{"1":[2656,6]}],[3,0,0,0,{},{"1":[2151,6]}],[3,0,0,0,{},{"1":[3069,6]}],[0,0,0,0,{},{"1":[3409,6]}],[0,0,0,0,{},{"1":[1216,6]}],[2,0,0,0,{},{"0":[2308,5]}],[4,0,0,0,{},{"0":[479,5]}],[3,0,0,0,{},{"1":[3541,6]}],[4,0,0,0,{},{"0":[1236,10],"2":[62,1]}],[4,0,0,0,{},{"2":[112,2],"0":[489,5]}],[6,0,0,0,{},{"2":[382,4]}],[0,0,0,0,{},{"1":[1787,6],"2":[1254,3]}],[4,0,0,0,{},{"0":[552,5]}],[4,0,0,0,{},{"0":[771,4]}],[3,0,0,0,{},{"1":[2968,6]}],[0,0,0,0,{},{"1":[1256,6]}],[0,0,0,0,{},{"1":[12770,35]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[672,5]}],[2,0,0,0,{},{"1":[2213,6]}],[0,0,0,0,{},{"1":[2513,12]}],[2,0,0,0,{},{"0":[2268,6]}],[2,0,0,0,{},{"0":[827,5]}],[0,0,0,0,{},{"1":[1071,5]}],[0,0,0,0,{},{"1":[2417,6]}],[4,0,0,0,{},{"0":[561,5]}],[0,0,0,0,{},{"1":[2223,6],"2":[424,2]}],[2,0,0,0,{},{"0":[786,2]}],[0,0,0,0,{},{"1":[2597,6]}],[4,0,0,0,{},{"0":[266,4]}],[4,0,0,0,{},{"0":[2107,10],"2":[54,1]}],[0,0,0,0,{},{"1":[3482,6]}],[2,0,0,0,{},{"0":[1549,6]}],[2,0,0,0,{},{"0":[1130,6]}],[0,0,0,0,{},{"0":[2355,3],"2":[1722,3]}],[0,0,0,0,{},{"1":[1052,6]}],[3,0,0,0,{},{"0":[676,4]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[857,6]}],[2,0,0,0,{},{"0":[1720,6],"1":[4363,6],"2":[315,3]}],[2,0,0,0,{},{"1":[1343,6]}],[0,0,0,0,{},{"0":[3020,6],"1":[2832,6]}],[2,0,0,0,{},{"1":[3354,6]}],[2,0,0,0,{},{"0":[3251,5]}],[2,0,0,0,{},{"2":[201,2],"0":[2762,6]}],[0,0,0,0,{},{"1":[3344,6]}],[0,0,0,0,{},{"0":[3920,5],"2":[559,2]}],[0,0,0,0,{},{"1":[1437,6]}],[3,0,0,0,{},{"1":[1353,6]}],[4,0,0,0,{},{"0":[537,5]}],[0,0,0,0,{},{"1":[4331,6],"2":[1369,3]}],[2,0,0,0,{},{"0":[2106,5]}],[0,0,0,0,{},{"0":[1393,6],"1":[3549,6]}],[2,0,0,0,{},{"0":[951,5]}],[0,0,0,0,{},{"1":[3000,6],"2":[1233,3]}],[0,0,0,0,{},{"1":[5209,10]}],[4,0,0,0,{},{"1":[274,3],"0":[682,5]}],[2,0,0,0,{},{"0":[1343,6]}],[4,0,0,0,{},{"0":[730,5]}],[4,0,0,0,{},{"0":[759,5]}],[2,0,0,0,{},{"1":[4580,6]}],[0,0,0,0,{},{"1":[1724,10]}],[2,0,0,0,{},{"0":[4974,5]}],[4,0,0,0,{},{"0":[510,5]}],[0,0,0,0,{},{"1":[5499,6],"2":[1677,3]}],[3,0,0,0,{},{"2":[489,2],"1":[1520,6]}],[4,0,0,0,{},{"0":[605,5]}],[0,0,0,0,{},{"1":[5771,6]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[1210,6]}],[0,0,0,0,{},{"1":[8942,9]}],[1,0,0,0,{},{"1":[1481,6]}],[0,0,0,0,{},{"1":[1286,6],"2":[418,3]}],[3,0,0,0,{},{"1":[824,6]}],[0,0,0,0,{},{"0":[1627,3],"2":[174,1]}],[4,0,0,0,{},{"0":[390,4],"2":[41,1]}],[2,0,0,0,{},{"0":[2500,5]}],[4,0,0,0,{},{"0":[683,5],"2":[50,1]}],[0,0,0,0,{},{"0":[790,6],"1":[770,6]}],[4,0,0,0,{},{"0":[664,9]}],[1,0,0,0,{},{"0":[1758,4],"2":[921,3]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[3105,6]}],[4,0,0,0,{},{"0":[281,5],"2":[144,3]}],[2,0,0,0,{},{"0":[625,6]}],[4,0,0,0,{},{"0":[350,5]}],[3,0,0,0,{},{"1":[2853,6]}],[0,0,0,0,{},{"1":[4278,12]}],[0,0,0,0,{},{"0":[1523,6],"1":[4581,6]}],[3,0,0,0,{},{"0":[1642,4]}],[0,0,0,0,{},{"0":[4790,5],"2":[1208,3]}],[2,0,0,0,{},{"0":[1059,6]}],[0,0,0,0,{},{"1":[3175,12]}],[0,0,0,0,{},{"0":[2683,4],"2":[1236,4]}],[0,0,0,0,{},{"1":[1423,6]}],[1,0,0,0,{},{"0":[1438,4],"2":[299,1]}],[0,0,0,0,{},{"0":[1259,6],"1":[1563,6]}],[2,0,0,0,{},{"0":[3548,5]}],[2,0,0,0,{},{"1":[2346,6]}],[0,0,0,0,{},{"1":[1497,6]}],[2,0,0,0,{},{"2":[261,2],"0":[2463,5]}],[0,0,0,0,{},{"1":[3000,6]}],[0,0,0,0,{},{"1":[3480,6]}],[0,0,0,0,{},{"1":[3736,7]}],[2,0,0,0,{},{"2":[108,1],"1":[260,1],"0":[3443,5]}],[4,0,0,0,{},{"0":[701,5]}],[0,0,0,0,{},{"1":[1711,6]}],[4,0,0,0,{},{"0":[1059,9],"2":[35,1]}],[0,0,0,0,{},{"1":[5788,9]}],[0,0,0,0,{},{"1":[1287,6]}],[0,0,0,0,{},{"1":[1737,6]}],[4,0,0,0,{},{"0":[691,5]}],[1,0,0,0,{},{"2":[1681,5],"0":[5557,7]}],[4,0,0,0,{},{"0":[380,5]}],[2,0,0,0,{},{"0":[1682,5]}],[2,0,0,0,{},{"2":[561,2],"0":[2499,5]}],[4,0,0,0,{},{"0":[424,4]}],[4,0,0,0,{},{"0":[1197,5]}],[0,0,0,0,{},{"1":[3477,6]}],[2,0,0,0,{},{"0":[2285,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"0":[3689,4],"2":[455,1]}],[2,0,0,0,{},{"0":[2491,5],"2":[445,1]}],[2,0,0,0,{},{"2":[295,2],"0":[2254,5]}],[0,0,0,0,{},{"1":[5609,6]}],[2,0,0,0,{},{"0":[3499,5]}],[0,0,0,0,{},{"1":[2957,6]}],[2,0,0,0,{},{"0":[589,5]}],[4,0,0,0,{},{"0":[265,5]}],[0,0,0,0,{},{"1":[3478,6]}],[4,0,0,0,{},{"2":[71,2],"0":[497,5]}],[4,0,0,0,{},{"0":[359,5]}],[0,0,0,0,{},{"1":[1297,6]}],[2,0,0,0,{},{"2":[385,2],"0":[3424,5]}],[2,0,0,0,{},{"2":[647,3],"0":[3694,5]}],[2,0,0,0,{},{"1":[2031,6]}],[4,0,0,0,{},{"0":[668,4],"2":[52,1]}],[0,0,0,0,{},{"1":[4800,6]}],[4,0,0,0,{},{"0":[461,5]}],[0,0,0,0,{},{"1":[6000,6]}],[0,0,0,0,{},{"0":[932,6],"1":[1821,6]}],[0,0,0,0,{},{"1":[1494,6]}],[3,0,0,0,{},{"1":[2309,6]}],[0,0,0,0,{},{"0":[3880,5],"2":[1866,3]}],[4,0,0,0,{},{"0":[461,4]}],[0,0,0,0,{},{"1":[3602,10]}],[4,0,0,0,{},{"0":[552,5]}],[2,0,0,0,{},{"0":[2500,5]}],[2,0,0,0,{},{"0":[1166,6]}],[0,0,0,0,{},{"1":[2582,6]}],[4,0,0,0,{},{"1":[623,3]}],[0,0,0,0,{},{"1":[3139,7]}],[2,0,0,0,{},{"0":[2296,5]}],[4,0,0,0,{},{"0":[366,5]}],[4,0,0,0,{},{"0":[400,5]}],[2,0,0,0,{},{"0":[2500,5]}],[0,0,0,0,{},{"1":[1585,7]}],[4,0,0,0,{},{"0":[554,5],"2":[44,1]}],[2,0,0,0,{},{"0":[3388,5]}],[4,0,0,0,{},{"0":[346,5]}],[0,0,0,0,{},{"1":[8513,12]}],[0,0,0,0,{},{"1":[2447,6]}],[0,0,0,0,{},{"1":[2645,6]}],[0,0,0,0,{},{"1":[1830,6]}],[0,0,0,0,{},{"1":[1024,6]}],[0,0,0,0,{},{"1":[4954,12]}],[4,0,0,0,{},{"1":[234,3],"0":[332,4]}],[4,0,0,0,{},{"2":[93,2],"0":[563,5]}],[2,0,0,0,{},{"0":[2143,5],"2":[155,1]}],[0,0,0,0,{},{"1":[2363,6]}],[0,0,0,0,{},{"1":[4453,6]}],[0,0,0,0,{},{"0":[3470,4],"2":[701,1]}],[3,0,0,0,{},{"1":[1543,6]}],[0,0,0,0,{},{"1":[2577,12]}],[0,0,0,0,{},{"1":[5429,6]}],[4,0,0,0,{},{"0":[340,5]}],[2,0,0,0,{},{"1":[9501,12],"2":[1621,13],"0":[2135,5]}],[4,0,0,0,{},{"0":[664,5]}],[4,0,0,0,{},{"0":[669,5]}],[4,0,0,0,{},{"0":[855,5]}],[0,0,0,0,{},{"1":[3605,10]}],[3,0,0,0,{},{"0":[1753,4]}],[4,0,0,0,{},{"0":[403,5],"2":[47,1]}],[2,0,0,0,{},{"1":[3927,6]}],[4,0,0,0,{},{"0":[570,5]}],[0,0,0,0,{},{"1":[2913,6]}],[4,0,0,0,{},{"0":[408,5]}],[4,0,0,0,{},{"0":[578,5]}],[0,0,0,0,{},{"0":[4955,5],"2":[724,1]}],[4,0,0,0,{},{"0":[561,5]}],[3,0,0,0,{},{"0":[1742,4]}],[0,0,0,0,{},{"0":[2818,3],"2":[967,3]}],[0,0,0,0,{},{"1":[2326,6]}],[2,0,0,0,{},{"0":[1946,6]}],[4,0,0,0,{},{"0":[553,5]}],[0,0,0,0,{},{"0":[2281,3]}],[0,0,0,0,{},{"1":[2014,6]}],[2,0,0,0,{},{"0":[2584,5],"1":[5499,6]}],[2,0,0,0,{},{"0":[1385,6]}],[0,0,0,0,{},{"1":[4389,6]}],[4,0,0,0,{},{"0":[156,4]}],[4,0,0,0,{},{"0":[726,5]}],[4,0,0,0,{},{"0":[620,5]}],[4,0,0,0,{},{"0":[320,4]}],[4,0,0,0,{},{"0":[507,5]}],[2,0,0,0,{},{"0":[2533,6]}],[3,0,0,0,{},{"0":[699,4]}],[4,0,0,0,{},{"0":[458,5]}],[4,0,0,0,{},{"0":[514,5]}],[4,0,0,0,{},{"0":[497,5]}],[2,0,0,0,{},{"0":[2327,5]}],[5,0,0,0,{},{"2":[323,2]}],[2,0,0,0,{},{"0":[4357,7]}],[4,0,0,0,{},{"0":[792,5]}],[3,0,0,0,{},{"0":[1661,4]}],[3,0,0,0,{},{"1":[2088,6]}],[4,0,0,0,{},{"0":[773,5]}],[1,0,0,0,{},{"0":[6120,8],"2":[1506,3]}],[0,0,0,0,{},{"0":[1682,3],"2":[1932,3]}],[4,0,0,0,{},{"0":[466,5]}],[0,0,0,0,{},{"1":[2090,6]}],[0,0,0,0,{},{"1":[1634,6]}],[2,0,0,0,{},{"0":[1659,6],"1":[1121,6]}],[2,0,0,0,{},{"2":[72,1],"1":[897,6]}],[2,0,0,0,{},{"1":[5340,6]}],[0,0,0,0,{},{"1":[10650,11]}],[6,0,0,0,{},{"2":[580,2]}],[0,0,0,0,{},{"0":[2335,6],"1":[2113,6]}],[2,0,0,0,{},{"0":[2951,6]}],[4,0,0,0,{},{"0":[500,5]}],[0,0,0,0,{},{"1":[1111,6]}],[1,0,0,0,{},{"1":[5588,6]}],[1,0,0,0,{},{"2":[1826,5],"0":[2496,4]}],[1,0,0,0,{},{"2":[1721,4],"0":[2432,4]}],[1,0,0,0,{},{"2":[1014,5],"0":[3053,6]}],[1,0,0,0,{},{"2":[2060,5],"0":[3133,4]}],[1,0,0,0,{},{"2":[1775,5],"0":[1907,4]}],[4,0,0,0,{},{"1":[801,3]}],[1,0,0,0,{},{"1":[472,3]}],[1,0,0,0,{},{"0":[2193,6]}],[1,0,0,0,{},{"0":[4172,8]}],[1,0,0,0,{},{"0":[2479,12]}],[1,0,0,0,{},{"0":[4534,6],"2":[309,1]}],[1,0,0,0,{},{"0":[2673,6],"2":[1160,3]}],[1,0,0,0,{},{"0":[2396,6],"2":[134,1]}],[1,0,0,0,{},{"0":[2404,6],"2":[248,1]}],[1,0,0,0,{},{"0":[1828,6]}],[1,0,0,0,{},{"0":[2526,4]}],[1,0,0,0,{},{"0":[4630,6],"2":[1379,3]}],[1,0,0,0,{},{"0":[3990,6],"2":[238,1]}],[1,0,0,0,{},{"0":[3485,5],"2":[516,1]}],[1,0,0,0,{},{"0":[2709,6],"2":[802,3]}],[1,0,0,0,{},{"0":[3611,6],"2":[1097,3]}],[1,0,0,0,{},{"0":[1897,6],"2":[260,2]}],[1,0,0,0,{},{"0":[2757,6],"2":[177,1]}],[1,0,0,0,{},{"0":[1623,6]}],[1,0,0,0,{},{"0":[3486,6],"2":[1006,3]}],[1,0,0,0,{},{"0":[1684,6],"2":[310,1]}],[1,0,0,0,{},{"0":[3942,6],"2":[206,1]}],[1,0,0,0,{},{"0":[2017,6],"2":[1074,3]}],[1,0,0,0,{},{"0":[4495,6],"2":[865,3]}],[1,0,0,0,{},{"0":[3063,4]}]],"bin":50,"xmax":1000,"threshold":200,"heat":{"models":["z-ai/glm-5.3-flash","google/gemini-3.8-flash","google/gemini-4-argon"],"catalogs":["ProgramBench","System design","Diagnosis, Debugging, and Bug Fixing","Feature implementation","Infrastructure as code","Data engineering","Migration"],"minTasks":5,"cells":[[0,1,2407,[0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1111,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0714,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1429,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1111,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1429,0.1429,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667]],[0,0,584,[0.1366,0.0559,0.1183,0.0821,0.059,0.0,0.3733,0.0,0.0,0.0,0.0,0.1667,0.5746,0.0,0.0,0.2589,0.0,0.0,0.6882,0.0,0.1305,0.0,0.188,0.0724,0.3661,0.0,0.0,0.0,0.0875,0.0,0.1318,0.1167,0.1669,0.0,0.2064,0.0,0.3333,0.0,0.0,0.1502,0.0,0.0,0.0,0.0176,0.0,0.0637,0.0,0.0,0.0,0.0389,0.0,0.0,0.1649,0.1781,0.0,0.3846,0.0,0.0603,0.0,0.0,0.0,0.0,0.1667,0.0,0.0532,0.0,0.0,0.0,0.0,0.033,0.0147,0.0,0.0,0.0,0.0,0.1827,0.0,0.0,0.0,0.0,0.0047,0.0877,0.0484,0.0,0.0755,0.0,0.0,0.0851,0.2647,0.163,0.0,0.0,0.0,0.4478,0.0,0.134,0.3007,0.0,0.0,0.2667,0.2221,0.027,0.1444,0.0,0.0,0.0,0.147,0.0,0.0,0.0,0.0,0.1605,0.0,0.3333,0.059,0.0,0.0,0.1014,0.2474,0.0,0.3974,0.0,0.0]],[0,2,281,[0.8451,0.4229,0.6731,0.0,0.3577,0.7524,0.0,0.5,0.7544,1.0,0.7922,0.0,0.7739,0.0,1.0,0.1456,0.9402,0.0353,0.4387,0.0,0.0,0.0,0.9459,0.0,0.4125,0.271,0.2278,0.6395,0.0,1.0,0.0,0.236,0.0,0.0,0.1335,0.0,0.0,0.3254,0.6403,0.0,0.9342,0.1315,0.0,0.0,0.1703,0.9086,0.774,0.7477,0.8154,0.5714,1.0,0.3269,0.0,0.0,0.0,0.3939,0.0483,0.3333,0.9487,0.4282,0.0,0.7882,0.3333,0.6414,0.8291,0.0,0.9615,0.5,0.0,0.0,0.5,0.8706,0.3947,0.6992,0.0,0.9559,0.3736,0.5147,0.4609,0.0,0.0,0.0816,0.0,0.1212,0.52,0.4505,1.0,0.5,0.8923,0.8961,0.0,0.0936,0.7167,0.0,0.0,0.0,0.5546,0.0,0.3333,0.3333,0.0,0.9574,0.5556,0.0,0.6038,0.0,0.9054,0.8626,0.1594,0.0]],[1,0,442,[0.75,0.25,0.5,0.5,0.5,0.25,0.5,0.125,0.625,0.0,0.3333,0.5,0.0,0.0,0.6,0.25,0.0,1.0,0.75,1.0,0.25,0.1667,0.75,0.5,0.0,0.6667,0.5,0.2,0.0,0.25,0.3333,0.1667,0.0,0.0,0.25,0.25,0.25,0.75,0.0,0.5,0.25,0.75,0.1667,0.3333,0.75,0.25,0.25,0.75,0.25,0.25,0.1429,0.125,0.0,0.0,0.5,0.5,1.0,0.6667,0.625,0.0833,0.3333,0.3333,0.3333,0.3333,0.6667,0.75,0.5,0.1667,0.4,0.3333,0.3333,0.3333,0.1667,0.6667,0.1667,0.1667,0.5,0.5,0.1667,0.25]],[1,2,195,[0.8,1.0,1.0,1.0,0.0,1.0,1.0,0.0,0.2,1.0,0.0,0.0,1.0,0.0,0.2,0.2,1.0,0.0,1.0,0.8,0.0,0.2,0.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,1.0,1.0,0.0,1.0,0.8,0.0,0.0,1.0,0.6,0.0,0.2,0.75,0.2,0.8,1.0,1.0,0.6667,1.0,1.0,0.3333,1.0,1.0,0.0,0.0,0.5,1.0,0.3333,1.0,1.0,0.0,0.3333]],[1,1,143,[0.0,0.0,0.0667,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0]],[2,0,1426,[0.0,0.1992,0.9104,0.2,0.7278,0.0,0.8917,0.4605,0.0,0.5579,0.0,0.6918,0.0,0.0,0.7227,0.5449,0.497,0.3617,0.6638,0.8918,0.0,0.6158,0.0,0.2233,0.7562,0.7222,0.0,0.0,0.0,0.0,0.2455,0.889,0.5724,0.6733,0.6667,0.6,0.3456,0.0,0.5287,0.0,0.4,0.0,0.0,0.0,0.0,0.0,0.0,0.7735,0.0,0.0,0.5222,0.0,0.0,0.1133,0.0,0.0,0.1069,0.0,0.0,0.2,0.6057,0.6698,0.0,0.0,0.0,0.0,0.6531,0.0,0.0,0.0,0.9332,0.4,0.0,0.0,0.6,0.0,0.0,0.0,0.0,0.0,0.5518,0.6,0.5058,0.8,0.6446,0.6,0.0,0.8962,0.0,0.9313,0.2,0.0,0.6955,0.0,0.6,0.0,0.7251,0.0,0.0,0.0,0.0,0.7774,0.8358,0.4,0.8411,0.0,0.0,0.0,0.0,0.2,0.6033,0.0,0.2,0.4865,0.2,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.765,0.8944,0.8829,0.0,0.7567,0.0,0.0,0.7587,0.0,0.8026,0.8,0.5355,0.67,0.0,0.2,0.7048,0.8381,0.2384,0.0,0.9381,0.0,0.0,0.0,0.0,0.1067,0.6641,0.0,0.2924,0.0,0.0,0.0,0.2285,0.7176,0.6753,0.0,0.7381,0.5472,0.0,0.8444,0.0,0.0,0.559,0.4,0.8024,0.0,0.5055,0.4475,0.0,0.0,0.606,0.0,0.6545,0.0,0.0,0.0,0.0,0.9973,0.0,0.0,0.2,0.3434,0.5324,0.0,0.0,0.0,0.2,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.9279,0.556,0.2541,0.0,0.4436,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.2,0.604,0.0,0.6,0.0,0.7724,0.6219,0.6066,0.7956,0.8286,0.0,0.7209,0.0,0.0,0.59,0.2,0.544,0.7703,0.0,0.0,0.8358,0.0,0.0,0.9167,0.7084,0.0,0.6,0.2,0.7968,0.0,0.0,0.0,0.2,0.0,0.2131,0.8,0.6,0.4,0.0,0.8218,0.0,0.0,0.0,0.2,0.2,0.6237,0.0,0.4282,0.5971,0.0,0.3662,0.0,0.4468]],[2,1,455,[0.0,0.1667,0.1667,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.6464,0.0,0.1667,0.1667,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0625,0.1667,0.1429,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.125,0.0,0.0,0.0,0.0,0.1667,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.5833,0.0,0.1667,0.0,0.1667,0.0]],[2,2,105,[1.0,0.0,0.5,0.3333,1.0,0.675,0.7812,1.0,0.0,0.0,0.0,1.0,0.0,1.0,1.0,0.0,0.2727,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,1.0,0.6923,1.0]],[3,1,651,[0.0,0.0,0.0,0.0,0.0909,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.125,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0]],[3,0,148,[0.75,0.0,0.0,0.0,0.0,0.0,0.75,0.4,0.0,0.0,0.75,0.5,0.0,0.0,0.0,0.0,0.75,0.0,0.0,0.0,0.25,0.75,0.0,0.25,0.5,0.75,0.5,0.75,0.75]],[3,2,63,[0.0,0.0,0.0,1.0,1.0,0.0,1.0,0.0,0.0,1.0,1.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.0,0.6667,0.0,0.0,0.0,1.0,0.0]],[4,0,1601,[0.4,0.4,0.4,0.8,0.8,0.4,0.8,0.6,0.6,0.8,0.5429,0.6,0.8,0.6667,0.8,0.8,0.7317,0.8,0.8,0.3473,0.8,0.6,0.6,0.6,0.6,0.75,0.75,0.6,0.7864,0.4194,0.8,0.6,0.6,0.9769,0.8,0.796,0.6,0.8,0.6,0.6,0.8,0.8,0.8,0.6,0.2,0.792,0.6,0.6,0.2567,0.375,0.2857,0.5,0.6,0.6,0.75,0.5361,0.8,0.4286,0.8,0.6,0.3857,0.4,0.6,0.8,0.6,0.384,0.75,0.4,0.75,0.8,0.25,0.4,0.5,0.9909,0.6,0.75,0.8,0.6667,0.6,0.5,0.8,0.327,0.8,0.6,0.6,0.75,0.6,0.8,0.6,0.0,0.7957,0.7951,0.9828,0.8,0.6,0.5,0.8,0.9891,0.8,0.4,0.7907,0.95,0.8,0.8,0.6,0.7539,0.8,0.75,0.2,0.4,0.8,0.7318,0.8,0.4286,0.6,0.6,0.6,0.8,0.8,0.8,0.8,0.8,0.8267,0.8,0.8,0.6,0.0,0.4,0.1875,0.75,0.4369,0.4,0.9833,0.6,0.4,0.8,0.8,0.8,0.4,0.8,0.9957,0.6,0.8,0.6,0.4,0.8,0.6,0.6,0.8,0.8,0.9917,0.8,0.9714,0.8,0.8,0.4483,0.7938,0.6,0.3419,0.9958,0.6,0.8,0.8,0.8,0.3975,0.5714,0.4,0.9929,0.8,0.8,0.8,0.8,0.6,0.8,0.5,0.7857,0.8,0.6,0.0,0.6,0.8,0.992,0.6,0.6,0.4,0.8,0.6667,0.6,0.4286,0.8,0.8,0.8,0.0,0.6,0.7862,0.8,0.8,0.6,0.0,0.375,0.8,0.8,0.8,0.8,0.1886,0.6,0.6,0.8,0.8,0.8,0.0,0.8,0.6,0.4,0.8,0.8,0.6,0.8,0.8,0.6,0.9955,0.2643,0.3636,0.8,0.992,0.8,0.8,0.6,0.8,0.4091,0.8,0.8,0.8,0.8,0.8,0.4,0.8,0.8,0.9945,0.7704,0.8,0.75,0.3978,0.9889,0.0,0.8,0.8,0.9655,0.8,0.5,0.4,0.5476,0.4,0.6,0.8,0.3241,0.6,0.8,0.75,0.8,0.984,0.0,0.8,0.5,0.8,0.75,0.6,0.8,0.6,0.4,0.8,0.0,0.4,0.6,0.6,0.8,0.9882,0.4,0.8,0.8,0.6,0.95,0.6,0.75,0.6,0.9935,0.75,0.6,0.8,0.8,0.9692,0.6,0.6,0.6,0.8]],[4,2,122,[1.0,0.5,0.0,1.0,0.4286,0.9655,1.0,1.0,1.0,1.0,1.0,0.5,1.0,0.8333,0.9722,1.0,1.0,0.5,1.0,1.0,1.0,0.5,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,0.3333,1.0,0.2733,0.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,1.0,0.9429,1.0,1.0,1.0,0.9811,1.0,0.0,0.9231,1.0,1.0,1.0,1.0,0.0,1.0,0.5,1.0,1.0,1.0,1.0]],[4,1,77,[1.0,1.0,1.0,0.625,0.6667,0.0,0.6,0.8652,1.0,1.0,1.0,0.0,1.0,0.6667,0.0,0.3333]],[5,2,64,[1.0,1.0,1.0,1.0,0.4167,0.0,1.0,1.0,1.0,1.0,0.0,1.0,1.0,1.0,1.0,0.8333,0.0]],[5,1,54,[0.2,0.4667,0.0,0.6,0.6667]],[5,0,21,[0.75,1.0,0.6,0.75,1.0]],[6,2,36,[0.5,1.0,0.3333,1.0,0.0,0.3333,1.0,1.0,0.0,0.6667,1.0,1.0,0.0,0.3333,0.9948,0.0,0.75,1.0]],[6,0,24,[0.0,0.241,0.2945,0.2399,0.5364]],[6,1,9,[0.0,0.0,0.0,0.0,0.0]]]}}</script>
<script>// Interactive charts for the catalog site. Each page carries one JSON data block; charts on a page share a store,
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
        h('div', 'cx-panel-foot', p.el, fmt(tot) + ' tasks' + (tot < S.tasks.length ? ' after filters' : ''));
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
  // ---- per-task average reward by model: box plot with one dot per task ----
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
    var svg = el('svg', { 'class': 'cx-svg', role: 'img', 'aria-label': 'Per-task average reward by model' }, box);
    h('p', 'cx-hint', box, 'Each dot is one task: its average grader score over a model\'s graded runs. Boxes span the middle half of tasks, the line is the median and the diamond the average. Drag the edges of the shaded band to change it. Hover a dot for its runs; click it for the task.');
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
        return { m: m, pts: pts, vs: vs, q1: quant(vs, 0.25), q2: quant(vs, 0.5), q3: quant(vs, 0.75), mu: mean(vs) };
      }).filter(function (r) { return r.pts.length; });
      rows.sort(function (a, b) { return (b.q3 - a.q3) || (b.q2 - a.q2) || (b.mu - a.mu); });
      var H = T + Math.max(1, rows.length) * ROW + B; svg.setAttribute('viewBox', '0 0 ' + W + ' ' + H); clear(gC); lastH = H; place();
      for (var v = 0; v <= 1.0001; v += 0.1) { el('line', { x1: x(v), x2: x(v), y1: T - 10, y2: H - B, stroke: 'var(--line-2)' }, gC); el('text', { x: x(v), y: H - B + 18, 'text-anchor': 'middle', 'class': 'cx-tick' }, gC, Math.round(100 * v) + '%'); }
      el('text', { x: (L + W - R) / 2, y: H - 6, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'Per-task average reward');
      if (!rows.length) el('text', { x: (L + W - R) / 2, y: T + 30, 'text-anchor': 'middle', 'class': 'cx-axis' }, gC, 'No graded runs for the selected models and filters');
      rows.forEach(function (r, j) {
        var cy = T + j * ROW + ROW / 2, g = el('g', {}, gC);
        el('text', { x: L - 14, y: cy - 2, 'text-anchor': 'end', 'class': 'cx-rowlab' }, g, r.m.label);
        el('text', { x: L - 14, y: cy + 14, 'text-anchor': 'end', 'class': 'cx-tick' }, g, fmt(r.pts.length) + ' tasks, average ' + pc(r.mu));
        var iqr = r.q3 - r.q1, wl = Math.max(r.vs[0], r.q1 - 1.5 * iqr), wh = Math.min(r.vs[r.vs.length - 1], r.q3 + 1.5 * iqr);
        el('line', { x1: x(wl), x2: x(r.q1), y1: cy, y2: cy, stroke: 'var(--ink)' }, g); el('line', { x1: x(r.q3), x2: x(wh), y1: cy, y2: cy, stroke: 'var(--ink)' }, g);
        el('rect', { x: x(r.q1), width: Math.max(1, x(r.q3) - x(r.q1)), y: cy - 14, height: 28, fill: 'var(--card)', stroke: 'var(--ink)' }, g);
        el('line', { x1: x(r.q2), x2: x(r.q2), y1: cy - 14, y2: cy + 14, stroke: 'var(--ink)', 'stroke-width': 2 }, g);
        r.pts.forEach(function (p) {
          var c = el('circle', { cx: x(p.v), cy: cy + jitter(p.i * 7 + r.m.k) * 26, r: focus === p.i ? 5 : 3.2, 'class': 'cx-pt' + (focus === p.i ? ' is-on' : '') }, g);
          c.addEventListener('mousemove', function (e) { t.show('<b>' + esc(r.m.label) + '</b><br>' + p.runs.length + ' graded run' + (p.runs.length > 1 ? 's' : '') + ': ' + p.runs.map(function (s) { return +s.toFixed(2); }).join(', ') + '<br>Average ' + pc(p.v), e); });
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
        D.models.forEach(function (name, k) { var s = tk.r[k]; if (s && s.length) parts.push(esc(name) + ': ' + s.map(function (v) { return +v.toFixed(2); }).join(', ') + ' (average ' + pc(mean(s)) + ')'); });
        detail.innerHTML = parts.join('<br>');
        var x0 = h('button', 'cx-link', detail, 'Close'); x0.type = 'button'; x0.addEventListener('click', function () { focus = null; draw(); });
      }
    }
    function tally() {  // the table under the chart, recomputed for the band
      var rows = lastRows; clear(summary);
      var cap = h('p', 'cx-cap', summary, 'Tasks by per-task average reward, with the band at ' + Math.round(100 * lo) + '-' + Math.round(100 * hi) + '%');
      var gtab = h('div', 'cx-grid cx-grid5', summary); gtab.setAttribute('role', 'table');
      var hr = h('div', 'cx-row cx-head', gtab); ['Model', 'Tasks', 'Average reward', 'Tasks at 0%', 'In the band', 'Tasks at 100%'].forEach(function (s) { h('span', '', hr, s); });
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
      reward: { label: 'Average reward', f: function (c) { return mean(c.pt); }, txt: pc },
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
    h('p', 'cx-hint', box, 'Hover a cell for its numbers; click it for the spread of per-task rewards.');
    var detail = h('div', 'cx-detail', box), t = tip(box); detail.hidden = true;
    var links = fig.querySelectorAll('[data-links] a');
    var C = {}; D.cells.forEach(function (c) { C[c[0] + ':' + c[1]] = { graded: c[2], pt: c[3] }; });
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
            t.show('<b>' + esc(mname) + '</b><br>' + esc(cn) + '<br>' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs<br>Average reward ' + pc(mean(c.pt)) + '<br>Middle half of tasks: ' + pc(quant(s, 0.25)) + ' to ' + pc(quant(s, 0.75)), e);
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
        h('p', 'cx-cap', detail, esc(D.models[ii]) + ' in ' + esc(D.catalogs[jj]) + ': ' + c.pt.length + ' tasks, ' + fmt(c.graded) + ' graded runs, average reward ' + pc(mean(c.pt)));
        var hist = h('div', 'cx-mini', detail);
        bins.forEach(function (n, k) { var col = h('div', 'cx-mini-col', hist); var b = h('div', 'cx-mini-bar', col); b.style.height = (mx ? 100 * n / mx : 0) + '%'; b.title = n + ' tasks'; h('div', 'cx-mini-n', col, String(n)); h('div', 'cx-mini-lab', col, (k * 10) + '-' + (k === 9 ? 100 : k * 10 + 9) + '%'); });
        var foot = h('p', 'cx-hint', detail, 'Tasks by per-task average reward. ');
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
