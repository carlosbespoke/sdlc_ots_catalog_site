**Payments rollout plan comes out wrong**

Our deploy tooling (shipyard) renders each service's deploy.star with go.starlark.net, and the plan it produced for payments in prod is wrong in two ways. ledger and payouts are both set to start with `--listen=:8090`, which is notifier's port; each of them has its own port in the config. And every CPU request below a full core comes out as `0m`, and all the canary percentages are 0, although the config asks for 500m/250m and 5-20% canaries. The config, the planner code and the plan it rendered are in /workdir/evidence.

The checkout is in /workdir. Could you track down where this actually goes wrong and fix it
there? Please include a regression test, as a _test.go file in the package it exercises (say
starlark/repro_test.go), that fails on the current code because of this problem (a failing
assertion, not an import or build error) and passes once it's fixed. Test the reported
behaviour, not your patch: it should still pass if the bug gets fixed some other correct way, so
no asserting on source text or on helpers only your fix has. It should run on its own from a
clean checkout with just your test files added. It can read files from /workdir/evidence.

I doubt I'm the only one hitting this. Anything else that goes through that code is probably
wrong too, so please fix it at the source rather than special-casing my input. The fix belongs in
the library itself, not in the tests. CI runs the full test suite on every change, so it
shouldn't break anything else.

When you're done, leave a short root-cause note at /workdir/rca.json:

```json
{
  "root_causes": [{"file": "path/from/repo/root.go", "function": "Recv.Method"}],
  "reproducer": "starlark/repro_test.go"
}
```

`root_causes` lists the function(s) where the problem actually starts (one or more), not where it
shows up: the file relative to the repo root and the name as `Func` or `Recv.Method`. Don't pad
the list with functions that only pass the bad value along; extra entries count against the note.
`reproducer` is the repo-relative path of your regression test.
