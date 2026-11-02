West-channel vessels keep getting dropped and re-tracked

We've started running the harbour tracker over the recorded radar plots. Both vessels using the west channel get their track dropped part-way along and a fresh one started a few seconds later, each at about the same point in the channel, so each comes out as two tracks. The other vessels come out as one track each. What I don't get is that the track goes after only a couple of missed scans there, when the tracker is set up to keep a track until it has had three scans in a row with nothing. My tracking script, the plot file from the 29 September trial and the script's output are in /workdir/evidence.

The checkout is in /workdir. Could you track down where this actually goes wrong and fix it
there? Please include a regression test, somewhere in a tests/ directory (say stonesoup/tests/test_repro.py), that fails on the current code because
of this problem (a real test failure, not an import error) and passes once it's fixed.
Test the reported behaviour, not your patch: it should still pass if the bug gets fixed some other correct
way, so no asserting on source text or on helpers only your fix has. It should run on its own
from a clean checkout with just your test files added. Keep it under a minute. It can read files from /workdir/evidence.

I doubt I'm the only one hitting this. Anything else that goes through that code is probably
wrong too, so please fix it at the source rather than special-casing my input. The fix belongs in
the library itself, not in the tests. CI runs the full test suite on every change,
so it shouldn't break anything else.

When you're done, leave a short root-cause note at /workdir/rca.json:

```json
{
  "root_causes": [{"file": "path/from/repo/root.py", "function": "Class.method"}],
  "reproducer": "stonesoup/tests/test_repro.py"
}
```

`root_causes` lists every function where the problem actually starts (one or more), not where
it shows up: the file relative to the repo root and the name as `function` or `Class.method`. If something goes
wrong on its own in more than one place, list each of them, and only those: a function that just
passes a bad value along isn't a root cause.
`reproducer` is the repo-relative path of your regression test.
