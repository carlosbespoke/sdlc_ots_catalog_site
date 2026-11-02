The repository at `/workdir` is dj-stripe, a Django application that keeps a copy of Stripe objects
as Django models: it syncs Stripe data into the database, receives, validates and processes Stripe
webhooks through webhook endpoints, dispatches signals for Stripe events to handlers, and manages API
keys and Stripe API versions.

Fix all implementation drift from the documentation in this repository.
Everything in scope is the dj-stripe library package: every Python module of the djstripe/ package except its migrations/ package, the admin templates under djstripe/templates/, and the documentation pages docs/README.md, docs/api_keys.md, docs/api_versions.md, docs/index.md, docs/installation.md, docs/settings.md, docs/stripe_elements_js.md, docs/upgrade_dj_stripe.md and every page under docs/usage/, together with the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.11 with Django 5.2, the stripe Python library 15.5, SQLite and no
network access, so nothing can reach the Stripe API; dj-stripe is imported from `/workdir`, and
pytest with pytest-django is installed. A small sandbox Django project, `djsproject` (the
`DJANGO_SETTINGS_MODULE`), installs `djstripe` with test-mode placeholder Stripe keys and the
dj-stripe URLs under `/stripe/`. Keep the public API stable and keep every behavior that already
matches its documentation working exactly as it does now.
