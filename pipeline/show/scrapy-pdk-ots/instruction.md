The repository at `/workdir` is Scrapy, a Python framework for crawling websites and extracting structured
data. Its request and response layer carries each `Request` from a spider through the spider and downloader
middlewares to the scheduler, which filters duplicates by request fingerprint, keeps requests in priority
queues (in memory, or on disk for a persistent job) and hands them to the downloader; responses come back through
the same middlewares. The AutoThrottle extension adjusts download delays, and a job directory lets a crawl be
paused and resumed.

Fix all implementation drift from the documentation in this part of the repository.
Everything in scope is Scrapy's request and response layer, its scheduling and duplicate filtering, job persistence, AutoThrottle and its built-in downloader and spider middlewares: the scrapy/http/ package, scrapy/core/scheduler.py, scrapy/pqueues.py, scrapy/squeues.py, scrapy/dupefilters.py, scrapy/utils/request.py, scrapy/utils/url.py, scrapy/utils/response.py, scrapy/utils/job.py, scrapy/extensions/throttle.py, scrapy/extensions/spiderstate.py, scrapy/exceptions.py and the scrapy/downloadermiddlewares/ and scrapy/spidermiddlewares/ packages, together with the documentation pages docs/topics/request-response.rst, scheduler.rst, jobs.rst, autothrottle.rst, downloader-middleware.rst, spider-middleware.rst, cookies.rst and exceptions.rst and the module, class and function docstrings of the in-scope modules.

Where the code and the documentation disagree about runtime behavior, the documentation is the
authority: change the implementation so that it does what the documentation says, and do not edit
or delete documentation to make a disagreement go away. The documentation is those pages and the
in-package docstrings and comments of the in-scope modules (including the `#:` attribute documentation
that the pages render), including their examples. The rest of the repository is context, not part of
the task.

The environment runs Python 3.11 with Scrapy's dependencies installed and has no network access;
`scrapy` is imported from `/workdir`. No website is reachable, and none of the work needs one: requests,
responses, middlewares and the scheduler can be built and driven directly in Python. The upstream test
suite is not supplied; write your own checks as needed. Keep the public API stable and keep every
behavior that already matches its documentation working exactly as it does now.
