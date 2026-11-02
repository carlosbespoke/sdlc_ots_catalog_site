# Repairing google/mangle's Datalog toolchain without a test suite

I use this to write rules over stored rows and derive new rows from them. The repository has received 30 separate undocumented edits. Ordinary programs still load and evaluate, so the damage is scattered rather than total; what follows is everything I could pin down by using the system normally.

Submitting a program to be vetted before it runs now goes wrong in both directions. Programs that could never be ordered for evaluation are waved through: two relations each negating the other, a rule negating the very relation it defines, and a recursive rule that tallies over its own output all pass without complaint. The opposite happens too, and programs whose rules agree perfectly with the argument types written for them are refused as type errors: a lone rule copying a number out of one relation into another, and likewise the cases involving several alternatives offered as one type, element types of lists and of maps, and prefix conditions on strings and on hierarchical names. Two mistakes at minimum feed those refusals, one in how the outcome of comparing an inferred type against a written one is read and one in which type is taken for an argument position of a body condition, so curing either alone leaves the refusals in place.

The smaller questions that same vetting leans on are answered wrongly too. Where one relation's argument is written to range over another relation's argument, the type it inherits once every annotation is worked out is no longer every alternative written for that other relation taken together: annotations offering several alternatives and annotations offering exactly one behave as though swapped. Normalizing a goal so that no variable occurs twice mishandles the anonymous placeholder — an argument written as an underscore, which should be left alone, is renamed and picks up an extra equality, an ordinary variable already used elsewhere is left in place instead of getting a new name of its own and an equality, and the list of variables the goal is said to bind no longer agrees. Asking a list of variables whether a given variable is among them answers inverted, calling one that is present absent and one that is absent present, while asking for a variable's position still gives the right index and still gives -1 for one that is missing. Gathering the hierarchical name constants used as types no longer reaches the ones nested inside compound types, so after scanning a handful of annotations the gathered set differs from the names they mention, and asking which gathered prefix covers /something/something/foo no longer answers /something/something. And looking up the type written for a named member of a compound type gives a wrong answer for the required member and the optional one alike, though listing that compound's required and optional members separately still returns exactly what was written.

Getting programs and outside data in has its own failures. A type annotation that nests a pair holding a compound with one optional member and one required member whose type is a list of alternatives comes back with a different shape than was written, while the simpler annotations in the same file, including one using a tagged variant with two branches, come back intact. A source unit whose statements include the header naming the unit it belongs to now fails outright with an error, whether that header carries only the name or extra annotations alongside it; a unit with no such header is handled as it always was. And converting a document in the usual textual interchange notation holding a string, a floating point number, an array of booleans and a nested object fails with an error instead of coming back as a value with named members.

Running a program and reading the answers back has lost whole kinds of rule. A rule that keeps rows of one relation only when they are absent from another produces nothing at all, so a "present here but not there" query comes back empty, and the ordering of such conditions inside a body no longer matters because none of them work. A rule whose body compares two quantities for order also stops contributing, so conclusions that depend on one node lying between two others, or on a cycle being found by comparison, never appear. Asking the supplied comparison whether one floating point number is strictly greater than another yields an error instead of yes or no, while less-than, less-or-equal and greater-or-equal on the same numbers still answer, so a query for readings above a threshold yields nothing while the other four threshold queries are fine. Asking whether a string starts with a given prefix now gives the wrong verdict, including for a string tested against itself.

Answers that have to be assembled rather than read off are wrong in their own ways. A rule that groups over a body of several conditions and takes a maximum produces no result whatsoever, and when such a rule is reshaped into two rules the intermediate relation invented for the first half is numbered one too high, so the helper that should carry a 1 in its name carries a 2 and the pair of rules that comes out does not line up with the original at all. In a program keeping only the best value per key, written with an annotation saying that two arguments fix the third together with the name of a helper relation choosing the shorter of two lists, the shortest route is no longer the one retained: the four-step route survives in the store when only the direct one should, and two distinct misreadings of that annotation contribute, one in the part saying which arguments determine which and one in the part naming the helper. Querying one of the interchangeable stores for a two-argument relation with the first argument pinned to a name and the second left open returns the wrong set of rows, while the same query against the other stores returns both answers, and other query shapes against that same store are fine.

Asking why a conclusion holds is unreliable. With no depth limit requested, the account that comes back is cut short: for a conclusion reached through a negated condition I no longer get one complete account with its two supporting steps and an absence entry for the missing row. The second way of obtaining an account, by replaying a trace of the evaluation, disagrees with the direct search for the same goal about which stored rows the proof finally rests on. And writing an account out as tuples into a store now fails with an error rather than emitting them, so neither the per-shape tallies nor the single absence entry can be had at all.

Moments and spans of time are subtly wrong in several places. A moment built from a year, a month and a day comes out a minute after midnight instead of at midnight, though the day, month, year and zone are right. Shifting a moment in a named zone forward by one week, where the clocks change within that week, lands nowhere near the expected instant, while shifting by days, months or years over the same kind of change, and shifting by zero units, all land where they should. Asking whether two spans cross when the first ends exactly at the instant the second begins answers no, although that shared instant should count; nested, partly crossing, earlier and later pairs all answer as expected. Asking whether one span lies entirely earlier than another answers yes when the first ends exactly where the second starts, which should not count, while genuinely separated, crossing and reversed pairs answer as expected. Asking whether one span falls within another answers no when the two are identical, while one strictly inside another still answers yes and a partial crossing still answers no. The cap on how many spans may be attached to a single item is enforced one too late: with a cap of three a fourth is accepted, and with a cap of a hundred the hundred-and-first is accepted instead of being refused. And asking for back-to-back spans to be joined leaves them apart: two where the second begins one nanosecond after the first ends still count as two afterwards.

It worked before a set of undocumented edits to the source of mangle. The repository has
no test suite to run: finding out what is wrong, and convincing yourself you have fixed
it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "analysis/declcheck.go",
      "function": "enclosing_function_name"
    },
    {
      "file": "analysis/declcheck.go",
      "function": "Type.method_name"
    }
  ]
}
```

`file` is the path of the file relative to the repository root, written exactly as it
appears in the tree. A file inside a directory keeps its directory prefix: the example
above is `analysis/declcheck.go`, not `declcheck.go`.

`function` is the function name. A class or receiver prefix, written `Type.name`, is
accepted anywhere and is required when two functions in the same file share a name: the
bare name cannot tell them apart. When an edit sits inside a function nested in another
function, either name is accepted. Name every function one of the undocumented edits is
in, and only those. Where you wrote the fix does not matter: if you restored the behavior
from a caller or from a helper of your own, name the function the edit is in rather than
the one you wrote. If you suspect a function but found no edit in it, leave it out.


Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
