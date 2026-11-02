# gocron: wrong next-run times, missing printed messages and lost executions, without a test suite

We upgraded to an internal build of this library for carrying out pieces of work on a repeating timetable, and a lot of its answers no longer match what we relied on. Nothing about our own code changed and nothing about the clock changed. The repository has received 16 separate undocumented edits.

Asking when a piece of work that repeats every so many days is due again gives an answer we did not ask for in every case we tried: one time of day at midnight, two times of day within a day, an every-two-days pattern with two times of day, and a pattern crossing the March spring-forward boundary in America/Chicago. The same wrongness shows up under each of the daylight-saving choices, whether the due instant is left to be normalized backwards, pushed past the transition, or skipped entirely, and also on an ordinary June day where nothing special should happen, so it is not confined to transition dates.

Work pinned to particular weekdays is just as bad. With Monday and Thursday chosen, the due instant following a Monday and the one following a Thursday both come back wrong, as does a Saturday firing either side of the spring-forward weekend, and an item created with a beginning instant two days in the past reports its first firing on the wrong date instead of two intervals ahead. Separately from all of that, telling such an item to skip the Sunday on which the clock jumps forward does not land it on the same weekday one week later: March 8 is skipped as asked, but the firing is placed a day beyond March 15.

Checking of the times of day we hand in has gone soft in one spot. An hour of 24 is now accepted and produces a result rather than reporting the hour-range complaint; sixty minutes and sixty seconds are still refused as before, an absent collection and an absent entry still report their own complaints, and a list of legitimate times still comes back ordered from earliest to latest.

Turning up the verbosity to watch it work is unreliable in a pattern that took us a while to pin down. At the chattiest setting, the most detailed line for a message never appears at all; at the middle setting, the line announcing ordinary progress never appears; with the setting that reports only failures, the failure line never appears. Cautionary lines, by contrast, still print at every setting where we expect them. Independently of that, when we pass a message plus two extra values, the printed line does not show those two joined as a name and a value with an equals sign between them, although a message with no extras and a message with one extra still read sensibly.

Taking a piece of work back out by identifier no longer complains about identifiers it does not know: a freshly generated random identifier is accepted silently instead of reporting that no such item exists, and the same silence follows when we try to drop one that had already been taken away on its own after its stop instant elapsed. Dropping something that really is present still works.

Accounting of pending work is off. With a ceiling of ten concurrent items and five one-shot items all coming due together, the number reported as waiting comes back as something other than zero, and with a ceiling of one the reported number is not the four we expect. Relatedly, asking which of a list of candidate instants a given beginning belongs to returns the second entry rather than the earliest when the beginning precedes all of them; an exact hit, a beginning falling between two entries, and a beginning after all of them still answer as before. An item capped at one firing also managed a second.

Behaviour around one-at-a-time and capped concurrency drifts. The first recorded firing instant of a one-at-a-time item on a 100 millisecond cadence comes back noticeably later than the first tick, ten short items behind a ceiling of two in waiting mode take longer than the half second we allow to all get through, and a one-at-a-time item we ask to carry out right now goes twice where one firing is intended.

Finally, the heavy case is badly degraded: a thousand items each due every 100 milliseconds, left going for a second, produced far fewer total firings than the roughly ten thousand we used to see, and the teardown afterwards left background workers from those items still alive rather than finishing cleanly. It looks as though an item's pending collection of upcoming due instants is no longer kept in earliest-first order once it has been pulled out for re-timing, and as though a firing already under way picks up an instant other than its earliest pending one. More than one edit only shows itself in this scenario, so one repair there will not bring the count back.

It worked before a set of undocumented edits to the source of gocron. The repository has
no test suite to run: finding out what is wrong, and convincing yourself you have fixed
it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "examples/elector/main.go",
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


Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
