# Repairing a batch of silent numeric faults in montanaflynn/stats without a test suite

I use this Go library to boil batches of measurements down to single figures and to compare one batch of readings against another. After upgrading to the current checkout, a great many calls give me answers I cannot reconcile with what they used to return, or with arithmetic I can do by hand, and elsewhere calls fail that used to work or stay quiet where they used to object. The repository has received 30 separate undocumented edits. Below is everything I was able to pin down from the outside, described by what I asked for and what came back.

Condensing a single list into one figure goes wrong in several ways. Asking which value or values occur most often no longer returns the set that actually repeats most often; an eight-number list whose only repeated value is 5 does not report 5 on its own, and several other lists come back with a set that is simply not what repeats. The reciprocal-based average of 1, 2, 3, 4, 5 should round to 2.19 and instead comes back many times too large, the error growing as the list gets longer, although lists holding a zero or a negative are refused as before. The uncertainty figure for a list containing a zero entry now evaluates to not-a-number, while lists whose entries are all strictly positive still give what I expect. Multiplying every value together fails at both edges: a one-element list such as a lone 7 comes back with a complaint and a not-a-number instead of 7, and an empty list comes back with a number and no complaint at all, where it used to report the empty-input error and a not-a-number. The robust centre figure still reads 7.25 on a nineteen-value list but returns quietly on an empty one rather than complaining.

Watching a list accumulate as it goes is broken at the edges. Running totals still give 1, 3, 6 for 1, 2, 3, but an empty list now comes back as an empty sequence with no complaint where the empty-input error used to come back, and a list holding a single value comes back with that complaint instead of echoing the value. Running peaks fail the same way: a list with a single value returns a complaint rather than echoing that value back, and an empty list returns a sequence with no complaint where the empty-input error used to come back, though three or more values still give the right sequence. Asking where things sit is no better. The position of the largest value is reported as a later occurrence than the first whenever the largest is repeated, so three equal values report the last of them and 1, 5, 2, 5 reports the second 5, while the position of the smallest value and the span between smallest and largest still come out as I expect. Asking for the value at a given share of the readings by ordinal position works at 25, 50, 75, 99 and 100, and empty lists, negative shares and shares above one hundred are still refused, but share zero of a hundred-and-one values never comes back with an answer where it used to hand over the smallest value. Asking what share of a list lies at or below a given figure is wrong in every case I checked: 3 within 1, 2, 3, 4 should come out at 62.5 and does not, a figure tying with several entries gives nonsense, and a figure matching nothing produces infinity instead of a percentage between zero and a hundred. Reading a y off a table of x/y pairs at an in-between x is also wrong, so 1.5 against x of 1 and 2 with y of 10 and 20 gives something other than 15 and every in-between point in a longer table is off, while query points landing exactly on a tabulated x or falling off either end still return the right value. Screening a fourteen-number list for unusually distant values sorts them into the wrong buckets: 15 and 18 no longer appear as the mild strays and -1000 and 100 are not reported as the severe ones, though an empty list is still refused.

Handing these calls input they ought to argue about has become unpredictable in both directions. A whole family of them has stopped objecting to an empty list: squashing values through the S-shaped zero-to-one transform, turning a list into exponential proportions that add up to one, taking the ratio of a list's spread to its average, working out the order positions of the values, and holding values between a floor and a ceiling all accept an empty list silently instead of reporting the empty-input error. In the other direction, some guards no longer fire. Standardizing a list, so that each value is expressed as how many standard deviations it sits from the average, returns numbers for three identical values with no spread at all, rather than the divide-by-zero complaint, while a list such as 1, 2, 3 whose standard deviation is exactly one is now refused with that complaint, and averaging three values whose attached multipliers are all zero likewise returns a number instead of that complaint. Averaging after discarding a fraction from each end now accepts a fraction of exactly 0.5 and produces a value, whereas 1.0, a negative fraction and a not-a-number fraction are still refused with the bounds complaint and a not-a-number result; pulling the outermost fraction at each end in to the boundary values behaves identically, accepting 0.5 where it still refuses 1.0, negatives and not-a-number. A sliding-window average over an empty list reports the wrong failure, a bounds complaint rather than the empty-input one, while window sizes of zero, negative one, or larger than the list are still refused with the bounds complaint. And drawing one hundred values at random, with replacement, from a five-element list gives me back only ninety-nine values.

Comparing two groups, or fitting a shape through paired columns, is worse than wrong: it is misleading. Comparing two groups of five readings whose averages are 5.12 and 4.36, with the spread pooled from the readings themselves, returns a figure smaller than one in magnitude and a p value above 0.05, reporting no difference between two groups that plainly differ. The variant where I supply a known spread never gets that far at all: with a known spread of 0.5 it hands back a complaint instead of the roughly 2.4 figure and its small p value, and with a known spread of 1 on two eight-value lists it likewise fails to return a result. Fitting a straight line through points has lost a safeguard, so a single point on its own, and a set of points all sharing one x coordinate, are no longer refused with the bounds complaint but come back with a fitted series, while the exponential and logarithmic fits still refuse single points, constant x, non-positive x and zero y exactly as before. Measuring how far apart two equal-length coordinate lists are using an adjustable exponent has stopped validating altogether: empty lists, lists of different lengths, and a pair whose result overflows to infinity all come back without any complaint, while every other way of measuring separation in the same family still rejects empty lists.

Three last things I noticed. Far out in the tail of the bell curve the numbers no longer match published reference values, so the tail probability above a large positive point, the probability below its mirror image, and the logarithms of both are all off, whereas the logarithm of the density at the same points still agrees to the last digit. Converting a mixed pile of values -- strings, integers, floating point values and timestamps thrown together -- into a list of numbers no longer survives every variety of input; at least one kind makes the conversion run past the end of its input and the call fails outright instead of producing the numbers. And the spread of the count of trials until a first success, for a success chance of 0.25, should be 12 and is not, and for a success chance of 0.5 should be 2 and is not.

It worked before a set of undocumented edits to the source of stats. The repository has
no test suite to run: finding out what is wrong, and convincing yourself you have fixed
it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "examples/functions/main.go",
      "function": "enclosing_function_name"
    },
    {
      "file": "examples/functions/main.go",
      "function": "Type.method_name"
    }
  ]
}
```

`file` is the path of the file relative to the repository root, written exactly as it
appears in the tree. A file inside a directory keeps its directory prefix: the example
above is `examples/functions/main.go`, not `main.go`.

`function` is the function name. A class or receiver prefix, written `Type.name`, is
accepted anywhere and is required when two functions in the same file share a name: the
bare name cannot tell them apart. When an edit sits inside a function nested in another
function, either name is accepted. Name every function one of the undocumented edits is
in, and only those. Where you wrote the fix does not matter: if you restored the behavior
from a caller or from a helper of your own, name the function the edit is in rather than
the one you wrote. If you suspect a function but found no edit in it, leave it out.
