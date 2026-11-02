The repository at `/workdir` is binrw, a Rust library with procedural macros for reading and writing binary data.

Fix all implementation drift from the documentation in this repository.
The documentation in scope is README.md, the reference pages under binrw/doc, and the doc comments and behavioural comments in binrw/src and binrw_derive/src.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
doc comments, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The repository is at `/workdir`. The environment runs Rust 1.97 and cargo with the repository's dependencies
installed, and has no network access. Keep the public API stable and keep every behavior that
already matches its documentation working exactly as it does now.
