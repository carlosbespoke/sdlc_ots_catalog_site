import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 900)
D.title('Scrapy: fix every place the request layer drifted from its documentation',
        'Scrapy is a Python framework for crawling websites. Its request and response layer, scheduler, duplicate filter, job persistence, AutoThrottle and built-in middlewares no longer do what their pages and docstrings say. The agent finds each disagreement and changes the code, never the documentation.')
top = 120
def stack(items, x, w, y, gap=12):
    for id, t, b, k, ic in items:
        y += D.box(id, x, y, w, t, b, k, ic) + gap
    return y
y1 = stack([('dc', 'docs/topics/, 8 pages', 'request-response, scheduler, jobs, autothrottle, downloader and spider middleware, cookies, exceptions', 'file', 'book'),
            ('ds', 'Docstrings and #: attribute docs', 'module, class and function documentation of the 45 in-scope modules, examples included', 'file', 'python'),
            ('cm', 'Code comments', 'also part of the documentation for this task', 'file', None)], 36, 298, top + 52)
y2 = stack([('code', 'The request and response layer', 'scrapy/http/, core/scheduler.py, pqueues, squeues, dupefilters, utils (request, url, response, job), throttle, spiderstate, exceptions', 'svc', 'python'),
            ('mw', 'Built-in middlewares', 'every module in scrapy/downloadermiddlewares/ and scrapy/spidermiddlewares/', 'svc', 'python'),
            ('api', 'Public API stays stable', 'behavior that already matches its documentation must work exactly as before; no upstream tests supplied', 'muted', None)], 406, 298, top + 52, 16)
y3 = stack([('ob', '147 observations', '146 small Scrapy programs compared with sealed expected values, plus one unedited-documentation check', 'fault', 'test-pipe'),
            ('f2p', '4 drift groups, 7 observations', 'fail on the delivered code, pass after the reference repair', 'fault', None),
            ('p2p', '35 guard groups, 140 observations', 'already pass and must keep passing', 'client', None),
            ('sc', 'Score', 'mean of drift groups fixed, times mean of guard groups kept', 'dark', None)], 776, 288, top + 52)
D.tag(704 - 8, top + 52 - 8, 'FIX')
bot = max(y1, y2, y3) + 6
D.zone(20, top, 330, bot - top, 'Documentation: the authority', 'side', 'read only; editing it to hide a drift does not count')
D.zone(390, top, 330, bot - top, 'Agent edits: /workdir/scrapy', 'app', 'Python 3.11, Twisted, offline; no website reachable')
D.zone(760, top, 320, bot - top, 'Hidden grader', 'grader', 'runs as user nobody after the session')
D.arrow([(334, D.pt('dc', 'r')[1]), (370, D.pt('dc', 'r')[1]), (370, top + 100), (406, top + 100)], 'compare', lpos=.5, loff=(-22, 0))
D.arrow([(704, top + 100), (776, top + 100)], 'patch', lpos=.5, loff=(0, -8))
# bottom: the path a request takes through the layer in scope, and the rule for each disagreement
y0 = bot + 26
py = y0 + 70
W, G = 176, 34
stages = [('sp', 'Spider', 'yields Request objects; callbacks get Response objects', 'muted'),
          ('smw', 'Spider middlewares', 'depth, referer, url length, http errors, offsite and more', 'svc'),
          ('sch', 'Scheduler', 'duplicate filter by request fingerprint, then priority queues in memory or on disk', 'svc'),
          ('dmw', 'Downloader middlewares', 'retry, redirect, cookies, compression, robots.txt, proxy and more', 'svc'),
          ('dl', 'Downloader', 'not reachable here: requests and responses are built and driven directly in Python', 'muted')]
for i, (id, t, b, k) in enumerate(stages):
    D.box(id, 36 + i * (W + G), py, W, t, b, k, h=104)
for i in range(4):
    x = 36 + (i + 1) * (W + G)
    D.arrow([(x - G + 2, py + 34), (x - 2, py + 34)], kind='flow', width=1.2)
    D.arrow([(x - 2, py + 78), (x - G + 2, py + 78)], kind='muted', width=1.2)
D.note(36, py + 122, 520, 'Requests travel right; responses come back left through the same middlewares.', 11.5, GREY)
ex = 36 + 2 * (W + G)
D.box('job', ex - 30, py + 150, 236, 'Job directory', 'pause and resume a crawl: on-disk queues, seen fingerprints, spider state', 'client', 'folder', h=78)
at_x = 36 + 4 * (W + G) - 60
D.box('at', at_x, py + 150, 236, 'AutoThrottle', 'adjusts download delays from observed latencies', 'client', 'clock', h=78)
D.arrow([(ex + W / 2, py + 104), (ex + W / 2, py + 150)], kind='muted', both=True, width=1.2)
D.arrow([(36 + 4 * (W + G) + W / 2, py + 150), (36 + 4 * (W + G) + W / 2, py + 104)], kind='muted', width=1.2)
ry = py + 262
D.note(36, ry, 1000, 'A drift can sit at any stage above. For each documented behavior:', 12.5, TEAL, True)
rules = [('keep', 'Code matches the docs: leave it', 'checked by the 140 guard observations', 'client'),
         ('fix', 'Code disagrees: change the code', 'checked by the 7 drift observations', 'new'),
         ('no', 'Never edit or delete the docs', 'one observation checks the documentation is unedited', 'fault')]
rh = max(D.box(id, 36 + i * 348, ry + 20, 336, t, b, k, h=62) for i, (id, t, b, k) in enumerate(rules))
D.cross(36 + 2 * 348 + 336 - 18, ry + 20 + 18, 6)
H = ry + 20 + rh + 20 - y0
D.zone(20, y0, 1060, H, 'Where a drift can sit, and what to do with it', 'plain', 'the prompt names the scope and the rule, not the drifts; the agent finds them by reading the documentation against the code')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
