"""Published source-scope rules plus conservative process-forgery checks."""
from pathlib import Path

EDITABLE = {"zstd.go"}
GENERATED_CACHE_SUFFIXES = (
    ".fasthttp.gz",
    ".fasthttp.br",
    ".fasthttp.zst",
)
GO_TEST_BINARY_SUFFIX = ".test"
ELF_MAGIC = b"\x7fELF"
PURE_IMPORTS = {
    "bytes", "errors", "fmt", "strconv", "strings", "sync", "time",
    "unicode", "unicode/utf8", "math", "math/bits", "encoding/binary",
    "sort", "slices",
}


def is_generated_go_test_binary(directory: str, name: str) -> bool:
    """Recognize Linux test binaries retained by Go profiling commands."""
    if not name.endswith(GO_TEST_BINARY_SUFFIX):
        return False
    path = Path(directory) / name
    try:
        with path.open("rb") as stream:
            return stream.read(len(ELF_MAGIC)) == ELF_MAGIC
    except OSError:
        return False


def candidate_copy_ignore(directory: str, names: list[str]) -> set[str]:
    """Discard VCS metadata and known generated test/runtime artifacts."""
    return {
        name
        for name in names
        if name == ".git"
        or name.endswith(GENERATED_CACHE_SUFFIXES)
        or is_generated_go_test_binary(directory, name)
    }


def changed_sources(baseline: Path, candidate: Path) -> tuple[set[str], str | None]:
    def files(root):
        return {
            p.relative_to(root).as_posix(): p
            for p in root.rglob("*")
            if ".git" not in p.relative_to(root).parts and p.is_file()
            and not p.name.endswith("_test.go")
        }
    base, cand = files(baseline), files(candidate)
    deleted = sorted(base.keys() - cand.keys())
    if deleted:
        return set(), f"baseline files were removed: {deleted[:8]}"
    changed = set()
    for name, path in cand.items():
        if name in base and path.read_bytes() == base[name].read_bytes():
            continue
        if name.endswith(".md"):
            continue
        is_new_helper = name not in base and "/" not in name and name.endswith(".go")
        if name not in EDITABLE and not is_new_helper:
            return set(), f"{name}: outside the published zstd decompression source scope"
        changed.add(name)
    return changed, None


FROZEN_FUNCTION = "I/O-bearing function: "
PACKAGE_CAPABILITY = "package I/O capability reference: "
PROCESS_REFERENCE = "process/output reference: "
# Exported type, interface, sentinel-error and constant names from process
# packages. Naming one (a variable or parameter type, an error comparison)
# performs no I/O, so mentioning it more often than the baseline is not a new
# capability. Calls such as io.Copy and values such as os.File stay counted.
TYPE_ONLY_SELECTORS = {
    "io.Reader", "io.Writer", "io.ReaderAt", "io.WriterAt", "io.ReaderFrom", "io.WriterTo",
    "io.Closer", "io.ReadCloser", "io.WriteCloser", "io.ReadWriter", "io.ReadSeeker",
    "io.ReadSeekCloser", "io.Seeker", "io.ByteReader", "io.ByteWriter", "io.StringWriter",
    "io.EOF", "io.ErrUnexpectedEOF", "io.ErrShortWrite", "io.ErrShortBuffer",
    "io.SeekStart", "io.SeekCurrent", "io.SeekEnd", "io.LimitedReader", "io.SectionReader",
    "os.FileInfo", "os.FileMode", "os.ErrNotExist", "os.ErrExist", "os.ErrPermission",
}


def _counted(reason: str) -> tuple[str, int] | None:
    stem, separator, count = reason.rpartition(" count=")
    if separator and count.isdigit():
        return stem, int(count)
    return None


def scan_violation(baseline: list[dict], candidate: list[dict], changed: set[str]) -> str | None:
    """Reject new capabilities in changed files.

    The editable file is request, file or stream handling code, so whole
    function bodies cannot be frozen and references to its own declarations
    shift with any edit. Process, output, goroutine, directive, init and import
    capabilities stay limited to what the baseline file already had, and a
    counted capability may only be used as often as before or less.
    """
    known = {(item["file"], item["kind"], item["reason"]) for item in baseline}
    # The instruction allows new imports of packages the editable file already
    # imports, including from new helper files; capability uses stay counted per file.
    editable_modules = {item["reason"].split(" ", 1)[0] for item in baseline
                        if item["file"] in EDITABLE and item["kind"] == "import"}
    known_counts = {}
    for item in baseline:
        counted = _counted(item["reason"])
        if item["kind"] == "risk" and counted:
            known_counts[(item["file"], counted[0])] = counted[1]
    for item in candidate:
        name, kind, reason = item["file"], item["kind"], item["reason"]
        if name not in changed or (name, kind, reason) in known:
            continue
        if kind == "package" and reason == "fasthttp":
            continue
        if kind == "import":
            module, alias = reason.split(" ", 1)
            if module in PURE_IMPORTS and alias not in {".", "_"}:
                continue
            if module in editable_modules and alias not in {".", "_"}:
                continue
        if kind == "risk" and reason.startswith((FROZEN_FUNCTION, PACKAGE_CAPABILITY)):
            continue
        counted = _counted(reason)
        if kind == "risk" and counted and counted[1] <= known_counts.get((name, counted[0]), -1):
            continue
        if kind == "risk" and counted and counted[0].removeprefix(PROCESS_REFERENCE) in TYPE_ONLY_SELECTORS:
            continue
        return f"{name}: {kind}: {reason}"
    return None
