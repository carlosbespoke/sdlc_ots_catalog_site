go-datastructures cannot gracefully stop concurrent queues and timed batching while draining accepted work. Add quiescence with one stable completion receipt covering delivered, abandoned, and canceled work, while preserving abrupt disposal when unused.

Queue, PriorityQueue, and RingBuffer start Open. BeginQuiesce establishes one shared admission boundary; later Put or Offer returns ErrQuiescing without changing the receipt. Drain earlier work in FIFO, comparator, or published-slot order. Complete only after every accepted item is delivered or abandoned. Canceling Completion.Wait releases blocked operations, abandons remaining work once, and permanently records ErrQuiesceCanceled.

Batcher.BeginQuiesce applies that boundary to Put and Flush, drains buffered batches, emits the partial batch once, and counts delivered and abandoned items separately. Cancellation releases blocked Flush and prevents post-terminal publication. RingBuffer cancellation releases blocked producers and consumers without counting reserved unpublished slots.

Preserve each Dispose method's results, idempotence, waiter release, and ErrDisposed behavior. Keep disposal observably distinct from quiescence. NewFromCompletion and NewSelectableFromCompletion publish the same cached terminal outcome to present and late observers, preserving Selectable's first-fill behavior and one channel closure. Error.SetIfUnset lets one concurrent terminal cause win without replacement.

Concurrent Queue consumption preserves earlier FIFO values and completes after final retrieval. PriorityQueue rejects late duplicates while draining accepted unique items in comparator order with balanced accounting. A canceled lifecycle publishes one receipt through every Future; concurrent error writers expose one stable cause.

These are required in what you deliver:

- From github.com/Workiva/go-datastructures/queue: Phase, Open, Receipt, Completion, ErrQuiescing, ErrQuiesceCanceled, Queue.Phase, Queue.BeginQuiesce, PriorityQueue.Phase, PriorityQueue.BeginQuiesce, RingBuffer.Phase, RingBuffer.BeginQuiesce.
- Phase, uint8 enum: Open = 0, Quiescing, Quiesced, Canceled.
- Receipt(Accepted uint64, Delivered uint64, Abandoned []interface{}, Err error).
- Completion.Wait(ctx context.Context) Receipt.
- ErrQuiescing = errors.New("queue: quiescing").
- ErrQuiesceCanceled = errors.New("queue: quiescence canceled").
- (*Queue) Phase() Phase; (*Queue) BeginQuiesce() Completion.
- (*PriorityQueue) Phase() Phase; (*PriorityQueue) BeginQuiesce() Completion.
- (*RingBuffer) Phase() Phase; (*RingBuffer) BeginQuiesce() Completion.
- From github.com/Workiva/go-datastructures/batcher: batcher.Batcher.BeginQuiesce() queue.Completion; futures.NewFromCompletion(completion) and futures.NewSelectableFromCompletion(completion).

Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
