Accented characters get mangled between our warehouse system and our Python services

We bridge an old warehouse system and our services over kombu, both ways. It writes CSV rows as
Windows-1252 text, and we publish them exactly as it hands them over, as bytes with content_type
text/csv and content_encoding cp1252. Since we updated kombu, our consumers get rows
like "4711;Zo� Bront�;Cr�me br�l�e;�4,50" where it should say "4711;Zoë Brontë;Crème brûlée;€4,50".
Plain ASCII rows look fine, and what our own Python services publish to each other (plain str
bodies, same content type and encoding) comes through fine too.

The checkout is in /workdir. Could you track down where this actually goes wrong and fix it
there? Please include a regression test, somewhere under tests/ (say tests/test_repro.py), that fails on the current code because
of this problem (a failing assertion, not an import or build error) and passes once it's fixed.
Test the reported behaviour, not your patch: it should still pass if the bug gets fixed some other correct
way, so no asserting on source text or on helpers only your fix has. It should run on its own
from a clean checkout with just your test files added.

I doubt I'm the only one hitting this. Anything else that goes through that code is probably
wrong too, so please fix it at the source rather than special-casing my input. The fix belongs in
the library itself, not in the tests. CI runs the full test suite on every change,
so it shouldn't break anything else.

When you're done, leave a short root-cause note at /workdir/rca.json:

```json
{
  "root_causes": [{"file": "path/from/repo/root.py", "function": "Class.method"}],
  "reproducer": "tests/test_repro.py"
}
```

`root_causes` lists the function(s) where the problem actually starts (one or more), not where it
shows up: the file relative to the repo root and the name as `function` or `Class.method`. Don't pad the list
with functions that only pass the bad value along; extra entries count against the note.
`reproducer` is the repo-relative path of your regression test.
