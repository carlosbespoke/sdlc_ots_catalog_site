Restish cannot publish a machine-readable completion receipt for a logical streamed invocation. Add an opt-in receipt for built-in formatters, plugins, event streams, and pagination without changing existing output or independently built formatter plugins. `GlobalFlags` from `github.com/rest-sh/restish/v2/internal/cli` carries the string field `StreamReceipt` selecting its destination.

Finalize each ValueStream session exactly once into an immutable terminal outcome available to every termination call. Closing is idempotent, emits final output once, and prevents later writes from changing output or accounting. Count values only after formatter acceptance and exactly the bytes successfully written, including framing, newlines, and close-time output. Preserve lines rendering for scalars and scalar arrays; reject structured values without counting them.

Preserve prior totals on failure, classify cancellation separately, redact plugin diagnostics, and exclude rejected, unencodable, and incompletely written values. Receipt-capable plugins exchange validated outcomes. Legacy plugins may end successfully with the one-way protocol, including silent termination. Resolve item sends, terminal acknowledgement, subprocess exit, cancellation, and close errors into one stable outcome without later failures hiding earlier ones.

Produce one invocation-level outcome for SSE, NDJSON, detected JSON-lines, and pagination. Cover every page, retain earlier-page accounting, treat configured limits as successful stops, and distinguish transport, normalization, filtering, and rendering failures. SSE cancellation closes once and publishes one canceled receipt with accepted totals.

Publish receipts separately from formatted stdout and stderr. Without a receipt, preserve existing bytes, rendering, and errors. Close paginated auto output's JSON frame before reporting totals including its bytes. Keep lines formatter failure primary after rejection. Rank source, formatter, close, then receipt-publication errors. Attempt a failing receipt destination once; its failure must not corrupt output or hide an earlier operational failure.

These are required in what you deliver:

- From github.com/rest-sh/restish/v2/internal/output: StreamStatus, StreamOutcome, ValueStream.Close, PluginFormatter.StartValueStream.
- StreamStatus string: StreamStatusComplete = "complete", StreamStatusFailed = "failed", StreamStatusCanceled = "canceled".
- StreamOutcome { Status StreamStatus; ValuesAccepted uint64; BytesCommitted uint64; Diagnostic string }.
- ValueStream.Close() (StreamOutcome, error).
- (*PluginFormatter) StartValueStream(w io.Writer, base *Response, color bool) (ValueStream, error).
- From github.com/rest-sh/restish/v2/plugin: FormatterOutcome, FormatterRequest.
- WriteFormatterOutcome(w io.Writer, outcome FormatterOutcome) error.
- FormatterOutcome { Status string `cbor:"status" json:"status"`; ValuesAccepted uint64 `cbor:"values_accepted" json:"values_accepted"`; BytesCommitted uint64 `cbor:"bytes_committed" json:"bytes_committed"`; Diagnostic string `cbor:"diagnostic,omitempty" json:"diagnostic,omitempty"` }.
- FormatterRequest { Type string `cbor:"type" json:"type"`; Format string `cbor:"format" json:"format"`; Color bool `cbor:"color,omitempty" json:"color,omitempty"`; Event string `cbor:"event" json:"event"`; Response FormatterResponse `cbor:"response" json:"response"`; Outcome *FormatterOutcome `cbor:"outcome,omitempty" json:"outcome,omitempty"`; WantOutcome bool `cbor:"want_outcome,omitempty" json:"want_outcome,omitempty"` }.
- From github.com/rest-sh/restish/v2/internal/cli: WriteStreamReceipt.
- WriteStreamReceipt(w io.Writer, outcome output.StreamOutcome) error.

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
