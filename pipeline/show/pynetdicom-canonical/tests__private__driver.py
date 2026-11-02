"""Observation driver.

Runs inside the sandboxed child process as an unprivileged user with the candidate's own
repository tree on ``sys.path``. It reads the whole case list from **stdin** before importing any
candidate code, runs each case in a fresh scratch directory and writes the observations it made to
the file named by ``argv[1]``. It never sees an expected value: the trusted parent holds those and
compares.

Each case is a short Python snippet that assigns ``result``. Snippets run in fresh namespaces, each
in its own empty working directory, and the working directory, environment, ``sys.path`` and the
set of imported modules are restored after every case, so a candidate that breaks one function
only loses the observations that depend on it. Association servers and associations a case opens
through the preamble helpers are shut down after the case, whatever happened. A raised exception is
itself an observation: that the case raised, not which exception class it raised (cases that
depend on a documented exception class check it themselves).
"""
import json
import logging
import os
import sys
import tempfile
import threading
import traceback
import warnings


def norm(value, depth=0):
    """A JSON-stable rendering of an observed value."""
    if depth > 10:
        return repr(value)
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, str):
        return str(value)
    if isinstance(value, int):
        return int(value)
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, bytes):
        return {"bytes": value.hex()}
    if isinstance(value, dict):
        return {"dict": sorted(([norm(k, depth + 1), norm(v, depth + 1)] for k, v in value.items()),
                               key=repr)}
    if isinstance(value, (set, frozenset)):
        return {"set": sorted((norm(v, depth + 1) for v in value), key=repr)}
    if isinstance(value, (list, tuple)):
        return [norm(v, depth + 1) for v in value]
    if isinstance(value, os.PathLike):
        return {"path": os.fspath(value)}
    return {"object": type(value).__name__}


PREAMBLE = r'''
import io
import logging
import threading
import time

logging.disable(logging.CRITICAL)
_SERVERS = []
_ASSOCS = []


def raises(call, *exceptions):
    """Run `call()`; return its value, or the name of the first class in `exceptions` that the
    raised exception is an instance of, or "raised" for any other exception."""
    try:
        return call()
    except Exception as exception:  # noqa: BLE001
        for kind in exceptions:
            if isinstance(exception, kind):
                return kind.__name__
        return "raised"


def quiet(ae, timeout=5):
    """Short timeouts for loopback work."""
    ae.acse_timeout = timeout
    ae.dimse_timeout = timeout
    ae.network_timeout = timeout
    return ae


def serve(ae, handlers=(), **kwargs):
    """Start `ae` as a non-blocking server on 127.0.0.1 with an ephemeral port.
    Returns the port. The server is shut down after the case."""
    quiet(ae)
    server = ae.start_server(("127.0.0.1", 0), block=False, evt_handlers=list(handlers), **kwargs)
    _SERVERS.append(server)
    return server.server_address[1]


def connect(ae, port, **kwargs):
    """Associate `ae` with the local server on `port` (released/aborted after the case)."""
    quiet(ae)
    assoc = ae.associate("127.0.0.1", port, **kwargs)
    _ASSOCS.append(assoc)
    return assoc


def ds(**elements):
    """A pydicom Dataset with the given keyword elements."""
    from pydicom.dataset import Dataset
    value = Dataset()
    for keyword, item in elements.items():
        setattr(value, keyword, item)
    return value


def image(sop_class="1.2.840.10008.5.1.4.1.1.2", instance="1.2.3.4.5.6.7",
          transfer_syntax="1.2.840.10008.1.2.1", **elements):
    """A small composite instance for C-STORE (CT Image Storage, Explicit VR Little Endian by
    default), with the file meta Transfer Syntax UID that send_c_store uses to pick a context."""
    from pydicom.dataset import FileMetaDataset
    fields = {"PatientName": "Test^Patient", "PatientID": "1234"}
    fields.update(elements)
    value = ds(SOPClassUID=sop_class, SOPInstanceUID=instance, **fields)
    value.file_meta = FileMetaDataset()
    value.file_meta.TransferSyntaxUID = transfer_syntax
    return value


def status_of(dataset):
    """The Status value of a response dataset, or None for an empty/missing response."""
    if dataset is None:
        return None
    return dataset.get("Status", None)


def cx_summary(contexts):
    """[(context id, abstract syntax, result, transfer syntax or None, as_scu, as_scp), ...]"""
    rows = []
    for cx in contexts:
        ts = cx.transfer_syntax[0] if cx.transfer_syntax else None
        rows.append([cx.context_id, str(cx.abstract_syntax), cx.result,
                     None if ts is None else str(ts), cx.as_scu, cx.as_scp])
    return rows
'''


def cleanup(namespace):
    for assoc in namespace.get("_ASSOCS", []):
        try:
            if assoc.is_established:
                assoc.abort()
        except BaseException:  # noqa: BLE001
            pass
    for server in namespace.get("_SERVERS", []):
        try:
            server.shutdown()
        except BaseException:  # noqa: BLE001
            pass
    # Give association threads a moment to wind down so they do not outlive the case.
    for thread in threading.enumerate():
        if thread is not threading.main_thread() and thread.is_alive():
            thread.join(timeout=2)


def main():
    output = sys.argv[1]
    argv = list(sys.argv)
    cases = json.loads(sys.stdin.read())
    sys.stdin.close()
    sys.setrecursionlimit(2000)
    # Load pynetdicom's third-party dependencies once, after the case list is consumed, so that the
    # per-case module cleanup below only ever re-imports pynetdicom itself.
    for dependency in ("pydicom", "pydicom.dataset", "pydicom.uid", "pydicom.filewriter",
                       "pydicom.filereader", "pydicom.tag", "pydicom.valuerep", "pydicom.datadict",
                       "pydicom.sequence", "pydicom.dataelem", "pydicom.charset", "pydicom.config",
                       "pydicom.encaps", "pydicom.misc", "socket", "socketserver", "ssl", "select",
                       "selectors", "queue", "struct", "datetime", "copy", "enum", "inspect",
                       "contextvars", "ctypes", "unicodedata", "tempfile", "zlib", "textwrap",
                       "collections", "importlib.metadata", "json", "math"):
        try:
            __import__(dependency)
        except Exception:  # noqa: BLE001 - a missing dependency shows up in the cases
            pass
    home = os.getcwd()
    environment = dict(os.environ)
    path = list(sys.path)
    scratch_root = tempfile.mkdtemp(prefix="observations-")
    results = {}
    for index, case in enumerate(cases):
        identifier = case["id"]
        work = os.path.join(scratch_root, f"case-{index:04d}")
        os.makedirs(work)
        os.chdir(work)
        before = set(sys.modules)
        namespace = {"__name__": "__observation__"}
        try:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                exec(PREAMBLE + case["code"], namespace)
                results[identifier] = {"ok": norm(namespace.get("result"))}
        except BaseException:  # noqa: BLE001 - a failing case is an observation
            results[identifier] = {"error": "raised"}
            if os.environ.get("PYNETDICOM_OBSERVATION_TRACE"):
                results[identifier]["trace"] = traceback.format_exc(limit=6)[-1500:]
        finally:
            cleanup(namespace)
            sys.settrace(None)
            os.chdir(home)
            os.environ.clear()
            os.environ.update(environment)
            sys.path[:] = path
            sys.argv[:] = argv
            # Drop every module the case imported, pynetdicom included, so each case starts from a
            # freshly imported pynetdicom (its configuration and registries are module state).
            for name in set(sys.modules) - before:
                del sys.modules[name]
            logging.disable(logging.NOTSET)
    with open(output, "w") as stream:
        json.dump({"results": results}, stream, sort_keys=True, default=str)
    # Association threads are daemons; exit without waiting on any that a candidate left behind.
    sys.stdout.flush()
    os._exit(0)


if __name__ == "__main__":
    main()
