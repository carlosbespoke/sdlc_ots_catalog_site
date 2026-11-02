**Wave w2 rollback put services back on the wrong releases**

Tuesday's w2 rollout failed its health checks, so the pipeline ran our rollback planner (risor CLI
built from this checkout) and on-call executed the plan it printed. Several services didn't end up
on the release on-call expected, gateway got skipped altogether, and the DB team says orders-db
was migrated to the wrong schema version. The script, its input and what it printed are in
/workdir/evidence.

The checkout is in /workdir. Could you track down where this actually goes wrong and fix it there?
Please include a regression test, as a _test.go file in the package it exercises (say
./repro_test.go), that fails on the current code because of this problem (a failing assertion, not
an import or build error) and passes once it's fixed. Test the reported behaviour, not your patch:
it should still pass if the bug gets fixed some other correct way, so no asserting on source text
or on helpers only your fix has. It should run on its own from a clean checkout with just your
test files added, as a compiled test binary without the repository's .go sources around. It can
read files from /workdir/evidence.

Fix it where it starts. Other code goes through the same place and needs to come out right too,
not just the case in this report. Changes to test files and test data aren't part of the fix. The
project's own test suite isn't in this checkout. The full suite runs against your change and needs
to stay green, apart from any test that asserts the current broken behaviour.

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
