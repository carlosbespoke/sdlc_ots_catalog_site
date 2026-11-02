The repository at `/workdir` is geomstats, a Python package for computations, statistics and machine
learning on manifolds. Its learning package (`geomstats.learning`) provides scikit-learn style estimators for
data on manifolds, such as Frechet means, k-means and other clustering methods, principal component analysis,
regression and classification, built on the Riemannian metrics of `geomstats.geometry`, the numerical solvers
and optimizers of `geomstats.numerics` and a few vendored scikit-learn helpers.

Fix all implementation drift from the documentation in this repository.
Everything in scope is the statistical learning layer of geomstats: the learning package geomstats/learning/, the scikit-learn-derived helpers it uses under geomstats/_sklearngs/, the numerical solvers and optimizers under geomstats/numerics/, the probability distributions under geomstats/distributions/ and the error helpers in geomstats/errors.py, together with README.rst, the getting-started pages under docs/getting_started/, docs/api/index.rst, and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.11 with geomstats' dependencies installed (NumPy, SciPy, scikit-learn,
autograd and a CPU build of PyTorch, among others) and has no network access. geomstats is not installed
as a package: it is imported from `/workdir`, which is on `PYTHONPATH`, and the default NumPy backend is
selected (`GEOMSTATS_BACKEND=numpy`). The upstream test suite is not included. Keep the public API stable
and keep every behavior that already matches its documentation working exactly as it does now.
