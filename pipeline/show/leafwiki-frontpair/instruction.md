Page dates are off by an hour or two between our two wiki installs

Our wiki runs on the office server (release binary, the box is on Berlin time). We're moving it
into Docker on a new host, and for now both installs run on copies of the same data folder,
synced through git both ways.

The page dates don't survive the trip. In Docker, pages from the office server show their
created and last-edited times an hour late, two hours for pages from last summer. Pages edited
in Docker come back to the office server an hour or two early. Content and titles are fine.

We'll run both for a few more weeks, so the dates need to come out the same whichever machine
wrote the page.

The checkout is in /workdir. Could you track down where this actually goes wrong and fix it
there? Please include a regression test, as a _test.go file in the package it exercises (say
repro_test.go next to the code it tests), that fails on the current code because of this problem
(a real test failure, not an import error) and passes once it's fixed.
Test the reported behaviour, not your patch: it should still pass if the bug gets fixed some other correct
way, so no asserting on source text or on helpers only your fix has. It should run on its own
from a clean checkout with just your test files added.

I doubt I'm the only one hitting this. Anything else that goes through that code is probably
wrong too, so please fix it at the source rather than special-casing my input. The fix belongs in
the code itself, not in the tests. CI runs the full test suite on every change,
so it shouldn't break anything else.

When you're done, leave a short root-cause note at /workdir/rca.json:

```json
{
  "root_causes": [{"file": "path/from/repo/root.go", "function": "Recv.Method"}],
  "reproducer": "path/to/repro_test.go"
}
```

`root_causes` lists the function(s) where the problem actually starts (one or more), not where it
shows up: the file relative to the repo root and the name as `Func` or `Recv.Method`. Don't pad the list
with functions that only pass the bad value along; extra entries count against the note.
`reproducer` is the repo-relative path of your regression test.
