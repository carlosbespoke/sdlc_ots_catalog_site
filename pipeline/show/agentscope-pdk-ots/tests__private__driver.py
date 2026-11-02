"""Observation driver.

Runs as an unprivileged user. It reads the whole case list from **stdin** before any candidate code
is imported: a JSON list of case sources, in order, with no identifiers (the trusted parent keeps
the identifiers and maps results back by position). It then points its own standard input at
/dev/null and marks itself non-dumpable, so no later process of the same user can read the list
through /proc. Every case runs in its own fresh interpreter (``python -I -S``, so no PYTHON* variable, site hook,
user site or working directory reaches it) whose ``sys.path`` gets the candidate's repository root
source directory (``src``, the directory holding ``agentscope``) appended *after* the standard library and site-packages: a
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
# The runner starts with -I -S, so site-packages is not set up at interpreter start and no
# sitecustomize/usercustomize module is ever imported (ISSUE-419). Set up the venv's site-packages here as
# site.main() would, minus those two customization imports; the candidate tree is not on sys.path yet.
import site
site.venv(None)
site.addsitepackages(set())
# Third-party modules first, from site-packages, before the candidate tree is reachable. The namespace
# packages are imported too: a regular package of the same name anywhere on sys.path (a candidate
# src/google/__init__.py, say) would otherwise win over a namespace portion found earlier.
import asyncio, google, jaraco, mpl_toolkits, opentelemetry, sphinxcontrib  # noqa: E401,F401  (namespace packages)
import annotated_types, grpc, httpx, numpy, pydantic, pydantic_core, qdrant_client, rich, typing_extensions, yaml  # noqa: E401,F401
sys.path.append(os.path.join(tree, "src"))
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

PREAMBLE = r'''"""Shared helpers inserted before every observation case of agentscope-pdk-ots.

`LocalEmbedding`, `numeric`, `summary`, `hits`, `_covers` and `observe_async` are the colleague original's
replay driver (pdk-drift-repository-9780fa9f1328 v2, tests/private/replay_driver.py), unchanged apart from
the coroutine's name: a call chunks sections with ApproxTokenChunker, or inserts documents into an in-memory
QdrantStore through KnowledgeBase handles backed by a deterministic offline embedding model (each text
"x,y" embeds as the vector [x, y]) and records what search, listing and deletion return. `observe` runs one
call to completion on a fresh event loop. No model provider or network is used.
"""
import asyncio
import json
import sys
from fractions import Fraction

from agentscope.embedding import EmbeddingModelBase, EmbeddingResponse
from agentscope.credential import DashScopeCredential
from agentscope.message import TextBlock, DataBlock
from agentscope.rag import KnowledgeBase, QdrantStore, ApproxTokenChunker, Section


class LocalEmbedding(EmbeddingModelBase):
    """Deterministic provider through the documented single-batch API."""
    def __init__(self, multimodal=False, missing=False):
        super().__init__(credential=DashScopeCredential(api_key='offline'),
                         model='local', dimensions=2, parameters=None,
                         context_size=10000, batch_size=1000,
                         max_retries=0, retry_delay=0)
        self.supports_multimodal = multimodal
        self.missing = missing

    async def _call_api(self, inputs, **kwargs):
        vectors = []
        for item in inputs:
            text = item if isinstance(item, str) else '1,1'
            vectors.append([float(x) for x in text.split(',')])
        if self.missing:
            vectors = vectors[:-1]
        return EmbeddingResponse(embeddings=vectors)


def numeric(value):
    """Compare quantities exactly without imposing int versus float spelling."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        f = Fraction(value)
        return [f.numerator, f.denominator]
    return {'invalid_numeric': str(value)}


def summary(rows):
    return sorted([{'id': r.document_id, 'count': r.chunk_count,
                    'source': r.source, 'metadata': r.metadata} for r in rows],
                  key=lambda r: r['id'])


def hits(rows):
    # Equal-score order is not constrained. Distinct-score order remains visible.
    groups = []
    for row in rows:
        score = numeric(row.score)
        item = {'id': row.document_id, 'index': row.chunk.chunk_index,
                'text': row.chunk.content.text, 'metadata': row.chunk.metadata}
        if not groups or groups[-1]['score'] != score:
            groups.append({'score': score, 'hits': []})
        groups[-1]['hits'].append(item)
    for group in groups:
        group['hits'].sort(key=lambda r: (r['id'], r['index'], r['text']))
    return groups


def _covers(text, pieces):
    """Accept different legal boundaries while requiring ordered complete coverage."""
    if not pieces:
        return not text
    positions = {(0, 0)}
    for piece in pieces:
        next_positions = set()
        for previous_start, covered in positions:
            for start in range(previous_start, covered + 1):
                if text.startswith(piece, start) and start + len(piece) >= covered:
                    next_positions.add((start, start + len(piece)))
        positions = next_positions
    return any(end == len(text) for _, end in positions)


async def observe_async(call):
    """Keep insert/search/list/delete sequences together within fresh store contexts."""
    async with QdrantStore(location=':memory:', distance='Dot') as store:
        model = LocalEmbedding(call.get('multimodal', False), call.get('missing', False))
        kb = KnowledgeBase('local', 'local corpus', model, store, 'corpus',
                           metadata_filter=call.get('scope'))
        if call['op'] == 'empty':
            result = await kb.insert_document([], document_id='empty')
            queries = [] if not call.get('data') else [DataBlock(source={'type': 'base64', 'media_type': 'image/png', 'data': 'YWJj'})]
            rows = await kb.search(queries)
            return {'id': result, 'hits': hits(rows), 'exists': await store.has_collection('corpus')}
        if call['op'] == 'chunk':
            chunker = ApproxTokenChunker(**call.get('chunker', {}))
            sections = [Section(content=TextBlock(text=t), source='doc.txt', metadata={'section': i})
                        for i, t in enumerate(call['sections'])]
            chunks = await chunker.chunk(sections)
            return {
                'indices': [c.chunk_index for c in chunks] == list(range(len(chunks))),
                'totals': all(c.total_chunks == len(chunks) for c in chunks),
                'source': all(c.source == 'doc.txt' for c in chunks),
                'sections': all(any(c.metadata == {'section': i} and c.content.text in t
                                    for i, t in enumerate(call['sections'])) for c in chunks),
                'budget': all(len(c.content.text.encode('utf-8')) // 4 <= chunker.chunk_size for c in chunks),
                'coverage': all(_covers(t, [c.content.text for c in chunks if c.metadata == {'section': i}])
                                for i, t in enumerate(call['sections'])),
            }
        inserted = []
        for doc in call.get('docs', []):
            owner = KnowledgeBase('writer', 'writer', model, store, 'corpus',
                                  metadata_filter=doc.get('scope', call.get('scope')))
            sections = [Section(content=TextBlock(text=t), source=doc['id']+'.txt',
                                metadata=doc.get('metadata', {})) for t in doc['texts']]
            chunks = await ApproxTokenChunker(chunk_size=64, overlap=0).chunk(sections)
            try:
                doc_id = await owner.insert_document(chunks, document_id=doc['id'],
                                                    document_metadata=doc.get('document_metadata'))
                inserted.append(doc_id == doc['id'])
            except RuntimeError:
                if not call.get('missing'):
                    raise
                return {'error': 'RuntimeError', 'documents': summary(await kb.list_documents())}
        if call.get('missing'):
            return {'error': None, 'documents': summary(await kb.list_documents())}
        if call['op'] == 'listing':
            before = summary(await kb.list_documents())
            if 'delete' in call:
                await kb.delete_document(call['delete'])
            return {'before': before, 'after': summary(await kb.list_documents()), 'ids': inserted}
        queries = [TextBlock(text=q) if call.get('text_blocks') else q for q in call.get('queries', ['1,0'])]
        if call.get('data'):
            queries.append(DataBlock(source={'type': 'base64', 'media_type': 'image/png', 'data': 'YWJj'}))
        kwargs = {key: call[key] for key in ('top_k', 'score_threshold') if key in call}
        rows = await kb.search(queries, **kwargs)
        return {'hits': hits(rows), 'ids': inserted}


def observe(call):
    return asyncio.run(observe_async(call))


# ---------------------------------------------------------------------------------------------------
# OTS copy coverage helpers (not part of the colleague original). Offline fixtures for the P2P coverage
# groups in coverage_cases.py: a configurable local embedding model, in-memory fixture files built with
# the installed document libraries, and views that keep only documented facts of parser output.
# ---------------------------------------------------------------------------------------------------
import base64 as _b64
import io as _io
import os as _os

from agentscope.embedding import EmbeddingUsage
from agentscope.rag import (Chunk, ExcelParser, ImageParser, PDFParser, PPTParser, TextParser,
                            WordParser)


def arun(coro):
    return asyncio.run(coro)


class StubEmbedding(EmbeddingModelBase):
    """Offline embedding model: a text embeds as letter counts of 'a', 'b', 'c' (plus 1 on the last axis)."""

    def __init__(self, dims=3, batch_size=100, multimodal=False, failures=0, retry_on=(),
                 max_retries=0, extra=None):
        super().__init__(credential=DashScopeCredential(api_key='offline'), model='stub',
                         dimensions=dims, parameters=None, context_size=1000,
                         batch_size=batch_size, max_retries=max_retries, retry_delay=0)
        self.supports_multimodal = multimodal
        self.batches = []
        self.kwargs_seen = []
        self.failures = failures
        self.retry_on = tuple(retry_on)
        self.attempts = 0

    def _get_retryable_exceptions(self):
        return self.retry_on

    def vector(self, item):
        if not isinstance(item, str):
            return [0.0] * (self.dimensions - 1) + [1.0]
        letters = 'abcdefghijklmnopqrstuvwxyz'
        vec = [float(item.count(letters[i])) for i in range(self.dimensions - 1)]
        return vec + [1.0]

    async def _call_api(self, inputs, **kwargs):
        self.attempts += 1
        if self.failures > 0:
            self.failures -= 1
            raise (self.retry_on[0] if self.retry_on else RuntimeError)('transient')
        self.batches.append([x if isinstance(x, str) else type(x).__name__ for x in inputs])
        self.kwargs_seen.append(sorted(kwargs))
        return EmbeddingResponse(embeddings=[self.vector(x) for x in inputs],
                                 usage=EmbeddingUsage(time=0.5, tokens=len(inputs)))


def png_bytes(size=(2, 2), color=(255, 0, 0)):
    from PIL import Image
    buffer = _io.BytesIO()
    Image.new('RGB', size, color).save(buffer, format='PNG')
    return buffer.getvalue()


def image_bytes(fmt):
    from PIL import Image
    buffer = _io.BytesIO()
    Image.new('RGB', (2, 2), (0, 128, 255)).save(buffer, format=fmt)
    return buffer.getvalue()


def pdf_bytes(pages):
    from reportlab.pdfgen import canvas
    buffer = _io.BytesIO()
    pdf = canvas.Canvas(buffer)
    for text in pages:
        if text:
            pdf.drawString(72, 720, text)
        pdf.showPage()
    pdf.save()
    return buffer.getvalue()


def docx_bytes(items):
    """items: ('p', text) | ('table', rows) | ('image',) in document order."""
    import docx
    document = docx.Document()
    for item in items:
        if item[0] == 'p':
            document.add_paragraph(item[1])
        elif item[0] == 'table':
            rows = item[1]
            table = document.add_table(rows=len(rows), cols=len(rows[0]))
            for r, row in enumerate(rows):
                for c, value in enumerate(row):
                    table.cell(r, c).text = value
        elif item[0] == 'image':
            document.add_picture(_io.BytesIO(png_bytes()))
    buffer = _io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def pptx_bytes(slides):
    """slides: list of lists of ('text', str) | ('table', rows) | ('image',)."""
    from pptx import Presentation
    from pptx.util import Inches
    presentation = Presentation()
    layout = presentation.slide_layouts[6]
    for shapes in slides:
        slide = presentation.slides.add_slide(layout)
        top = 0
        for item in shapes:
            if item[0] == 'text':
                box = slide.shapes.add_textbox(Inches(0.5), Inches(0.5 + top), Inches(6), Inches(1))
                box.text_frame.text = item[1]
            elif item[0] == 'table':
                rows = item[1]
                frame = slide.shapes.add_table(len(rows), len(rows[0]), Inches(0.5), Inches(0.5 + top),
                                               Inches(6), Inches(1.5))
                for r, row in enumerate(rows):
                    for c, value in enumerate(row):
                        frame.table.cell(r, c).text = value
            elif item[0] == 'image':
                slide.shapes.add_picture(_io.BytesIO(png_bytes()), Inches(0.5), Inches(0.5 + top))
            top += 1.6
    buffer = _io.BytesIO()
    presentation.save(buffer)
    return buffer.getvalue()


def xlsx_bytes(sheets, image_sheet=None):
    """sheets: {name: rows (first row = header)}."""
    import openpyxl
    workbook = openpyxl.Workbook()
    workbook.remove(workbook.active)
    for name, rows in sheets.items():
        sheet = workbook.create_sheet(name)
        for row in rows:
            sheet.append(row)
        if name == image_sheet:
            from openpyxl.drawing.image import Image as XlImage
            sheet.add_image(XlImage(_io.BytesIO(png_bytes())), 'E2')
    buffer = _io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def section_view(sections):
    """Per section: its kind (text/data), source, metadata, and the media type of a data block."""
    view = []
    for section in sections:
        content = section.content
        row = {'source': section.source, 'metadata': section.metadata}
        if isinstance(content, TextBlock):
            row['kind'] = 'text'
        else:
            row['kind'] = 'data'
            row['media_type'] = content.source.media_type
        view.append(row)
    return view


def texts(sections):
    return [s.content.text for s in sections if isinstance(s.content, TextBlock)]
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
                       stderr=subprocess.DEVNULL, timeout=60)
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
