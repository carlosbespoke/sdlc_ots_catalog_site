The repository at `/workdir` is throttled-py, a Python rate-limiting library: the Fixed Window, Sliding
Window, Token Bucket, Leaky Bucket and GCRA algorithms over in-memory and Redis stores, quota strings and
Quota objects, the `Throttled` function-call, decorator and context-manager interfaces with wait-and-retry,
hooks and the OpenTelemetry hook, and the FastAPI integration, each with a synchronous and an asynchronous
(`throttled.asyncio`) form.

Fix all implementation drift from the documentation in this repository.
Everything in scope is the throttled/ package (every module under throttled/, including throttled/asyncio/ and the contrib integrations), together with the documentation pages README.md, docs/source/index.rst, docs/source/installation.rst and every page under docs/source/quickstart/, docs/source/advance_usage/, docs/source/observability/ and docs/source/contrib/, the example scripts under examples/ that those pages include, and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages, the example
scripts and the in-package docstrings; in-package code comments are only supporting evidence, and when a
comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.12 with redis-py, fakeredis (with Lua scripting), FastAPI with httpx, the
OpenTelemetry API and SDK, pytest and pytest-asyncio, and has no network access, so no Redis server is
reachable; throttled is imported from `/workdir`. Keep the public API stable and keep every behavior that
already matches its documentation working exactly as it does now.
