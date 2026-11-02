"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I``, so no PYTHON* variable,
user site or working directory reaches it) whose ``sys.path`` gets the candidate's repository root
(the directory holding ``moviepy``) appended *after* the standard library and site-packages: a
candidate file named like a standard-library or third-party module can never replace one. Each
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
# Third-party modules first, from site-packages, before the candidate tree is reachable.
import numpy, PIL.Image, PIL.ImageDraw, PIL.ImageFont, imageio, imageio.v2, imageio.v3, imageio_ffmpeg, cv2, proglog, decorator, dotenv  # noqa: E401,F401
sys.path.append(tree)
warnings.simplefilter("ignore")


def norm(value, depth=0):
    if depth > 14:
        return repr(value)[:500]
    if value is None or isinstance(value, bool):
        return value
    if type(value).__module__ == "numpy" and getattr(value, "ndim", None) == 0 and hasattr(value, "item"):
        return norm(value.item(), depth + 1)
    if type(value).__module__ == "numpy" and type(value).__name__ == "ndarray":
        return norm(value.tolist(), depth + 1)
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

PREAMBLE = r'''"""Replay helpers of the colleague original (tests/private/replay_driver.py without main), unchanged:
observe public timeline APIs using generated in-memory media."""
import json
import numbers
import sys

import numpy as np
from moviepy import AudioClip, ColorClip, VideoClip, concatenate_videoclips


def normalize(value):
    """Compare numeric quantities exactly without imposing an int/float spelling."""
    if isinstance(value, np.ndarray):
        return normalize(value.tolist())
    if isinstance(value, (bool, np.bool_)):
        return bool(value)
    if isinstance(value, numbers.Integral):
        return {'n': int(value), 'd': 1}
    if isinstance(value, numbers.Real):
        n, d = float(value).as_integer_ratio()
        return {'n': n, 'd': d}
    if isinstance(value, dict):
        return {k: normalize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [normalize(v) for v in value]
    return value


def make_clip(duration=8, attachments=True, still=False):
    """Real VideoClip/AudioClip callbacks expose local media time, not cached state."""
    if still:
        c = ColorClip((2, 2), color=(16, 32, 48), duration=duration)
    else:
        c = VideoClip(lambda t: np.full((2, 2, 3), 16 + 8*t), duration=duration)
    if attachments:
        c = c.with_mask(VideoClip(lambda t: np.full((2, 2), (t+1)/16), is_mask=True, duration=duration))
        c = c.with_audio(AudioClip(lambda t: np.array([t/8, -t/16]), duration=duration, fps=16))
    return c


def snapshot(c, times):
    """Read timing and public media samples for the clip and existing attachments."""
    out = {'timing': [c.start, c.end, c.duration], 'frames': [c.get_frame(t) for t in times]}
    for name in ('mask', 'audio'):
        a = getattr(c, name, None)
        if a is not None:
            out[name] = {'timing': [a.start, a.end, a.duration], 'frames': [a.get_frame(t) for t in times]}
    return out


def run(call):
    op = call['op']
    if op == 'sequence':
        clips = []
        for i, spec in enumerate(call['clips']):
            c = ColorClip(tuple(spec['size']), color=(32*(i+1), 16*i, 8), duration=spec['duration'])
            if spec.get('audio'):
                c = c.with_audio(AudioClip(lambda t, i=i: np.array([(i+1)/8+t/16]), duration=spec['duration'], fps=16))
            if spec.get('fps') is not None:
                c = c.with_fps(spec['fps'])
            clips.append(c)
        kw = {'bg_color': (0, 0, 0)}
        if 'method' in call:
            kw['method'] = call['method']
        c = concatenate_videoclips(clips, **kw)
        return {'media': snapshot(c, call['times']), 'fps': c.fps}
    c = make_clip(call.get('duration', 8), call.get('attachments', True), call.get('still', False))
    times = call.get('times', [0, .5, 1])
    if op == 'start':
        if call.get('initial_start') is not None:
            c = c.with_start(call['initial_start'])
        kw = {} if 'change_end' not in call else {'change_end': call['change_end']}
        result = c.with_start(call['start'], **kw)
        if 'next_duration' in call:
            result = result.with_duration(call['next_duration'], change_end=call.get('duration_change_end', True))
    elif op == 'remap':
        kw = {k: call[k] for k in ('apply_to', 'keep_duration') if k in call}
        result = c.time_transform(lambda t: call['factor']*t + call.get('offset', 0), **kw)
    elif op == 'subclip':
        kw = {'start_time': call['begin']}
        if 'end' in call:
            kw['end_time'] = call['end']
        result = c.subclipped(**kw)
    elif op == 'cut':
        result = c.with_section_cut_out(call['begin'], call['end'])
    elif op == 'speed':
        kw = {k: call[k] for k in ('factor', 'final_duration') if k in call}
        result = c.with_speed_scaled(**kw)
    else:
        raise ValueError('Unknown replay operation')
    return {'result': snapshot(result, times), 'original': snapshot(c, times)}


# --- Coverage helpers (OTS copy): small in-memory clips and plain-value summaries.
def tclip(duration=2, fps=None, size=(2, 2)):
    """A video clip whose uniform frame value at time t is round(40*t) (mod 256)."""
    w, h = size
    c = VideoClip(lambda t: np.full((h, w, 3), int(round(40 * t)) % 256, dtype=np.uint8), duration=duration)
    return c.with_fps(fps) if fps is not None else c


def mclip(duration=2, size=(2, 2)):
    """A mask clip whose uniform value at time t is (t mod 4) / 4."""
    w, h = size
    return VideoClip(lambda t: np.full((h, w), (t % 4) / 4), is_mask=True, duration=duration)


def tone(duration=2, fps=100, stereo=False):
    """An audio clip whose sample at time t is 0.1 + 0.1*t (the right channel negated when stereo)."""
    if stereo:
        return AudioClip(lambda t: np.array([0.1 + 0.1 * np.asarray(t), -(0.1 + 0.1 * np.asarray(t))]).T,
                         duration=duration, fps=fps)
    return AudioClip(lambda t: 0.1 + 0.1 * np.asarray(t), duration=duration, fps=fps)


def tvals(clip, times):
    return [int(clip.get_frame(t)[0, 0, 0]) for t in times]


def mvals(mask, times, index=(0, 0)):
    return [round(float(mask.get_frame(t)[index]), 4) for t in times]


def asamp(clip, times):
    return np.round(np.asarray(clip.get_frame(np.array(times, dtype=float)), dtype=float), 4).tolist()


def grid(frame):
    a = np.asarray(frame)
    if a.dtype.kind == 'f':
        return np.round(a, 4).tolist()
    return a.astype(int).tolist()


def pattern(w=4, h=3):
    return (np.arange(h * w * 3).reshape(h, w, 3) * 7 % 256).astype(np.uint8)


def sclip(duration=2, fps=None, size=(2, 2)):
    """A video clip whose uniform frame value is 40*floor(t): constant over each whole second."""
    w, h = size
    c = VideoClip(lambda t: np.full((h, w, 3), (40 * int(np.floor(t))) % 256, dtype=np.uint8), duration=duration)
    return c.with_fps(fps) if fps is not None else c
'''


def run_case(source, tree, scratch):
    # opaque per-case directory: nothing the candidate can see names the observation
    directory = tempfile.mkdtemp(prefix="case-", dir=scratch)
    environment = {"PATH": os.environ.get("PATH", "/usr/bin:/bin"), "HOME": directory,
                   "TMPDIR": directory, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "TZ": "UTC",
                   "CASE_TREE": tree}
    try:
        subprocess.run([sys.executable, "-I", "-B", "-c", RUNNER], cwd=directory, env=environment,
                       input=(PREAMBLE + "\n" + source + "\n").encode(), stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL, timeout=120)
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
