Pendulum cannot consistently control or inspect daylight-saving gap and overlap resolution across temporal workflows while preserving legacy behavior when no policy is chosen. Make `TransitionRule`, `TransitionKind`, `TransitionResolution`, `transition_context`, `get_transition_rule`, and `resolve_local` public from `pendulum.tz`; keep `datetime`, `parse`, and `from_format` public from `pendulum`.

Use explicit rules before scoped defaults, and legacy fold behavior only when neither exists. Make `transition_context` nested, concurrency-isolated, and restoring on every exit; `get_transition_rule` reports its active default. Classify wall times, select the requested side, and report adjustment as resolved minus requested wall time. RAISE uses existing transition exceptions for ambiguous or nonexistent named-zone times.

Apply consistent outcomes to construction, replacement, native conversion, calendar arithmetic, Duration application, Interval shifting, and both parsing forms. Preserve subclasses, normalized zones, orientation, locale interpretation, unrelated fields, and existing omitted-policy behavior, including serialization and extension-enabled or disabled behavior. Equivalent DateTime and Duration calendar components must agree; fixed components retain elapsed seconds. Interval shifting is atomic and matches standalone failures.

Generic and localized formatted parsing must match direct construction. Generic parsing applies rules to named-zone wall times; numeric offsets remain unique, instant-preserving values, and duration or interval text keeps its public result type. Aware DateTime conversion preserves timestamp, originating subclass, destination timezone, and fold under every rule. Explicit wall reinterpretation selects a side without changing unrelated fields. Explicit construction overrides nested contexts, whose rules resume afterward. Omitted-policy overlaps retain observed characteristics through replacement, arithmetic, UTC conversion, and serialization.

These are required in what you deliver:

- TransitionRule(str, Enum): PRE = 'pre', POST = 'post', RAISE = 'raise'
- TransitionKind(str, Enum): EXACT = 'exact', AMBIGUOUS = 'ambiguous', NONEXISTENT = 'nonexistent'
- TransitionResolution(requested, resolved, kind, rule, adjustment), frozen
- resolve_local(dt, tz, rule=None)
- datetime(year, month, day, hour=0, minute=0, second=0, microsecond=0, tz=UTC, fold=1, raise_on_unknown_times=False, transition=None)
- @classmethod create(cls, year, month, day, hour=0, minute=0, second=0, microsecond=0, tz=UTC, fold=1, raise_on_unknown_times=False, transition=None)
- resolve(self, transition=None)
- apply(self, dt, transition=None)
- shift(self, duration, transition=None)
- parse(text, *, exact=False, strict=True, tz=UTC, transition=None, **options)
- from_format(string, fmt, tz=UTC, locale=None, transition=None)

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
