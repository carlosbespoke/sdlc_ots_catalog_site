hackbrowserdata cannot safely merge repeated exports into existing destinations without losing old or newly extracted browser records. Add conflict-aware writing to live dumps and portable restores without changing ordinary exports.

The `github.com/moond4rk/hackbrowserdata/output` package must expose `MergeMode`, `ParseMergeMode`, `MergeOptions`, `RecordIdentity`, `MergeConflict`, `CategoryMergeResult`, `MergeReport`, `MergeError`, `NewWriterWithMerge`, and `Writer.WriteMerged`. Choose keep, replace, or reject independently from retaining exact duplicates.

Give equivalent browser records the same identity across formats despite different field shapes. Keep category, encounter, conflict, and report order deterministic, independent of map and filesystem order.

Merge CSV using declared headers and textual values. Accept its BOM, but reject incompatible category headers before commit. Merge flattened browser and profile JSON rows, rejecting malformed documents and category-incompatible shapes. Reconcile CookieEditor cookies through transformed fields; keep ordinary JSON representation and identity rules for other categories.

Commit all affected category artifacts atomically. Decoding, reconciliation, policy, staging, or commit failure must preserve every original byte, including when malformed JSON follows valid CSV staging. Successful commits leave no staging artifacts, and expose CSV rows, JSON rows, and cookies together.

Reports describe only committed destinations and distinguish inserted, retained, replaced, duplicate, and conflicting records by category. `MergeError.Error` identifies failures; `MergeError.Unwrap` exposes `Err`. Leave categories without incoming records untouched. Ordinary writers keep established replacement behavior and serialized output.

Dump and restore must share merge policies and validate them before extraction changes output. Their CLI policy values are `keep-existing`, `replace-existing`, and `reject-conflicts`. Restore applies them and the same transaction guarantees after rebuilding browsers from portable keys and copied data. Without merge options, preserve its replacement workflow and input preconditions. Root default and explicit dump keep ordinary replacement until their shared merge option is supplied. Reject-conflicts failures preserve destination bytes and existing archives. Compress only after a complete commit.

These are required in what you deliver:

- MergeMode with MergeKeepExisting = iota, MergeReplaceExisting, MergeRejectConflicts.
- MergeOptions(Mode, KeepExactDuplicates).
- RecordIdentity(Category, Browser, Profile, Key).
- MergeConflict(Identity, Existing, Incoming).
- CategoryMergeResult(Category, Inserted, Retained, Replaced, Duplicates, Conflicts).
- MergeReport(Categories, Conflicts, Committed).
- MergeError(Category, Path, Err).
- ParseMergeMode(value string) (MergeMode, error).
- NewWriterWithMerge(dir, format string, options MergeOptions) (*Writer, error).
- (o *Writer) WriteMerged() (*MergeReport, error).

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
