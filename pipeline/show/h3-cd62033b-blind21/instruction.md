# uber/h3: diagnosing seventeen injected faults without a test suite

A program that pins places onto a grid of cells covering the globe, and asks this library questions about those cells, now gets wrong answers back from a great many of them. The repository has received 17 separate undocumented edits. The symptoms below are everything that has been observed from the outside, calling the library the way any user would.

Measuring how much ground one cell covers. The figure in steradians, the figure in square kilometres and the figure in square metres all come back far from the true value, and the same wrongness shows up when the thing measured is a closed ring of latitude and longitude points rather than a cell. Separately, the square-kilometre answer for a cell is many orders of magnitude smaller than it should be, as though the planet's radius never entered the arithmetic at all. Asking instead for the length of an edge in metres gives a number roughly one part in a thousand too large.

Stepping outward from a starting cell into what surrounds it. The collection of cells within a given number of steps contains cells that cannot be reached in that many steps, and the ring of cells at exactly that distance comes back with wrong members, or fails outright, for a great many starting cells. Asking whether two cells sit side by side answers wrongly, so an index built for the join between two touching cells either fails or names a join that does not connect them.

Laying a cell out as coordinates on a flat grid anchored at some other cell. The coordinates handed back do not describe the cell they were asked for, and the count of steps between two cells worked out that way is wrong or is reported as a failure. Going the other way, feeding such coordinates back in returns a different cell from the one they were made from, and the chain of cells traced from one endpoint to another contains entries that are not next to each other.

Asking for the corners of cells and tracing outlines around them. The full list of corner indexes for a five-sided cell comes back one entry too long, the surplus slot holding something that is not a corner. Asking for a single numbered corner hands back the wrong one, or an error, depending on the resolution asked for. Corner indexes for cells that sit beside a five-sided cell are wrong too, so an outline traced around a group of cells has its corners misplaced and the shape does not close where it should. Flattening such an outline into plain nested coordinate arrays gives loops and coordinate counts that do not match the outline it was handed.

Placing a cell within the hierarchy it belongs to. Asking where a cell falls among the ordered children of a coarser ancestor returns the wrong position, and feeding that position back in to recover a cell yields a different cell than the one started with.

Covering a drawn region with cells, which goes wrong in several ways at once. The set returned includes cells lying wholly outside the drawn shape, well away from any of its sides, while cells that straddle its rim are dropped, leaving gaps along the boundary where cells plainly overlap the region. Asked for in condensed form, where coarse cells stand in for whole blocks of finer ones, the cells handed back do not line up with the region that was drawn. The number given beforehand as an upper bound on how many cells the covering will need disagrees with how many the covering actually produces. And an option value that is not one of the defined choices for how the covering should be done is quietly accepted, the call returning a result rather than refusing the option.

It worked before a set of undocumented edits to the source of h3. This checkout has
no test suite.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "src/h3lib/lib/algos.c",
      "function": "enclosing_function_name"
    },
    {
      "file": "src/h3lib/lib/algos.c",
      "function": "Type.method_name"
    }
  ]
}
```

`file` is the path of the file relative to the repository root, written exactly as it
appears in the tree. A file inside a directory keeps its directory prefix: the example
above is `src/h3lib/lib/algos.c`, not `algos.c`. An absolute path, or a path with a `..`
segment, does not name a file in the repository and counts as a wrong entry.

`function` is the function name. A class or receiver prefix, written `Type.name`, is
accepted anywhere and is required when two functions in the same file share a name, since
the bare name cannot tell them apart; a function with no class or receiver has no prefix to
add, and its bare name names it. When an edit sits inside a function nested in another
function, name the innermost function that directly contains it; the enclosing function's
name is accepted in its place, except when that function holds another edit too, where only
the innermost names tell them apart. Name every function one of the undocumented edits is
in, and only those, once each: an entry for an edit another entry already names, such as
the same function written twice, with and without its prefix, or by its enclosing function
beside its innermost one, counts as a wrong entry. Where you wrote the fix does not matter:
if you restored the behavior from a caller or from a helper of your own, name the function
the edit is in rather than the one you wrote. If you suspect a function but found no edit
in it, leave it out.
