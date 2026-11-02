"""Per-language config for TEST-ONLY translation mode.

Test-only mode ports ONLY the crate's tests (+ a compile-only skeleton) to a
target language, skips the oracle/impl entirely, and therefore skips validation
(no-op). This table is what makes the port-agent, grader, and harbor packager
language-agnostic. Add a language = add an entry here.

Each entry:
  ext           source file extension (the impl/skeleton file)
  test_suffix   how a test file is named
  test_re       regex capturing test-function ids inside a test file
  base_image    harbor docker base
  apt / setup   image build lines to make `run_one`/`compile` work
  module_files  {relpath: content} written into the work dir so it compiles
  compile       shell (in workdir) that must exit 0 iff tests+skeleton COMPILE
  run_one_tmpl  shell template (fields: {tid}) run in workdir; exit 0 == pass
  test_kill_sec seconds after which the grader kills (fails) one test
  framework     human note used in the agent prompt
"""

GO = dict(
    name="go", ext=".go", test_suffix="_test.go",
    test_re=r'func\s+(Test[A-Za-z0-9_]+)\s*\(',
    base_image="golang:1.21-bookworm",
    apt="RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates tmux asciinema && rm -rf /var/lib/apt/lists/*\n"
        # put `go` on the default PATH so the solver never hunts for it (see
        # to_harbor_projmig GO_APT; measured in eval transcripts).
        "RUN ln -sf /usr/local/go/bin/go /usr/local/bin/go && ln -sf /usr/local/go/bin/gofmt /usr/local/bin/gofmt\n",
    module_files={"go.mod": "module migtests\n\ngo 1.21\n"},
    # COMPILE ONCE (pristine tests), then run EACH test from the built binary —
    # never re-run `go test` (which recompiles from the on-disk tree an init()
    # could have overwritten). Mirrors the full-port grader_go. Exit code of
    # `./mig_tb -test.run ^Id$` == that test's real result (impl can't exit: see
    # the import-path bans).
    compile='GOFLAGS=-mod=mod GOCACHE=/tmp/gc go test -c -o ./mig_tb -vet=off . 2>&1',
    run_one_tmpl='./mig_tb -test.run "^{tid}$" -test.count=1 -test.timeout=60s',
    test_kill_sec=60,        # -test.timeout above (the grader's 75 s cap is the backstop)
    # enumerate the tests actually in the compiled binary -> phantom-test guard.
    list_tmpl='./mig_tb -test.list ".*"',
    framework="Go's testing package (`func TestXxx(t *testing.T)`), one flat package `migtests`",
    # DISCLOSED grading constraints (argus dusk-plonk v9). Kept in sync with
    # grader_tests.GO_BANNED_PATHS + BANS["raw"]. A ban that isn't disclosed is a
    # false-reject bug; every ban here is load-bearing for exit-code grading.
    constraints=(
        "Your implementation is compiled into the test package `migtests` and is "
        "graded solely by whether each test passes. To keep grading sound, your "
        "implementation files must NOT import any of `os`, `os/exec`, `syscall`, "
        "`runtime`, `plugin`, `net`, `net/http`, `net/rpc`, `io/ioutil`, `embed`, "
        "`unsafe`, `flag`, `testing` (or any `testing/...` package), or use cgo "
        "(`import \"C\"`), and must NOT use `//go:linkname` or `//go:embed` "
        "directives or redefine the test functions. Every non-test `.go` file "
        "anywhere under the port directory is checked, so keep scratch programs "
        "outside it. A from-scratch algorithm port needs none of these. You MAY "
        "use any other standard-library package (including `math/bits`, "
        "`encoding/binary`, `reflect`) and pure-Go code (use `math.Float64bits` "
        "and friends instead of `unsafe` casts). Limits: each "
        "test runs on its own, is killed after 60 seconds and runs under a 2 GB "
        "virtual-memory (address-space) limit, of which the Go runtime reserves "
        "about 0.7 GB, so a test has about 1.3 GB of heap; the grading machine "
        "has 2 vCPUs."),
)

PYTHON = dict(
    name="python", ext=".py", test_suffix="_test.py",
    test_re=r'def\s+(test_[A-Za-z0-9_]+)\s*\(',
    # pytest node ids are `file::name`, not a bare name -> qualify at extraction.
    qualify_file=True,
    base_image="python:3.12-slim",
    apt="RUN pip install --no-cache-dir pytest && apt-get update && apt-get install -y --no-install-recommends git tmux asciinema && rm -rf /var/lib/apt/lists/*\n",
    module_files={"conftest.py": "import sys, os\nsys.path.insert(0, os.path.dirname(__file__))\n"},
    compile='python3 -m pytest --collect-only -q 2>&1',
    # tid is "file::test_name"; grader wraps its own subprocess timeout.
    run_one_tmpl='python3 -m pytest "{tid}" -q -p no:cacheprovider',
    test_kill_sec=75,        # grader_tests.py run_id subprocess cap
    framework="pytest (`def test_xxx():` with `assert`), impl importable as a top-level module",
    constraints=(
        "Your implementation is graded solely by whether each test passes. To "
        "keep grading sound, your implementation must NOT import `os`, `sys`, "
        "`subprocess`, `socket`, or `ctypes`, must NOT call `__import__`, and must "
        "NOT define `test_*` functions itself. A from-scratch algorithm port needs "
        "none of these; any other pure-Python standard-library module is fine."),
)

# PRELOAD-FREEZE (argus CRITICAL — TS exit-code grading bypass): TS tasks are
# graded by the EXIT CODE of `tsx --test --test-name-pattern=^Id$` (exit 0 ==
# pass). The `process` GLOBAL is always available (never imported), so a crate.ts
# that calls a process-termination primitive AT IMPORT TIME forces exit 0 on
# every per-test run — a full false pass (skeleton 0/83 -> 83/83). A regex ban on
# `process.exit` alone is evadable: `process['exit'](0)`, `const {exit}=process`,
# and especially `process.reallyExit(0)` / `process._exit(0)` / `process.abort()`
# all bypass it. The UN-EVADABLE fix is to PRELOAD this module (via node's
# `--import`) BEFORE the solver's crate.ts is dynamically imported, and neutralize
# every process-termination primitive so the call is a no-op and node:test can
# finish and report the REAL per-test result. Frozen with configurable:false so a
# malicious crate.ts cannot redefine them back. A genuinely passing test still
# exits 0 and a genuinely failing test still exits non-zero (we only neutralize
# forced-exit, not node:test's own faithful exit-code reporting).
_TS_PRELOAD = (
    "'use strict';\n"
    "// Imported for the assertion freeze below. Static imports are hoisted and\n"
    "// evaluated before the rest of this preload (and before the solver's\n"
    "// crate.ts), and resolve to the SAME cached module objects the hidden tests\n"
    "// import, so freezing them here makes the test's assert unforgeable.\n"
    "import __assert from 'node:assert';\n"
    "import __assertStrict from 'node:assert/strict';\n"
    "import * as __nodeTest from 'node:test';\n"
    "// Neutralize process-termination primitives so a solver's crate.ts cannot\n"
    "// force exit 0 (or any exit) at import time and thereby fake a passing test.\n"
    "// Frozen (writable+configurable:false) so it cannot be redefined back.\n"
    "const __noop = function () { return undefined; };\n"
    "for (const __n of ['exit', 'reallyExit', '_exit', 'abort']) {\n"
    "  try {\n"
    "    Object.defineProperty(process, __n, {\n"
    "      value: __noop, writable: false, configurable: false, enumerable: false,\n"
    "    });\n"
    "  } catch (__e) { /* already frozen — fine */ }\n"
    "}\n"
    "// process.kill(pid, sig) can terminate the current process (or its group).\n"
    "// Make it a no-op for our own pid / pgid; delegate for any other pid.\n"
    "const __realKill = typeof process.kill === 'function' ? process.kill.bind(process) : null;\n"
    "try {\n"
    "  Object.defineProperty(process, 'kill', {\n"
    "    value: function (pid, signal) {\n"
    "      if (pid === process.pid || pid === 0 || pid === -process.pid) return true;\n"
    "      return __realKill ? __realKill(pid, signal) : true;\n"
    "    },\n"
    "    writable: false, configurable: false, enumerable: false,\n"
    "  });\n"
    "} catch (__e) { /* already frozen — fine */ }\n"
    "// ASSERTION FREEZE (argus CRITICAL — the second exit-code bypass): TS is\n"
    "// graded by the exit code of `tsx --test`, which is 0 iff node:test saw no\n"
    "// assertion throw. A solver's crate.ts, imported BEFORE the test body runs,\n"
    "// could monkeypatch the assert functions the hidden tests call to no-ops\n"
    "// (`assert.strictEqual = () => {}`), so every assertion silently passes ->\n"
    "// exit 0 AND a genuine TAP `ok` (defeating the TAP cross-check too). The test\n"
    "// runner imports the SAME cached node:assert object, so we deep-freeze it here\n"
    "// first: Object.freeze makes every method non-writable+non-configurable, so a\n"
    "// reassignment from the solver's ESM (always strict mode) THROWS and errors\n"
    "// the run, or — if wrapped in try/catch — is a silent no-op leaving the real\n"
    "// assert in place. Honest tests only CALL these functions, never reassign\n"
    "// them, so the freeze never affects an honest port. node:test is frozen for\n"
    "// the same reason (a solver cannot swap out the runner's `test`/`it`).\n"
    "for (const __m of [__assert, __assert && __assert.strict, __assertStrict,\n"
    "                   __nodeTest, __nodeTest && __nodeTest.default]) {\n"
    "  try { if (__m) Object.freeze(__m); } catch (__e) { /* fine */ }\n"
    "}\n"
    "// RESULT-CHANNEL INTEGRITY: node:test runs IN-PROCESS with the solver's\n"
    "// crate.ts, so the TAP stream is reachable from agent code. Make\n"
    "// process.stdout/stderr.write non-replaceable (still callable), so a crate.ts\n"
    "// cannot filter `not ok`/`# fail` out of the runner's TAP. (process.exitCode\n"
    "// is a non-configurable accessor in Node 20 and cannot be locked; resetting it\n"
    "// alone is caught by the grader's TAP cross-check.)\n"
    "for (const __s of [process.stdout, process.stderr]) {\n"
    "  try {\n"
    "    const __bw = __s.write.bind(__s);\n"
    "    Object.defineProperty(__s, 'write', { value: __bw, writable: false, configurable: false });\n"
    "  } catch (__e) { /* fine */ }\n"
    "}\n"

)

TYPESCRIPT = dict(
    name="typescript", ext=".ts", test_suffix=".test.ts",
    test_re=r'''(?:test|it)\s*\(\s*['"`]([^'"`]+)['"`]''',
    base_image="node:20-bookworm-slim",
    # python3 is REQUIRED: test.sh runs the grader with python3. node:20-slim
    # ships neither python3 nor it — without it every task errors with
    # RewardFileNotFoundError (measured in eval b689b165, all 27 TS tasks).
    apt="RUN apt-get update && apt-get install -y --no-install-recommends git ca-certificates python3 tmux asciinema && rm -rf /var/lib/apt/lists/* && npm i -g tsx@4 >/dev/null 2>&1\n",
    # `mig_preload.mjs` is written into the workdir (it's a module_file, so the
    # grader lays it down and impl_files() never treats it as a solver file, and a
    # solver-submitted file of the same name is ignored). Loaded via --import
    # BEFORE any *.test.ts (and thus before the dynamically-imported crate.ts) so
    # process-termination is already neutralized when the impl runs.
    module_files={
        "package.json": '{"name":"migtests","type":"module","private":true}\n',
        "mig_preload.mjs": _TS_PRELOAD,
    },
    compile='npx --yes tsx --import ./mig_preload.mjs --test *.test.ts >/dev/null 2>&1 || node --import ./mig_preload.mjs --experimental-strip-types --test *.test.ts >/dev/null 2>&1; echo done',
    # node:test name pattern; tid is the test title. --import preloads the freeze
    # before crate.ts, so exit-code grading is faithful (a forced exit() no longer
    # short-circuits the real assertions).
    run_one_tmpl='npx --yes tsx --import ./mig_preload.mjs --test --test-name-pattern="^{tid}$" *.test.ts',
    test_kill_sec=75,        # grader_tests.py run_id subprocess cap
    framework="node:test with tsx (`import {{ test }} from \\'node:test\\'; import assert from \\'node:assert\\'`)",
    constraints=(
        "Your implementation is graded solely by whether each test passes. To "
        "keep grading sound, your implementation must NOT import any Node built-in "
        "that provides process control, filesystem, or network I/O — specifically "
        "`child_process`, `fs` (incl. `fs/promises`), `process`, `net`, `http`, "
        "`https`, `os`, `dgram`, `dns`, `tls`, `cluster`, `worker_threads`, `vm`, "
        "`module`, or `v8` — in EITHER their bare form (e.g. `'fs'`) OR their "
        "`node:`-prefixed form (e.g. `'node:fs'`), whether via `import ... from`, "
        "`require(...)`, or dynamic `import(...)`. You also must NOT terminate the "
        "process in ANY form — including `process.exit`, `process['exit']`, "
        "`process.reallyExit`, `process._exit`, `process.abort`, `process.kill`, "
        "or a destructured `exit`/`reallyExit`/`_exit`/`abort` taken off "
        "`process` — nor call `eval`, nor define `test`/`it` cases itself, nor "
        "monkeypatch the assertion library or test runner (e.g. reassigning "
        "`assert.strictEqual` to a no-op), nor replace `process.stdout.write`/"
        "`process.stderr.write`. (The test runner neutralizes these terminators, "
        "deep-freezes `node:assert`/`node:test`, and locks the output streams' "
        "`write` at load time, so a "
        "forced exit cannot fake a pass and the assertion functions cannot be "
        "replaced; such attempts are rejected or are silent no-ops.) CALLING a "
        "method named `test`/`it` on your own value — e.g. `regex.test(s)` or "
        "`obj.it(x)` — is fine; only a bare, unqualified `test(...)`/`it(...)` "
        "definition is rejected. The framework's own `node:test` and `node:assert` "
        "imports are fine. A from-scratch algorithm port needs none of the banned "
        "modules."),
)

# C++: header-only impl (crate.hpp) + a tiny self-contained test harness so we
# need no gtest. Tests are `TEST(Name){ CHECK(cond); }`; `main.cpp` runs the one
# test named on argv. Hardest target (manual everything, exact numerics) ->
# lowest solver scores.
#
# OUT-OF-BAND GRADING (argus CRITICAL — C++ exit-code grading bypass): the old
# grader trusted the PROCESS EXIT CODE of `./mig_tb "<Name>"` (exit 0 == pass).
# An agent-owned crate.hpp can plant a STATIC INITIALIZER that issues a raw
# inline-asm `exit_group(0)` syscall (or `_exit`/`syscall(60)` variants) BEFORE
# `main` runs, forcing exit 0 with NO implementation -> reward 1.0. That path is
# below libc, so the `_Exit` override and every `<cstdlib>`/`<unistd.h>` token
# ban are bypassable, and a token/#include ban can never enumerate raw syscalls.
# The un-evadable fix: DO NOT trust the exit code. The grader passes a fresh
# random NONCE and a unique RESULT PATH per test invocation (argv[2]/argv[3]);
# `main` runs the test and, ONLY AFTER it actually finished, writes exactly
# "<nonce> PASS" or "<nonce> FAIL" to that path, then returns normally. The
# grader reads the file and scores PASS iff it exists AND holds "<nonce> PASS".
# A static-init raw-syscall exit happens before that write -> no file / no
# matching nonce -> FAIL. The nonce is random per run and unknown at build time,
# so a crate.hpp cannot forge a PASS by writing the file itself. The macro-neuter
# defenses (th::check_* inline funcs + raw bans) are KEPT as additional layers;
# the nonce'd result token is authoritative.
#
# The assertion LOGIC lives in inline functions in the harness namespaces (th::check_true;
# the templates check_eq / check_near / check_throws* in the reserved `__mig_th`, see
# RESERVED NAMESPACE below). The CHECK* macros are only thin wrappers that
# forward to those functions (passing the stringized expression for diagnostics).
# This is the load-bearing anti-neuter design: even if a malicious crate.hpp
# `#undef`s and `#define`s CHECK to a no-op, the assertion functions in `th::`
# CANNOT be redefined by the solver (crate.hpp referencing `th::` is statically
# rejected). The generated test file re-`#define`s the wrappers AFTER crate.hpp is
# included so every TEST body below expands to a real `th::check_*` call, and
# grader_tests.py additionally rejects any crate.hpp that `#undef`/`#define`s the
# CHECK* / TEST macros. Three independent layers -> a solver cannot silence checks.
# EXIT-CODE grading (argus CRITICAL, definitive fix). The nonce'd result PIPE was
# defeated repeatedly because agent crate.hpp code runs in the SAME process and kept
# finding new ways to recover the per-run nonce off argv (environ stack-walk,
# /proc/<pid>/cmdline via getpid+openat, atoi interposition on main's argv[3], …)
# and forge a "<nonce> PASS" line — argus: "token-blacklisting keeps regressing; the
# fix is architectural: do not execute agent code in the result-reporting process."
# So we REMOVE the nonce + the result write channel entirely: main just RETURNS
# th::run()'s code and the grader trusts ONLY the process exit code. There is now no
# secret to recover and no result line to forge. The only residual is "force exit 0
# for a failing test" — a FINITE, enumerable set of primitives (exit/_exit/_Exit/
# quick_exit/pthread_exit/thrd_exit/exec*/system/raw syscall/asm) all statically
# banned in BANS['cpp']; main returns 0 ONLY when th::run caught no exception, i.e.
# the test genuinely passed (agent code cannot make th::run return 0 for a throwing
# CHECK — th::run is harness code and CHECK/TEST/th:: are unforgeable).
# RESERVED NAMESPACE (anti-specialization backstop). Every harness TEMPLATE a test's
# verdict goes through -- check_eq / check_near / check_throws / check_throws_as and
# the strict comparison machinery (cmp) -- lives in `__mig_th`, a reserved
# identifier no solver code may name (BANS['cpp']). An explicit specialization
# (`template<> void X::check_eq<int,int>(...) {}`, `template<> struct X::cmp::i128<Box>
# : std::true_type {}`) replaces what a comparison does with no operator involved;
# with `namespace hh = th;` such a specialization forged every comparison. The
# CHECK_EQ / CHECK_NEAR / CHECK_THROWS* macros call `::__mig_th::...` directly, so even
# a path to `th` that the source rules missed reaches nothing they use. Namespace `th`
# keeps its public names for grader-owned spec headers (th::check_true, th::Reg,
# th::run, and th::check_eq / check_near / check_throws / check_throws_as as thin
# forwarders: distinct functions, so specializing one never changes a CHECK macro).
# CHECK expands to th::check_true and TEST to th::Reg, which are not templates.
# STRICT COMPARISON MODE (anti-forgery for comparisons; see __mig_th::cmp below). The
# legacy CHECK_EQ evaluates a bare `a==b`, so it trusts ANY operator== the solver
# writes: a crate.hpp that defines an always-true operator== on its types (or
# returns a decoy type with one, or an always-true operator bool for CHECK(obj))
# passes every test that compares crate objects with no implementation at all
# (measured: 847 of 17,707 C++ tests across 28 tasks are fully forgeable this way).
# With MIG_STRICT_COMPARE defined (the grader passes -DMIG_STRICT_COMPARE=1 when the
# task manifest says "cpp_compare": "strict"), CHECK_EQ / CHECK / CHECK_NEAR compare
# only GRADER-TRUSTED values with harness-owned code that never calls an operator
# the solver can define: numbers (incl. __int128), enums (by underlying value),
# std::string / string_view / C strings, pointers, and std containers / optional /
# pair / tuple / variant of those, recursively. A comparison of any other type is a
# compile error (static_assert), so tests must compare a trusted projection of crate
# objects. CHECK(cond) decomposes a top-level comparison (`CHECK(f(x) == 3)` compares
# through the trusted path too, so a decoy return type cannot answer it). Calls are
# fully qualified (no ADL), the decomposer's operators are rvalue-ref-qualified
# member templates (more specialized than any generic operator template a solver can
# write without naming the harness namespaces, which is banned), and no libc routine
# is called.
# Without the macro the legacy behaviour is unchanged byte for byte in effect, so
# existing tasks are unaffected until they are certified in strict mode.
_TH_STRICT = r"""
 namespace cmp{
  template<class...> struct dep_false:std::false_type{};
  template<class T> using bare=std::remove_cv_t<std::remove_reference_t<T>>;
  template<class T> struct i128:std::false_type{};
#ifdef __SIZEOF_INT128__
  template<> struct i128<__int128>:std::true_type{};
  template<> struct i128<unsigned __int128>:std::true_type{};
#endif
  template<class T> inline constexpr bool num_v=std::is_arithmetic_v<T>||i128<T>::value;
  template<class T> inline constexpr bool scalar_v=num_v<T>||std::is_enum_v<T>;
  template<class T> struct chr:std::false_type{};
  template<> struct chr<char>:std::true_type{};
  template<> struct chr<wchar_t>:std::true_type{};
  template<> struct chr<char16_t>:std::true_type{};
  template<> struct chr<char32_t>:std::true_type{};
  template<class T> struct text{static constexpr bool value=false;using ch=void;};
  template<class C,class R,class A> struct text<std::basic_string<C,R,A>>{static constexpr bool value=chr<C>::value;using ch=C;};
  template<class C,class R> struct text<std::basic_string_view<C,R>>{static constexpr bool value=chr<C>::value;using ch=C;};
  template<class C> struct text<C*>{static constexpr bool value=chr<std::remove_cv_t<C>>::value;using ch=std::remove_cv_t<C>;};
  template<class C,std::size_t N> struct text<C[N]>{static constexpr bool value=chr<std::remove_cv_t<C>>::value;using ch=std::remove_cv_t<C>;};
  template<class T> struct opt:std::false_type{};
  template<class T> struct opt<std::optional<T>>:std::true_type{};
  template<class T> struct pr:std::false_type{};
  template<class A,class B> struct pr<std::pair<A,B>>:std::true_type{};
  template<class T> struct tup:std::false_type{};
  template<class... T> struct tup<std::tuple<T...>>:std::true_type{};
  template<class T> struct var:std::false_type{};
  template<class... T> struct var<std::variant<T...>>:std::true_type{};
  template<class T> struct seq:std::false_type{};
  template<class T,class A> struct seq<std::vector<T,A>>:std::true_type{};
  template<class T,std::size_t N> struct seq<std::array<T,N>>:std::true_type{};
  template<class T,class A> struct seq<std::deque<T,A>>:std::true_type{};
  template<class T,class A> struct seq<std::list<T,A>>:std::true_type{};
  template<class K,class A> struct seq<std::set<K,std::less<K>,A>>:std::true_type{};
  template<class K,class A> struct seq<std::set<K,std::less<>,A>>:std::true_type{};
  template<class K,class A> struct seq<std::multiset<K,std::less<K>,A>>:std::true_type{};
  template<class K,class V,class A> struct seq<std::map<K,V,std::less<K>,A>>:std::true_type{};
  template<class K,class V,class A> struct seq<std::map<K,V,std::less<>,A>>:std::true_type{};
  template<class K,class V,class A> struct seq<std::multimap<K,V,std::less<K>,A>>:std::true_type{};
  template<class T,std::size_t N> struct seq<T[N]>:std::bool_constant<!chr<std::remove_cv_t<T>>::value>{};
  template<class T> struct uno:std::false_type{};
  template<class K,class H,class A> struct uno<std::unordered_set<K,H,std::equal_to<K>,A>>:std::true_type{};
  template<class K,class H,class A> struct uno<std::unordered_multiset<K,H,std::equal_to<K>,A>>:std::true_type{};
  template<class K,class V,class H,class A> struct uno<std::unordered_map<K,V,H,std::equal_to<K>,A>>:std::true_type{};
  template<class K,class V,class H,class A> struct uno<std::unordered_multimap<K,V,H,std::equal_to<K>,A>>:std::true_type{};
  template<class T> struct uinfo{static constexpr bool map=false,multi=false;};
  template<class K,class H,class A> struct uinfo<std::unordered_set<K,H,std::equal_to<K>,A>>{static constexpr bool map=false,multi=false;};
  template<class K,class H,class A> struct uinfo<std::unordered_multiset<K,H,std::equal_to<K>,A>>{static constexpr bool map=false,multi=true;};
  template<class K,class V,class H,class A> struct uinfo<std::unordered_map<K,V,H,std::equal_to<K>,A>>{static constexpr bool map=true,multi=false;};
  template<class K,class V,class H,class A> struct uinfo<std::unordered_multimap<K,V,H,std::equal_to<K>,A>>{static constexpr bool map=true,multi=true;};
  template<class T> struct ord:std::false_type{};
  template<class K,class C,class A> struct ord<std::set<K,C,A>>:std::true_type{};
  template<class K,class C,class A> struct ord<std::multiset<K,C,A>>:std::true_type{};
  template<class K,class V,class C,class A> struct ord<std::map<K,V,C,A>>:std::true_type{};
  template<class K,class V,class C,class A> struct ord<std::multimap<K,V,C,A>>:std::true_type{};
  // KEY SAFETY. A set/map orders (an unordered one matches) its keys with operator< /
  // operator== called inside std, where argument-dependent lookup finds operators the
  // solver declares for its own enums (or for std::pair<Enum, ...> in Enum's namespace):
  // an always-false operator< collapses the TEST's expected std::set<Color>{Red, Blue} to
  // one element, which a one-element answer then matches. Keys are trusted when every
  // comparison on them is built in or std's own: numbers, pointers, std strings, and
  // std optional/pair/tuple/variant/containers of those; an enum key only when no
  // operator< / operator== is declared for it (the function-call form below finds
  // declared operators only, never the built-in ones). The key's SHAPE is the test's
  // choice and checked at compile time (keyshape); whether an enum has such an operator
  // depends on the solver's crate.hpp, so that is checked when the comparison runs
  // (keys_trusted): it fails that one comparison, never the whole build, so the other
  // tests of an honest port that declared an operator< for its enum still count.
  // Probed via a wrapper that converts ONLY to E, so an operator reachable only through
  // a further conversion (enum -> int -> another type's converting ctor) never counts.
  template<class E> struct only_{operator const E&()const;};
  template<class E,class=void> struct user_lt:std::false_type{};
  template<class E> struct user_lt<E,std::void_t<decltype(operator<(std::declval<const only_<E>&>(),std::declval<const only_<E>&>()))>>:std::true_type{};
  template<class E,class=void> struct user_eq:std::false_type{};
  template<class E> struct user_eq<E,std::void_t<decltype(operator==(std::declval<const only_<E>&>(),std::declval<const only_<E>&>()))>>:std::true_type{};
  template<class T> struct stdtext:std::false_type{};
  template<class C,class A> struct stdtext<std::basic_string<C,std::char_traits<C>,A>>:chr<C>{};
  template<class C> struct stdtext<std::basic_string_view<C,std::char_traits<C>>>:chr<C>{};
  template<class T> constexpr bool plainkey();
  template<class... T> constexpr bool plainkeys(std::tuple<T...>*){return (true&&...&&::__mig_th::cmp::plainkey<T>());}
  template<class... T> constexpr bool plainkeys(std::variant<T...>*){return (true&&...&&::__mig_th::cmp::plainkey<T>());}
  template<class T> constexpr bool plainkey(){
   using U=bare<T>;
   if constexpr(num_v<U>||std::is_pointer_v<U>||std::is_null_pointer_v<U>||std::is_same_v<U,std::monostate>||stdtext<U>::value)return true;
   else if constexpr(opt<U>::value)return ::__mig_th::cmp::plainkey<typename U::value_type>();
   else if constexpr(pr<U>::value)return ::__mig_th::cmp::plainkey<typename U::first_type>()&&::__mig_th::cmp::plainkey<typename U::second_type>();
   else if constexpr(tup<U>::value||var<U>::value)return ::__mig_th::cmp::plainkeys(static_cast<U*>(nullptr));
   else if constexpr((seq<U>::value&&!std::is_array_v<U>)||uno<U>::value)return ::__mig_th::cmp::plainkey<typename U::value_type>();
   else return false;}
  template<class T> constexpr bool keyshape(){using U=bare<T>;return std::is_enum_v<U>||::__mig_th::cmp::plainkey<U>();}
  template<class T> constexpr bool keysafe(){
   using U=bare<T>;
   if constexpr(std::is_enum_v<U>)return !user_lt<U>::value&&!user_eq<U>::value;
   else return ::__mig_th::cmp::plainkey<U>();}
#define MIG_TH_KEYS_ "CHECK_EQ compares std::set / std::map / unordered containers only when their keys are numbers, strings, pointers, enums, or std pairs / tuples / optionals / containers of numbers, strings and pointers: other keys are ordered or matched by operators the solver can define. Compare a std::vector of the elements (or of a numeric projection of the keys) instead."
#define MIG_TH_ENUMKEY_ "comparison not trusted: a std::set / std::map / unordered container keyed by an enum is compared, and crate.hpp declares operator< or operator== for that enum; the container orders or matches its keys with that operator, so the comparison is not trusted. Do not declare comparison operators for enums: they compare by value."
  template<class C> void keys_trusted(){if constexpr(!::__mig_th::cmp::keysafe<typename C::key_type>())throw std::runtime_error(MIG_TH_ENUMKEY_);}
  // STD ITERATORS (libstdc++, the grading toolchain): two iterators are equal when they
  // point at the same position, read from the iterator's own position member and
  // compared as built-in pointers -- never through operator==, which a solver could
  // overload for a std iterator type in the global namespace.
  template<class T> struct itr{static constexpr int kind=0;};
#if defined(__GLIBCXX__)
  template<class P,class C> struct itr<__gnu_cxx::__normal_iterator<P,C>>{static constexpr int kind=std::is_pointer_v<P>?1:0;};
  template<class V> struct itr<std::_Rb_tree_iterator<V>>{static constexpr int kind=2;};
  template<class V> struct itr<std::_Rb_tree_const_iterator<V>>{static constexpr int kind=2;};
  template<class V> struct itr<std::_List_iterator<V>>{static constexpr int kind=2;};
  template<class V> struct itr<std::_List_const_iterator<V>>{static constexpr int kind=2;};
  template<class V,bool C,bool H> struct itr<std::__detail::_Node_iterator<V,C,H>>{static constexpr int kind=3;};
  template<class V,bool C,bool H> struct itr<std::__detail::_Node_const_iterator<V,C,H>>{static constexpr int kind=3;};
  template<class V,class R,class P> struct itr<std::_Deque_iterator<V,R,P>>{static constexpr int kind=std::is_pointer_v<P>?3:0;};
  template<> struct itr<std::_Bit_iterator>{static constexpr int kind=4;};
  template<> struct itr<std::_Bit_const_iterator>{static constexpr int kind=4;};
  template<class I> struct itr<std::reverse_iterator<I>>{static constexpr int kind=(std::is_pointer_v<I>||itr<I>::kind)?5:0;};
  template<class I> struct itr<std::move_iterator<I>>{static constexpr int kind=(std::is_pointer_v<I>||itr<I>::kind)?5:0;};
#endif
  template<class T> inline constexpr bool iter_v=itr<T>::kind!=0;
  template<class A,class B> bool same_pos(const A& a,const B& b){
   using X=bare<A>;using Y=bare<B>;
   if constexpr(std::is_pointer_v<X>&&std::is_pointer_v<Y>)return a==b;
   else if constexpr(itr<X>::kind==5&&itr<Y>::kind==5)return ::__mig_th::cmp::same_pos(a.base(),b.base());
   else if constexpr(itr<X>::kind==1&&itr<Y>::kind==1)return a.base()==b.base();
   else if constexpr(itr<X>::kind==2&&itr<Y>::kind==2)return a._M_node==b._M_node;
   else if constexpr(itr<X>::kind==3&&itr<Y>::kind==3)return a._M_cur==b._M_cur;
   else if constexpr(itr<X>::kind==4&&itr<Y>::kind==4)return a._M_p==b._M_p&&a._M_offset==b._M_offset;
   else{static_assert(dep_false<A,B>::value,"CHECK: these iterators belong to different kinds of container.");return false;}}
  // SMART POINTERS / std::function: their null state, read through std's own members
  // (get() is a raw pointer for the default deleter; a custom deleter's `pointer`
  // type could be a class with solver-defined operators, so it is not trusted).
  template<class T> struct sp:std::false_type{};
  template<class T> struct sp<std::unique_ptr<T,std::default_delete<T>>>:std::true_type{};
  template<class T> struct sp<std::shared_ptr<T>>:std::true_type{};
  template<class T> struct fn:std::false_type{};
  template<class R,class... P> struct fn<std::function<R(P...)>>:std::true_type{};
  template<class T> inline constexpr bool ptrish_v=sp<T>::value||std::is_pointer_v<T>||std::is_null_pointer_v<T>;
  template<class T> auto raw(const T& p){if constexpr(sp<bare<T>>::value)return p.get();else return p;}
  template<class T> constexpr auto val(const T& v){if constexpr(std::is_enum_v<T>)return static_cast<std::underlying_type_t<T>>(v);else return v;}
  template<class C> struct tv{const C* p;std::size_t n;bool null;};
  template<class T> tv<typename text<bare<T>>::ch> view(const T& t){
   using U=bare<T>;using C=typename text<U>::ch;
   if constexpr(std::is_pointer_v<U>){if(!t)return {nullptr,0,true};std::size_t n=0;while(t[n]!=C())++n;return {t,n,false};}
   else if constexpr(std::is_array_v<U>){std::size_t n=0;while(n<std::extent_v<U>&&t[n]!=C())++n;return {t,n,false};}
   else return {t.data(),t.size(),false};}
  template<class A,class B> bool text_eq(const A& a,const B& b){
   auto x=::__mig_th::cmp::view(a);auto y=::__mig_th::cmp::view(b);
   if(x.null||y.null)return x.null==y.null;
   if(x.n!=y.n)return false;
   for(std::size_t i=0;i<x.n;++i)if(x.p[i]!=y.p[i])return false;
   return true;}
  template<class A,class B> int text_cmp(const A& a,const B& b){
   auto x=::__mig_th::cmp::view(a);auto y=::__mig_th::cmp::view(b);
   std::size_t n=x.n<y.n?x.n:y.n;
   for(std::size_t i=0;i<n;++i){
    auto u=x.p[i];auto w=y.p[i];
    if constexpr(std::is_same_v<decltype(u),char>){if(static_cast<unsigned char>(u)!=static_cast<unsigned char>(w))return static_cast<unsigned char>(u)<static_cast<unsigned char>(w)?-1:1;}
    else{if(u!=w)return u<w?-1:1;}}
   return x.n<y.n?-1:(y.n<x.n?1:0);}
  template<class A,class B> bool eq(const A& a,const B& b);
  template<class T> std::size_t count(const T& t){if constexpr(std::is_array_v<T>)return std::extent_v<T>;else return t.size();}
  template<class T> auto first(const T& t){if constexpr(std::is_array_v<T>)return std::addressof(t[0]);else return t.begin();}
  template<class T> struct elem{using type=typename T::value_type;};
  template<class T,std::size_t N> struct elem<T[N]>{using type=T;};
  template<class T,class I> decltype(auto) at(const I& i){if constexpr(std::is_same_v<bare<typename elem<T>::type>,bool>)return static_cast<bool>(*i);else return *i;}
  template<class A,class B> bool seq_eq(const A& a,const B& b){
   std::size_t n=::__mig_th::cmp::count(a);if(n!=::__mig_th::cmp::count(b))return false;
   auto x=::__mig_th::cmp::first(a);auto y=::__mig_th::cmp::first(b);
   for(std::size_t i=0;i<n;++i,++x,++y)if(!::__mig_th::cmp::eq(::__mig_th::cmp::at<A>(x),::__mig_th::cmp::at<B>(y)))return false;
   return true;}
  template<class C,class E> const auto& key_of(const E& e){if constexpr(uinfo<C>::map)return e.first;else return e;}
  // Every element of `a` is in `b` with an equal mapped value, as often. Looks keys up
  // with b.count / b.at / b.equal_range (std's, matching with std::equal_to on a
  // trusted key type) and never compares two iterators, so it is O(n).
  template<class A,class B> bool uno_in(const A& a,const B& b){
   using X=bare<A>;using Y=bare<B>;
   std::size_t n=a.size();auto x=a.begin();
   for(std::size_t i=0;i<n;++i,++x){
    const auto& k=::__mig_th::cmp::key_of<X>(*x);
    const std::size_t cb=b.count(k);
    if constexpr(!uinfo<X>::multi&&!uinfo<Y>::multi){
     if(cb!=1)return false;
     if constexpr(uinfo<X>::map){if(!::__mig_th::cmp::eq(x->second,b.at(k)))return false;}}
    else{
     if(a.count(k)!=cb)return false;
     if constexpr(uinfo<X>::map){
      auto ra=a.equal_range(k);auto rb=b.equal_range(k);
      std::vector<char> used(cb,0);auto p=ra.first;
      for(std::size_t s=0;s<cb;++s,++p){bool hit=false;auto q=rb.first;
       for(std::size_t t=0;t<cb;++t,++q)if(!used[t]&&::__mig_th::cmp::eq(p->second,q->second)){used[t]=1;hit=true;break;}
       if(!hit)return false;}}}}
   return true;}
  template<class A,class B> bool uno_eq(const A& a,const B& b){
   using X=bare<A>;using Y=bare<B>;
   static_assert(uinfo<X>::map==uinfo<Y>::map,"CHECK_EQ: an unordered map compared with an unordered set");
   static_assert(::__mig_th::cmp::keyshape<typename X::key_type>()&&::__mig_th::cmp::keyshape<typename Y::key_type>(),MIG_TH_KEYS_);
   ::__mig_th::cmp::keys_trusted<X>();::__mig_th::cmp::keys_trusted<Y>();
   std::size_t n=a.size();if(n!=b.size())return false;
   if constexpr(std::is_same_v<typename X::key_type,typename Y::key_type>)
    return ::__mig_th::cmp::uno_in(a,b)&&::__mig_th::cmp::uno_in(b,a);   // both ways: a duplicate key cannot hide a missing one
   else{                                          // different key types: no lookup across them
    std::vector<char> used(n,0);auto x=a.begin();
    for(std::size_t i=0;i<n;++i,++x){bool hit=false;auto y=b.begin();
     for(std::size_t j=0;j<n;++j,++y)if(!used[j]&&::__mig_th::cmp::eq(*x,*y)){used[j]=1;hit=true;break;}
     if(!hit)return false;}
    return true;}}
  template<class A,class B,std::size_t... I> bool tup_eq(const A& a,const B& b,std::index_sequence<I...>){return (true&&...&&::__mig_th::cmp::eq(std::get<I>(a),std::get<I>(b)));}
  template<class A,class B,std::size_t... I> bool var_eq(const A& a,const B& b,std::index_sequence<I...>){
   if(a.valueless_by_exception()||b.valueless_by_exception())return a.valueless_by_exception()&&b.valueless_by_exception();
   if(a.index()!=b.index())return false;
   bool r=false;(void)(false||...||(a.index()==I&&(r=::__mig_th::cmp::eq(*std::get_if<I>(std::addressof(a)),*std::get_if<I>(std::addressof(b))),true)));
   return r;}
  template<class A,class B> bool eq(const A& a,const B& b){
   using X=bare<A>;using Y=bare<B>;
   if constexpr(scalar_v<X>&&scalar_v<Y>)return ::__mig_th::cmp::val(a)==::__mig_th::cmp::val(b);
   // Two raw pointers (char* included) are equal at the same address, as `p == q` is in
   // C++ (`CHECK_EQ(find(s, 'x'), s + 2)`); a C string compared with a string literal,
   // a char array or a std string compares its text.
   else if constexpr(std::is_pointer_v<X>&&std::is_pointer_v<Y>)return a==b;
   else if constexpr(text<X>::value&&text<Y>::value){
    static_assert(std::is_same_v<typename text<X>::ch,typename text<Y>::ch>,"CHECK_EQ: the two strings have different character types");
    return ::__mig_th::cmp::text_eq(a,b);}
   else if constexpr((std::is_pointer_v<X>||std::is_null_pointer_v<X>)&&(std::is_pointer_v<Y>||std::is_null_pointer_v<Y>))return a==b;
   else if constexpr(ptrish_v<X>&&ptrish_v<Y>)return ::__mig_th::cmp::raw(a)==::__mig_th::cmp::raw(b);
   else if constexpr(fn<X>::value&&std::is_null_pointer_v<Y>)return !static_cast<bool>(a);
   else if constexpr(std::is_null_pointer_v<X>&&fn<Y>::value)return !static_cast<bool>(b);
   else if constexpr(iter_v<X>&&iter_v<Y>)return ::__mig_th::cmp::same_pos(a,b);
   else if constexpr(opt<X>::value&&opt<Y>::value){if(a.has_value()!=b.has_value())return false;return !a.has_value()||::__mig_th::cmp::eq(*a,*b);}
   else if constexpr(opt<X>::value&&std::is_same_v<Y,std::nullopt_t>)return !a.has_value();
   else if constexpr(std::is_same_v<X,std::nullopt_t>&&opt<Y>::value)return !b.has_value();
   else if constexpr(std::is_same_v<X,std::nullopt_t>&&std::is_same_v<Y,std::nullopt_t>)return true;
   else if constexpr(opt<X>::value)return a.has_value()&&::__mig_th::cmp::eq(*a,b);
   else if constexpr(opt<Y>::value)return b.has_value()&&::__mig_th::cmp::eq(a,*b);
   else if constexpr(std::is_same_v<X,std::monostate>&&std::is_same_v<Y,std::monostate>)return true;
   else if constexpr(pr<X>::value&&pr<Y>::value)return ::__mig_th::cmp::eq(a.first,b.first)&&::__mig_th::cmp::eq(a.second,b.second);
   else if constexpr(tup<X>::value&&tup<Y>::value){
    static_assert(std::tuple_size_v<X> ==std::tuple_size_v<Y>,"CHECK_EQ: tuples of different sizes");
    return ::__mig_th::cmp::tup_eq(a,b,std::make_index_sequence<std::tuple_size_v<X>>{});}
   else if constexpr(var<X>::value&&var<Y>::value){
    static_assert(std::variant_size_v<X> ==std::variant_size_v<Y>,"CHECK_EQ: variants with different numbers of alternatives");
    return ::__mig_th::cmp::var_eq(a,b,std::make_index_sequence<std::variant_size_v<X>>{});}
   else if constexpr(seq<X>::value&&seq<Y>::value){
    if constexpr(ord<X>::value){static_assert(::__mig_th::cmp::keyshape<typename X::key_type>(),MIG_TH_KEYS_);::__mig_th::cmp::keys_trusted<X>();}
    if constexpr(ord<Y>::value){static_assert(::__mig_th::cmp::keyshape<typename Y::key_type>(),MIG_TH_KEYS_);::__mig_th::cmp::keys_trusted<Y>();}
    return ::__mig_th::cmp::seq_eq(a,b);}
   else if constexpr(uno<X>::value&&uno<Y>::value)return ::__mig_th::cmp::uno_eq(a,b);
   else{static_assert(dep_false<A,B>::value,"CHECK_EQ / CHECK compare only grader-trusted values: numbers, enums, std::string, std::string_view, C strings, pointers, std::unique_ptr / std::shared_ptr (by address), std container iterators (by position), and std containers / optional / pair / tuple / variant of those. Compare a projection of a crate type (an accessor returning such values), never the crate object itself.");return false;}}
  enum class Op{eq,ne,lt,le,gt,ge};
  template<Op O,class A,class B> bool rel(const A& a,const B& b){
   using X=bare<A>;using Y=bare<B>;
   if constexpr(O==Op::eq)return ::__mig_th::cmp::eq(a,b);
   else if constexpr(O==Op::ne){if constexpr(scalar_v<X>&&scalar_v<Y>)return ::__mig_th::cmp::val(a)!=::__mig_th::cmp::val(b);else return !::__mig_th::cmp::eq(a,b);}
   else if constexpr(scalar_v<X>&&scalar_v<Y>){auto x=::__mig_th::cmp::val(a);auto y=::__mig_th::cmp::val(b);
    if constexpr(O==Op::lt)return x<y;else if constexpr(O==Op::le)return x<=y;else if constexpr(O==Op::gt)return x>y;else return x>=y;}
   // Raw pointers and arrays (C strings included) order by address, as C++ orders them
   // (`CHECK(p < end)` over a buffer); text orders only with a std::string /
   // std::string_view on one side, as std's operators do.
   else if constexpr((std::is_pointer_v<X>||std::is_array_v<X>)&&(std::is_pointer_v<Y>||std::is_array_v<Y>)){
    const auto x=static_cast<std::decay_t<const A&>>(a);const auto y=static_cast<std::decay_t<const B&>>(b);
    if constexpr(O==Op::lt)return x<y;else if constexpr(O==Op::le)return x<=y;else if constexpr(O==Op::gt)return x>y;else return x>=y;}
   else if constexpr(text<X>::value&&text<Y>::value){
    static_assert(std::is_same_v<typename text<X>::ch,typename text<Y>::ch>,"CHECK: the two strings have different character types");
    int c=::__mig_th::cmp::text_cmp(a,b);
    if constexpr(O==Op::lt)return c<0;else if constexpr(O==Op::le)return c<=0;else if constexpr(O==Op::gt)return c>0;else return c>=0;}
   else{static_assert(dep_false<A,B>::value,"CHECK: an ordering comparison (<, <=, >, >=) needs numbers, enums or strings; compare a numeric or string projection of crate types.");return false;}}
  template<class T> bool truthy(const T& v){
   using U=bare<T>;
   if constexpr(std::is_same_v<U,bool>)return v;
   else if constexpr(num_v<U>)return v!=0;
   else if constexpr(std::is_enum_v<U>)return ::__mig_th::cmp::val(v)!=0;
   else if constexpr(std::is_pointer_v<U>||std::is_null_pointer_v<U>)return v!=nullptr;
   else if constexpr(opt<U>::value)return v.has_value();
   else if constexpr(sp<U>::value)return v.get()!=nullptr;
   else if constexpr(fn<U>::value)return static_cast<bool>(v);
   else{static_assert(dep_false<T>::value,"CHECK(x) needs a bool, number, enum, pointer, std::optional, std::unique_ptr / std::shared_ptr or std::function; never a crate object (its operator bool is not trusted). Assert on a trusted projection instead (e.g. CHECK_EQ(m.count(k), 1u), CHECK(p.get() != nullptr)).");return false;}}
#define MIG_TH_SPLIT_ "CHECK: write one condition per CHECK. Split a top-level &&, ||, &, |, ^ or comma into separate CHECKs, or parenthesize the whole condition: CHECK((a && b))."
  template<class L,class R,Op O> struct Bin{
   L l;R r;
   explicit operator bool() const{return ::__mig_th::cmp::rel<O>(l,r);}
   template<class T> bool operator&&(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator||(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator&(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator|(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator^(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator,(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator==(T&&)&&{static_assert(dep_false<T>::value,"CHECK: chained comparison; compare one pair of values per CHECK.");return false;}
   template<class T> bool operator!=(T&&)&&{static_assert(dep_false<T>::value,"CHECK: chained comparison; compare one pair of values per CHECK.");return false;}
   template<class T> bool operator<(T&&)&&{static_assert(dep_false<T>::value,"CHECK: chained comparison; compare one pair of values per CHECK.");return false;}
   template<class T> bool operator<=(T&&)&&{static_assert(dep_false<T>::value,"CHECK: chained comparison; compare one pair of values per CHECK.");return false;}
   template<class T> bool operator>(T&&)&&{static_assert(dep_false<T>::value,"CHECK: chained comparison; compare one pair of values per CHECK.");return false;}
   template<class T> bool operator>=(T&&)&&{static_assert(dep_false<T>::value,"CHECK: chained comparison; compare one pair of values per CHECK.");return false;}
  };
  template<class T> using hold=std::conditional_t<scalar_v<bare<T>>,bare<T>,const bare<T>&>;
#define MIG_TH_REL_(OP,TAG) \
   template<class R,std::enable_if_t<!scalar_v<bare<R>>,int> =0> Bin<L,const bare<R>&,Op::TAG> operator OP(R&& r)&&{return {v,r};} \
   template<class R,std::enable_if_t<scalar_v<R>,int> =0> Bin<L,R,Op::TAG> operator OP(R r)&&{return {v,r};}
  template<class L> struct Lhs{
   L v;
   explicit operator bool() const{return ::__mig_th::cmp::truthy(v);}
   MIG_TH_REL_(==,eq) MIG_TH_REL_(!=,ne) MIG_TH_REL_(<,lt) MIG_TH_REL_(<=,le) MIG_TH_REL_(>,gt) MIG_TH_REL_(>=,ge)
   template<class T> bool operator&&(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator||(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator&(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator|(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator^(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
   template<class T> bool operator,(T&&)&&{static_assert(dep_false<T>::value,MIG_TH_SPLIT_);return false;}
  };
#undef MIG_TH_REL_
#undef MIG_TH_SPLIT_
#undef MIG_TH_KEYS_
#undef MIG_TH_ENUMKEY_
  struct Decomposer{
   template<class T,std::enable_if_t<!scalar_v<bare<T>>,int> =0> Lhs<const bare<T>&> operator<=(T&& v)&&{return {v};}
   template<class T,std::enable_if_t<scalar_v<T>,int> =0> Lhs<T> operator<=(T v)&&{return {v};}
  };
  template<class L> bool truth(Lhs<L>&& e){return ::__mig_th::cmp::truthy(e.v);}
  template<class L,class R,Op O> bool truth(Bin<L,R,O>&& e){return ::__mig_th::cmp::rel<O>(e.l,e.r);}
  template<class T> bool truth(T&& v){return ::__mig_th::cmp::truthy(v);}
  template<class A,class B,class E> bool near(const A& a,const B& b,const E& eps){
   static_assert(num_v<bare<A>>&&num_v<bare<B>>&&num_v<bare<E>>,"CHECK_NEAR takes numbers; compare a numeric projection of crate types.");
   const double x=static_cast<double>(a),y=static_cast<double>(b),t=static_cast<double>(eps);
   const double inf=std::numeric_limits<double>::infinity();
   if(!(y==y))return !(x==x);
   if(y==inf||y==-inf)return x==y;
   double d=x-y;if(d<0)d=-d;
   return d<=t;}
 }
 template<class A,class B> void check_eq(const A&a,const B&b,const char*e){if(!::__mig_th::cmp::eq(a,b))throw std::runtime_error(std::string("CHECK_EQ failed: ")+e);}
 template<class A,class B,class E> void check_near(const A&a,const B&b,const E&eps,const char*e){if(!::__mig_th::cmp::near(a,b,eps))throw std::runtime_error(std::string("CHECK_NEAR failed: ")+e);}
"""
_TH_HPP = (
    '#pragma once\n#include <string>\n#include <map>\n#include <functional>\n'
    '#include <iostream>\n#include <stdexcept>\n#include <cmath>\n#include <cstdio>\n'
    # Declares every std type the strict comparison recognises. Included in both
    # modes so a solver's local build sees exactly the headers grading sees.
    '#include <cstddef>\n#include <limits>\n#include <memory>\n#include <string_view>\n'
    '#include <type_traits>\n#include <utility>\n#include <tuple>\n#include <optional>\n'
    '#include <variant>\n#include <vector>\n#include <array>\n#include <deque>\n#include <list>\n'
    '#include <set>\n#include <unordered_map>\n#include <unordered_set>\n'
    # The specializable machinery, in the reserved namespace (see RESERVED NAMESPACE).
    'namespace __mig_th{\n'
    # CHECK_THROWS(expr) passes iff evaluating expr throws (any exception). Some
    # translated suites use it (they shipped it in a spec harness copy, which grading
    # replaces with this one, so those tests did not compile when graded).
    ' template<class F> void check_throws(F&&f,const char*e){bool threw=false;'
    'try{f();}catch(...){threw=true;}'
    'if(!threw)throw std::runtime_error(std::string("CHECK_THROWS failed: ")+e);}\n'
    # CHECK_THROWS_AS(expr, Type): passes iff evaluating expr throws a Type (or a type
    # derived from it); another exception or none fails the test.
    ' template<class X,class F> void check_throws_as(F&&f,const char*e){'
    'try{f();}catch(const X&){return;}catch(...){'
    'throw std::runtime_error(std::string("CHECK_THROWS_AS failed (threw another type): ")+e);}'
    'throw std::runtime_error(std::string("CHECK_THROWS_AS failed (nothing thrown): ")+e);}\n'
    '#ifndef MIG_STRICT_COMPARE\n'
    ' template<class A,class B> void check_eq(const A&a,const B&b,const char*e){'
    'if(!(a==b))throw std::runtime_error(std::string("CHECK_EQ failed: ")+e);}\n'
    # NaN never compares near a number (a NaN result used to pass: `fabs(NaN)>eps` is
    # false), an expected NaN needs a NaN, an expected infinity needs the same infinity.
    ' inline void check_near(double a,double b,double eps,const char*e){'
    'bool ok=std::isnan(b)?std::isnan(a):std::isinf(b)?(a==b):(std::fabs(a-b)<=eps);'
    'if(!ok)throw std::runtime_error(std::string("CHECK_NEAR failed: ")+e);}\n'
    '#else' + _TH_STRICT +
    '#endif\n'
    '}\n'
    'namespace th{\n'
    ' inline std::map<std::string,std::function<void()>>& reg(){'
    'static std::map<std::string,std::function<void()>> r;return r;}\n'
    ' struct Reg{Reg(const char*n,std::function<void()> f){reg()[n]=f;}};\n'
    ' inline int run(const std::string&n){auto it=reg().find(n);'
    'if(it==reg().end()){std::cerr<<"no test "<<n<<"\\n";return 2;}'
    'try{it->second();}catch(const std::exception&e){std::cerr<<e.what()<<"\\n";return 1;}'
    'catch(...){return 1;}return 0;}\n'
    ' inline void check_true(bool c,const char*e){'
    'if(!c)throw std::runtime_error(std::string("CHECK failed: ")+e);}\n'
    # Public names for spec headers that call them directly (forwarders: the CHECK_*
    # macros call __mig_th, so specializing one of these changes no CHECK).
    ' template<class F> void check_throws(F&&f,const char*e){::__mig_th::check_throws(static_cast<F&&>(f),e);}\n'
    ' template<class X,class F> void check_throws_as(F&&f,const char*e){'
    '::__mig_th::check_throws_as<X>(static_cast<F&&>(f),e);}\n'
    ' template<class A,class B> void check_eq(const A&a,const B&b,const char*e){::__mig_th::check_eq(a,b,e);}\n'
    '#ifndef MIG_STRICT_COMPARE\n'
    ' inline void check_near(double a,double b,double eps,const char*e){::__mig_th::check_near(a,b,eps,e);}\n'
    '#else\n'
    ' template<class A,class B,class E> void check_near(const A&a,const B&b,const E&eps,const char*e){'
    '::__mig_th::check_near(a,b,eps,e);}\n'
    '#endif\n'
    '}\n'
    '#define TEST(name) static void name(); static th::Reg th_reg_##name(#name,name); static void name()\n'
    '#ifndef MIG_STRICT_COMPARE\n'
    '#define CHECK(c) th::check_true(static_cast<bool>(c), #c)\n'
    '#else\n'
    '#define CHECK(...) th::check_true(::__mig_th::cmp::truth(::__mig_th::cmp::Decomposer{} <= __VA_ARGS__), #__VA_ARGS__)\n'
    '#endif\n'
    '#define CHECK_EQ(a,b) ::__mig_th::check_eq((a),(b), #a " == " #b)\n'
    '#define CHECK_NEAR(a,b,eps) ::__mig_th::check_near((a),(b),(eps), #a " ~ " #b)\n'
    '#ifndef CHECK_THROWS\n'
    '#define CHECK_THROWS(...) ::__mig_th::check_throws([&](){ (void)(__VA_ARGS__); }, #__VA_ARGS__)\n'
    '#endif\n'
    '#ifndef CHECK_THROWS_AS\n'
    '#define CHECK_THROWS_AS(expr, ...) ::__mig_th::check_throws_as<__VA_ARGS__>([&](){ (void)(expr); }, #expr)\n'
    '#endif\n')
# Force-included FIRST in every C++ translation unit (`-include mig_guard.hpp`, in
# every compile/preprocess command the grader runs). `#pragma push_macro` /
# `pop_macro` change a macro without any #define/#undef line, so a solver could
# restore a macro the grader's macro audit saw #undef'd (e.g. one that rewrites
# th::check_true inside the CHECK expansions) -- spelled through a token-pasted
# `_Pragma`, which no source scan can see. Poisoned pragma names make every
# `_Pragma("push_macro(...)")` a compile error (the directive form `#pragma
# push_macro` is visible in source and rejected there). No toolchain header, hidden
# test or reference uses either name (measured).
_MIG_GUARD = ('// Grader-owned: force-included first in every translation unit.\n'
              '#pragma GCC poison push_macro pop_macro\n')
# main runs the ONE named test and RETURNS th::run()'s code (0 pass, 1 threw/failed,
# 2 no such test). The exit code IS the result — no nonce, no pipe, no result write.
_MAIN_CPP = ('#include "test_harness.hpp"\n'
             'int main(int argc,char**argv){\n'
             ' return th::run(argc>1?argv[1]:"");\n'
             '}\n')
# Manifest key that turns on the strict comparison harness for one task. Set for
# every NEW C++ translation (MIG_CPP_STRICT_COMPARE=0 opts out), and adopted by an
# existing task once its oracle scores 1.0 and its skeleton 0.0 under it
# (qhardener.adopt_strict_compare); absent == legacy comparisons.
CPP_CONSTRAINTS_PREVIOUS = (
        "Your `crate.hpp` is compiled with the test harness into a small program "
        "that runs ONE test and is graded solely by its PROCESS EXIT CODE (0 iff "
        "that test passed). Your `crate.hpp` must ONLY implement the required "
        "functions/types — it must NOT run any code outside the test-called "
        "functions, and must NOT be able to influence the process exit status. "
        "Concretely, to keep grading sound, do NOT: `#include <cstdlib>`, "
        "`<unistd.h>`, `<csignal>`, `<fstream>`, `<pthread.h>`, `<thread>`, or "
        "`<csetjmp>`; call any process-exit or process-replacing primitive "
        "(`exit`/`_exit`/`_Exit`/`quick_exit`/`abort`/`system`/`pthread_exit`/"
        "`thrd_exit`/`exec*`/`posix_spawn`) or issue a raw exit syscall / inline "
        "assembly; write a `main()`, define `TEST(...)` cases, or reference "
        "`th::`/`test_harness`; or `#undef`/`#define` the macros `CHECK`, `CHECK_EQ`, "
        "`CHECK_NEAR`, `TEST`. Also do NOT run code before/after `main` via a "
        "destructor `~Name()`, a constructor/destructor attribute "
        "(`__attribute__((constructor))` / `[[gnu::constructor]]` etc.), an "
        "`atexit`/`at_quick_exit`/`__cxa_atexit` hook, or a `.init_array`/`.ctors` "
        "section; read the process command line or environment (`/proc/...`, "
        "`environ`, `program_invocation_name`, `__libc_argv`, `getpid`); or open "
        "any file (`fopen`/`open`/`openat`/`creat`/`ifstream`/`ofstream`). A "
        "from-scratch algorithm port needs none of these; ordinary global lookup "
        "tables and other plain constant data are fine.")

STRICT_COMPARE_KEY = "cpp_compare"
STRICT_DEFINE = "-DMIG_STRICT_COMPARE=1"

CPP = dict(
    name="cpp", ext=".hpp", test_suffix="_test.cpp",
    test_re=r'TEST\(\s*([A-Za-z_]\w*)\s*\)',
    base_image="gcc:13-bookworm",
    apt="RUN apt-get update && apt-get install -y --no-install-recommends git python3 ca-certificates tmux asciinema && rm -rf /var/lib/apt/lists/*\n",
    # (The std canary is not shipped: a separate program the solver can detect, with
    # partial type coverage, ~13s/grade; cpp_std_tamper's allowlist is the protection.)
    module_files={"test_harness.hpp": _TH_HPP, "main.cpp": _MAIN_CPP, "mig_guard.hpp": _MIG_GUARD},
    compile='g++ -std=c++17 -O0 -include mig_guard.hpp -I. main.cpp *_test.cpp -o ./mig_tb 2>&1',
    # The same build with the strict comparison harness (manifest cpp_compare=strict).
    strict_compile=('g++ -std=c++17 -O0 -include mig_guard.hpp ' + STRICT_DEFINE
                    + ' -I. main.cpp *_test.cpp -o ./mig_tb 2>&1'),
    # Grading is by PROCESS EXIT CODE: mig_tb runs the one named test and returns
    # 0 iff it passed. No nonce, no pipe, no result write — nothing for agent code
    # to forge; the only residual (forcing exit 0) is a finite set of banned exit
    # primitives.
    run_one_tmpl='./mig_tb "{tid}"',
    test_kill_sec=75,        # grader_tests.py _run_cpp
    framework=('a header-only C++17 impl in `crate.hpp` plus a test file that '
               '`#include "test_harness.hpp"` and `#include "crate.hpp"`, with '
               'tests written as `TEST(Name){ CHECK(cond); CHECK_EQ(a,b); '
               'CHECK_NEAR(a,b,eps); }`. Do NOT write a main() — the harness '
               'provides it. Implement all signatures header-only in crate.hpp'),
    constraints=(
        "Your `crate.hpp` is compiled with the test harness into a small program "
        "that runs ONE test and is graded solely by its PROCESS EXIT CODE (0 iff "
        "that test passed). Your `crate.hpp` must ONLY implement the required "
        "functions/types — it must NOT run any code outside the test-called "
        "functions, and must NOT be able to influence the process exit status. "
        "Concretely, to keep grading sound, do NOT: `#include <cstdlib>`, "
        "`<unistd.h>`, `<csignal>`, `<fstream>`, `<pthread.h>`, `<thread>`, or "
        "`<csetjmp>`; call any process-exit or process-replacing primitive "
        "(`exit`/`_exit`/`_Exit`/`quick_exit`/`abort`/`system`/`pthread_exit`/"
        "`thrd_exit`/`exec*`/`posix_spawn`) or issue a raw exit syscall / inline "
        "assembly; write a `main()`, define `TEST(...)` cases, or reference "
        "`th::`/`test_harness`. Preprocessor macros (prefer `constexpr` constants "
        "and inline functions): a macro your files `#define` must not still be "
        "defined when a test file, the harness or a system header that uses its name "
        "is read, so `#undef` it at the end of the file that defines it (a classic "
        "include guard `#ifndef X` / `#define X` with a name of your own is fine, and "
        "so is a feature macro such as `__STDC_FORMAT_MACROS` defined around a "
        "system `#include`); you may `#undef` a macro your files defined or a name "
        "that is not a macro, but never one the toolchain, the harness or the tests "
        "defined, and you may redefine such a macro only with the identical "
        "definition (e.g. `#define _GNU_SOURCE 1`). Never `#define`/`#undef` a C++ "
        "keyword (e.g. `static_assert`), the harness macros `CHECK`, `CHECK_EQ`, "
        "`CHECK_NEAR`, `CHECK_THROWS`, `TEST`, or `assert`/`NDEBUG`/`MIG_*`, and do "
        "not use `#line`, `%:` digraph directives, `#pragma push_macro`/"
        "`pop_macro`/`redefine_extname`/`GCC system_header`, or `push_macro` / "
        "`pop_macro` as identifiers. Do 