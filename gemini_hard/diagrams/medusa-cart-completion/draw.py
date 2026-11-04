import os, sys; HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, os.path.dirname(HERE))
from sd import *
D = Diagram(1100, 1000)
D.title('Medusa: crash-safe cart completion',
        'A store server can die in the middle of checkout, after the order exists but before the cart points at it. The agent makes cart completion produce exactly one order across separate server and worker processes, and makes the survivors clean up without waiting for a client.')
top, bot = 104, 540
D.zone(20, top, 200, bot - top, 'Clients', 'client')
D.zone(236, top, 284, bot - top, 'Medusa processes', 'app', 'TypeScript workspace in /app')
D.zone(540, top, 222, bot - top, 'Hidden grader', 'grader', 'locks and process kills')
D.zone(782, top, 298, bot - top, 'Local services', 'side', 'same container, no internet')
D.box('sf', 34, top + 52, 172, 'storefront', 'POST /store/carts/:id/complete, retried on either server', 'client')
D.box('burst', 34, top + 178, 172, 'ten requests at once', 'split across the two servers', 'client')
D.box('adm', 34, top + 286, 172, 'admin', 'reservations list, workflow executions list', 'client')
D.box('S1', 252, top + 52, 252, 'Server A, port 9121', 'MEDUSA_WORKER_MODE=server', 'svc', 'typescript')
D.box('S2', 252, top + 142, 252, 'Server B, port 9122', 'same build, separate process', 'svc', 'typescript')
D.box('WK', 252, top + 232, 252, 'Two workers, ports 9123 and 9124', 'MEDUSA_WORKER_MODE=worker', 'svc', 'nodedotjs')
D.box('wf', 252, top + 330, 252, 'complete-cart workflow', 'runs in every process: order, payment authorization, one reservation per stocked line, cart link', 'new', tag='EXTENDED')
D.box('lk', 556, top + 96, 190, 'Cart row lock', 'holds the cart row so checkout stops after the order exists', 'fault', h=100)
D.box('kill', 556, top + 232, 190, 'SIGKILL', 'kills a server mid-checkout, then restarts it', 'fault', h=72)
D.note(556, top + 330, 190, '2 hidden tests and 6 hidden guards, plus 20 existing locking and workflow engine tests', 11, '#c83220')
D.store('PG', 800, top + 46, 262, 'PostgreSQL', 'database sdmedusa: carts, orders, payments, reservations, workflow executions', 'postgresql')
D.store('RD', 800, top + 196, 262, 'Redis', 'workflow engine, locking provider and event bus', 'redis')
D.link('sf', 'r', 'S1', 'l', fb=.4)
D.link('burst', 'r', 'S2', 'l', fb=.5, via=[(228, top + 218), (228, top + 176)])
D.link('adm', 'r', 'S2', 'l', fb=.8, via=[(222, top + 318), (222, top + 190)])
D.arrow([(504, top + 74), (800, top + 74)], 'orders, carts, executions', lpos=.55)
D.arrow([(504, top + 162), (522, top + 162), (522, top + 74)], head=False)
D.arrow([(504, top + 252), (522, top + 252), (522, top + 162)], head=False)
D.arrow([(522, top + 214), (786, top + 214), (786, top + 240), (800, top + 240)], 'locks and workflow state', lpos=.45)
y0 = bot + 26
end = D.seq(36, y0 + 64, 1028, [('C', 'Storefront', 'client'), ('A', 'Server A', 'svc'), ('B', 'Server B or a worker', 'svc'), ('R', 'Redis', 'svc'), ('P', 'PostgreSQL', 'svc')], [
    {'a': 'C', 'b': 'A', 'label': 'complete cart c'},
    {'a': 'A', 'b': 'R', 'label': 'take the completion lock'},
    {'a': 'A', 'b': 'P', 'label': 'order created, cart not linked yet'},
    {'a': 'A', 'label': 'Server A is SIGKILLed', 'kind': 'fault', 'mark': 'bolt'},
    {'a': 'B', 'label': 'no client request: finds the abandoned execution', 'kind': 'new', 'gap': .2},
    {'a': 'B', 'b': 'P', 'label': 'finish it (one linked order) or undo it (no order, no reservations)', 'kind': 'ok', 'mark': 'ok'},
    {'a': 'P', 'label': 'settled within 45 s', 'kind': 'ok'},
    {'a': 'C', 'b': 'B', 'label': "retry on Server B: 200, the same order id", 'kind': 'ok', 'mark': 'ok', 'gap': .3},
    {'a': 'B', 'label': "the dead holder's lock delays it at most 15 s", 'kind': 'ok'},
    {'a': 'C', 'b': 'A', 'label': 'ten requests across both servers', 'gap': .3},
    {'a': 'A', 'label': 'each gets the order, or 409 while completion is in progress', 'kind': 'ok'},
], row=31)
fin = D.note(36, end + 22, 1028, 'At most one order, one payment authorization and one reservation per stocked line; an unknown payment provider keeps its existing error and creates no order.', 12, TEAL, True)
H = fin + 4 - y0
D.zone(20, y0, 1060, H, 'What the instruction asks for', 'plain', 'a server dies between creating the order and linking the cart')
D.h = y0 + H + 20
D.save(HERE + '/diagram.svg')
