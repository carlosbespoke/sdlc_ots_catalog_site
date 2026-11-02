# A Go package-reproduction toolchain gives wrong answers in eighteen places, diagnosed without a test suite

The repository has received 18 separate undocumented edits. What follows is everything I could pin down from the outside.

I use this toolchain to reproduce published package artifacts from source, to compare a fresh result against the published one, and to drive those jobs from a hosted service. Every stage of that work now answers wrongly somewhere. No upstream host changed what it serves and no code of mine changed, yet the same inputs that used to be judged correctly are judged wrongly, and in several places work that used to succeed now dies with an error.

Keeping track of which positions in a fixed-size set are marked is unreliable in two ways. Asking whether a given position holds a one answers yes for positions that were never touched, and it keeps answering yes after that position has been cleared; the same untrustworthy answers show up after intersecting two sets or taking their exclusive or, so the surviving positions match neither input. Separately, inverting a set whose declared length is indivisible by sixty-four leaves the wrong number of ones behind: a fresh set of one hundred positions, inverted, reports a population other than one hundred.

Working out what a package download points at is wrong in several places, with clearly working neighbours alongside. Image manifest addresses, both those aimed at a tag and those aimed at a digest, no longer yield an identifier, and neither do blob-by-digest addresses; a blob upload endpoint that used to be reported as deliberately ignored is no longer reported that way either. Mirror addresses for the packages of a musl-based Linux distribution fail the same way in both its main and its community trees, while a mis-shaped .apk filename is still reported as unrecognized. A well-formed wheel filename such as package-1.0.0-py3-none-any.whl no longer resolves to the package and release it names, whether handed over as a bare filename or as a full download address, although source distribution filenames with the usual compressed suffixes still resolve and the .metadata suffix is still reported as skipped. Java artifact addresses, from both the central host and the plugin host, and with or without a trailing qualifier in the filename, come back with something other than the expected identifier. One JavaScript case is off on its own: a package download whose release ends in an un-hyphenated release-candidate suffix, like express-2.0.0rc.tgz, no longer yields the identifier it used to, while plain, scoped, hyphenated-name and dotted-prerelease download addresses all still resolve. Rust downloads, cloud-storage objects, source-control endpoints and Debian and Ubuntu pool addresses behave as before. Two questions put to upstream hosting services also fail on their happy day: asking for the metadata document for a Rust package, against a plain 200 answer carrying valid JSON, comes back as an error instead of the parsed record, and asking for the per-release detail document for a Ruby package is treated as a failure status although the host answered 200, so inferring a reproduction recipe for such a package dies with an error rather than returning the recipe with its spec-file location, directory and timestamp.

Fetching source through the service that keeps its own copies of repositories fails at both ends. Over the wire, a read request with no address at all, or with a time bound that is malformed rather than RFC 3339, answers 401 instead of 400, even though the explanatory text in the body is still the right one; the same endpoint still answers 400 for a time bound far in the future, for an address it is unable to canonicalize, and for an address with too many segments. From the calling side, copying a repository down through that service fails outright for both filesystem-backed and in-memory storage, and two separate steps misjudge success: asking for the download location of a requested revision reports an error when the lookup in fact succeeded, and the retrieval of the packed repository treats a 200 answer as a failure. Once a copy is in hand, unpacking a compressed package file into a destination directory silently drops entries it ought to write: a file collection holding a single well-formed symbolic pointer, aimed at a sibling file inside the same destination, leaves the destination empty and reports no error at all. Entries whose own name or whose pointer climbs out of the destination are still absent afterwards.

Comparing a pair of artifacts is broken twice over. Handing in a list of well-formed user-supplied normalization entries answers with an error instead of the assembled rules, so the whole summary of a pair of artifacts fails at that point. And the rule that is meant to drop members whose names match a glob drops none of them, so two zip files that differ only in one such member no longer reduce to the same digest.

Carrying out a reproduction phase inside a sandbox yields the wrong command lines. The command that launches the sandbox now carries a memory-cap flag with a blank value even when no cap was asked for, so the argument vector differs from what I requested in every configuration I tried, including the default one, the one with an inline auth header, the one removed on exit and both privileged variants. The per-phase command then hands the sandbox a script in which the strict-mode prelude is glued directly onto the first line of the phase script with no line break, producing one mangled line instead of a prelude followed by the commands.

Finally, kicking off a long-lived reproduction hands back an operation identifier, and fetching the operation by that identifier works, but turning that identifier back into the name under which the saved record lives fails with a complaint about its shape, so the record behind an in-flight job is impossible to locate and its eventual completion never surfaces.

It worked before a set of undocumented edits to the source of oss-rebuild. The repository has
no test suite to run: finding out what is wrong, and convincing yourself you have fixed
it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "internal/api/apiservice/agent.go",
      "function": "enclosing_function_name"
    }
  ]
}
```

`function` is the function name. A class prefix is ignored if you include one. When an
edit sits inside a function nested in another function, either name is accepted. Name
every function one of the undocumented edits is in, and only those. Where you wrote the
fix does not matter: if you restored the behavior from a caller or from a helper of your
own, name the function the edit is in rather than the one you wrote. If you suspect a
function but found no edit in it, leave it out.
