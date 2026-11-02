"""Observe calls in untrusted source without receiving their answers.

The root-owned grader supplies only public invocation data on stdin. This process imports
the candidate-controlled source and reports raw returns, exceptions, selected object state
and argument mutations. Expected observations never enter this interpreter; the trusted
parent compares them after this process exits.

Run as a script this is the ordinary caller: a plain interpreter with no test runner
anywhere. The observing is kept in probe(), separate from where the work list comes from
and where the results go, so the grader can also drive it from inside a real pytest run
when it needs to know whether a function behaves differently while a test is watching.
"""
import json
import os
import re
import sys
import types

# One description of how a recorded value is written down and read back, shared verbatim
# by the recorder, the build time replay and the grading worker. Three copies of a
# serialisation drift, and a drift here is a correct repair called a difference.
#
# Three forms, all of them text, so a recording made before any of this still reads.
#
#   a repr        the value printed, kept only when eval of it prints identically
#   @import m:q   a class or a function, named by where it is defined
#   @obj {...}    an object, named by its class and the serialisable part of its state
#
# The third one is why methods are probeable at all. A bound method's receiver is
# argument zero, and almost no receiver has a literal repr, so before this every method
# on a class of its own was unrecordable and object oriented code was unprobeable by
# construction. The __init__ path already had the shape of the answer, which is to
# reproduce an object by building one rather than by printing it; this is that move made
# available in every position instead of only in argument zero of a constructor.
#
# The stand-in is never a stub. It is the real class, taken out of the tree under test, so
# the methods that run on it are the ones being graded. What it can lose is state: an
# attribute that cannot be written down is left off. That is why nothing here is trusted
# on its own. Every widened recording is replayed against the untouched tree through this
# same path and has to reproduce what was recorded exactly, so a stand-in that lost
# something the function reads is dropped at build time rather than failing an honest
# repair at grading time.
IMPORT_MARK = "@import "
OBJECT_MARK = "@obj "
MAX_TEXT = 2000
MAX_SPEC = 12000
MAX_DEPTH = 3
MAX_FIELDS = 60
SAFE_NAMES = {"set": set, "frozenset": frozenset, "bytearray": bytearray}
ADDRESS = re.compile(r"0x[0-9a-fA-F]{6,}")
# Ordered so the most derived builtin is found first: bool before int, and the containers
# before anything else. A class cannot inherit from two of these.
BUILTIN_BASES = (dict, list, set, frozenset, tuple, bytearray, bytes, str, bool, int,
                 float, complex)


def _importable(module, mod):
    """Whether a reference to something in this module still resolves at grading time.

    Only the recorder can answer this, because only the recorder can see where the module
    came from, so it replaces this. Reading a recording back never asks the question: the
    reference was checked when it was written.
    """
    return True


def _same_type(a, b):
    """The same types all the way down, not merely the same printing.

    A subclass of a builtin prints exactly like the builtin, so printing alone accepted a
    dict subclass and read it back as a plain dict. That is the silent kind of unfair: the
    stand-in answers attribute access differently from the real thing, the function under
    test reads it, and an honest repair is called a difference for a reason no one can
    see. A value is only written down as a literal when reading it back gives the same
    types in the same places.
    """
    if type(a) is not type(b):
        return False
    try:
        if isinstance(a, dict):
            for (ka, va), (kb, vb) in zip(a.items(), b.items()):
                if not _same_type(ka, kb) or not _same_type(va, vb):
                    return False
        elif isinstance(a, (list, tuple, set, frozenset)):
            for x, y in zip(a, b):
                if not _same_type(x, y):
                    return False
    except BaseException:
        return False
    return True


def _literal(value):
    """repr(value), but only when eval of it reproduces the same value. Else None.

    repr and eval is the serialisation, chosen because it is self checking: a value is
    kept only when it can be written down and read back to something that prints
    identically and is built out of the same types, which is exactly the property a
    replay needs. It accepts literals and containers of literals and rejects everything
    else, including anything carrying a memory address.
    """
    try:
        text = repr(value)
    except BaseException:
        return None
    if len(text) > MAX_TEXT or ADDRESS.search(text):
        return None
    try:
        back = eval(text, {"__builtins__": {}}, dict(SAFE_NAMES))
        if repr(back) != text or not _same_type(back, value):
            return None
    except BaseException:
        return None
    return text


def _ref(value):
    """module:qualname for a class or a function, when that name gives it back.

    A class and a function do not print in a form that can be read back, and they do not
    need to: they are reproduced by importing them. Resolution happens against the tree
    under test, so an edited definition is the one that gets used.
    """
    if not (isinstance(value, type) or isinstance(value, types.FunctionType)
            or isinstance(value, types.BuiltinFunctionType)):
        return None
    module = getattr(value, "__module__", None)
    qualname = getattr(value, "__qualname__", None)
    if not module or not qualname or "<" in qualname:
        return None
    mod = sys.modules.get(module)
    if mod is None or not _importable(module, mod):
        return None
    found = mod
    for part in qualname.split("."):
        found = getattr(found, part, None)
        if found is None:
            return None
    return module + ":" + qualname if found is value else None


def _plain(value):
    """The builtin content of a subclass of a builtin, written down. Else None.

    A dict subclass keeps its items where dict keeps them rather than in __dict__, so
    rebuilding one from its attributes alone would hand the function an empty mapping and
    call whatever came back a repair. Losing the contents is not allowed, so a value whose
    contents cannot be written down is not encoded at all.
    """
    for kind in BUILTIN_BASES:
        if isinstance(value, kind) and type(value) is not kind:
            return kind, _literal(kind(value))
    return None, None


def _state_items(value):
    """The attributes an object keeps, whether in __dict__ or in slots."""
    out = {}
    try:
        held = vars(value)
    except BaseException:
        held = {}
    try:
        for name, item in list(held.items()):
            if isinstance(name, str):
                out[name] = item
    except BaseException:
        pass
    try:
        for cls in type(value).__mro__:
            slots = cls.__dict__.get("__slots__") or ()
            if isinstance(slots, str):
                slots = (slots,)
            for name in slots:
                if not isinstance(name, str) or name in ("__dict__", "__weakref__"):
                    continue
                if name in out:
                    continue
                try:
                    out[name] = getattr(value, name)
                except BaseException:
                    pass
    except BaseException:
        pass
    return out


def _encode(value, depth=0):
    """How this value is written down, in whichever of the three forms fits. Else None."""
    text = _literal(value)
    if text is not None:
        return text
    ref = _ref(value)
    if ref is not None:
        return IMPORT_MARK + ref
    if depth >= MAX_DEPTH:
        return None
    cls = type(value)
    cls_ref = _ref(cls)
    if cls_ref is None or cls.__module__ == "builtins":
        return None
    spec = {"class": cls_ref}
    kind, content = _plain(value)
    if kind is not None:
        if content is None:
            return None
        spec["base"] = content
    state = {}
    items = _state_items(value)
    if len(items) > MAX_FIELDS:
        return None
    for name in sorted(items):
        # An attribute that cannot be written down is left off rather than guessed at,
        # and the build time self check is what decides whether leaving it off mattered.
        sub = _encode(items[name], depth + 1)
        if sub is not None:
            state[name] = sub
    spec["state"] = state
    text = OBJECT_MARK + json.dumps(spec, sort_keys=True)
    return None if len(text) > MAX_SPEC else text


def _resolve(ref):
    module, _, qualname = ref.partition(":")
    found = __import__(module, fromlist=["_"])
    for part in qualname.split("."):
        found = getattr(found, part)
    return found


def _blank(cls):
    """An instance of cls with nothing run on it.

    object.__new__ is the one that runs no code of the class's own, so it is tried first.
    A type implemented in C refuses it, and for those the class's own __new__ with no
    arguments is the only way in.
    """
    try:
        return object.__new__(cls)
    except TypeError:
        return cls.__new__(cls)


def _rebuild(spec):
    """The stand-in: the real class, an instance of it, and the state that was kept."""
    cls = _resolve(spec["class"])
    content = spec.get("base")
    if content is None:
        obj = _blank(cls)
    else:
        content = _value(content)
        kind = None
        for candidate in BUILTIN_BASES:
            if issubclass(cls, candidate):
                kind = candidate
                break
        if kind is dict:
            obj = dict.__new__(cls)
            dict.update(obj, content)
        elif kind is list:
            obj = list.__new__(cls)
            list.extend(obj, content)
        elif kind is set:
            obj = set.__new__(cls)
            set.update(obj, content)
        elif kind is bytearray:
            obj = bytearray.__new__(cls)
            bytearray.extend(obj, content)
        elif kind is None:
            obj = _blank(cls)
        else:
            obj = kind.__new__(cls, content)
    for name, text in (spec.get("state") or {}).items():
        setattr(obj, name, _value(text))
    return obj


def _value(text):
    """The value a recorded text denotes."""
    if isinstance(text, str):
        if text.startswith(IMPORT_MARK):
            return _resolve(text[len(IMPORT_MARK):])
        if text.startswith(OBJECT_MARK):
            return _rebuild(json.loads(text[len(OBJECT_MARK):]))
    return eval(text, {"__builtins__": {}}, dict(SAFE_NAMES))


def _reshow(value, template):
    """Describe a value again the way it was described before the call.

    What a call did to its arguments is compared as text, so both sides have to describe
    the same object the same way. A live receiver carries far more than was written down
    and a stand-in carries only what was, so describing either one freely would make every
    method that mutates its receiver look changed. The recorded description is the
    template: the same fields, in the same order, and nothing else.
    """
    if isinstance(template, str) and template.startswith(OBJECT_MARK):
        try:
            spec = json.loads(template[len(OBJECT_MARK):])
        except ValueError:
            return None
        out = {"class": spec.get("class")}
        if spec.get("base") is not None:
            kind, content = _plain(value)
            out["base"] = content
        state = {}
        for name, sub in (spec.get("state") or {}).items():
            try:
                state[name] = _reshow(getattr(value, name), sub)
            except BaseException:
                state[name] = None
        out["state"] = state
        return OBJECT_MARK + json.dumps(out, sort_keys=True)
    if isinstance(template, str) and template.startswith(IMPORT_MARK):
        ref = _ref(value)
        return IMPORT_MARK + ref if ref is not None else None
    return _literal(value)


MISSING = "<VPROBE-MISSING>"


def _payload():
    raw = sys.stdin.read()
    try:
        behind = os.path.realpath("/proc/self/fd/0")
        if os.path.isfile(behind):
            os.unlink(behind)
    except OSError:
        pass
    try:
        sys.stdin.close()
    except Exception:
        pass
    sys.argv = [sys.argv[0]]
    return json.loads(raw)


def _stdout_say(**fields):
    sys.stdout.write("VPROBE " + json.dumps(fields, sort_keys=True) + "\n")
    sys.stdout.flush()


def _show(value):
    try:
        text = repr(value)
    except BaseException as exc:
        text = "<repr raised " + type(exc).__name__ + ">"
    return text[:20000]


def _observe(value, template):
    """How an argument is described after the call, so the grader can compare it.

    An argument written down as an object was never described by printing it, because a
    live receiver carries far more than was written down and a rebuilt one carries only
    what was. The recorded description is the template: the same fields and nothing else.
    """
    if isinstance(template, str) and (template.startswith(OBJECT_MARK)
                                      or template.startswith(IMPORT_MARK)):
        return _reshow(value, template)
    return _show(value)


def _types(exc):
    return [t.__module__ + "." + t.__qualname__ for t in type(exc).__mro__]


def _one(fn, call):
    args = [_value(text) for text in call.get("args") or []]
    kwargs = {key: _value(text) for key, text in (call.get("kwargs") or {}).items()}
    try:
        result = fn(*args, **kwargs)
    except BaseException as exc:
        outcome = {"kind": "raise", "types": _types(exc)}
    else:
        if call.get("outcome_kind") == "state":
            fields = {}
            for field in call.get("state_fields") or []:
                try:
                    fields[field] = _show(getattr(result, field))
                except BaseException:
                    fields[field] = MISSING
            outcome = {"kind": "state", "fields": fields}
        else:
            outcome = {"kind": "return", "repr": _show(result)}
    given = call.get("args") or []
    after_args = {}
    for index in call.get("after_args") or []:
        try:
            after_args[str(index)] = _observe(args[int(index)], given[int(index)])
        except BaseException:
            after_args[str(index)] = MISSING
    after_kwargs = {}
    for key in call.get("after_kwargs") or []:
        try:
            after_kwargs[key] = _observe(kwargs[key],
                                         (call.get("kwargs") or {}).get(key))
        except BaseException:
            after_kwargs[key] = MISSING
    return {"outcome": outcome, "after_args": after_args,
            "after_kwargs": after_kwargs}


def _search_paths(root, roots):
    # Same rule as the build time replay: a source root that IS a package goes on the
    # path by its parent, because that is the directory `import <package>` looks in.
    out = []
    for item in roots:
        directory = os.path.join(root, item)
        if not os.path.isdir(directory):
            continue
        if os.path.exists(os.path.join(directory, "__init__.py")):
            out.append(os.path.dirname(directory))
        else:
            out.append(directory)
    out.append(root)
    return out


def probe(payload, say):
    root = payload["root"]
    for path in reversed(_search_paths(root, payload.get("source_roots") or [])):
        sys.path.insert(0, path)
    say(kind="start", runner_loaded=("pytest" in sys.modules))
    for site in payload.get("sites") or []:
        sid = site.get("id")
        try:
            module = __import__(site["module"], fromlist=["_"])
        except BaseException as exc:
            say(kind="site", site=sid, status="skip", why=type(exc).__name__)
            continue
        loaded = getattr(module, "__file__", None)
        wanted = os.path.realpath(os.path.join(root, site["file"]))
        if not loaded or os.path.realpath(loaded) != wanted:
            say(kind="site", site=sid, status="skip", why="another copy was imported")
            continue
        obj = module
        parts = site["qualname"].split(".")
        for part in (parts[:-1] if site.get("kind") == "construct" else parts):
            obj = getattr(obj, part, None)
            if obj is None:
                break
        if obj is None or not callable(obj):
            say(kind="site", site=sid, status="skip", why="the function is not there")
            continue
        for index, call in enumerate(site.get("calls") or []):
            try:
                observation = _one(obj, call)
            except BaseException as exc:
                observation = {"outcome": {"kind": "worker_error", "types": _types(exc)},
                               "after_args": {}, "after_kwargs": {}}
            say(kind="call", site=sid, call=index, **observation)
    say(kind="done")


def main():
    probe(_payload(), _stdout_say)


if __name__ == "__main__":
    main()