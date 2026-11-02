The repository at `/workdir` is OpenTelemetry Python Contrib, the monorepo of OpenTelemetry instrumentation
packages for Python. Its HTTP client instrumentations (for `requests`, `urllib`, `urllib3`, `httpx` and
`aiohttp`) create client spans and metrics for outgoing requests, with options such as excluded URLs, captured and
sanitized headers and request/response hooks; they build on the shared `opentelemetry-util-http` helpers and on the
`opentelemetry-instrumentation` base package (`BaseInstrumentor`, auto-instrumentation and bootstrap).

Fix all implementation drift from the documentation in this repository.
Everything in scope is the outgoing HTTP client instrumentation of this repository: the requests, urllib, urllib3, httpx and aiohttp-client instrumentation packages (the src/ tree and README.rst of each instrumentation/opentelemetry-instrumentation-<name>/ directory), the shared HTTP helpers of util/opentelemetry-util-http/ (its src/ tree and README.rst) and the instrumentation base package they build on (opentelemetry-instrumentation/src/ and opentelemetry-instrumentation/README.rst), together with their documentation pages under docs/instrumentation/ (aiohttp_client/, base/, httpx/, requests/, urllib/ and urllib3/) and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.11 with the repository's locked dependencies installed and has no network access;
every package of the repository is installed in editable mode from its `src/` directory under `/workdir`. No
remote HTTP service or telemetry collector is reachable from here. Keep the public API stable and keep every
behavior that already matches its documentation working exactly as it does now.
