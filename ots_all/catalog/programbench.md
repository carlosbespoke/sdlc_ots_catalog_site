# ProgramBench

## Executive summary

<div class="kpis"><div class="kpi"><div class="kpi-value">434</div><div class="kpi-label">Tasks</div></div><div class="kpi"><div class="kpi-value">8%</div><div class="kpi-label">z-ai/glm-5.3-flash average reward</div></div><div class="kpi"><div class="kpi-value">1%</div><div class="kpi-label">google/gemini-3.8-flash average reward</div></div><div class="kpi"><div class="kpi-value">43%</div><div class="kpi-label">google/gemini-4-argon average reward</div></div></div>

Each task asks the agent to make software behave exactly like a reference version. In the reimplementation tasks the agent writes a new program from scratch, in a language of its choice, from a reference program and its documentation. In the upgrade tasks the agent brings an existing repository up to the reference's newer release by changing its code. In 19% of tasks the agent chooses the language; the most common fixed languages are Rust (26%) and Go (23%).

Every task has graded runs. The model with the most runs here, google/gemini-3.8-flash, has an average reward of 1% over 2,318 graded runs and scores 0 on every run of 93% of the 353 tasks it ran.

## Why this catalog

### Problems engineers face

Engineers often have to make software behave exactly like a version they cannot reuse: rebuilding a tool whose source is unavailable, or bringing an old codebase up to a newer release. In both cases the specification is observable behaviour. The hard part is inferring the rules from outputs and documentation, then matching exit codes, output, file effects and numeric precision without seeing the tests.

### How the tasks reproduce them

Every task runs offline, and hidden tests compare the result with a reference program the agent can run but not read. For a reimplementation, the agent writes a source project and a `compile.sh` from the reference and its documentation. For an upgrade, the agent changes an existing repository in `/app/repo`, which is built with a fixed `/opt/task/build.sh`.

### Typical prompts

- Reproduce the documented behaviour of an execute-only program, delivered as source code plus `compile.sh`.
- Update an existing repository to match a reference program, after first writing a research and plan file.

## Domain breakdown

The tasks span eight domains. The largest, Languages & developer tooling, makes up 48% of the catalog.

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
| Rust | 26.3% |
| Go | 22.6% |
| Agent's choice | 18.7% |
| C++ | 16.4% |
| C | 16.1% |

### Seniority

| Seniority | % of catalog |
|---|---:|
| Senior | 81.3% |
| Staff+ | 18.7% |

## Model average reward across the catalog

A model's average reward is average@k: on each task, the mean grader score over its graded runs, with partial credit counted as scored; then the mean over the tasks it ran. Runs that errored are left out. Models are listed by number of runs, and a model needs graded runs on five or more tasks for a row.

| Model | Tasks run | Graded runs | Average reward | Tasks at 0% | Tasks at 20-80% | Tasks at 100% |
|---|---:|---:|---:|---:|---:|---:|
| google/gemini-3.8-flash | 353 | 2,318 | 1% | 93% | 0% | 0% |
| z-ai/glm-5.3-flash | 120 | 566 | 8% | 55% | 13% | 0% |
| google/gemini-4-argon | 22 | 84 | 43% | 9% | 68% | 0% |

<div class="cx" data-chart="reward">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Per-task average reward by model</h4></div>
<div class="fig-box" data-body></div>
</div>

## Turn counts and long-horizon tasks

A task's turn count is the average over its completed runs, from every model. A task is long horizon when that average is 200 or more turns. 434 of the 434 tasks have a completed run.

| Measure | Value |
|---|---:|
| Average turn count | 470.9 |
| Median turn count | 423.0 |
| Range | 93 to 1000 |
| Long-horizon tasks (200+ turns) | 89% of tasks |

<div class="cx" data-chart="turns" data-group="Domain">
<div class="fig-head"><span class="lab">Interactive figure</span><h4>Turns per task</h4></div>
<div class="fig-box" data-body></div>
</div>

| Model | % of tasks | Mean turns | % of runs with 200+ turns |
|---|---:|---:|---:|
| google/gemini-3.8-flash | 81% | 437.7 | 81% |
| z-ai/glm-5.3-flash | 28% | 538.6 | 81% |
| google/gemini-4-argon | 5% | 355.5 | 75% |

## Sample tasks

### Example 1: Media processing (Agent's choice)

| Field | Value |
|---|---|
| Task id | [`svtav1-encoder-rebuild`](https://drive.google.com/file/d/1JmlCRxmj-7RJ9yZ698lASh-GGDr2N9Je/view) |
| Final category | ProgramBench reimplementation |
| Domain | Applications & business domains |
| Sub-domain | Media processing |
| Language | Agent's choice |
| Seniority | Staff+ |
| Turn count | 752 (z-ai/glm-5.3-flash), 401 (google/gemini-4-argon) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

###### Task context

Reproduce the documented behavior of the program in this workspace. The reference program is `/opt/task-reference/executable`. Its bundled documentation is available in the workspace. The task runs model commands as the non-root `agent` user. The reference is execute-only for that user, so it can be run but not read, copied, hard-linked, or recovered through `/proc`. A root model shell means the task platform did not honor the declared user and is not part of the task contract.

###### Required result

Write a source code project and an executable `./compile.sh`. Running `./compile.sh` on a fresh checkout must produce `./executable` in the workspace root. The rebuilt executable must match the reference program's observable behavior, including output, exit codes, and file system effects.

You may choose the implementation language and design. You can learn the behavior from the bundled documentation and by running the reference program.

The grader checks only your submission's fresh offline build and its observable behavior. It does not assess your implementation language or how you learned the behavior. Do not include the reference executable's bytes in the submission under another name or embedded inside another file. Do not read or inspect the grader harness, hidden tests, or recorded expectations, even if a platform defect makes them accessible. During grading, the internet, package registries, the reference program, and system copies of the same tool are unavailable. Your build and executable must work without them.

###### Reusable input assets

When `/workspace/assets` exists, it contains hard-to-create reusable inputs
such as media, archives, databases, or custom binary files. You may inspect,
copy, or modify these inputs while recreating the program. Ordinary source and
text inputs are not provided and should be created as needed.

###### How your work is scored

Your executable is graded by replaying many recorded behaviors of the
reference program against it and scoring the fraction that match. A
match always requires the same exit code and the same file system effects.
Plain output and ordinary files are compared byte for byte. JSON output and
JSON files are normally compared as parsed values, so insignificant whitespace
and object key order do not matter unless the documentation makes formatting or
ordering part of the behavior. SQLite files are compared by their logical
contents. Terminal progress output is compared by its final visible text. A
recorded behavior can require exact bytes when formatting or ordering is part
of the documented behavior. Partial credit is the norm, so every additional
behavior you match raises your score, and there is no bonus for finishing early.

###### Coverage to aim for

Grading samples behavior from the documented interface. Only behavior that can be tested reliably in a bounded offline run is graded.

When applicable, support:

- commands, subcommands, options, aliases, and short forms
- representative documented values
- help and version output
- standard input, files, and directories
- configuration files and environment variables
- standard output, standard error, exit codes, and file system effects
- error handling
- empty, non-ASCII, binary, and unusually named inputs

The test suite may not cover every documented behavior.

###### Using the reference program

Run `/opt/task-reference/executable` to observe the reference. The file is
outside the submitted workspace and is unavailable during grading. Your
`./compile.sh` can therefore write `./executable` without replacing the
reference while you work.

###### Before you finish

Passing tests you wrote yourself is not evidence that you are done.
Before you stop:

1. list every option and subcommand in the reference program's help output;
2. for each one, run `/opt/task-reference/executable` and your executable on the
   same input and compare output using the scoring rules above, along with the
   exit code and files written;
3. fix every disagreement you find, then repeat from step 1.

Stop when no disagreement remains or when your budget is spent,
whichever comes first.

</div>
</details>

#### Average reward

| Model | Graded runs | Average reward |
|---|---:|---:|
| z-ai/glm-5.3-flash | 5 | 7% |
| google/gemini-4-argon | 2 | 4% |

#### Environment

![How the task works](assets/env-svtav1-encoder-rebuild.svg)

### Example 2: Build systems (Agent's choice)

| Field | Value |
|---|---|
| Task id | `bazel-gazelle-rebuild` |
| Final category | ProgramBench reimplementation |
| Domain | Build, release & supply chain |
| Sub-domain | Build systems |
| Language | Agent's choice |
| Seniority | Staff+ |
| Turn count | 617 (google/gemini-4-argon) |
| Long horizon | yes |

#### Prompt

<details open><summary>Full instruction given to the agent (instruction.md)</summary>
<div class="prompt-md">

Our build team uses Gazelle to write and update the Bazel BUILD files in our Go and protobuf repositories. We want to add rules of our own to it later, so we need our own version that writes exactly the same BUILD files. All we have is the installed program and its docs, so work out how it behaves by running it.

Build it in `/workspace`. It should work the way the original does for:
- its three commands: `update` (the default), `fix` and `update-repos`
- generating Go and proto rules from the source tree, including build constraints, embeds, cgo options and import naming
- `# gazelle:` directives, and merging into existing BUILD files, including `# keep` comments
- resolving imports to labels, with the rule index and external repositories
- updating repository rules from Go module files
- help and version output, errors, and unusual inputs such as empty files, non-ASCII text and odd file names

The original is at `/opt/reference/executable`. Running `./compile.sh` on a fresh checkout must build `./executable` in `/workspace`. Our builds run in an offline image, so both have to work with no internet, no package registries, and no copy of the original or any other Gazelle. For the same arguments and input, your version must give the same exit code, standard output, standard error and file changes as the original, byte for byte. Write it yourself: don't copy the original program.

`/workspace/README.md` explains how to work with the original and what counts as the same.

</div>
</details>

#### Average reward

| Model | Graded runs | Average reward |
|---|---:|---:|
| google/gemini-4-argon | 5 | 27% |

#### Environment

![How the task works](assets/env-bazel-gazelle-rebuild.svg)

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
<script type="application/json" data-chart-data>{"cross":true,"models":["google/gemini-3.8-flash","z-ai/glm-5.3-flash","google/gemini-4-argon"],"dims":{"g":["Applications & business domains","Build, release & supply chain","Cloud infrastructure & IaC","Data engineering & databases","Languages & developer tooling","Scientific & ML software","Security","Systems, hardware & accelerators"],"c":["AI agents & retrieval","API tooling","Binary analysis","Build systems","CAD / CAM","CI/CD","CLI tooling","Calendaring & recurrence","Cloud infra: AWS platform stacks","Cloud infra: containers & self-hosted platforms","Cloud security & compliance","Compilers & language runtimes","Compression & data integrity","Configuration management","Cryptography & secure protocols","Data formats & serialization","Data validation","Databases & storage engines","Emulators","Filesystems","Fonts & text rendering","Frontend & UI state","Games & game engines","Geospatial","Graph algorithms","Hardware RTL","IoT & smart home","Logic programming","Machine learning & MLOps","Media processing","Memory management","Networking & HTTP","Parser security hardening","Payments & banking","Probabilistic data structures","SQL tooling","Scientific computing","Secret scanning","Secrets & access control","Software supply chain","Text & NLP processing","Web applications","Web crawling"],"l":["Agent's choice","C","C++","Go","Rust"],"s":["Senior","Staff+"]},"tasks":[[4,11,0,1,{"1":[0,0.6831,0,0,0]},{"1":[2155,5]}],[4,11,0,1,{"1":[0.2796,0,0,0,0],"2":[0,0.6237,0.6022,0.6774,0.6344,0]},{"1":[3697,5],"2":[3595,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[2097,6]}],[1,3,3,0,{"0":[0,0,0,0,0,0]},{"0":[1552,6]}],[4,11,0,1,{"1":[0,0.3173,0,0.274,0]},{"1":[4036,5]}],[7,12,2,0,{"0":[0,0,0,0,0,0,0,0]},{"0":[1215,8]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1509,6]}],[4,11,0,1,{"1":[0.2462,0,0]},{"1":[2174,3]}],[3,17,0,1,{"1":[0.1538,0,0.0231]},{"1":[1975,3]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[2521,6]}],[0,29,2,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1422,6],"0":[879,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1414,6]}],[6,14,4,0,{"0":[0,0,0,0,0,0]},{"0":[1523,6]}],[4,11,4,0,{"0":[1,0,0,1,0,0,0,0,0,0,0,0]},{"0":[6676,12]}],[7,12,1,0,{"0":[0,0,0,0,0,0]},{"0":[1637,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[1514,6]}],[4,11,0,1,{"1":[0,0.4762,0,0.619,0.7714],"2":[0.9048,0.8857,0,0.9048,0.9238,0.8952]},{"1":[4147,5],"2":[1662,6]}],[5,36,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0]},{"0":[4925,11]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[1111,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[5604,6]}],[6,2,1,0,{"0":[0,0,0,0,0,0]},{"0":[903,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[1561,6]}],[3,15,4,0,{"0":[0,0,0,0,0,0]},{"0":[1020,6]}],[7,19,1,0,{"0":[0,0,0,0,0,0,0,1,0,0,0,0,0,0]},{"0":[3042,14]}],[1,5,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1295,6],"0":[1550,6]}],[0,29,2,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2592,6],"0":[2919,6]}],[4,6,1,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[2605,9]}],[7,26,1,0,{"0":[0,0,0,0,0,0]},{"0":[945,6]}],[3,17,4,0,{"0":[0,0,0,0,0,0]},{"0":[3215,6]}],[3,15,4,0,{"1":[0,0,0,0,0,0],"0":[0,1,0,0,0,0]},{"1":[1174,6],"0":[1256,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[1336,6]}],[5,23,1,0,{"0":[0,0,0,0,0,0]},{"0":[1756,6]}],[4,27,2,0,{"0":[0,0,0,0]},{"0":[788,4]}],[1,3,1,0,{"0":[0,0,0,0,0,0]},{"0":[1010,6]}],[4,6,1,0,{"1":[0,1,0,0,0,0],"0":[0,0,0,0,0,0,0,0,0,0,0]},{"1":[1226,6],"0":[2932,11]}],[4,11,1,0,{"0":[0,0,0,0,0]},{"0":[2337,5]}],[7,12,0,1,{"2":[1,0],"1":[0.9014,0,0,0.9859,0.9859]},{"2":[175,2],"1":[1934,5]}],[4,11,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1167,6],"0":[1634,6]}],[4,1,4,0,{"0":[0,0,0,0,0,0]},{"0":[6000,6]}],[3,35,4,0,{"0":[0,0,0,0,0,0]},{"0":[5966,6]}],[3,15,3,0,{"0":[0,0,0,0,0,0]},{"0":[887,6]}],[4,6,0,1,{"2":[0.8105,0.6984],"1":[0,0,0.6928,0.3427]},{"2":[976,2],"1":[2835,4]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[6000,6]}],[5,28,0,1,{"1":[0,0,0,0]},{"1":[1796,4]}],[4,1,4,0,{"0":[0,0,0,0,0,0]},{"0":[3495,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1725,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[1308,6]}],[3,15,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2083,6],"0":[2597,6]}],[6,14,3,0,{"0":[0,0,0,0,0,0]},{"0":[2463,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[1345,6]}],[0,33,3,0,{"0":[0,0,0,0,0,0]},{"0":[683,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[2904,12]}],[4,6,0,1,{"1":[0.8627,0.8235,0.9118,0,0.8431],"2":[0.9118,0.9118,0.3333,0.8922,0.9118]},{"1":[3806,5],"2":[936,5]}],[4,6,3,0,{"0":[0,0,0,0,0,0,0,0,0,0,0]},{"0":[7246,11]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[2384,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[1388,6]}],[5,23,2,0,{"0":[0,0,0,0,0,0]},{"0":[2523,6]}],[0,29,4,0,{"0":[0,0,0,0,0,0]},{"0":[5586,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[1746,6]}],[7,12,0,1,{"1":[0,0,0,0]},{"1":[1952,4]}],[1,3,0,1,{"1":[0.2411,0.1773,0.1064,0.1206,0.0071]},{"1":[3488,5]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[685,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[1077,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[1683,6]}],[0,29,0,1,{"1":[0,0,0,0,0]},{"1":[3668,5]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[1385,6]}],[3,15,2,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[7990,9]}],[4,11,0,1,{"1":[0,0,0.5641]},{"1":[1012,3]}],[3,15,1,0,{"0":[0,0,0,0,0,0]},{"0":[1971,6]}],[4,40,1,0,{"0":[0,0,0,0,0,0]},{"0":[606,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0,0,0]},{"0":[1027,8]}],[0,29,0,1,{"2":[0,0.0706],"1":[0,0,0,0,0.362]},{"2":[802,2],"1":[3761,5]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[3161,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1100,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[1855,6]}],[4,11,0,1,{"2":[0,0.8774],"1":[0.4581,0.3097,0.3097,0.3871]},{"2":[645,2],"1":[4000,4]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[857,6]}],[5,23,2,0,{"0":[0,0,0,0,0,0]},{"0":[2510,6]}],[4,11,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2268,6],"0":[5999,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2879,6]}],[4,6,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1513,6],"0":[2737,6]}],[0,7,1,0,{"0":[0,0,0,0,0]},{"0":[4125,5]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[2004,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[2464,6]}],[3,15,4,0,{"0":[0,0,0,0,0,0]},{"0":[1406,6]}],[5,36,0,1,{"1":[0,0,0,0,0]},{"1":[4269,5]}],[5,36,0,1,{"1":[0,0.2626,0]},{"1":[1585,3]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[2468,6]}],[0,29,1,0,{"0":[0,0,1,0,0,0]},{"0":[1069,6]}],[4,11,2,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[3264,6],"0":[5312,6]}],[3,15,0,1,{"1":[0,0,0,0.527]},{"1":[2785,4]}],[3,15,3,0,{"0":[0,0,0,0,0,0]},{"0":[2748,6]}],[1,3,3,0,{"0":[0,0,0,0,0,0]},{"0":[1676,6]}],[5,36,2,0,{"0":[0,0,0,0,0,0]},{"0":[4138,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[2367,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2462,6]}],[4,1,0,1,{"2":[0.825,0],"1":[0,0.5833,0,0,0]},{"2":[377,2],"1":[3879,5]}],[5,4,2,0,{"0":[0,0,0,0,0,0]},{"0":[2102,6]}],[4,1,0,1,{"1":[0.1261,0.1184,0.423,0]},{"1":[3999,4]}],[4,11,0,1,{"1":[0,0,0,0,0]},{"1":[3425,5]}],[0,22,0,1,{"2":[0.6395],"1":[0.314,0.2791,0,0.2326]},{"2":[761,1],"1":[2883,4]}],[4,1,4,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[1334,9]}],[0,29,1,0,{"0":[1,0,0,0,0,0]},{"0":[1596,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[2007,6]}],[7,18,1,0,{"0":[0,0,0,0,0,0]},{"0":[2374,6]}],[0,33,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1481,6],"0":[2643,6]}],[4,11,4,0,{"1":[0,1,0,0,1,0],"0":[0,1,0,0,0,0]},{"1":[1576,6],"0":[1972,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0,0,0,0,0]},{"0":[5768,10]}],[7,30,4,0,{"0":[0,0,0,0,0,0]},{"0":[1665,6]}],[4,27,4,0,{"0":[0,0,0,0,0,0]},{"0":[4496,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[1152,6]}],[4,11,1,0,{"0":[0,0,0,0,0]},{"0":[2512,5]}],[0,20,4,0,{"0":[0,0,0,1,0,0]},{"0":[5944,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[1980,6]}],[6,2,4,0,{"0":[0,0,0,0,0,0]},{"0":[3300,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[1998,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3594,6]}],[5,4,2,0,{"1":[0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1934,5],"0":[2507,6]}],[5,0,4,0,{"0":[0,0,1,0,0,0]},{"0":[3218,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[3836,6]}],[7,25,4,0,{"0":[0,0,0,0,0,0]},{"0":[5922,6]}],[3,16,3,0,{"0":[0,0,0,0,0,0,0,0]},{"0":[1528,8]}],[3,35,0,1,{"1":[0,0,0,0],"2":[0.6977,0,0.7183,0,0,0]},{"1":[3187,4],"2":[831,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[1386,6]}],[3,15,0,1,{"1":[0.1798,0,0.4209,0]},{"1":[3887,4]}],[4,6,1,0,{"0":[0,0,0,0,0,0]},{"0":[5830,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[2726,6]}],[1,3,3,0,{"0":[0,0,0,0,0,0]},{"0":[4200,6]}],[4,11,2,0,{"0":[0,0,0,0,0]},{"0":[1550,5]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[4288,6]}],[0,29,0,1,{"1":[0,0,0,0,0],"2":[0,0,0.2817,0.3858,0]},{"1":[3866,5],"2":[2932,5]}],[1,3,2,0,{"0":[0,0,0,0,0,0]},{"0":[5300,6]}],[0,29,0,1,{"1":[0,0,0]},{"1":[1891,3]}],[2,13,1,0,{"0":[0,0,0,0,0,0]},{"0":[1299,6]}],[4,11,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0,0,0,0,0]},{"1":[1820,6],"0":[7053,10]}],[4,11,0,1,{"1":[0,0,0,0,0.0882]},{"1":[2645,5]}],[4,6,0,1,{"1":[0,0,0,0,0],"2":[0.652,0.619,0.6813,0,0,0]},{"1":[2931,5],"2":[1326,6]}],[7,19,2,0,{"0":[0,0,0,0,0,0]},{"0":[1733,6]}],[5,36,2,0,{"0":[0,0,0,0,0,0]},{"0":[5998,6]}],[4,11,0,1,{"1":[0,0,0,0.2548]},{"1":[2801,4]}],[6,38,3,0,{"0":[0,0,1,0,0,0]},{"0":[1927,6]}],[0,20,4,0,{"1":[0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1685,4],"0":[4746,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[2741,6]}],[0,29,3,0,{"0":[0,0,0,0,0,0]},{"0":[4758,6]}],[7,31,3,0,{"0":[0,0,0,0,0,0]},{"0":[782,6]}],[3,15,3,0,{"0":[0,0,0,0,0,0]},{"0":[1862,6]}],[1,3,2,0,{"0":[0,0,0,0,0,0]},{"0":[2253,6]}],[3,15,2,0,{"0":[0,0,0,0,0,0]},{"0":[556,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1728,6]}],[7,12,2,0,{"0":[0,0,0,0,0,0]},{"0":[2361,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[2425,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1652,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[753,6]}],[6,14,0,1,{"1":[0,0,0]},{"1":[2759,3]}],[7,12,0,1,{"1":[0,0,0,0,0],"2":[0,0,0.6576,0,0]},{"1":[2766,5],"2":[1960,5]}],[0,29,0,1,{"1":[0,0,0.1556,0]},{"1":[3483,4]}],[5,36,2,0,{"0":[0,0,0,0,0,0]},{"0":[6000,6]}],[6,38,4,0,{"0":[0,0,0,0,0,0]},{"0":[1009,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[837,6]}],[0,29,4,0,{"0":[0,0,0,0,0,0]},{"0":[1566,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3440,6]}],[3,15,0,1,{"1":[0,0]},{"1":[1934,2]}],[5,24,2,0,{"0":[0,0,0,0,0,0]},{"0":[1249,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[4523,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[3757,6]}],[4,6,0,1,{"2":[0.9011,0.9161],"1":[0,0,0.4946]},{"2":[373,2],"1":[2645,3]}],[4,6,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[6725,15]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[4285,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[2381,6]}],[7,12,4,0,{"0":[0,0,0,0,0,0]},{"0":[961,6]}],[4,11,0,1,{"1":[0,0.3699,0.4384,0,0.0822],"2":[0.9863,0,0.8767,0.8493,0.9726,0.9589]},{"1":[3470,5],"2":[2214,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[2423,6]}],[3,17,0,1,{"1":[0,0,0,0]},{"1":[1578,4]}],[5,36,1,0,{"0":[0,0,0,0,0,0,0]},{"0":[3355,7]}],[4,11,0,1,{"1":[0.3231,0.3692,0.4308,0.4154,0.3846]},{"1":[3995,5]}],[4,11,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[8620,12]}],[7,19,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1692,6],"0":[1888,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[2678,6]}],[5,36,1,0,{"0":[0,0,0,0,0,0,0]},{"0":[5300,7]}],[7,31,1,0,{"0":[0,0,0,0,0,0]},{"0":[1463,6]}],[6,2,2,0,{"0":[0,0,0,0,0,0]},{"0":[3657,6]}],[4,11,0,1,{"1":[0,0,0.3016,0,0]},{"1":[3776,5]}],[3,15,1,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2296,6],"0":[5967,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[4778,12]}],[4,6,4,0,{"0":[0,0]},{"0":[844,2]}],[6,37,3,0,{"0":[0,0,0,0,0,0]},{"0":[1947,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[4016,6]}],[0,29,1,0,{"0":[0]},{"0":[259,1]}],[4,11,1,0,{"1":[0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[883,5],"0":[3428,6]}],[4,1,2,0,{"0":[0,0,0,0,0,0]},{"0":[1113,6]}],[3,15,3,0,{"0":[0,0,0,0,0,0]},{"0":[2688,6]}],[4,40,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[7163,16]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[2094,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[1699,6]}],[0,29,0,1,{"1":[0,0]},{"1":[1023,2]}],[4,1,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2858,6],"0":[3693,6]}],[3,15,1,0,{"1":[0,0,0,0,0,1],"0":[0,0,0,0,0,0]},{"1":[1032,6],"0":[1451,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[3515,9]}],[3,15,3,0,{"0":[0,0,0,0,0,0]},{"0":[3578,6]}],[2,13,3,0,{"0":[0,0,0,0,0,0]},{"0":[1868,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2437,6]}],[5,36,0,1,{"2":[0,0.7879],"1":[0,0,0,0,0]},{"2":[600,2],"1":[3753,5]}],[0,22,1,0,{"0":[0,0,0,0,0,0]},{"0":[879,6]}],[6,32,3,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[8599,12]}],[2,9,3,0,{"0":[0,0,0,0,0,0]},{"0":[1104,6]}],[0,29,3,0,{"0":[0,0,0,0,0,0]},{"0":[1555,6]}],[4,1,0,1,{"1":[0.0493,0,0.0542,0.0936,0.069],"2":[0,0,0.2414,0,0]},{"1":[4641,5],"2":[3368,5]}],[7,19,4,0,{"0":[0,0,0,0,0,0]},{"0":[2237,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[5312,6]}],[3,17,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[610,6],"0":[819,6]}],[4,6,0,1,{"1":[0,0,0,0]},{"1":[3292,4]}],[0,42,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1663,6],"0":[1818,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[4405,6]}],[7,12,0,1,{"1":[0,0]},{"1":[734,2]}],[5,36,1,0,{"0":[0,1,0,0,0,0]},{"0":[3155,6]}],[4,1,4,0,{"0":[1,0,0,0,0,0]},{"0":[2513,6]}],[0,29,0,1,{"1":[0,0.1649,0,0,0],"2":[0,0,0,0,0]},{"1":[3211,5],"2":[2654,5]}],[7,12,0,1,{"1":[0,0.0588,0,0]},{"1":[2207,4]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[800,6]}],[5,36,4,0,{"0":[0,0,0,0,0,0]},{"0":[5215,6]}],[5,34,0,1,{"1":[0,0,0,0,0],"2":[0.9545,1,0.9242,0,0,0.9697]},{"1":[1887,5],"2":[1077,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[5234,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1393,6]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[5947,6]}],[1,3,3,0,{"0":[0,0,0,0,0,0]},{"0":[4286,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[2291,6]}],[1,39,0,1,{"1":[0,0,0,0]},{"1":[3098,4]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3713,6]}],[3,15,4,0,{"0":[0,0,0,0,0,0]},{"0":[3361,6]}],[0,29,0,1,{"1":[0,0,0]},{"1":[1552,3]}],[5,36,1,0,{"0":[0,0,0,0,0,0]},{"0":[1085,6]}],[5,36,2,0,{"0":[0,0,0,0,0,0]},{"0":[2652,6]}],[7,12,3,0,{"0":[0,0,0,0,0,0]},{"0":[2047,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[2544,6]}],[4,11,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0,0,0]},{"1":[1781,6],"0":[3794,8]}],[0,29,1,0,{"0":[0,0,0,0,0,0]},{"0":[1046,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[3735,6]}],[3,15,0,1,{"1":[0,0.3654,0.3654,0]},{"1":[3000,4]}],[0,29,2,0,{"0":[0,0,0,0,0]},{"0":[1964,5]}],[0,29,4,0,{"0":[0,0,0,0,0,0]},{"0":[3800,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[1285,6]}],[5,23,2,0,{"0":[0,0,0,0,0,0]},{"0":[2606,6]}],[4,11,2,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1441,6],"0":[1011,6]}],[7,12,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[3599,12]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[691,6]}],[7,25,1,0,{"0":[0,0,0,0,0,0]},{"0":[6000,6]}],[7,31,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[11218,12]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2174,6]}],[4,6,4,0,{"0":[0,0,0,1,0,0]},{"0":[1378,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0,0]},{"0":[2892,7]}],[4,11,1,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[894,6],"0":[1194,6]}],[6,2,3,0,{"1":[0,0,0,0,0],"0":[1,0,0,0,0,0]},{"1":[1193,5],"0":[2109,6]}],[4,11,1,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2450,6],"0":[3755,6]}],[5,36,2,0,{"0":[0,0,0,0,0,0]},{"0":[3004,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[3306,6]}],[3,15,4,0,{"0":[0,0,0,0,0]},{"0":[1607,5]}],[7,25,4,0,{"0":[0,0,0,0,0,0,0]},{"0":[3156,7]}],[0,29,0,1,{"1":[0,0,0,0.0235,0]},{"1":[2240,5]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[1853,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[2405,12]}],[6,2,3,0,{"0":[0,0,0,0,0,0]},{"0":[2827,6]}],[2,13,4,0,{"0":[0,0,0,0,0,0]},{"0":[1196,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[1268,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[1136,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[6404,9]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1767,6]}],[1,3,4,0,{"0":[0,0,0,0,0,0]},{"0":[1796,6]}],[4,11,0,1,{"1":[0,0.2018,0,0.193,0.0439]},{"1":[3628,5]}],[3,35,0,1,{"2":[0.7226,0.6758],"1":[0,0.1935,0,0]},{"2":[777,2],"1":[3502,4]}],[4,11,0,1,{"1":[0,0,0,0,0]},{"1":[4070,5]}],[0,41,4,0,{"0":[0,0,0,0,0,0]},{"0":[2168,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0]},{"0":[6029,11]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[5595,6]}],[7,12,1,0,{"0":[0,0,0,0,0,0]},{"0":[1047,6]}],[2,13,0,1,{"1":[0,0,0.1691,0.2083,0]},{"1":[2971,5]}],[4,6,3,0,{"0":[0,0,0,0,0,0,0]},{"0":[3264,7]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[990,6]}],[4,6,1,0,{"0":[0,0,0,0,0,0]},{"0":[5400,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2605,6]}],[4,11,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1555,6],"0":[2741,6]}],[5,24,2,0,{"0":[0,0,0,0,0,0]},{"0":[1766,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[2014,6]}],[4,1,4,0,{"0":[0,0,0,0,0,0]},{"0":[1809,6]}],[0,29,2,0,{"0":[0,0,0,0,0]},{"0":[1374,5]}],[4,6,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0]},{"1":[1360,6],"0":[1807,5]}],[6,2,1,0,{"0":[0,0,0,0,0,0]},{"0":[1441,6]}],[4,11,0,1,{"2":[0,0.7471],"1":[0.0575,0.3448,0,0.023,0]},{"2":[585,2],"1":[4361,5]}],[4,6,0,1,{"1":[0.2353,0.2794,0.5441,0]},{"1":[3949,4]}],[4,40,3,0,{"0":[0,0,0,0,0,0]},{"0":[1281,6]}],[4,11,0,1,{"1":[0,0,0.6522,0]},{"1":[2941,4]}],[5,36,0,1,{"1":[0,0,0,0]},{"1":[3129,4]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3587,6]}],[0,41,3,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[5155,9]}],[2,13,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1114,6],"0":[1161,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0,0,0,0,0]},{"0":[5164,10]}],[0,29,1,0,{"0":[0,0,0,0,0,0]},{"0":[3447,6]}],[3,15,4,0,{"0":[0,0,0,0,0,0]},{"0":[2383,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3163,6]}],[7,12,3,0,{"0":[0,0,0,0,0,0]},{"0":[1213,6]}],[4,11,4,0,{"0":[0,0,0,0,0,1]},{"0":[2360,6]}],[0,29,0,1,{"1":[0,0,0]},{"1":[1345,3]}],[0,41,1,0,{"0":[0,0,0,0,0,0]},{"0":[3343,6]}],[4,6,4,0,{"0":[0,0,0,0,0]},{"0":[2349,5]}],[7,12,4,0,{"0":[0,0,0,0,0,0]},{"0":[1475,6]}],[6,14,4,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[3832,9]}],[4,6,4,0,{"0":[0,0,0,0,0]},{"0":[2734,5]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[3257,6]}],[4,6,0,1,{"1":[0.6848,0.5598,0,0.1359,0.8587]},{"1":[3342,5]}],[0,29,0,1,{"1":[0,0,0]},{"1":[898,3]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[2500,6]}],[0,7,3,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[5548,12]}],[5,36,3,0,{"0":[0,0,0,0,0]},{"0":[1198,5]}],[0,20,2,0,{"0":[1,0,0,0,0,0]},{"0":[3439,6]}],[0,22,2,0,{"0":[0,0,0,0,0,0]},{"0":[3700,6]}],[7,12,0,1,{"1":[0,0.248,0,0.288]},{"1":[2705,4]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[3691,6]}],[7,12,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[2714,12]}],[5,36,1,0,{"0":[0,0,0,0,0,0]},{"0":[5971,6]}],[5,28,3,0,{"0":[0,0,0,0,0,0]},{"0":[1033,6]}],[3,35,4,0,{"0":[0,0,0,0,0,0]},{"0":[2783,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2959,6]}],[7,12,4,0,{"0":[0,0,0,0,0,0]},{"0":[1714,6]}],[5,24,0,1,{"1":[0.3919,0.4324,0.3784,0]},{"1":[2092,4]}],[4,1,0,1,{"1":[0,0,0,0,0]},{"1":[2606,5]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3512,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[5312,9]}],[7,12,2,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2015,6],"0":[1991,6]}],[4,6,4,0,{"0":[0,0,0,0,0,1]},{"0":[1788,6]}],[1,3,4,0,{"0":[0,0,0,0,0,0]},{"0":[2398,6]}],[4,11,0,1,{"1":[0,0.4154,0.3846]},{"1":[2926,3]}],[0,20,2,0,{"0":[0,0,0,0,0,0]},{"0":[2227,6]}],[2,13,0,1,{"1":[0,0.3571,0.3312,0.4221,0]},{"1":[3690,5]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[3350,6]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[3381,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[8999,14]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[4129,6]}],[0,41,4,0,{"0":[0,0,0,0,0,0]},{"0":[2101,6]}],[5,36,3,0,{"0":[0,0,0,0,0,0]},{"0":[4327,6]}],[7,12,1,0,{"0":[0,0,0,0,0,0,1]},{"0":[757,7]}],[5,36,2,0,{"0":[0,0,0,0,0,0]},{"0":[4652,6]}],[6,37,0,1,{"1":[0.1348,0,0,0,0]},{"1":[4028,5]}],[7,31,3,0,{"0":[0,0,0,0,0,0]},{"0":[2320,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[2417,6]}],[4,11,0,1,{"1":[0,0.25,0.1833]},{"1":[2531,3]}],[0,29,4,0,{"0":[0,0,0,0,0,0]},{"0":[3148,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[4196,6]}],[0,20,2,0,{"0":[0,0,0,0,0,0]},{"0":[815,6]}],[0,29,1,0,{"0":[0,0,0,0,0]},{"0":[1092,5]}],[5,36,2,0,{"0":[0,0,0,0,0]},{"0":[1588,5]}],[0,29,2,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1857,6],"0":[2896,6]}],[0,21,3,0,{"0":[0,0,0,0,0,0]},{"0":[3409,6]}],[7,12,4,0,{"0":[0,0,0,0,0,0]},{"0":[1216,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[1787,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[1256,6]}],[4,27,4,0,{"0":[0,0,0,0,0,0]},{"0":[1797,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[2513,12]}],[3,17,3,0,{"0":[0,0,0,0,0]},{"0":[1071,5]}],[1,5,4,0,{"0":[0,0,0,0,0,0]},{"0":[2417,6]}],[0,29,1,0,{"0":[0,0,0,0,0,0]},{"0":[2223,6]}],[2,9,3,0,{"0":[0,0,0,0,0,0]},{"0":[2597,6]}],[5,28,2,0,{"0":[0,0,0,0,0,0]},{"0":[3482,6]}],[5,36,0,1,{"1":[0,0,0]},{"1":[2355,3]}],[6,2,3,0,{"0":[0,0,0,0,0,0]},{"0":[1052,6]}],[4,1,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[3020,6],"0":[2832,6]}],[7,26,4,0,{"0":[0,0,0,0,0,0]},{"0":[3344,6]}],[4,1,0,1,{"1":[0,0.3279,0,0,0.4071]},{"1":[3920,5]}],[6,38,3,0,{"0":[0,0,0,0,0,0]},{"0":[1437,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[4331,6]}],[4,11,3,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1393,6],"0":[3549,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3000,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0,0,0,0,0]},{"0":[5209,10]}],[0,29,2,0,{"0":[0,0,0,0,0,0,1,0,0,0]},{"0":[1724,10]}],[0,29,2,0,{"0":[0,0,0,0,0,0]},{"0":[5499,6]}],[2,9,4,0,{"0":[0,0,0,0,0,0]},{"0":[5771,6]}],[5,36,1,0,{"0":[0,0,0,0,0,0,0,0,0]},{"0":[8942,9]}],[6,10,3,0,{"0":[0,0,0,0,0,0]},{"0":[1286,6]}],[4,6,0,1,{"1":[0,0,0]},{"1":[1627,3]}],[3,15,1,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[790,6],"0":[770,6]}],[3,15,3,0,{"0":[0,0,0,0,0,0]},{"0":[3105,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[4278,12]}],[7,12,1,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1523,6],"0":[4581,6]}],[4,11,0,1,{"1":[0,0.2641,0.2692,0.2692,0]},{"1":[4790,5]}],[3,15,1,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[3175,12]}],[6,10,0,1,{"1":[0,0,0,0],"2":[0,0,0,0]},{"1":[2683,4],"2":[1236,4]}],[7,12,1,0,{"0":[0,0,0,0,0,0]},{"0":[1423,6]}],[3,15,4,0,{"1":[1,1,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[1259,6],"0":[1563,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[1497,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[3000,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[3480,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0,0]},{"0":[3736,7]}],[4,1,4,0,{"0":[0,0,0,0,0,0]},{"0":[1711,6]}],[4,11,1,0,{"0":[0,0,0,0,1,0,0,0,0]},{"0":[5788,9]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[1287,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[1737,6]}],[4,11,3,0,{"0":[0,0,0,0,0,0]},{"0":[3477,6]}],[4,6,0,1,{"1":[0.2358,0,0,0]},{"1":[3689,4]}],[7,12,1,0,{"0":[0,0,0,0,0,0]},{"0":[5609,6]}],[2,9,3,0,{"0":[0,0,0,0,0,0]},{"0":[2957,6]}],[5,23,2,0,{"0":[0,0,0,0,0,0]},{"0":[3478,6]}],[0,29,1,0,{"0":[0,0,0,0,0,0]},{"0":[1297,6]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[4800,6]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[6000,6]}],[4,11,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[932,6],"0":[1821,6]}],[6,32,1,0,{"0":[0,0,0,0,0,0]},{"0":[1494,6]}],[5,36,0,1,{"1":[0,0,0,0,0]},{"1":[3880,5]}],[4,27,4,0,{"0":[0,0,0,0]},{"0":[1746,4]}],[4,1,3,0,{"0":[0,0,0,0,0,0]},{"0":[2582,6]}],[4,11,4,0,{"0":[0,1,0,0,0,0,0]},{"0":[3139,7]}],[4,11,1,0,{"0":[0,0,0,0,0,1,0]},{"0":[1585,7]}],[0,29,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[8513,12]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[2447,6]}],[3,15,1,0,{"0":[0,0,0,0,0,0]},{"0":[2645,6]}],[3,15,1,0,{"0":[0,0,0,0,0,0]},{"0":[1830,6]}],[4,11,1,0,{"0":[0,0,0,0,0,0]},{"0":[1024,6]}],[4,11,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[4954,12]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[2363,6]}],[2,8,2,0,{"0":[0,0,0,0,0,0]},{"0":[4453,6]}],[4,11,0,1,{"1":[0,0,0.4054,0]},{"1":[3470,4]}],[5,36,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0,0]},{"0":[2577,12]}],[5,23,2,0,{"0":[0,1,0,0,0,0]},{"0":[5429,6]}],[5,36,2,0,{"0":[0,0,0,0,0,0,0,0,0,0]},{"0":[3605,10]}],[4,6,3,0,{"0":[0,0,0,0,0,0]},{"0":[2913,6]}],[4,11,0,1,{"1":[0.3886,0,0.2701,0.2891,0.2891]},{"1":[4955,5]}],[4,11,0,1,{"1":[0,0,0]},{"1":[2818,3]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[2326,6]}],[2,13,0,1,{"1":[0,0.6156,0.5765]},{"1":[2281,3]}],[4,6,4,0,{"0":[0,0,0,0,0,0]},{"0":[2014,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[4389,6]}],[4,27,0,1,{"1":[0,0,0]},{"1":[1682,3]}],[4,11,2,0,{"0":[0,0,0,0,0,0]},{"0":[2090,6]}],[4,11,4,0,{"0":[0,0,0,0,0,0]},{"0":[1634,6]}],[5,4,2,0,{"0":[0,0,0,0,0,0,0,0,0,0,0]},{"0":[10650,11]}],[4,6,4,0,{"1":[0,0,0,0,0,0],"0":[0,0,0,0,0,0]},{"1":[2335,6],"0":[2113,6]}],[7,12,2,0,{"0":[0,0,1,0,0,0]},{"0":[1111,6]}]],"minTasks":5,"sat":0.8,"bin":50,"xmax":1000,"threshold":200}</script>
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
