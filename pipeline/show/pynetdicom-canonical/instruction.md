The repository at `/workdir` is pynetdicom, a Python implementation of the DICOM networking
protocol: Application Entities that request and accept associations, presentation context
negotiation with SCP/SCU role selection and extended negotiation, the ACSE, DIMSE and DICOM Upper
Layer services and their PDUs, the DIMSE-C and DIMSE-N service classes with the statuses they
return, and the event and handler system that applications use to take part in all of this.

Fix all implementation drift from the documentation in this repository.
Everything in scope is the core of the pynetdicom package: every Python module directly under pynetdicom/ (the apps, benchmarks and tests subpackages are not in scope), together with README.rst, docs/index.rst, every page under docs/user/, docs/service_classes/, docs/tutorials/ and docs/examples/, and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings, including their examples; in-package code comments are only supporting
evidence, and when a comment conflicts with the documentation, follow the documentation.

The environment runs Python 3.12 with pydicom 3.0.1 installed and has no network access, although
associations over the local loopback interface work; pynetdicom is imported from `/workdir`. Keep
the public API stable and keep every behavior that already matches its documentation working
exactly as it does now.
