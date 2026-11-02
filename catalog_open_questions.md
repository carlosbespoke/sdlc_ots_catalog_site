# Open questions from the catalog drafts

Internal working notes; not part of the catalog pages.

## ProgramBench

- What does the reference version in upgrade tasks represent, for example the next release or an arbitrary later commit? The instructions do not say.
- Do the three batches overlap in repositories? Some repositories appear in more than one upgrade batch.
- How many hidden behaviors does each task replay, and how are they selected? Only branch archives are listed, not counts per task.
- Why do some reimplementation tasks run the reference through a launcher and others do not? The Dockerfiles differ and no rationale is given.
- Is upgrade scoring all-or-nothing, as the instruction says every hidden test must pass, or is partial credit recorded?
- The gitleaks task ships `files.7z` in `/workspace/assets`. Its contents were not inspected, so these inputs are not described.
- The example has no repository upgrade task, so the upgrade environment diagram was not checked against task files, only against instructions.

## System design

- Hidden tests and graders were not described here, so how failures are injected (kill, pause, network cut) in each task is UNKNOWN beyond what the instruction states.
- The agent environment has no Docker, yet `environment/docker-compose.yaml` exists for grist and immich. It is unclear whether the agent container gets those services through compose or starts local copies; diagrams show them as services.
- For wild-workouts, cortex, buildbot, dialogporten and aodh no compose file is in the files, so the location of PostgreSQL, Redis and RabbitMQ (local to the container or sidecar) is inferred from the instruction and Dockerfile.
- Whether the 217 tasks should be split into system design (multi-instance) and fault tolerance (single component) in the catalog is not stated; the sample split here is by reading each instruction.
- Batch names (system-design-cohere-ots, alpharecon-deepswe-binary) suggest different authoring pipelines; their grading format was not inspected.

## Diagnosis, Debugging, and Bug Fixing

- `tests/rubrics.json` in one task holds research and planning rubrics. It is not established whether a model or rules score them, or whether they affect the reward.
- The h3 `task.toml` name is h3-17f-687c550d while the catalog uses a different name. The mapping between the two names is not stated.
- One task is labelled multi-bug diagnosis, but its description says the four defects are real upstream bugs and not injected edits. Confirm whether real-bug tasks belong under the same shape label.

## Feature implementation

- The batch alpharecon-deepswe-binary holds 433 of 636 tasks, but neither provided task comes from it. Does the large batch use the same task layout and grading as the two example tasks?
- One task's `tests/` folder lists a grader script and manifest, but their contents were not in the provided files. How is the reward computed there, as pass/fail or as a weighted fraction?
- Several sampled task names start with 'tests-50pct' or 'tests-75pct'. What do these prefixes mean for what the agent sees or for grading?
- Do the Cohere batches and the alpharecon batches share one grading policy, or is each batch graded differently?

## Infrastructure as code

- The tasks file contains 29 Terraform module refactors and one CDK task. Pulumi ports and policy remediation appear only in the example set, so their share of the 325 tasks is UNKNOWN.
- One task sits in the SRE-xai-ots batch and the other Terraform tasks in IaC-ots. The files do not say how the two batches differ in origin or authoring.
- Seniority labels in the input (all Senior) are not stated in any task file, so their source is UNKNOWN.
- The README files and instructions name real open-source projects and companies as the origin of some stacks, but `task.toml` leaves `source_repository` empty. Whether these stacks are derived from public repositories is UNKNOWN.
- The Terraform tasks say a pristine state exists in the verifier, but the grader and spec were only skimmed for the Terraform tasks. Details of the hidden probes for the Terraform refactors beyond what `instruction.md` states were not reviewed.
- Reference solutions and the full `grade.py` logic were deliberately not described, so the catalog owner should confirm how much of the grading detail may be published.
- Show folders outside the example list, were not read.

## Data engineering

- The brief names two roles, but one example task has the category Sports analytics and another Payments and banking. Is the catalog meant to include them under data engineering?
- Two sampled tasks have empty instruction text in the tasks file. Is that a data export error?
- Which Python process user and privileges does the agent have at run time? Dockerfiles mention an unprivileged user dpapp for the verifier, but the agent's user is not stated in the files I read.
- One task's Dockerfile starts with template comments (FILL markers). Are these comments leftovers, and does the task have no `/data` sample folder?
- What are the reward and pass criteria in `grader.py` (number of hidden tests, weighting between repo checks and hidden suite)? I did not describe them.

## Migration

- The input labels the shape of these tasks as 'Evolve a repo from one release to the next', but every file shows a cross-language port. Should the shape label be changed?
- The `task.toml` files describe the tasks as tests-only translations (category migration-tests). Is the hidden test suite always a mechanical translation of the original tests, and who checks that translation?
- Samples mention a C++ target for four tasks, and none of those were provided with files. Should the catalog report the target-language split?
- The migration-ots batch of five tasks uses a different prompt template from the 32 migration-xai-ots tasks. Is the grading the same?
- The grader files show a fractional reward in some code paths and a binary reward in others. Which mode applies to the released tasks?
