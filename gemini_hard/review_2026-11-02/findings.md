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