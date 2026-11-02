go-sqlite3 cannot currently checkpoint, restore, or combine statistics aggregates without a database connection. Allow callers to checkpoint, restore, and merge statistics aggregates without a database connection, then continue additions and sliding removals. Preserve existing SQL and third-party window-function behavior.

`StatefulWindowFunction` from `github.com/ncruces/go-sqlite3` must optionally extend `WindowFunction` without changing the legacy callback surface. Export `Accumulator`, `NewAccumulator`, its lifecycle methods, `Register`, and the three classified errors from `github.com/ncruces/go-sqlite3/ext/stats`.

Make snapshots deterministic, versioned binary representations preserving function identity, immutable configuration, typed representation state, and everything needed for continued updates. Prefix snapshots with the binary format marker `SQLiteStats\x00\x01`, where the final byte is version 1. Restore and merge must be atomic. Invalid data returns `ErrInvalidState` with "stats: invalid state"; incompatibility returns `ErrIncompatibleState` with "stats: incompatible state"; the destination remains exactly unchanged. Unknown SQL names return `ErrUnknownFunction` with "stats: unknown function". Validate required configuration for every registered boolean, mode, percentile, variance, covariance, regression, higher-moment, and JSON result variant.

Merged partitions must have the same mathematical result and storage class as one-pass evaluation, including compensated large-offset data, unequal partitions, thresholds, ties, NULLs, raw percentile samples, quantile arrays, and every higher-moment and regression result variant. Preserve `regr_json` sample-size thresholds and JSON subtype content. Match shrinking SQL frames after snapshot, restore, merge, update, and removal.

Reset must discard accumulated values while retaining valid configuration. SQL registration must preserve names, filtering, storage classes, window results, statement errors, and non-stateful `WindowFunction` compatibility.

Configured percentile restore and merge failures must leave later values, additions, removals, and snapshots unchanged. Direct boolean and mode accumulators must match SQL windows for identical mixed inputs, including SQLite storage classes. Unequal direct partitions for variance, covariance, regression, skewness, and kurtosis must match SQL over concatenated rows. Equivalent typed mode and configured percentile states must produce repeatable snapshots restoring blobs, samples, and quantile ordering.

These are required in what you deliver:

- StatefulWindowFunction interface { WindowFunction; MarshalBinary() ([]byte, error); UnmarshalBinary([]byte) error; Merge(StatefulWindowFunction) error }
- NewAccumulator(function, parameters ...any) (*Accumulator, error)
- (a *Accumulator) Add(values ...any) error
- (a *Accumulator) Remove(values ...any) error
- (a *Accumulator) Value() (any, error)
- (a *Accumulator) Reset()
- (a *Accumulator) MarshalBinary() ([]byte, error)
- (a *Accumulator) UnmarshalBinary(data) error
- (a *Accumulator) Merge(other *Accumulator) error
- Register(db *sqlite3.Conn) error

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
