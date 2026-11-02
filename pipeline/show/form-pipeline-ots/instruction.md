The repository at `/workdir` is TanStack Form, a TypeScript library for managing form state and validation across UI frameworks.

Fix all implementation drift from the documentation in this repository.
The @tanstack/form-core subsystem is specified by the API reference under docs/reference and the documentation comments in packages/form-core/src.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
JSDoc comments, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The repository is at `/workdir`. The environment runs TypeScript on Node.js 24 with the repository's dependencies
installed, and has no network access. Keep the public API stable and keep every behavior that
already matches its documentation working exactly as it does now.
