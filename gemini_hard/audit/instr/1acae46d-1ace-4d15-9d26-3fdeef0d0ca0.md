Let applications describe obsolete command and flag spellings, guide users toward supported replacements, and inspect deprecated usage after execution. Apply one deprecation policy consistently across invocation, help, suggestions, documentation, runtime completion, and fish completion. Existing applications that declare no deprecations must behave exactly as before.

A command exposes its optional `Deprecation`, while each `DeprecatableFlag` exposes `DeprecatedAliases() []DeprecatedAlias` so aliases can be deprecated independently without affecting canonical or undeclared spellings. `DeprecationPolicy` selects `DeprecationVisible`, `DeprecationHidden`, or `DeprecationReject`; rejection returns `DeprecationError` before the obsolete command's callbacks execute. Replacements are resolved against the active command graph, and only valid non-self replacements are advertised, although unresolved declarations remain diagnostic metadata. Each `Run` produces a fresh `DeprecationReport` containing every actual deprecated spelling in traversal and argv order, and the report survives action or lifecycle errors. Recording repeated aliases must not alter duplicate rejection, boolean counts, or final parsed values. Suggestions prefer supported spellings; visible mode may annotate an otherwise unmatched deprecated suggestion, while hidden mode omits it. Help at every command depth, generated flag documentation, runtime completion, and fish completion apply the same visibility, message, and resolved-replacement decisions, with each annotation emitted once and native escaping preserved. Compatible deprecated parents retain supported descendants, and undeclared commands preserve callback outcomes, help bytes, templates, writers, and successful help behavior.

A nested invocation with repeated deprecated aliases preserves traversal and occurrence order while retaining normal flag values. Reject mode blocks obsolete commands before actions, while permitted invocations retain notices after independent callback failures. A resolved replacement is consistent in help and completion even when hidden policy suppresses the obsolete command. An unresolved replacement remains reportable after failure, a clean rerun clears it, and compatible descendants remain discoverable.

These are required in what you deliver:

- From `github.com/urfave/cli/v3`: `Deprecation`, `DeprecatedAlias`, `DeprecationMode`, `DeprecationPolicy`, `DeprecationNotice`, `DeprecationReport`, `DeprecatableFlag`, `Command.Deprecated` (`*Deprecation` field), `Command.Deprecation`, `Command.Deprecations`, `DeprecationError`.
- Deprecation { Message string; Replacement []string }
- DeprecatedAlias { Name string; Message string; Replacement string }
- DeprecationMode int; `DeprecationVisible DeprecationMode = iota`, `DeprecationHidden`, `DeprecationReject`
- DeprecationPolicy { Mode DeprecationMode }
- DeprecationNotice { CommandPath []string; UsedName string; Message string; Replacement []string }
- DeprecationReport { Notices []DeprecationNotice }
- (cmd *Command) Deprecation() *Deprecation; (cmd *Command) Deprecations() DeprecationReport
- DeprecationError { Notice DeprecationNotice }

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
