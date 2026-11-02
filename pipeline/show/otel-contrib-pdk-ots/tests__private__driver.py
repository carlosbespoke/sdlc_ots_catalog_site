"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable,
user site, working directory or startup customization module reaches it; the runner sets up the venv's
site-packages itself). The image installs every workspace member of the repository
editable: site-packages ``.pth`` files append ``/workdir/<member>/src`` after the standard library and
site-packages. The runner removes those ``/workdir`` entries, imports the third-party libraries the cases
use from site-packages, and then appends the same member source directories of the *staged* candidate
tree in the same order, so the candidate is imported from the trusted staged copy and still only after
the standard library and site-packages: a candidate file named like a standard-library or third-party
module can never replace one. Each
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
# The editable installs put /workdir/<member>/src on sys.path (site-packages .pth files, after the
# standard library and site-packages). Drop them, import the third-party libraries from site-packages
# before any candidate source is reachable, then append the staged tree's member sources in their order.
# The member list is read from the site-packages .pth files themselves (in the order site processes them),
# so it does not depend on what exists under /workdir in this container.
# The runner starts with -S, so neither site-packages nor a sitecustomize/usercustomize module is set up
# at interpreter start: a candidate file of that name in a member src/ directory (which the editable .pth
# files put on sys.path) can never run before the case. Set up the venv's site-packages here exactly as
# site.main() would, minus those two customization imports.
import glob, site
site.venv(None)
site.addsitepackages(set())
members = []
for directory in site.getsitepackages():
    for pth in sorted(glob.glob(os.path.join(directory, "*.pth"))):
        with open(pth) as handle:
            for line in handle:
                line = line.strip()
                if (line == "/workdir" or line.startswith("/workdir/")) and line not in members:
                    members.append(line)
sys.path[:] = [entry for entry in sys.path if not (entry == "/workdir" or entry.startswith("/workdir/"))]
import aiohttp, httpx, requests, urllib3, wrapt  # noqa: E401,F401
import opentelemetry.sdk.trace, opentelemetry.sdk.metrics, opentelemetry.semconv  # noqa: E401,F401
sys.path.extend(os.path.join(tree, os.path.relpath(entry, "/workdir")) for entry in members)
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

PREAMBLE = r'''# Case preamble of otel-contrib-pdk-ots (embedded in tests/private/driver.py, run before every case).
#
# Part 1 is the colleague original's replay helper `observe` (pdk-drift-repository-0fc024cbd7cb v1,
# tests/private/replay_driver.py without its `main`), unchanged: it drives Requests through real SDK
# spans and an offline transport adapter. Each replay case is `result = observe(<call>)`.
import json
import os
import sys


def observe(call):
    # Every case has a fresh import snapshot and public instrumentation lifecycle.
    for key in list(os.environ):
        if key.startswith('OTEL_'):
            del os.environ[key]
    os.environ.update(call.get('env', {}))
    import requests
    from requests.adapters import BaseAdapter
    from requests.structures import CaseInsensitiveDict
    from opentelemetry.instrumentation.requests import RequestsInstrumentor
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    events = []

    class Transport(BaseAdapter):
        def send(self, request, **kwargs):
            events.append(['send', request.headers.get('X-Hook')])
            response = requests.Response()
            response.status_code = 200
            response.url = request.url
            response.request = request
            response.headers = CaseInsensitiveDict(call.get('response', {}))
            response._content = b'offline'
            return response

        def close(self):
            pass

    def request_hook(span, request):
        events.append(['request', span.is_recording(), isinstance(request, requests.PreparedRequest)])
        request.headers['X-Hook'] = 'changed'
        span.set_attribute('hook.request', 'yes')

    def response_hook(span, request, response):
        events.append(['response', span.is_recording(), response.request is request, response.status_code])
        span.set_attribute('hook.response', 'yes')

    instrumentor = RequestsInstrumentor()
    options = {'tracer_provider': provider}
    if 'excluded' in call:
        options['excluded_urls'] = call['excluded']
    if call.get('hooks') in ('both', 'request'):
        options['request_hook'] = request_hook
    if call.get('hooks') in ('both', 'response'):
        options['response_hook'] = response_hook
    os.environ.update(call.get('after_import', {}))
    instrumentor.instrument(**options)
    sessions = [requests.Session(), requests.Session()]
    for session in sessions:
        session.trust_env = False
        session.mount('https://', Transport())
    results = []
    for step in call.get('steps', [{}]):
        if step.get('action') == 'session_off':
            instrumentor.uninstrument_session(sessions[step.get('session', 0)])
        elif step.get('action') == 'off':
            instrumentor.uninstrument()
        elif step.get('action') == 'on':
            os.environ.update(step.get('env', {}))
            instrumentor.instrument(**options)
        else:
            os.environ.update(step.get('env', {}))
            result = sessions[step.get('session', 0)].get(
                step.get('url', call.get('url', 'https://example.test/resource')),
                headers=call.get('headers', {}), timeout=1,
            )
            results.append([result.status_code, result.text])
    spans = []
    for span in exporter.get_finished_spans():
        spans.append({k: list(v) if isinstance(v, (tuple, list)) else v
                      for k, v in span.attributes.items()
                      if k.startswith(('http.request.header.', 'http.response.header.', 'hook.'))})
    instrumentor.uninstrument()
    for session in sessions:
        session.close()
    provider.shutdown()
    return {'responses': results, 'events': events, 'spans': spans}


# Part 2: helpers of the OTS documentation-coverage groups (coverage_cases.py). Everything is offline:
# HTTP clients talk to a loopback server started in this process, and telemetry goes to the SDK's
# in-memory span exporter and metric reader.
import asyncio
import http.server
import threading
import types
import urllib.parse

SERVER_LOG = []


class _LoopbackHandler(http.server.BaseHTTPRequestHandler):
    """Answers every method. Query `status=N` sets the status, each `h=Name:Value` adds a response header;
    the body is a short JSON document naming the path. Every request is appended to SERVER_LOG."""
    protocol_version = "HTTP/1.1"

    def _answer(self):
        length = int(self.headers.get("Content-Length") or 0)
        body = self.rfile.read(length) if length else b""
        parts = urllib.parse.urlsplit(self.path)
        query = urllib.parse.parse_qs(parts.query)
        SERVER_LOG.append({"method": self.command, "path": parts.path,
                           "headers": {k.lower(): v for k, v in self.headers.items()},
                           "body": body.decode("latin-1")})
        payload = json.dumps({"path": parts.path}).encode()
        self.send_response(int(query.get("status", ["200"])[0]))
        for item in query.get("h", []):
            name, _, value = item.partition(":")
            self.send_header(name, value)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(payload)

    do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = do_PATCH = do_OPTIONS = _answer

    def log_message(self, *args):
        pass


def loopback():
    """Start the loopback HTTP server; return its base URL (http://127.0.0.1:PORT)."""
    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _LoopbackHandler)
    server.daemon_threads = True
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return "http://127.0.0.1:%d" % server.server_address[1]


def telemetry(set_global=False):
    """A TracerProvider with an in-memory exporter and a MeterProvider with an in-memory reader."""
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import InMemoryMetricReader
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
    exporter = InMemorySpanExporter()
    tracer_provider = TracerProvider()
    tracer_provider.add_span_processor(SimpleSpanProcessor(exporter))
    reader = InMemoryMetricReader()
    meter_provider = MeterProvider(metric_readers=[reader])
    if set_global:
        from opentelemetry import metrics, trace
        trace.set_tracer_provider(tracer_provider)
        metrics.set_meter_provider(meter_provider)
    return types.SimpleNamespace(tp=tracer_provider, mp=meter_provider, exporter=exporter, reader=reader)


def scrub(value, base):
    """Replace the loopback base URL and its host:port in strings (ports are random)."""
    host = base.split("//", 1)[1]
    if isinstance(value, str):
        return value.replace(base, "BASE").replace(host, "HOST")
    if isinstance(value, dict):
        return {k: scrub(v, base) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [scrub(v, base) for v in value]
    return value


def spans(t, base=None, keys=(), prefixes=()):
    """Finished spans as name, kind, status and the selected attributes (tuples as lists)."""
    out = []
    for span in t.exporter.get_finished_spans():
        attributes = {k: (list(v) if isinstance(v, tuple) else v) for k, v in sorted(span.attributes.items())
                      if k in keys or k.startswith(tuple(prefixes))}
        row = {"name": span.name, "kind": span.kind.name, "status": span.status.status_code.name,
               "attributes": attributes}
        out.append(scrub(row, base) if base else row)
    return out


def metric_summary(t):
    """Metric name -> unit, number of points, total count and the histogram bucket boundaries."""
    data = t.reader.get_metrics_data()
    out = {}
    for resource_metrics in (data.resource_metrics if data else []):
        for scope_metrics in resource_metrics.scope_metrics:
            for metric in scope_metrics.metrics:
                points = list(metric.data.data_points)
                out[metric.name] = {
                    "unit": metric.unit, "points": len(points),
                    "count": sum(getattr(point, "count", 0) for point in points),
                    "bounds": [float(b) for b in (getattr(points[0], "explicit_bounds", None) or [])] if points else [],
                }
    return out


def raised(function, *args, **kwargs):
    try:
        function(*args, **kwargs)
    except Exception as exception:  # noqa: BLE001
        return type(exception).__name__
    return None


def run_async(coroutine):
    return asyncio.run(coroutine)


def instrument_cli(arguments, extra_env=None):
    """Run the `opentelemetry-instrument` entry point (auto_instrumentation.run) in a child interpreter that
    imports the same sources as this case (no site initialisation: it gets this case's sys.path); its source
    goes on stdin, so the command line holds only the CLI arguments. Returns (exit code, stdout, stderr tail)."""
    import subprocess
    code = ("import sys\nsys.path[:] = %r\nsys.argv = %r\n"
            "from opentelemetry.instrumentation.auto_instrumentation import run\nrun()\n"
            % (list(sys.path), ["opentelemetry-instrument"] + list(arguments)))
    environment = {k: v for k, v in os.environ.items() if not k.startswith("OTEL_") and k != "PYTHONPATH"}
    environment.update(extra_env or {})
    completed = subprocess.run([sys.executable, "-I", "-S", "-"], input=code, capture_output=True, text=True,
                               timeout=60, env=environment)
    return completed.returncode, completed.stdout, completed.stderr[-300:]


def env_lines(text, prefixes=("OTEL_",)):
    """KEY=VALUE lines of `env` output whose key starts with one of the prefixes, as a sorted dict."""
    pairs = (line.split("=", 1) for line in text.splitlines() if "=" in line)
    return dict(sorted((k, v) for k, v in pairs if k.startswith(tuple(prefixes))))
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
