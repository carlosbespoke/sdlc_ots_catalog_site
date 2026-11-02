The repository at `/workdir` is a system for assigning and grading Jupyter notebooks. Instructors write source
notebooks whose cells carry metadata (solution cells, autograded test cells, read-only cells, points); preprocessors
built on nbconvert turn them into the student version (replacing solution regions with stubs, removing hidden tests,
locking cells, recording checksums), the converters run the course pipeline (generating the student version, executing
and scoring submissions, producing feedback), a SQLAlchemy gradebook stores students, assignments, cells, grades,
comments, scores and late penalties, and plugins customise late-submission penalties, grade export and the collection
of submissions from archives.

Fix all implementation drift from the documentation in this repository. The documentation and the code under repair
are: in the Python package at the repository root (the directory holding api.py, coursedir.py and utils.py), the
preprocessors, converters and plugins subpackages, the notebook metadata format subpackage (the directory holding
v1.py, v2.py and v3.py), the modules api.py, coursedir.py, utils.py, validator.py and dbutil.py, and the modules
api.py and baseapp.py of the apps subpackage; the pages configuration/student_version.rst,
contributor_guide/metadata.rst, contributor_guide/database.rst, plugins/index.rst, plugins/late-plugin.rst,
plugins/export-plugin.rst, plugins/zipcollect-plugin.rst, user_guide/advanced.rst, user_guide/faq.rst,
user_guide/autograding_resources.rst, user_guide/philosophy.rst, api/gradebook.rst, api/models.rst and
api/high_level_api.rst and the example script user_guide/extract_grades.py in that package's docs/source directory;
and the docstrings of those modules (module, class, function and method docstrings, including their examples).

Where the code and the documentation disagree about runtime behavior, the documentation is the authority: change the
implementation so that it does what the documentation says, and do not edit or delete documentation to make a
disagreement go away. The documentation is those pages, that example script and those docstrings; in-package code
comments are only supporting evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.12 with nbformat, nbconvert, nbclient, traitlets, SQLAlchemy, alembic, jsonschema,
Jupyter Server, ipykernel (a `python3` kernel) and pytest, and has no network access; the package is imported from
`/workdir`. Keep the public API stable and keep every behavior that already matches its documentation working exactly
as it does now.
