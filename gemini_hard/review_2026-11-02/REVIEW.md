# Writing review: Coding OTS RL Envs (overview + 4 catalog pages)

2 Nov 2026 · Writing Evaluation Rubric · review only, nothing changed

**Verdict: 4 of 5 pages score 0 on knockout K3; Debugging scores 62 (Developing).** Every page's executive summary has a second paragraph that runs pass rates and languages together, which fails the paragraph test. On a short page, two such failures trigger K3. Coverage: 342 of 342 nodes evaluated. Format checks: 2 of 5. Penalties: −36 in total.

Scope and assumptions: client-facing catalog report ("Proposal/plan/report" format). Reader: a buyer evaluating RL environments. Purpose: show which coding tasks Gemini finds hard and what they look like. Not a research text, so Rubric 5 is skipped. Weights move 5 points from Concision to Evidence. Verbatim task prompts (collapsed "Full instruction" blocks) are task content and were not scored. Tables, plots and diagrams count as blocks.

## Scores

| Page | Core | Semantic | Reading | Composite | Penalties | Knockouts | Final |
|---|---:|---:|---:|---:|---:|---|---:|
| Overview | 58.8 | 68.8 | 62.5 | 63.3 | −6 | K3 | **0** |
| ProgramBench and Migration | 62.5 | 68.8 | 56.3 | 62.5 | −8 | K3 | **0** |
| System design & IaC | 62.5 | 68.8 | 62.5 | 64.6 | −10 | K3 | **0** |
| Diagnosis, Debugging, and Bug Fixing | 66.3 | 68.8 | 62.5 | 65.8 | −4 | pass | **61.8** (Developing) |
| Feature implementation | 62.5 | 68.8 | 56.3 | 62.5 | −8 | K3 | **0** |

Without the knockouts, the four failing pages would land between 54 and 57 (Weak). The gap to Proficient (75) is structure, audience vocabulary and the task-count framing, not the sentences themselves.

## Knockouts

| ID | Overview | ProgramBench | System design | Debugging | Feature impl. | Evidence |
|---|---|---|---|---|---|---|
| K1 Governing idea | Pass | Pass | Pass | Pass | Pass | Each page states what its tasks are in the opening paragraph. |
| K2 Hierarchy | Pass | Pass | Pass | Pass | Pass | No section or paragraph sits outside its parent. |
| K3 Paragraphs | **KO** (1 of 2 fails) | **KO** (2) | **KO** (2) | Pass (1) | **KO** (2) | D.S1.P2 on every catalog page, plus one "Why this catalog" paragraph on three pages. |
| K4 Factual integrity | Pass* | Pass* | Pass* | Pass* | Pass* | All 761 numbers recompute from the snapshot. *The task counts (605, 283...) are estimates shown as counts; see fix 2. |
| K5 Purpose | Pass | Pass | Pass | Pass | Pass | Each page says what the tasks are. None states why they were chosen. |
| K6 Audience | Pass* | Pass* | Pass* | Pass* | Pass* | *Internal vocabulary reaches the client: "main/attached sample", "shortlist", "Final category", "family". |

## Reverse outline (catalog pages share one structure)

Marks: ✗P failed paragraph · ≈ sibling fault · … no framing sentence.

- **Overview.** Governing idea: "These are coding environments for reinforcement learning, grouped into 4 catalogs."
  - D.P1 ✗P: description, then results (s3), then a scope note (s4); ends on a new idea.
  - Gemini pass rates (D.S1) …: a plot and a table with no sentence.
  - Samples (D.S2) ≈: "3 main samples go into the catalog and 12 are attached." The all-catalog turns plot is wedged in here with no heading.
- **Each catalog page.**
  - Executive summary.
    - P1 ✓: what the tasks are.
    - P2 ✗P: Argon rate, Flash rate, then languages (a new idea). The domain table under it is not introduced by any sentence.
  - Why this catalog: no lead sentence.
    - Problems: ✓, but its first sentence repeats the summary (SD, FI) or is a general claim (ProgramBench, Debugging). FI ✗P: data pipelines (s3) is a second problem.
    - How the tasks reproduce them: ProgramBench ✗P (main idea in the last sentence); SD ✗P (two task types, no umbrella sentence); Debugging and FI ✓, each with one repeated sentence.
    - Typical prompts: list ✓, parallel.
  - Domain breakdown …, Language and seniority …, Gemini pass rates across the catalog …: blocks only, no takeaway sentence. Numbers repeat the summary.
  - Turn counts: defines the measure ✓ but never states the result.
  - Example tasks: intro ✓ (internal terms). Each example: prompt-shape line ✓ and "How it maps to the work" ✓.
    - SD ≈: Examples 5 and 6 have identical headings.
    - FI: all three examples are data-pipeline tasks, so the core feature work has no example.

## Penalties

| Break | Node | Penalty |
|---|---|---:|
| Failed paragraph | Overview D.P1 | −4 |
| Sibling fault | Overview D.S2 | −2 |
| Failed paragraph | ProgramBench D.S1.P2, D.S2.S2.P1 | −8 |
| Failed paragraph | System design D.S1.P2, D.S2.S2.P1 | −8 |
| Sibling fault | System design D.S7 | −2 |
| Failed paragraph | Debugging D.S1.P2 | −4 |
| Failed paragraph | Feature impl. D.S1.P2, D.S2.S1.P1 | −8 |
| **Total** | | **−36** |

## Core rubric (same levels on all pages except where noted)

| Dimension | Weight | Level | Evidence | Top fix |
|---|---:|---:|---|---|
| Purpose & bottom line | 15 | 3 (overview 2) | Overview D.P1.s1 "These are coding environments..."; no page says why these tasks | Lead with the point: these are the tasks Gemini fails |
| Audience fit | 15 | 2 | D.S7.P1.s1 "main sample for the catalog"; field tables show "Final category" | Replace internal terms with client terms |
| Structure | 15 | 1 (Debugging 2) | D.S1.P2 fails on every page; D.S2.S2.P1 (PB, SD) | One idea per paragraph; frame every block |
| Clarity | 15 | 3 | PB D.S1.P2.s3 lists "Agent's choice" as a language | Define terms once; write "lets the agent choose" |
| Concision | 5 | 3 | "Why this catalog" repeats the summary in 9 sentences | Say each fact once |
| Evidence & accuracy | 15 | 2 | KPI "283 Tasks" is an estimate; "passes 39% of its runs on these tasks" covers only the tasks Argon ran | Label estimates; bound each rate's scope |
| Tone & voice | 10 | 4 | Plain, confident, no hype | Keep |
| Mechanics & presentation | 10 | 3 | "behaviour" vs "behavior"; "HCL (Terraform) (33%)"; sentences opening with numerals | One spelling; no nested parentheses |

Sentence statistics: 152 sentences and items, 20.2 words on average, 22 (14%) over 30 words.

## Semantic integrity (all pages)

| Dimension | Level | Evidence |
|---|---:|---|
| Seriousness & register | 4 | Measured claims, no hype. |
| Logical coherence | 3 | Claims follow from the task descriptions; "Why this catalog" never says *why*. |
| Internal consistency | 2 | The KPI task counts (an estimate: 605 in all) disagree with what the body describes (322 identified tasks). "behaviour/behavior" and "rca.json" vs "/app/rca.json" also vary. |
| Precision of meaning | 2 | "on these tasks" implies every task; Argon has run 53 of the 322. "Gemini 3.8 Flash passes 0%" when it has 2 passes. |

Consistency scan: every number that appears twice (summary, tables, examples, overview) agrees. Logic screen: hasty generalization in the "on these tasks" pass rates.

## Checkpoint log (final pass)

| Page | Readability | Flow & hierarchy | Factual | Information value | Note |
|---|---:|---:|---:|---:|---|
| Overview | 3 | 1 | 2 | 4 (100% new) | Clean sentences, but the opening paragraph mixes three ideas |
| ProgramBench | 3 | 1 | 2 | 3 (90%) | "How" paragraph buries its main idea |
| System design | 3 | 1 | 2 | 4 (96%) | "How" paragraph has no umbrella sentence |
| Debugging | 3 | 2 | 2 | 3 (87%) | Two filler or repeat lines in the examples |
| Feature impl. | 3 | 1 | 2 | 3 (93%) | Data pipelines folded into a feature-work paragraph |

Factual is 2 everywhere for the same reason: the estimated task counts read as counts.

## Format checks (Proposal/plan/report): 2 of 5

- Standalone executive summary: ✓ on catalog pages; the overview has none.
- Problem, solution, cost, timeline, risks: ✗. No cost, availability or limits section.
- Data-backed with sources: ✗. Pass rates carry no date, snapshot or run basis.
- Headings carry the argument: ✗. Headings are labels ("Domain breakdown"), not takeaways.
- Detail in an appendix: ✓. The examples and full prompts carry the detail.

## Fact-check

| Claim | Where | Status | Source |
|---|---|---|---|
| Every pass rate, "fails every run" share, turn figure, sample rate and CSV figure (761 values) | all pages | Verified | `bin/check_consistency.py` against the 2 Nov snapshot |
| Task mechanics in "How the tasks reproduce them" (offline, `compile.sh`, `/opt/task/build.sh`, `mig-check` in most, `rca.json`, refresh-disabled plans) | all catalog pages | Verified | Counts over the selected tasks' prompts and task files |
| Task counts 605 / 283 / 123 / 98 / 101 | overview, KPI cards | Unverified as counts | Modeled estimates (Argon share × catalog size), presented without "estimated" |
| "Engineers often have to make software behave exactly like a version they cannot reuse" | PB D.S2.S1.P1.s1 | Unverified | General claim with no source |
| "Maintainers are handed code that is wrong in several places" | Debugging D.S2.S1.P1.s1 | Unverified | General claim with no source |

## Sentence findings (all 54)

| Page | id | Excerpt | Label | Failed checks | Fix |
|---|---|---|---|---|---|
| README | D.P1.s1 | These are coding environments for reinforcement learning, grouped into | new | 19 | Spell out "four catalogs"; add the point: "...grouped into four catalogs and chosen because Gemini rarely passes them." |
| README | D.P1.s2 | Each task puts the agent in a real open-source codebase or program, gi | new | 7 | split into two sentences |
| README | D.P1.s3 | Gemini 4 Argon passes 23% of its runs on these tasks and Gemini 3.8 Fl | new | 6,14 | Bound the scope: "On the tasks each model has run, Gemini 4 Argon passes 23% of its runs and Gemini 3.8 Flash 2%." |
| README | D.S2.P1.s1 | 3 main samples go into the catalog and 12 are attached. | new | 5,13,19 | "Three samples are written up in full in the catalog pages, and 12 more are attached." (define "attached"; avoid opening with a numeral) |
| README | D.S2.P1.s2 | All come from the shortlist. | new | 5 | Name the source the reader knows, or cut: "All come from our curated shortlist of 120 tasks." |
| programbench | D.S1.P2.s1 | Gemini 4 Argon passes 39% of its runs on these tasks, and it fails eve | new | 14 | Say the rate covers the tasks Argon has run, not all 283. |
| programbench | D.S1.P2.s3 | The main languages are Agent's choice (42%), Go (23%) and C++ (13%). | new | 6,13 | "Agent's choice" is not a language: "42% of tasks let the agent choose the language; the rest use Go (23%) or C++ (13%)." |
| programbench | D.S2.S1.P1.s1 | Engineers often have to make software behave exactly like a version th | unverifiable | 7,21 | Anchor in the tasks rather than a general claim about engineers, and split: "These tasks ask for software that behaves exactly like a version the engineer cannot reuse." |
| programbench | D.S2.S2.P1.s1 | Reimplementation and upgrade tasks give the agent a reference program  | repeat | 21 | Cut; open with s5 as the main idea. |
| programbench | D.S2.S2.P1.s5 | Every task runs offline, and hidden tests compare the result with the  | repeat | 21 | Move to the front as the main idea and cut the repeat in the Executive summary. |
| programbench | D.S7.P1.s1 | The first example is a main sample for the catalog; the others are att | new | 5,13 | replace internal terms (main/attached sample, shortlist) or define them once |
| programbench | D.S7.P1.s2 | All of them come from the shortlist and have Gemini runs that pass at  | new | 5 | replace internal terms (main/attached sample, shortlist) or define them once |
| programbench | D.S7.S1.P1.s1 | Prompt shape: A first-person request to port a named library to Go fro | new | 7 | split into two sentences |
| programbench | D.S7.S1.S4.P1.s2 | The work is to reproduce histogram layouts and floating point behavior | new | 19 | "floating point" -> "floating-point" (attributive) |
| programbench | D.S7.S2.P1.s1 | Prompt shape: A first-person request to port a named library to Go fro | new | 7 | split into two sentences |
| system-design | D.S1.P1.s2 | In the system design tasks the agent makes a multi-process service hol | new | 7 | split into two sentences |
| system-design | D.S1.P2.s1 | Gemini 4 Argon passes 20% of its runs on these tasks, and it fails eve | new | 14 | Say the rate covers the tasks Argon has run. |
| system-design | D.S1.P2.s3 | The main languages are HCL (Terraform) (33%), Go (31%) and Python (13% | new | 19 | Avoid nested parentheses: "Terraform HCL (33%), Go (31%) and Python (13%)". |
| system-design | D.S2.S1.P1.s1 | Engineers here change production systems that must keep running. | repeat | 21 | Cut, or replace with what makes this hard: "The failures appear only when processes stop, retry or race." |
| system-design | D.S2.S1.P1.s2 | In services where several processes share state and any of them can st | new | 7 | split into two sentences |
| system-design | D.S2.S2.P1.s3 | Hidden tests then kill or pause processes and confirm that existing be | repeat | 21 | Keep here, cut from the Executive summary. |
| system-design | D.S7.P1.s1 | The first example is a main sample for the catalog; the others are att | new | 5,13 | replace internal terms (main/attached sample, shortlist) or define them once |
| system-design | D.S7.P1.s2 | All of them come from the shortlist and have Gemini runs that pass at  | new | 5 | replace internal terms (main/attached sample, shortlist) or define them once |
| system-design | D.S7.S1.P1.s1 | Prompt shape: A product-style problem statement followed by `What we n | new | 7 | split into two sentences |
| system-design | D.S7.S1.S4.P1.s3 | The hard part is the protocol: a conditional checkpoint commit tied to | new | 7 | split into two sentences |
| system-design | D.S7.S2.P1.s1 | Prompt shape: A paragraph stating the current insecure behavior, a bul | new | 7 | split into two sentences |
| system-design | D.S7.S2.S4.P1.s3 | The hard part is the lifecycle across processes: keeping secrets out o | new | 7 | split into two sentences |
| system-design | D.S7.S3.P1.s1 | Prompt shape: A two-sentence problem statement, a bullet list of requi | new | 7 | split into two sentences |
| system-design | D.S7.S3.S4.P1.s3 | The hard part is fencing: a writer whose database claim has expired mu | new | 7 | split into two sentences |
| system-design | D.S7.S5.S4.P1.s3 | The engineer relies on the recorded state and the CI plan. | new | 6 | Say what the CI plan checks: "CI accepts the change only when the plan shows moves and no replacements." |
| system-design | D.S7.S6.P1.s1 | Prompt shape: A first-person request to modularize a named Terraform s | new | 7 | split into two sentences |
| debugging | D.S1.P2.s1 | Gemini 4 Argon passes 25% of its runs on these tasks, and it fails eve | new | 14 | Say the rate covers the tasks Argon has run. |
| debugging | D.S2.S1.P1.s1 | Maintainers are handed code that is wrong in several places and must f | unverifiable | 21 | Tie to the tasks: "Each task hands the agent code that is wrong in several places and no test suite." |
| debugging | D.S2.S1.P1.s5 | In all of them the engineer reproduces the symptom, finds the faulty f | repeat | 21 | Cut, or keep here and shorten the Executive summary. |
| debugging | D.S2.S2.P1.s5 | Hidden tests check the repairs and the behaviour that was already corr | repeat | 21 | Cut. |
| debugging | D.S7.P1.s1 | The first example is a main sample for the catalog; the others are att | new | 5,13 | replace internal terms (main/attached sample, shortlist) or define them once |
| debugging | D.S7.P1.s2 | All of them come from the shortlist and have Gemini runs that pass at  | new | 5 | replace internal terms (main/attached sample, shortlist) or define them once |
| debugging | D.S7.S1.P1.s1 | Prompt shape: A first-person symptom report grouped by subsystem and w | new | 7 | split into two sentences |
| debugging | D.S7.S1.S4.P1.s3 | The hard part is tracing each symptom to the function that holds the e | new | 7 | split into two sentences |
| debugging | D.S7.S2.S4.P1.s3 | This is the documentation-drift repair family. | filler | 5,13,21 | Cut ("family" is internal vocabulary and the prompt-shape line already says this). |
| debugging | D.S7.S3.P1.s1 | Prompt shape: A short description of the library, a one-line directive | new | 7 | split into two sentences |
| debugging | D.S7.S3.S4.P1.s3 | The hard part is reading a large documented surface of transforms, dat | new | 7 | split into two sentences |
| debugging | D.S7.S4.P1.s1 | Prompt shape: A production complaint written as a ticket (diverged run | new | 7,13 | Use the same path as Example 1: `/app/rca.json`; split the sentence. |
| debugging | D.S7.S4.S4.P1.s2 | The engineer has to follow the NaN from the CSV plugin back to where t | new | 7 | split into two sentences |
| debugging | D.S7.S4.S4.P1.s3 | The work mirrors an incident ticket against a shared tool. | repeat | 15,21 | Cut; the prompt-shape line already says it is written as a ticket. |
| feature-implementation | D.S1.P1.s1 | Each task asks the agent to add a capability to an existing open-sourc | new | 6,7 | "specified the way a series of pull requests would be" is vague; say what the spec contains (required types and signatures). |
| feature-implementation | D.S1.P2.s1 | Gemini 4 Argon passes 11% of its runs on these tasks, and it fails eve | new | 14 | Say the rate covers the tasks Argon has run. |
| feature-implementation | D.S1.P2.s2 | Gemini 3.8 Flash passes 0%, and it fails every run on 98% of the tasks | new | 17 | "passes 0%" while it has 2 passes: write "under 1%". |
| feature-implementation | D.S2.S1.P1.s1 | Maintainers add a capability that runs through many code paths of an u | repeat | 21 | Replace with what makes it hard, e.g. the number of code paths a change touches. |
| feature-implementation | D.S2.S1.P1.s3 | Data engineers face a related problem: after an upstream format or sch | new | 7 | Give the data-pipeline problem its own short paragraph. |
| feature-implementation | D.S2.S2.P1.s1 | Each task pins an open-source repository, mostly Go or Python, in an o | new | 7 | split into two sentences |
| feature-implementation | D.S2.S2.P1.s3 | After the session, hidden acceptance tests check the new behaviour and | repeat | 21 | Cut from one of the two places. |
| feature-implementation | D.S7.P1.s1 | These examples are attached samples. | new | 5,13 | replace internal terms (main/attached sample, shortlist) or define them once |
| feature-implementation | D.S7.P1.s2 | All of them come from the shortlist and have Gemini runs that pass at  | new | 5 | replace internal terms (main/attached sample, shortlist) or define them once |

## Top fixes, by impact

1. **Split Executive summary P2 on every page (clears K3 on ProgramBench, System design and Feature implementation, together with fix 3).**
   - Before: "Gemini 4 Argon passes 39%... Gemini 3.8 Flash passes 1%... The main languages are..."
   - After: one paragraph on results, opening with its point ("Gemini rarely passes these tasks: ..."). Move languages to the paragraph that describes the tasks, and add a sentence that introduces the domain table.
2. **Label the task counts as estimates and bound the pass-rate scope.** "283 Tasks" becomes "≈283 tasks (estimated)"; "passes 39% of its runs on these tasks" becomes "passes 39% of its runs on the tasks it has run". This resolves the main consistency and precision faults.
3. **Repair the failing "Why this catalog" paragraphs.**
   - ProgramBench: put "Every task runs offline, and hidden tests compare the result with the reference" first.
   - System design: open with one sentence covering both task types.
   - Feature implementation: give data pipelines their own paragraph.
   - Everywhere: cut the sentences that repeat the summary.
4. **Fix the overview opening (clears its K3).**
   - Split D.P1: one paragraph on what the set is and why it exists (Gemini rarely passes these tasks), one on results.
   - Move the Gemini-only note under the pass-rate table.
   - Give the turns plot its own heading.
5. **Replace internal vocabulary and give every block a takeaway sentence.**
   - "main/attached sample", "shortlist", "Final category" and "family" become client terms, or are cut.
   - Domain breakdown, pass-rate and turn sections each get one sentence stating what the plot or table shows.

Estimated after fixes 1 to 4: no knockouts, penalties near −2, finals around 70 to 75 (Developing to Proficient).
