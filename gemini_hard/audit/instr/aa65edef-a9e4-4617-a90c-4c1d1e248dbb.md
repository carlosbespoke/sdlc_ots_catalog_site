The repository at `/workdir` is sqlglot, a dependency-free SQL parser, transpiler, optimizer and engine
written in Python: it tokenizes and parses SQL into an expression tree, generates SQL for many dialects,
builds and transforms expression trees programmatically, optimizes queries and executes them in Python.

Fix all implementation drift from the documentation in this repository.
Everything in scope is sqlglot's dialect-independent core: the packages sqlglot/expressions/, sqlglot/optimizer/ and sqlglot/executor/; the modules sqlglot/__init__.py, sqlglot/_typing.py, sqlglot/anonymize.py, sqlglot/diff.py, sqlglot/errors.py, sqlglot/generator.py, sqlglot/helper.py, sqlglot/jsonpath.py, sqlglot/lineage.py, sqlglot/parser.py, sqlglot/planner.py, sqlglot/schema.py, sqlglot/serde.py, sqlglot/time.py, sqlglot/tokenizer_core.py, sqlglot/tokens.py, sqlglot/transforms.py and sqlglot/trie.py (every module directly in sqlglot/ except sqlglot/__main__.py); together with the pages README.md, posts/ast_primer.md and posts/onboarding.md and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.12 with no network access. sqlglot is imported from `/workdir` (it is on
`PYTHONPATH`) as pure Python: the optional compiled extensions (`sqlglot[c]`/sqlglotc and the
deprecated sqlglotrs tokenizer) are not installed, and the generated `sqlglot/_version.py` is absent,
so importing sqlglot logs that `__version__` cannot be set. pytest is installed. The upstream test
suite and Git history are not provided. Keep the public API and function signatures stable (a default
value may change only where the documentation requires it), do not add files, and keep every behavior
that already matches its documentation working exactly as it does now.
