golang-jwt/jwt cannot assess registered signing methods offline or quarantine cryptographic failures. Add deterministic self-tests and optional health enforcement without changing behavior when enforcement is disabled.

Each built-in SigningMethod must complete a positive signature round trip and reject altered signatures. HS256, HS384, and HS512 cover byte secrets, constant-time verification, tampering, and distinct wrong secrets. RS256, RS384, RS512, PS256, PS384, and PS512 cover their distinct padding and independently generated wrong keys. RSA-PSS compatibility verification must not change signing salt policy. ES256, ES384, and ES512 use their required curves and reject wrong-curve keys and malformed fixed-width signatures. EdDSA uses the unprehashed crypto.Signer path and rejects malformed public keys, wrong keys, and altered messages. The none method is skipped by default, runs only when explicitly included with existing unsafe authorization, and exclusion never makes it healthy.

Publish each completed run atomically as one immutable generation, ordered by ascending algorithm name. Concurrent registration must not enter an active generation. Cancellation returns cancellation and preserves prior health and quarantine state instead of recording cryptographic failure. GetSigningMethodHealth returns the snapshot. Quarantine exactly the failed algorithms when requested.

Quarantine blocks Token.SignedString before compact output and health-enforcing parsing before Keyfunc, using ErrSigningMethodQuarantined from github.com/golang-jwt/jwt/v5 with the exact string "signing method is quarantined". WithSigningMethodHealth enables enforcement. github.com/golang-jwt/jwt/v5/request.WithParser must preserve it after successful extraction, including custom claims, and return the same outcome as direct parsing. Healthy and unenforced methods keep normal behavior.

The command's `--self-test` flag runs offline self-tests, emits ascending algorithm-sorted JSON, and its `--quarantine` flag optionally quarantines failures, then applies that state to signing or verification. Its default report distinguishes skipped none from healthy methods. Preserve existing signatures, errors, none authorization, parser defaults, request delegation, and RSA-PSS compatibility.

A failed HMAC wrong-secret probe publishes one generation and blocks signing before compact output. Cancellation during Ed25519 probing retains the prior generation so healthy parsing continues. An ECDSA malformed-width failure is reported and quarantined before later command signing.

These are required in what you deliver:

- SelfTestStatus with SelfTestUntested = iota, SelfTestHealthy, SelfTestFailed, SelfTestSkipped.
- SelfTestOptions { Context context.Context; IncludeNone bool; QuarantineFailures bool }.
- SelfTestResult { Algorithm string; Generation uint64; Status SelfTestStatus; Err error }.
- SigningMethodHealth { Generation uint64; Results []SelfTestResult }.
- SigningMethod.SelfTest(options SelfTestOptions) SelfTestResult.
- RunSigningMethodSelfTests(options SelfTestOptions) (SigningMethodHealth, error).
- Token.SignedString: (t *Token) SignedString(key any) (string, error).
- NewParser(options ...ParserOption) *Parser.
- WithParser(parser *jwt.Parser) ParseFromRequestOption.

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
