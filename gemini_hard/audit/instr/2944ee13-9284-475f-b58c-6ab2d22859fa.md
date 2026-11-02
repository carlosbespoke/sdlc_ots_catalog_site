go-tc cannot replay traffic-control objects without discarding kernel extensions. Add lossless replay that exposes preserved netlink attributes, allows typed edits, and reconstructs or submits complete objects. Preserve strict decoding, default decoding, and unconfigured transport behavior.

`ParseObject` must produce identical typed options and envelope attributes whether options precede or follow Kind. `DecodePreserve` returns typed data and well-formed raw attributes in `ScopeEnvelope`, `ScopeOptions`, or `ScopeNested`. `DecodeStrict` retains existing rejection behavior. Always reject malformed framing.

`RawAttribute.Bytes`, `Object.RawAttributes`, `Atm.RawAttributes`, and `Cbq.RawAttributes` return independently owned copies preserving duplicates, flags, scopes, order, and payloads. Replay envelope, ATM, and CBQ scopes losslessly and deterministically. Preserve unedited order and unrelated bytes exactly; reparsing must yield a coherent equivalent object.

Apply `ReplayOptions` with `ConflictReject`, `ConflictPreferTyped`, or `ConflictPreferRaw`. Rejection returns `ReplayError` with numeric type and scope before transport. A preference emits its selected occurrence once without suppressing unrelated data. Reconcile ATM FD, Excess, State, and AtmPvc independently. Reconcile CBQ native structures, Police, Rate, RTab, duplicates, and unknown options independently.

`Tc.SetDecodeMode(mode)` and `Tc.SetReplayOptions(options)` govern `Qdisc.Get` and monitoring through a `Tc` returned by `Open`. `Qdisc.Add(info)` and `Qdisc.Replace(info)` retain distinct flags. Class, Filter, and Chain mutations retain request types, validation, and framing. Class emits one TCA_OPTIONS and no duplicate TCA_KIND.

Malformed preserved attributes and rejected conflicts fail consistently before transport. Parsing, marshaling, submission, and failure never mutate input Objects, typed values, or payload slices.

Preserve interleaved duplicate and unknown ATM options, scopes, and relative order without edits. Prefer-typed CBQ native edits preserve unrelated RTab entries, unknowns, duplicates, positions, and bytes. ATM conflicts return ReplayError before transport and leave the Object reusable. Class submission loses no edited CBQ Rate, RTab, or unknown data. Qdisc Add and Replace preserve their legacy flag difference and leave preserved Objects reusable. Transport-preserved data remains independent of source buffers when replayed prefer-raw through another eligible facade.

These are required in what you deliver:

- From `github.com/florianl/go-tc`: `AttributeScope`, `ScopeEnvelope`, `ScopeOptions`, `ScopeNested`, `RawAttribute`, `DecodeMode`, `DecodeStrict`, `DecodePreserve`, `ReplayConflictPolicy`, `ConflictReject`, `ConflictPreferTyped`, `ConflictPreferRaw`, `ReplayOptions`, `ReplayError`, `ParseObject`, `Object.MarshalBinary`, `Object.RawAttributes`, `Atm.RawAttributes`, `Cbq.RawAttributes`, `Tc.SetDecodeMode`, `Tc.SetReplayOptions`, `Qdisc.Get`, `Qdisc.Add`, `Qdisc.Replace`.
- `AttributeScope`: `ScopeEnvelope = 0`, `ScopeOptions = 1`, `ScopeNested = 2`.
- `RawAttribute(Type, Flags, Scope)`; `(a RawAttribute) Bytes()`.
- `DecodeMode`: `DecodeStrict = 0`, `DecodePreserve = 1`.
- `ReplayConflictPolicy`: `ConflictReject = 0`, `ConflictPreferTyped = 1`, `ConflictPreferRaw = 2`.
- `ReplayOptions(ConflictPolicy)`.
- `ReplayError(Scope, Type, Err)`.
- `ParseObject(action, data, mode) (..., error)`.
- `(o Object) MarshalBinary(action, options) (..., error)`.
- `(qd *Qdisc) Get() (..., error)`; `(qd *Qdisc) Add(info) error`; `(qd *Qdisc) Replace(info) error`.

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
