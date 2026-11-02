# Goal

`MasterLock` currently limits work only within a master process: two masters sharing a database can both run a step protected by the same lock. Make `MasterLock` enforce one cluster-wide limit across the Buildbot masters that share a PostgreSQL database, with the lock state kept in that database; masters on a different database are not limited by it. Both build-level and step-level locks are in scope.

# Requirements

1. With `maxCount=1`, locked steps on different masters never overlap, and waiting builds complete successfully after the holder releases the lock.
2. With `maxCount=2`, counting accesses use no more than two units across masters; exclusive access runs alone, including when counting and exclusive requests are mixed.
3. Waiting requests acquire in the order they entered the cluster-wide queue, even when consecutive requests belong to different masters.
4. After a lock-holding master is killed, its holds cease blocking another master within 45 seconds. The same bound applies when a holding master is frozen; after it resumes, it starts no further locked steps on a lost hold and its affected build ends `RETRY` or `EXCEPTION`.
5. Add `GET /api/v2/locks`: from either master it returns a JSON collection `locks` with each lock's `name`, `maxCount`, and `holders` and `waiters` arrays. Entries include `masterid`, `buildid`, `access` (`counting` or `exclusive`), and `count`; waiters appear in admission order.

# Keep compatible

A single master still serializes its build-level and step-level `MasterLock` users and continues to support `WorkerLock`. `GET /api/v2/masters` still returns `masters` with `masterid`, `name`, `active`, `last_active` and `meta.total`.

# Environment

The repository is at `/app` (Buildbot master and worker). PostgreSQL is local: start it with `sudo service postgresql start`. For development use `postgresql://postgres:postgres@localhost/postgres`; the isolated runtime supplies its own PostgreSQL credentials. The masters use `mq: simple`. Run Python with `/app/.venv/bin/python` from `/app`.
