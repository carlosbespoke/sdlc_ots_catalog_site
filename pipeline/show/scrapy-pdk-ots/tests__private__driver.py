"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself). The runner imports the third-party libraries the cases use (and the ``zope``
namespace package) from site-packages first, and only then appends the *staged* candidate tree's root
directory to ``sys.path``, after the standard library and site-packages: a candidate file named like a
standard-library or third-party module can never replace one, and the candidate's ``scrapy`` package is
imported from the trusted staged copy. Each
case is a short Python module that assigns ``result``; its source is passed to the runner on
**stdin**, read before any candidate code is imported, and executed from memory as
``case_module``. The runner also points its standard input at /dev/null and marks itself
non-dumpable before the case starts. The case runs in its own empty working directory (an opaque
temporary name that reveals nothing about the case), and no file, path, argument or environment
variable the candidate can read names or contains the case. Cases run one at a time, and before each
case starts the driver kills every other process of its own uid (anything an earlier case left
running), so no candidate process is alive while a runner holds an unread case on its stdin. The driver records the
JSON-normalised ``result`` of each case, or the name of the exception class when a case raises,
and writes the list of observations to ``argv[1]``. It never sees an expected value: the trusted
parent holds those and compares.

    python driver.py RESULT_PATH CANDIDATE_TREE < case-sources.json
"""
import ctypes
import json
import os
import signal
import subprocess
import sys
import tempfile


def seal_self():
    """Detach stdin and make this process non-dumpable (no /proc/<pid>/{fd,mem,environ} for peers)."""
    null = os.open(os.devnull, os.O_RDONLY)
    os.dup2(null, 0)
    os.close(null)
    try:
        ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)  # PR_SET_DUMPABLE, 0
    except (OSError, AttributeError):
        pass


def live_peers(me, uid):
    """Other live (non-zombie) processes of this uid."""
    peers = []
    for pid in os.listdir("/proc"):
        if not pid.isdigit() or int(pid) == me:
            continue
        try:
            with open("/proc/%s/status" % pid) as handle:
                fields = dict(line.split(":", 1) for line in handle if ":" in line)
        except (OSError, ValueError):
            continue
        if int(fields.get("Uid", "-1").split()[0]) == uid and fields.get("State", "").split()[:1] not in (["Z"], ["X"]):
            peers.append(int(pid))
    return peers


def sweep_peers():
    """Kill every other process of this uid before the next case starts (none is legitimate)."""
    me, uid = os.getpid(), os.getuid()
    if uid == 0:
        return  # authoring harnesses run this driver as root; the grader always runs it as nobody
    for _ in range(200):
        try:
            os.kill(-1, signal.SIGKILL)  # every process this uid may signal, except this one
        except ProcessLookupError:
            pass
        if not live_peers(me, uid):
            return
    raise RuntimeError("a previous case left processes that could not be stopped")


RUNNER = r'''
import ctypes, json, os, sys, types, warnings
case_dir = os.getcwd()
tree = os.environ.pop("CASE_TREE")
# The case source arrives on stdin and is consumed before any candidate code runs.
case_source = sys.stdin.read()
null = os.open(os.devnull, os.O_RDONLY)
os.dup2(null, 0)
os.close(null)
sys.stdin = open(os.devnull)
try:
    ctypes.CDLL(None, use_errno=True).prctl(4, 0, 0, 0, 0)
except (OSError, AttributeError):
    pass
# The runner starts with -S, so neither site-packages nor a sitecustomize/usercustomize module is set up
# at interpreter start: a candidate file of that name can never run before the case. Set up the venv's
# site-packages here exactly as site.main() would, minus those two customization imports, drop any
# /workdir entry, import the third-party libraries (and the zope namespace package, which a regular
# package of the same name later on sys.path would otherwise shadow) before any candidate source is
# reachable, then append the staged tree's root.
import site
site.venv(None)
site.addsitepackages(set())
sys.path[:] = [entry for entry in sys.path if not (entry == "/workdir" or entry.startswith("/workdir/"))]
import twisted.internet.defer, twisted.python.failure, zope.interface, lxml.etree, lxml.html  # noqa: E401,F401
import parsel, w3lib.url, w3lib.http, queuelib, protego, brotli, tldextract, itemadapter  # noqa: E401,F401
import cssselect, defusedxml, OpenSSL, cryptography, pydispatch, packaging.version  # noqa: E401,F401
sys.path.append(tree)
warnings.simplefilter("ignore")


def norm(value, depth=0):
    if depth > 14:
        return repr(value)[:500]
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value[:2000]
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, bytes):
        return {"bytes": value.decode("latin-1")[:2000]}
    if isinstance(value, dict):
        return {str(k): norm(v, depth + 1) for k, v in value.items()}
    if isinstance(value, (set, frozenset)):
        return {"set": sorted((norm(v, depth + 1) for v in value), key=repr)}
    if isinstance(value, (list, tuple)):
        return [norm(v, depth + 1) for v in value]
    return {"repr": repr(value)[:500]}


try:
    case_module = types.ModuleType("case_module")
    sys.modules["case_module"] = case_module
    exec(compile(case_source, "<case>", "exec"), case_module.__dict__)
    out = {"value": norm(case_module.result)}
except BaseException as exception:  # noqa: BLE001
    out = {"error": type(exception).__name__[:100]}
sys.stdout.flush()
with open(os.path.join(case_dir, "result.json"), "w") as handle:
    json.dump(out, handle)
os._exit(0)
'''

PREAMBLE = r'''"""Replay helpers: the colleague original's tests/private/replay_driver.py without main(), unchanged.

`observe(call)` drives one scheduler through its public lifecycle (from_crawler, open, enqueue_request,
next_request, len, has_pending_requests, close) and returns admissions, drain order, sizes, pending flags
and scheduler statistics.
"""
import json
import sys

from scrapy import Request, Spider
from scrapy.core.scheduler import Scheduler
from scrapy.crawler import Crawler
from scrapy.statscollectors import MemoryStatsCollector
from scrapy.utils.request import RequestFingerprinter


def observe(call):
    """Check duplicate admission, request order, counts and exhaustion together."""
    settings = {'SCHEDULER_PRIORITY_QUEUE': 'scrapy.pqueues.ScrapyPriorityQueue'}
    settings.update(call.get('settings', {}))
    crawler = Crawler(Spider, settings=settings)
    crawler.stats = MemoryStatsCollector(crawler)
    crawler.request_fingerprinter = RequestFingerprinter(crawler)
    spider = Spider.from_crawler(crawler, name='replay')
    scheduler = Scheduler.from_crawler(crawler)
    scheduler.open(spider)
    admissions = []
    sizes = []
    pending = []
    drained = []
    for index, spec in enumerate(call['requests']):
        kwargs = dict(spec)
        kwargs['meta'] = dict(kwargs.get('meta', {}), replay_label=index)
        request = Request(**kwargs)
        admissions.append(scheduler.enqueue_request(request))
        sizes.append(len(scheduler))
        pending.append(scheduler.has_pending_requests())
    # Bounded calls include two reads beyond the maximum possible queue size.
    for _ in range(len(call['requests']) + 2):
        request = scheduler.next_request()
        drained.append(None if request is None else request.meta['replay_label'])
        sizes.append(len(scheduler))
        pending.append(scheduler.has_pending_requests())
    stats = {key: crawler.stats.get_value(key, 0) for key in (
        'scheduler/enqueued', 'scheduler/enqueued/memory', 'scheduler/enqueued/disk',
        'scheduler/dequeued', 'scheduler/dequeued/memory', 'scheduler/dequeued/disk')}
    scheduler.close('finished')
    return {'admissions': admissions, 'drained': drained, 'sizes': sizes,
            'pending': pending, 'stats': stats}


# ---------------------------------------------------------------------------------------------------------
# Coverage helpers (OTS documentation-coverage groups, coverage_cases.py). Offline: every request and
# response is built locally; nothing is downloaded.
import asyncio
import types

from scrapy.http import (FormRequest, Headers, HtmlResponse, JsonRequest, JsonResponse, Response,
                         TextResponse, XmlResponse)
from scrapy.utils.misc import build_from_crawler
from scrapy.utils.test import get_crawler


def make_crawler(settings=None, spider_cls=Spider, name='cov', **spider_attrs):
    """A crawler with its spider created (no engine, no download) and an in-memory stats collector."""
    crawler = get_crawler(spider_cls, dict(settings or {}))
    crawler.spider = crawler._create_spider(name, **spider_attrs)
    return crawler


def component(cls, settings=None, spider_cls=Spider, **spider_attrs):
    """Build a middleware or extension the way Scrapy does (from_crawler), plus its crawler."""
    crawler = make_crawler(settings, spider_cls, **spider_attrs)
    return build_from_crawler(cls, crawler), crawler


def run(awaitable):
    """Run a coroutine to completion in a fresh event loop."""
    return asyncio.run(awaitable)


def drain(agen):
    """Collect an async iterator into a list."""
    async def collect():
        return [item async for item in agen]
    return asyncio.run(collect())


async def aiter_of(items):
    for item in items:
        yield item


def kind(obj):
    """Short type name of a middleware result (None, Request, Response, HtmlResponse, ...)."""
    return None if obj is None else type(obj).__name__
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "CASE_TREE": tree}
    try:
        subprocess.run([sys.executable, "-I", "-S", "-B", "-c", RUNNER], cwd=directory, env=environment,
                       input=(PREAMBLE + "\n" + source + "\n").encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=90)
    except subprocess.TimeoutExpired:
        return {"error": "timeout"}
    try:
        with open(os.path.join(directory, "result.json")) as handle:
            return json.load(handle)
    except (OSError, ValueError):
        return {"error": "no-result"}


def main():
    sources = json.loads(sys.stdin.read())
    seal_self()
    result_path, tree = sys.argv[1], os.path.abspath(sys.argv[2])
    scratch = tempfile.mkdtemp(prefix="obs-")
    results = []
    for source in sources:
        sweep_peers()
        results.append(run_case(source, tree, scratch))
    sweep_peers()
    with open(result_path, "w") as handle:
        json.dump({"results": results}, handle)


if __name__ == "__main__":
    main()
