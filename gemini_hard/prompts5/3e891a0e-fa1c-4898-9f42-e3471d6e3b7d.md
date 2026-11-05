## Goal

The production database is still on the CTFd 3.x schema (Alembic revision `f63a9205d72f`), which CTFd 4.0 can't run on. It has to move to the 4.0 model without downtime, following the approved plan in `MIGRATION_SPEC.md` while both app versions share it.

## Requirements

1. Ship section 1's four release steps as revisions with the fixed ids `ctfd4_expand`, `ctfd4_backfill`, `ctfd4_dual` and `ctfd4_contract`, each leaving the database as described there.
2. Chain them in that order from `f63a9205d72f`, with `ctfd4_contract` the only head. Extra revisions in between are fine.
3. While a version is deployed, each of its catalog statements returns or changes exactly the rows the plan implies, failing only where the plan's model rejects it.
4. Convert every legacy value by section 3's rules, including rows written mid-rollout, and end on exactly its target model.
5. Beyond what the plan converts or removes, every existing row and value survives unchanged.
6. Every step obeys section 2's rules R1-R5 (concurrent index builds, `NOT VALID` then validate, no table rewrites, committed batches of at most 10,000 rows, `lock_timeout` between 1 ms and 5 s).
7. Steps 1-3 roll back per section 4: after both versions have written data, `alembic downgrade f63a9205d72f` restores exactly the starting schema and v1 sees everything either version wrote.
8. Apply the rules to any data of this shape, not just the rows in your copy.
9. Each `alembic upgrade` succeeds and exits without leaving processes running.

## Keep compatible

- Both query catalogs run exactly as written, with any valid parameter values: `app_queries/v1` until `ctfd4_contract` (still through `tracking`), `app_queries/v2` from `ctfd4_dual` on.
- Don't change the 34 existing files in `migrations/versions/`, the 10 in `app_queries/`, `MIGRATION_SPEC.md`, `CTFd/utils/countries/__init__.py`, `CTFd/constants/email.py`, `LICENSE` or `NOTICE`. Adding files is fine.

## Environment

- The repo is a git checkout at `/workspace/ctfd`; Alembic 1.20.0, PostgreSQL 16.15 (database `ctfd`), no network.
- The deploy pipeline runs `alembic upgrade <revision>` from the repo root, once per step in order, as `ctfd` (schema owner, not a superuser). `DATABASE_URL` and the `PG*` variables already connect as that role.
- `dbm status` shows your private copy of the production database; `dbm reset` restores the original snapshot, `dbm save NAME` and `dbm load NAME` keep intermediate states, and `dbm sql` opens psql as `ctfd`.
