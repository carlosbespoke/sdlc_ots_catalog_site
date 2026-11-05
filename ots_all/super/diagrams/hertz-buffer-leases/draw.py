import os, sys; HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, '/Users/carlos/code/sdlc_final_samples/gemini_hard/diagrams')
from sd import *
D = Diagram(1100, 1000)
D.title('Hertz: borrowed buffers that report when they are safe to reuse',
        'The agent adds borrowed-buffer writes to the CloudWeGo Hertz HTTP framework. Every submitted buffer gets one lease that settles exactly once, after the bytes are copied, flushed, failed or abandoned, while the bytes on the wire stay what Hertz sends today.')
top, bot = 104, 540
D.zone(20, top, 300, bot - top, 'What the agent receives', 'side', 'offline container, 2 CPUs, 8 GB, up to 12 hours')
y = top + 50
for k, t, body, kind, ic in [('repo', 'Hertz checkout in /app', 'cloudwego/hertz at commit d651020, Go modules already downloaded; GOPROXY off', 'svc', 'go'),
        ('pk', 'Packages to extend', 'pkg/network: leases, borrowing writers, LeaseError; pkg/protocol/http1/resp and http1/req: borrowed response and request writers', 'svc', 'binary-tree'),
        ('rules', 'Constraints', 'same wire output, request targets and error classes; existing Writer-only implementations keep working', 'muted', None)]:
    y += D.box(k, 36, y, 268, t, body, kind, ic) + 12
D.zone(340, top, 400, bot - top, 'Agent writes, in this order', 'app', 'the collected diff of /app is what gets graded')
D.box('plan', 356, top + 50, 368, '1. RESEARCH_AND_PLANNING.md', 'what the existing code does, the constraints, the plan and how to know it works; written before any code and not rewritten afterwards', 'new', 'markdown', tag='FIRST')
D.box('code', 356, top + 176, 368, '2. The change', 'lease types and NewWriter; WriteResponseBorrowed, WriteRequestBorrowed, WriteProxyRequestBorrowed, NewBorrowedChunkWriter; client and server lifecycles settle leases before retry, pooling or reuse', 'svc', 'file-code')
D.box('patch', 356, top + 318, 368, 'model.patch', 'git diff of /app against the base commit, collected after the session', 'dark')
D.arrow([(540, top + 150), (540, top + 176)])
D.arrow([(540, top + 292), (540, top + 318)])
D.arrow([(304, top + 210), (356, top + 210)], 'context', lpos=.5, loff=(0, -6))
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'Go tests, run after the session')
D.box('f2p', 776, top + 50, 288, '29 new-behavior tests', 'must fail on the base commit and pass with the patch', 'fault', 'test-pipe')
y = top + 134
groups = [('writer leases and errors', 8), ('fixed, streamed and HEAD', 7), ('requests and proxies', 6),
          ('chunked responses', 3), ('same output as before', 3), ('connection backends', 2)]
for name, n in groups:
    D._t(790, y + 4, name, 11.5, False, INK); D._t(1052, y + 4, str(n), 11.5, True, '#c83220', 'end')
    D.el.append(f'<rect x="{960}" y="{y - 6}" width="{n / 8 * 76:.1f}" height="10" rx="2" fill="#f7b3a9"/>')
    y += 20
D.box('p2p', 776, y + 6, 288, '88 existing tests', 'across the repository, must still pass', 'svc', 'test-pipe')
D.box('sc', 776, y + 92, 288, 'All or nothing', 'reward 1 only if all 29 pass and none of the 88 breaks', 'dark')
D.arrow([(724, top + 345), (742, top + 345), (742, top + 76), (776, top + 76)], 'patch', lpos=.12, loff=(0, -6))
# bottom: one borrowed chunk, from submission to its single terminal result
y0 = bot + 28
end = D.seq(36, y0 + 64, 1028, [('HD', 'Handler', 'client'), ('CW', 'BorrowedChunkWriter', 'svc'), ('CN', 'Connection writer', 'svc'), ('WR', 'Wire', 'muted')], [
    {'a': 'HD', 'b': 'CW', 'label': 'lease, _ := cw.WriteBorrowed(buf)    (buf: 4,096 bytes, illustrative)'},
    {'a': 'CW', 'b': 'HD', 'label': 'lease.Result().State == LeasePending: buf still belongs to Hertz', 'kind': 'muted'},
    {'a': 'CW', 'b': 'CN', 'label': 'chunk size line, then buf itself, not a copy'},
    {'a': 'CN', 'b': 'WR', 'label': 'Flush(): framing and payload sent', 'kind': 'new'},
    {'a': 'CN', 'b': 'HD', 'label': 'Done() closes; Result() = {LeaseReleased, Bytes: 4096}: buf may be reused', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'CN', 'b': 'HD', 'label': 'if the flush fails instead: {LeaseFailed, Bytes affected, Err: *LeaseError wrapping the cause}', 'kind': 'fault', 'gap': .2},
    {'a': 'HD', 'b': 'CW', 'label': 'FinalizeCompletion(): one OutputCompletion for all chunks, terminal framing, trailers and the final flush'},
], row=32)
fin = D.note(36, end + 22, 1028, 'Each lease reaches exactly one terminal state, released, failed or abandoned, and later flushes cannot change it.', 12, TEAL, True)
fin = D.note(36, fin + 8, 1028, 'The bytes on the wire are the same as the existing chunked writer sends today.', 11.5, GREY)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'One borrowed chunk, from submission to its single result', 'plain', 'illustrative example: the handler, the buffer size and the order of calls are made up for this picture')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
