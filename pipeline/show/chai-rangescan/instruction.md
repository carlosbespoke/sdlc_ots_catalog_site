**Range queries on our imported history skip everything from the 90s**

Last month we imported our legacy history (back to 1993). Row by row it's fine, and
`SELECT min(logged_at) FROM audit_log` says 1993-04-12. But time-range queries don't see the old
rows:

- The nightly retention job, `DELETE FROM audit_log WHERE logged_at < '2005-01-01'`, removes the
  2000s rows and leaves the old ones, so `min(logged_at)` never moves.
- The archive screen pages newest first with
  `SELECT id, happened_at FROM events WHERE happened_at < '<cursor>' ORDER BY happened_at DESC LIMIT 50`.
  The pages stop around the turn of 2000.

The indexes are `audit_log(logged_at)` and `events_by_time ON events(happened_at DESC)`. No
errors, the results are just short.

The checkout is in /workdir. Could you track down where this actually goes wrong and fix it there?
Please include a regression test, as a _test.go file in the package it exercises (say
./repro_test.go), that fails on the current code because of this problem (a failing assertion, not
an import or build error) and passes once it's fixed. Test the reported behaviour, not your patch:
it should still pass if the bug gets fixed some other correct way, so no asserting on source text
or on helpers only your fix has. It should run on its own from a clean checkout with just your
test files added, as a compiled test binary without the repository's .go sources around.

I doubt I'm the only one hitting this. Anything else that goes through that code is probably
wrong too, so please fix it at the source rather than special-casing my input. The fix belongs in
the library itself, not in the tests. CI runs the full test suite on every change, so it shouldn't
break anything else.

When you're done, leave a short root-cause note at /workdir/rca.json:

```json
{
  "root_causes": [{"file": "path/from/repo/root.go", "function": "Recv.Method"}],
  "reproducer": "repro_test.go"
}
```

`root_causes` lists the function(s) where the problem actually starts (one or more), not where it
shows up: the file relative to the repo root and the name as `Func` or `Recv.Method`. Don't pad
the list with functions that only pass the bad value along; extra entries count against the note.
`reproducer` is the repo-relative path of your regression test.
