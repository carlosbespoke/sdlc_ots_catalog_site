#!/usr/bin/env python3
"""Pin a repository's pytest setup at image build, so grading cannot pick up a submission's.

    cd <repo> && <repo's python> extract_base_pytest.py <repo dir> <out dir> [base pytest args...]

Run once at image build (test.sh pin-base), as root, on the BASE tree, with the repository's own
interpreter and the same args the repo suite runs with. It asks the installed pytest itself which
config file, rootdir and confcutdir it picks for those args, and which entry-point plugins it
autoloads, and stops before any conftest or test module is imported. It writes, root-owned:

  <out dir>/base-pytest.ini   that config file's pytest settings, as one standalone [pytest] section
  <out dir>/base-pytest.args  one argument per line: --rootdir, --confcutdir and a `-p <name>` for
                              every autoloaded entry-point plugin whose code is outside the repository
  <out dir>/base-pytest.shadow  repository paths where a new module would be imported in place of one
                              of those plugins or of a `-p` plugin the pinned addopts keep (grader.py
                              removes such files before the suite runs)
  <out dir>/base-pytest.importdirs  the repository folders on the suite's import path
  <out dir>/base-pytest.metadata/   a copy of the package metadata folders (*.dist-info, *.egg-info) in
                              them; grader.py removes any other, since `-p NAME` loads an entry point
                              named NAME from any of them

A plugin whose code is in the repository (an entry point, or a `-p` module in the base addopts) is
not loaded during grading, since the submission could change it.

Grading runs the repo suite with `pytest -c base-pytest.ini <base-pytest.args>` and plugin autoload
off, so a submission cannot inject pytest settings (for example `addopts = -p <its plugin>`, which
loads a hook-wrapper that flips failing tests to passed) through pytest.ini, pyproject.toml, tox.ini
or setup.cfg, and cannot load a plugin from a file it can change. Anything it cannot render exits
non-zero, which fails the image build: a wrong pin would silently change the suite.
"""
import configparser
import os
import shlex
import shutil
import sys
import types
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python < 3.11: pytest itself depends on tomli there.
    try:
        import tomli as tomllib
    except ModuleNotFoundError:
        tomllib = None

# pytest's own "args" and "paths" ini options: the value is shlex-split, so list items are quoted.
# Every other option (linelist such as markers or filterwarnings, plugin options) is one item a line.
SHLEX_KEYS = {"addopts", "testpaths", "python_files", "python_classes", "python_functions",
              "norecursedirs", "usefixtures", "doctest_optionflags", "required_plugins", "pythonpath"}


class PinError(Exception):
    pass


class _Stop(Exception):
    pass


def _plugin_module(plugin):
    """(module name, file) of a plugin, which is a module or an object (`pkg.mod:obj`) defined in one."""
    if isinstance(plugin, types.ModuleType):
        module = plugin.__name__
    else:
        module = getattr(plugin, "__module__", None) or type(plugin).__module__
    path = getattr(sys.modules.get(module), "__file__", None)
    if not path:
        raise PinError(f"cannot locate the code of plugin {plugin!r} (module {module})")
    return module, path


def probe(args):
    """What the installed pytest picks for `pytest <args>` run from the current directory: config
    file, rootdir, confcutdir, autoloaded entry-point plugins and the (module, file) of every `-p`
    plugin in the args and addopts. It stops pytest right after it decides these, before any conftest
    is imported."""
    import pytest

    found = {}

    class Probe:
        @pytest.hookimpl(tryfirst=True)
        def pytest_load_initial_conftests(self, early_config):
            pm = early_config.pluginmanager
            named = {}
            for name in early_config.known_args_namespace.plugins or []:
                name = name.strip()                    # as pytest itself reads a -p value
                if name.startswith("no:"):
                    continue
                plugin = pm.get_plugin(name)
                if plugin is None:
                    raise PinError(f"cannot locate the code of plugin {name!r}: -p {name} did not load it "
                                   f"(blocked by a -p no:, skipped at import, or a deprecated name)")
                named[name] = _plugin_module(plugin)
            found.update(
                rootdir=str(early_config.rootpath),
                inifile=str(early_config.inipath) if early_config.inipath else None,
                confcutdir=early_config.known_args_namespace.confcutdir,
                plugins=[(pm.get_name(plugin), *_plugin_module(plugin))
                         for plugin, _dist in pm.list_plugin_distinfo()],
                named=named,
                sys_path=list(sys.path))
            raise _Stop

    try:
        code = pytest.main(["-p", "no:cacheprovider", "-s", *args], plugins=[Probe()])
    except _Stop:
        return found
    raise PinError(f"pytest exited ({code}) before reading its config; run it on the base tree")


def _ini_value(key, value):
    """One config value as pytest's ini parser reads it back."""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        if key in SHLEX_KEYS:
            return "\n".join(shlex.quote(str(v)) for v in value)
        return "\n".join(str(v) for v in value)
    return str(value)


def _read_ini(path, section):
    parser = configparser.ConfigParser(interpolation=None)
    parser.optionxform = str  # keep key case (e.g. DJANGO_SETTINGS_MODULE)
    try:
        with open(path, encoding="utf-8") as fh:
            parser.read_file(fh)
    except (OSError, UnicodeDecodeError, configparser.Error) as exc:
        raise PinError(f"cannot read {path}: {exc}") from exc
    if not parser.has_section(section):
        return {}
    return {key: parser.get(section, key) for key in parser.options(section)}


def _read_toml(path, *tables):
    if tomllib is None:
        raise PinError(f"cannot read {path}: no TOML parser on this interpreter")
    try:
        with open(path, "rb") as fh:
            data = tomllib.load(fh)
    except (OSError, ValueError) as exc:
        raise PinError(f"cannot read {path}: {exc}") from exc
    for table in tables:
        node = data
        for part in table:
            node = node.get(part) if isinstance(node, dict) else None
        if isinstance(node, dict):
            return {k: v for k, v in node.items() if not isinstance(v, dict)}
    return {}


def read_config(inifile):
    """The pytest settings in the config file pytest picked, as {key: value}."""
    if inifile is None:
        return {}
    path = Path(inifile)
    name = path.name
    if name in ("pytest.ini", ".pytest.ini", "tox.ini"):
        return _read_ini(path, "pytest")
    if name == "setup.cfg":
        return _read_ini(path, "tool:pytest")
    if name == "pyproject.toml":
        return _read_toml(path, ("tool", "pytest", "ini_options"), ("tool", "pytest"))
    if name in ("pytest.toml", ".pytest.toml"):
        return _read_toml(path, ("pytest",))
    raise PinError(f"unknown pytest config file {path}")


def render_ini(config, inifile):
    # pytest resolves `pythonpath` against the config file's directory, and grading reads the config
    # from elsewhere, so make those entries absolute.
    config = dict(config)
    if "pythonpath" in config and inifile is not None:
        value = config["pythonpath"]
        items = value if isinstance(value, (list, tuple)) else shlex.split(str(value))
        config["pythonpath"] = [str((Path(inifile).parent / p).resolve()) for p in items]
    lines = ["[pytest]"]
    for key, value in config.items():
        rendered = _ini_value(key, value)
        if "\n" in rendered:
            lines.append(f"{key} =")
            lines.extend(f"    {line}" for line in rendered.splitlines() if line.strip())
        else:
            lines.append(f"{key} = {rendered}")
    return "\n".join(lines) + "\n"


def _in_repo(path, repo):
    resolved = Path(path).resolve()
    return resolved == repo or repo in resolved.parents


def _outside_plugins(found, repo):
    # A plugin whose code is in the repository is left out: the submission could change it. Tests
    # that need it fail in every run, so they drop out of P2P (pin-base prints what it left out).
    return [(name, module) for name, module, path in found["plugins"] if not _in_repo(path, repo)]


def _outside_named(found, repo):
    """(name, module) of each `-p` plugin from outside the repository (it stays in the pinned addopts)."""
    return [(name, module) for name, (module, path) in found.get("named", {}).items()
            if not _in_repo(path, repo)]


def pinned_args(found, repo):
    """--rootdir, --confcutdir and the entry-point plugins from outside the repository."""
    repo = Path(repo).resolve()
    args = ["--rootdir", found["rootdir"]]
    if found["confcutdir"]:
        args += ["--confcutdir", str(found["confcutdir"])]
    for name, _module in _outside_plugins(found, repo):
        args += ["-p", name]
    return args


def _pythonpath_dirs(found, config):
    value = config.get("pythonpath")
    if not value or found["inifile"] is None:
        return []
    items = value if isinstance(value, (list, tuple)) else shlex.split(str(value))
    return [(Path(found["inifile"]).parent / p).resolve() for p in items]


def import_dirs(found, config, repo):
    """The repository folders on the suite's import path when pytest loads its plugins (relative, "."
    for the root): the repository root, `pythonpath` folders and the ones an editable install or
    PYTHONPATH adds. Python searches each sys.path entry as written, so an entry counts by its
    literal path (it may not exist yet, or be a link) as well as by where it resolves."""
    repo = Path(repo).resolve()
    rels = {"."}
    for d in [*_pythonpath_dirs(found, config), *(p or os.getcwd() for p in found.get("sys_path", []))]:
        for path in (Path(os.path.normpath(os.path.abspath(d))), Path(d).resolve()):
            if path == repo or repo in path.parents:
                rels.add(path.relative_to(repo).as_posix())
    return sorted(rels)


def is_package_metadata(name):
    return name.lower().endswith((".dist-info", ".egg-info"))


def snapshot_metadata(dirs, repo, dest):
    """Copies every package metadata folder (name.dist-info, name.egg-info) in the import folders to
    dest/<folder>/. importlib.metadata finds one in any import folder, and `-p NAME` loads a pytest11
    entry point named NAME from it, before any module and even with autoload off, so grader.py puts
    back exactly these and removes any other before the suite runs."""
    repo = Path(repo).resolve()
    for rel in dirs:
        try:
            entries = sorted(os.listdir(repo / rel))
        except OSError:
            continue
        for entry in entries:
            if is_package_metadata(entry):
                src, dst = repo / rel / entry, dest / rel / entry
                dst.parent.mkdir(parents=True, exist_ok=True)
                if src.is_dir() and not src.is_symlink():
                    shutil.copytree(src, dst, symlinks=True)
                else:
                    shutil.copy2(src, dst, follow_symlinks=False)


def shadow_stems(found, config, repo):
    """Repository paths (no suffix) where a new module would be imported instead of a pinned plugin:
    in each repository folder on the import path (import_dirs: the root, where the suite runs, and
    `pythonpath`, PYTHONPATH and editable-install folders), the plugin's top-level module, and every
    level of it below a namespace package (foo/bar for a plugin foo.bar when foo has no __init__). That covers the
    autoloaded entry-point plugins and the `-p` plugins the pin keeps. grader.py removes any such
    module a submission adds before the suite runs."""
    repo = Path(repo).resolve()
    names = set()
    for _name, module in _outside_plugins(found, repo) + _outside_named(found, repo):
        parts = module.split(".")
        names.add(parts[0])
        for i in range(1, len(parts)):
            package = sys.modules.get(".".join(parts[:i]))
            if package is None or getattr(package, "__file__", None) is not None:
                break                          # a regular package: nothing below it can be shadowed
            names.add("/".join(parts[:i + 1]))
    stems = []
    for rel in import_dirs(found, config, repo):
        stems += [n if rel == "." else f"{rel}/{n}" for n in sorted(names)]
    return sorted(set(stems))


def _repo_module(name, found, repo):
    """True when the plugin `-p <name>` loaded is from inside the repository. Fails closed: a `-p` the
    probe did not see load cannot be placed, so it is an error rather than kept."""
    if name not in found.get("named", {}):
        raise PinError(f"cannot locate the code of plugin {name!r}")
    return _in_repo(found["named"][name][1], repo)


def _without_repo_plugins(tokens, found, repo):
    """The tokens with every `-p <module>` that resolves inside the repository removed, and those names."""
    kept, dropped, i = [], [], 0
    while i < len(tokens):
        tok = tokens[i]
        name, width = (tokens[i + 1].strip(), 2) if tok == "-p" and i + 1 < len(tokens) else \
            (tok[2:].strip(), 1) if tok.startswith("-p") and len(tok) > 2 else (None, 1)
        if name and not name.startswith("no:") and _repo_module(name, found, repo):
            dropped.append(name)
        else:
            kept += tokens[i:i + width]
        i += width
    return kept, dropped


def drop_repo_plugins(config, args, found, repo):
    """The config without `-p` plugins from the repository in its addopts (the submission could change
    them), and their names. Such a plugin in the base pytest args is an error."""
    repo = Path(repo).resolve()
    _kept, in_args = _without_repo_plugins(list(args), found, repo)
    if in_args:
        raise PinError(f"BASE_PYTEST_ARGS loads plugins from the repository ({in_args}); leave them out")
    value = config.get("addopts")
    if not value:
        return config, []
    tokens = list(value) if isinstance(value, (list, tuple)) else shlex.split(str(value))
    kept, dropped = _without_repo_plugins(tokens, found, repo)
    if not dropped:
        return config, []
    return dict(config, addopts=shlex.join(kept)), dropped


def main(argv):
    if len(argv) < 2:
        print("usage: extract_base_pytest.py <repo dir> <out dir> [base pytest args...]", file=sys.stderr)
        return 2
    repo, out, args = argv[0], Path(argv[1]), argv[2:]
    # Same import path as `python -m pytest` from the repository.
    sys.path.insert(0, os.getcwd())
    try:
        found = probe(args)
        config, dropped = drop_repo_plugins(read_config(found["inifile"]), args, found, repo)
        ini = render_ini(config, found["inifile"])
    except PinError as exc:
        print(f"[pin-base] {exc}", file=sys.stderr)
        return 1
    (out / "base-pytest.ini").write_text(ini)
    (out / "base-pytest.args").write_text("".join(f"{a}\n" for a in pinned_args(found, repo)))
    (out / "base-pytest.shadow").write_text("".join(f"{s}\n" for s in shadow_stems(found, config, repo)))
    dirs = import_dirs(found, config, repo)
    (out / "base-pytest.importdirs").write_text("".join(f"{d}\n" for d in dirs))
    shutil.rmtree(out / "base-pytest.metadata", ignore_errors=True)
    (out / "base-pytest.metadata").mkdir()
    snapshot_metadata(dirs, repo, out / "base-pytest.metadata")
    left_out = sorted(set(dropped) | {p[0] for p in found["plugins"] if _in_repo(p[2], Path(repo).resolve())})
    print(f"[pin-base] config {found['inifile'] or '(none)'}, rootdir {found['rootdir']}, "
          f"plugins {[p[0] for p in found['plugins']]}")
    if left_out:
        print(f"[pin-base] NOTE: plugins from the repository are not loaded during grading (the "
              f"submission could change them): {left_out}; tests that need them drop out of P2P")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
