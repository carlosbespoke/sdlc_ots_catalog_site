# Fenced failover for document workers

We need documents served by a stopped or partitioned document worker to move to another worker, without the old worker overwriting edits if it comes back. Today such a worker keeps its Redis assignments after its liveness report expires, so requests to those documents hang, and simply reassigning them would let the old worker overwrite edits when it resumes.

## What we need

- With `GRIST_DOC_WORKER_LEASE_SECONDS=3`, a worker that no longer renews its lease relinquishes its documents on the next home-server lookup. Another available worker serves the last flushed document and accepts edits. Concurrent lookups from two home servers agree on one owner and do not duplicate the document.
- A worker reporting within its lease retains its assignments.
- An old worker resuming after takeover refuses actions from its existing websocket clients and cannot publish another document state or overwrite its checksum. An upload started before takeover but completed afterward cannot become the current document, even if the new owner has already saved edits.

## Keep working

Normal document reads and edits on multiple workers, the existing worker lookup and `GET /status`, and coordinated moves through `POST /api/docs/:docId/assign` that retain flushed edits. Healthy assignments stay stable across home servers and distribute documents across available workers.

## Setup

The checkout is at `/app`. Redis, PostgreSQL and a versioned S3-compatible object store are available through `REDIS_URL`, `TYPEORM_*` and `GRIST_DOCS_S3_*`. Home and doc workers are separate processes from this build (`GRIST_SERVERS=home` or `GRIST_SERVERS=docs`). The solver container has no Docker daemon or internet; dependencies are installed. Run TypeScript builds from `/app` with `yarn run build`.
