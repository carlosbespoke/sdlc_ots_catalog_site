kin-openapi cannot preserve whether OpenAPI fields were omitted, null, zero, empty, or populated. Carry that authorship through composition, loading, reference resolution, serialization, and supported v2/v3 conversions. Existing entry points must behave unchanged.

The `openapi3` package provides the shared `PresenceState` and `FieldPresence` vocabulary. Recognized absent fields differ from unknown names, and retained snapshots cannot affect later serialization. Expose detached snapshots from `MediaType.FieldPresence`, `Encoding.FieldPresence`, `Example.FieldPresence`, `ExampleRef.FieldPresence`, `SchemaRef.FieldPresence`, and `T.FieldPresence`. `NewExampleWithPresence` records value authorship.

Preserve independent states across media fields, encoding options, examples, descriptive fields, extensions, recursive schemas, and empty collections. Keep existing omission rules and example validation exclusivity. V3 reference wrappers retain `$ref` precedence, permitted siblings, explicit nulls, wrapper-target separation, and the first reference-path origin.

The `openapi2` package exposes `V2SchemaRef.FieldPresence`, `V2Schema.FieldPresence`, and `V2T.FieldPresence`. Preserve reference form, extensions, false and zero scalars, null children, empty collections, and recursive metadata.

`Loader.LoadFromDataPreservingPresence` retains root and nested authorship through local, external, repeated, and recursive resolution. Ordinary loading remains unchanged.

The `openapi2conv` package exposes `PresenceLoss`, `PresenceConversionReport`, `ToV3PreservingPresence`, and `FromV3PreservingPresence`. Preserve every representable state. Report each incompatible state once, deterministically and in source-path order. Existing conversion entry points retain their schema, reference, media, and response-example outputs.

Resolved media schemas distinguish omitted from explicit-null nested states. Converted v2 zero constraints remain authored. Reference conversion preserves legal siblings and reports every incompatible sibling. Repeated resolution keeps wrapper presence separate and the first origin. Explicitly null examples retain authorship through constructors, composition, and supported round trips. Reverse conversion of loaded external recursive schemas preserves nested snapshots and stable loss ordering.

Objects created without decoded presence metadata keep their current JSON and YAML omission behavior.

These are required in what you deliver:

- PresenceState uint8; PresenceAbsent = 0; PresenceNull = 1; PresenceExplicit = 2
- (p FieldPresence) State(name) (PresenceState, bool)
- NewExampleWithPresence(value) *Example
- (loader *Loader) LoadFromDataPreservingPresence(data) (*T, error)
- PresenceLoss(SourcePath string, TargetPath string, State openapi3.PresenceState, Reason string)
- PresenceConversionReport(Losses []PresenceLoss)
- ToV3PreservingPresence(doc *openapi2.T) (*openapi3.T, PresenceConversionReport, error)
- FromV3PreservingPresence(doc *openapi3.T) (*openapi2.T, PresenceConversionReport, error)

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
