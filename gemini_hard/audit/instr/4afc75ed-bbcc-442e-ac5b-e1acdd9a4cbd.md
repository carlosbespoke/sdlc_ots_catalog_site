django-allauth cannot retarget an active verification process without changing the process being completed. Implement transactional retargeting that commits the normalized destination and replacement challenge together, refuses without side effects, or restores all prior durable state after failure. Browser and headless flows must report the same authoritative outcome while preserving presentation and authentication conventions.

On delivery or persistence failure, `retarget` returns the RESTORED outcome and does not raise. `RetargetFailure` is reserved for internal transactional helpers and must be caught before `retarget` returns.

Across EmailVerificationProcess, LoginCodeVerificationProcess, PasswordResetVerificationProcess, and PhoneVerificationStageProcess, preserve identity, timeout origin, attempt and resend accounting, completion context, abort semantics, and Login stage. Replace only destination-dependent state and record one change only on commit. Make validation, delivery, account mutation, and persistence atomic. Failure must restore the destination, code, account data, session state, durable challenge, and resumable stage.

Preserve enumeration-safe fake email verification. Login codes may switch between eligible email and phone transports. Password-reset retargeting always refuses without disclosure or side effects. Serialization keeps exactly one current stage, never authenticates prematurely, and preserves committed or restored state across requests.

Browser requests delegate to the active process, reject stale codes after commit, and render refused or restored outcomes without disturbing existing resend, error, completion, redirect, or cleanup behavior when no retarget occurs. Headless results deterministically expose status and authoritative destination while preserving browser-client and app-client authentication behavior. Cross-interface retargeting must retain process identity, the original redirect, one authoritative destination and code, and completion through either interface. Failed browser SMS retargeting leaves the old destination, code, and stage usable.

`RetargetStatus` is a str and Enum. `RetargetDestinationKind` is a str and Enum. `RetargetFailure` is an Exception. `RetargetResponse` is an APIResponse. `RetargetStatus`, `RetargetDestinationKind`, `RetargetDestination`, `RetargetResult`, and `RetargetFailure` are public from `allauth.account.verification`; `retarget_result_data` is public from `allauth.headless.account.verification`, and `RetargetResponse` is public from `allauth.headless.account.response`.

These are required in what you deliver:

- RetargetStatus: COMMITTED = 'committed', REFUSED = 'refused', RESTORED = 'restored'
- RetargetDestinationKind: EMAIL = 'email', PHONE = 'phone'
- RetargetDestination(kind, value), frozen dataclass
- RetargetResult(status, destination, changed), frozen dataclass
- RetargetFailure attributes: result, cause
- retarget(self, destination)
- retarget_result_data(result)
- RetargetResponse.__init__(self, request, result)

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
