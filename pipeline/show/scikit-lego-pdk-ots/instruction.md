The repository at `/workdir` is scikit-lego, a collection of scikit-learn compatible transformers,
estimators, meta-estimators and helpers ("lego bricks" for scikit-learn pipelines).

Fix all implementation drift from the documentation in this repository.
Everything in scope is the preprocessing and meta-estimator subsystem of scikit-lego: every module under sklego/preprocessing/ and sklego/meta/ and the shared modules sklego/__init__.py, sklego/base.py, sklego/common.py and sklego/notinstalled.py, together with the pages readme.md, docs/index.md, docs/user-guide/preprocessing.md, docs/user-guide/meta-models.md, docs/api/preprocessing.md, docs/api/meta.md, docs/api/decay-functions.md, docs/api/shrinkage-functions.md, docs/api/base.md and docs/api/common.md, the example scripts docs/_scripts/preprocessing.py and docs/_scripts/meta-models.py that the two user-guide pages include, the rendered example outputs (the .md and .html files) under docs/_static/preprocessing/ and docs/_static/meta-models/, and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.11 with no network access. scikit-lego is imported from `/workdir`
(it is on `PYTHONPATH`); its dependencies and every optional extra the repository declares
(scikit-learn, pandas, narwhals, formulaic, cvxpy, umap-learn, polars, pyarrow, matplotlib and
pytest among them) are installed. The upstream test suite and Git history are not provided.
Keep the public API stable and keep every behavior that already matches its documentation
working exactly as it does now.
