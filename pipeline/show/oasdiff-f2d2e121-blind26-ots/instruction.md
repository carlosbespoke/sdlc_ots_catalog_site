# oasdiff: wrong answers all over the comparison output, to be diagnosed without a test suite

I use this program to compare two versions of an API description and be told what changed between them and whether any of it would break existing callers. Something went through this codebase and quietly changed one line here and one line there; the result is that a lot of unrelated runs now come back wrong, and nothing prints a warning while doing it. The repository has received 26 separate undocumented edits. What follows is what I actually did and what actually came back.

Asking what changed about what a client is allowed to send, the answers are wrong in several places at once. Comparing a base document against a revision that adds parameters to endpoints already present in both, the newly required query and header parameters and the newly optional ones are no longer listed the way they were; seven entries about added parameters used to come back, and what comes back now is another set entirely. The same trouble shows up when I list every change between two sample documents and ask for extra attributes to be carried through: the total count of entries is off, and the entry that should carry the beta and extension attributes is no longer where it was. When a parameter's schema has a property whose list of accepted types gains or loses a member, nothing is reported about that property being widened or narrowed, although the same widening and narrowing reported directly on the parameter itself still arrives. Where a query parameter and a property nested in a parameter schema switch between accepting null and not, with the type written as a list that includes null, the expected pair of entries about that does not both come back, in either direction of the comparison. Changing a request body property default from 10 to 20 no longer yields the entry naming the old and the new value, and removing defaults outright — one on a text/plain body, one on a JSON property — no longer yields the two removal entries. Adding a maximum length of 15 to a request body property that had none is no longer reported. A request parameter that gains an exclusive minimum is no longer flagged. Removing one of the permitted values from the vendor extension that enumerates allowed values on a request body property yields nothing at all, so the pointer back to line 20 of the base file, where the removed value stood, is gone with it.

Asking what changed about what comes back to a client is no better. Comparing two documents where the mapping that tells a client which alternative shape a reply takes gains one key, drops another and repoints a third, essentially nothing about those additions, deletions and re-targetings is reported, neither for the body itself nor for the mapping on a property nested inside one of the alternatives; five entries were expected and they are not there. Dropping a maximum length of 13 from a response body schema no longer reports the limit being removed, even with every rule turned on. Moving the properties of a body inside a set of alternatives used to come back as exactly one breaking entry per body; now the comparison floods out all the mechanical consequences instead — properties reported as removed, required ones reported as having become optional, alternatives reported as added, and the top-level type reported as changed to any — and it does this for request bodies and response bodies alike, instead of the single wrapping entry at error level.

Reading the wording of the entries that do arrive, some of them describe the wrong thing. A query parameter that becomes deprecated is still noticed, but the sentence it produces is wrong: it tacks a stability note onto the message when the document declares no stability, and it leaves the stability note out when the document does declare one; the sunset date part of the sentence reads as before in both. Going the other way, comparing a document whose endpoint is deprecated against one where the deprecation has been taken away produces no entry at all, so the endpoint coming back into service is never announced. And wherever a change inside an unnamed alternative is described, that alternative is numbered one too high: the first alternative of a list is called number two, and a pair of them reads as the second and third. Alternatives referred to by schema name read as before.

Reading the high-level tally at the top of a comparison, it now claims nothing changed among the labels that group endpoints, although two of them did change; the counts for paths, servers, schemas, headers, parameters, request bodies, responses and security schemes are all still right. Worse, comparing a pair of 3.1 documents whose declared identifier for the terms the document is published under goes from MIT to Apache-2.0, the result carries no information about those terms whatsoever — the identifier change simply is not in there. This one missing piece has more than one cause and needs more than one repair: the emptiness verdict for that part of the result is inverted, so a populated section is thrown away as if it held nothing, and two separate steps that assemble it bail out on success instead of on failure, so the old and new identifier never get recorded. Nothing shows up until all three are dealt with.

Asking for the result in the various shapes I normally consume it in fails in as many ways. Rendered as HTML, or as plain text, I get a document that no longer contains the "New Endpoints: None" section at all; both of those two renderings behave as though they had been routed somewhere else. Comparing two whole directories of files merged into a single pair no longer prints the one deleted endpoint it should print, and asking to upload such a merged comparison for sharing ends with a non-zero exit code where it used to finish at zero. Asking for the XML shape a build system reads, when the change list is empty, no longer emits the single passing case saying no breaking changes were detected — the zero-change document comes out looking like something else entirely. Rendering an empty, nil set of single-document findings as JSON, or as YAML, returns something other than the empty list [] that both used to produce. And in the machine-readable listing of the rules used when reporting all changes, every entry comes back without a severity, so I can no longer see at which level each rule fires; the listing of the single-document screening rules still carries both an id and a severity for every entry.

Steering a run from the command line has its own two faults. Passing extra key=value metadata alongside a run, an entry that begins with an equals sign — that is, one with an empty key — is now swallowed silently instead of being refused with the "expected key=value" complaint; entries containing no equals sign at all, and repeated keys, are still refused, a value that itself contains equals signs still splits on the first one only, and an empty value is still accepted. Running with a suppression file aimed at two removals of shared definitions, far more than those two entries vanish from the output: lines in that file now silence findings they do not name, and the surviving count falls well short of everything-minus-two.

Finally, screening a single document on its own, the complaint about a format that is defined for one type but attached to another has gone quiet. A document with an integer property carrying a date-time format, an integer carrying double, and a third such property nested deeper in a schema produces no findings where three used to be raised, each naming the type the format actually belongs to. And in a document where a property's type is written as a list of a real type together with null, the same complaint says nothing about a uuid format sitting on an integer, where one finding naming that property used to come back — two distinct problems that both have to be fixed before this complaint reports anything usefully again.

It worked before a set of undocumented edits to the source of oasdiff. The repository has
no test suite to run: finding out what is wrong, and convincing yourself you have fixed
it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "checker/api_change.go",
      "function": "enclosing_function_name"
    },
    {
      "file": "checker/api_change.go",
      "function": "Type.method_name"
    }
  ]
}
```

`file` is the path of the file relative to the repository root, written exactly as it
appears in the tree. A file inside a directory keeps its directory prefix: the example
above is `checker/api_change.go`, not `api_change.go`.

`function` is the function name. A class or receiver prefix, written `Type.name`, is
accepted anywhere and is required when two functions in the same file share a name: the
bare name cannot tell them apart. When an edit sits inside a function nested in another
function, either name is accepted. Name every function one of the undocumented edits is
in, and only those. Where you wrote the fix does not matter: if you restored the behavior
from a caller or from a helper of your own, name the function the edit is in rather than
the one you wrote. If you suspect a function but found no edit in it, leave it out.
