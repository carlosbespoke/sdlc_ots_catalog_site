# Reduce reallocation when decompressing zstd bodies

The repository at `/app` is the Go source tree for fasthttp. Applications that accept or fetch zstd-compressed bodies decompress them through `AppendUnzstdBytes`, `WriteUnzstd`, `Request.BodyUnzstd` and the related response and limit variants. For bodies of a megabyte or more, decompression currently spends a large share of its time and allocations on work that does not produce output.

Make decompression of large zstd bodies materially cheaper in time and allocations. Find the unnecessary work and remove it while preserving the package's existing behaviour.

The repository has no dedicated benchmark for these functions. Write your own, for example a `testing.B` benchmark that decompresses varied bodies of one to two megabytes, and run it with:

```sh
go test -run '^$' -bench '<YourBenchmark>' -benchmem .
```

## Requirements

- Preserve the behaviour and public API of `AppendUnzstdBytes`, `WriteUnzstd`, `Request.BodyUnzstd`, `Request.BodyUnzstdWithLimit`, `Response.BodyUnzstd`, `Response.BodyUnzstdWithLimit`, `BodyUncompressed` and `BodyUncompressedWithLimit`, including decoded output, returned counts and errors, body size limits, bytes already present in the destination, custom `io.Writer` destinations, skippable and multiple frames, and truncated or corrupt input.
- Input is untrusted. Never size memory from values the input declares without a bound, and keep every body size limit in force.
- Keep the existing test suite passing.
- Improve the general decompression path. Hidden checks use different bodies, sizes, frame layouts, destinations and limits; do not special-case a benchmark or its inputs.
- Do not modify or disable tests or benchmarks to obtain a result. Canonical hidden workloads are restored by the verifier before grading.
- Keep production edits in `zstd.go`; new Go helpers in the root package are allowed. Keep other source files, module files, dependencies, and build settings unchanged. Markdown planning notes are allowed. Before finishing, delete any other files you created under `/app`, such as profiles (`*.out`, `*.pprof`), scratch or patch scripts, and backup copies, and do not delete repository files: apart from compiled Go test binaries and the compressed file caches that fasthttp's own tests write, any new or removed file other than a new root-package `.go` helper or Markdown notes makes the submission score 0.
- New imports may use `bytes`, `errors`, `fmt`, `strconv`, `strings`, `sync`, `time`, `unicode`, `unicode/utf8`, `math`, `math/bits`, `encoding/binary`, `sort`, or `slices`, besides packages the edited file already imports. Do not add `init` functions, compiler directives, goroutines, process inspection, or output manipulation, and do not use the file, network, logging or process capabilities that `zstd.go` already has more often than the untouched file does. Naming I/O types, interfaces, sentinel errors or constants such as `io.Reader` or `io.EOF` is not a capability use.
- Decompress each supplied input. Do not memoize complete inputs or outputs, recognize test names, emit benchmark results, or change behaviour according to the evaluation process.
- Work offline. The required Go toolchain, modules, and build cache are already present in the image.

For the offline repository suite, use `go test ./... -skip '^(TestDialerGetDialFunc|TestDialerGetDialFuncForTLSNoProxy)$'`. Those proxy tests depend on the host network (one connects to GitHub, the other expects a direct dial to an unroutable address to fail) and are excluded in the verifier; the other repository tests and the hidden checks must pass.

## Grading

Correctness is a hard gate. A faster implementation that changes behaviour receives no credit. For each optimized workload, recover at least 75% of the allocation improvement between the untouched baseline and the private reference, and reduce median time versus the same-run baseline by at least 15%, or by at least 10% when decoding into a fresh `bytes.Buffer` with `WriteUnzstd`. Exact malloc counts divided by the number of measured inputs are used rather than rounded whole allocations per operation. For each side and workload, at least nine of ten launches must form a dominant cluster no wider than one raw malloc or 1% of the cluster's smallest count, whichever is larger, across 256 compressed bodies of roughly one to two megabytes; that cluster's median is scored and any single outside sample remains recorded as an outlier. Evidence without such a cluster is invalid rather than a solver failure. A comparison delta of at most one raw malloc, or 1% of the baseline's count when that is larger, is treated as counter noise. The timing improvement must also pass an exact one-sided Mann-Whitney permutation test at an alpha of 0.05. All three conditions must pass for appending decoded bodies whose frames declare their size, decoding request bodies with `Request.BodyUnzstd`, and decoding into a fresh `bytes.Buffer` with `WriteUnzstd`.

The small-body workload, bodies of 48 to 64 kilobytes, is a non-regression control: it must add no allocations and its median time may be at most 20% slower than the same-run baseline. The verifier uses ten launches per implementation, single-use varied inputs with every result checked in the timed pass, identical resource limits, and a binary verdict: 1 only when all correctness and performance conditions pass; otherwise 0 for a completed task evaluation. If that complete ten-launch cohort is invalid solely because it lacks the required allocation-stability cluster, the verifier discards the entire cohort and runs one fresh ten-launch cohort; attempts are never merged or cherry-picked, and no performance failure is retried. The result also records the measured allocation recovery, timing ratio, p-value, and partial progress for each optimized workload. Performance and differential records are written by restored verifier code; candidate stdout is diagnostic only.

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the modules, functions and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
