# ZHA quirks collection: diagnosing thirty regressions without a test suite

Everything below was observed on a running installation after a routine update, with no configuration change on my side. The repository has received 30 separate undocumented edits. The same equipment is still on the air, speaking the same protocol it always did, but numbers now arrive wrong, alarms stay silent, shades travel the wrong way, keys on the remotes do nothing, and options written from the app no longer land.

Start with the plain readings that equipment sends in unprompted. A mains-powered wall unit that measures its own internal temperature of 25 degrees used to surface 2500 in hundredths and now surfaces 2525, while the lowest and highest figures it has recorded still pass through untouched. A mains socket that measures consumption has the mirror-image trouble: an instantaneous demand of 25000 is surfaced verbatim instead of being scaled down to 25, and its cumulative delivered-energy total of 25 now arrives as 0, because the scaling that belongs to the demand figure is applied to everything else instead. A combined presence-and-brightness sensor converts its raw readings wrongly in two separate ways at once: every reading is one step too high across the whole range, so pitch darkness that used to surface as 1 now surfaces as 2, and independently of that the brightest raw readings are grossly overstated, with a raw 34299 that should convert to 26989 coming back as an enormous number. An air-quality sensor now accepts and surfaces a particulate reading of 1001, where readings past the plausible range used to be dropped, while 1000 still comes through as before, and the temperature carried in those same reports is roughly a tenth too large, so a figure that should be 2880 arrives noticeably higher and negative figures are skewed the same way. Several sensors that run on batteries pack many fields into a single report, and that packed frame no longer decodes to the values it actually carries, particularly when it includes text or raw-byte members.

Alarms and presence that should raise a state the app watches now fail in three ways. A ceiling-mounted presence sensor used to blank out its second alarm bit and now passes that bit straight through, while a genuine first-alarm report from it is blanked to zero instead. A lamp with presence sensing built in reports movement on a maker-specific reading, and that report no longer reaches the alarm state at all, so the alarm never trips and never clears. A detector that watches for fire behaves the same way: its state changes leave the alarm state completely untouched, so neither the alarm nor the all-clear that used to follow each change ever appears.

Tapping the keys of the handheld remotes mostly produces nothing now. A small remote that reports single taps, double taps and holds inside a maker-specific frame fires no event whatsoever for any of the three, though the frames still arrive. A four-key remote credits a tap on one key to a different key entirely, and the set of status values it treats as a real tap has shifted, so some taps that used to be reported are now discarded. On a dimmer remote, a burst of four quick taps is no longer collapsed into one four-tap report: the instant of the last tap is recorded on a different time scale from the one it is later compared against, so the grouped callback never fires with the right count. A two-gang wall switch is worse still — an actual tap produces no event at all, while a later update of that switch's status text produces a spurious tap event out of nowhere.

Telling blinds and shades to move, or asking where they are, goes wrong in several ways. A blind whose internals run backwards used to have its open and close instructions exchanged before transmission; both now leave exactly as issued, so it travels opposite to what was asked for. A shade takes the wrong action both for a move-to-percentage request and for the plain movement instructions — the two handling paths have traded places, so the wrong figure is written to the hardware in each case, and the position that should be read back afterwards is not. Another shade reports 175 for a position report of 75, where 25 was expected. Asking a blind controller to read back its fourteen stored setup figures now leaves one of them out of the request. And waiting for that same controller's motor to come to rest returns immediately after a single poll even while the motor still reports itself running, while the timeout failure that used to be raised when a motor never stops is never raised any more.

Writing settings down to equipment from the app is the next sore spot. Writing a target temperature to an electric heating panel produces the wrong outgoing frame, although writing its operating mode still produces precisely the frame it always did, and that same panel's incoming reports are mis-scaled in opposite directions, with a measured room temperature that should surface as 1790 arriving far too small while the setpoint it echoes back arrives far too large. On a radiator valve, turning on the display auto-lock option no longer produces the message it used to, while the many other writes to that valve are unchanged. A mains-wired heating controller used to turn a write of its heating-mode setting into a maker-specific instruction, and that translation no longer happens, so a plain write is attempted instead. Converting a weekly heating programme into its byte form and back yields wrong temperatures in every slot, though the days and the switch-over times survive the round trip intact. And on a multi-gang switch, writing the option that detaches the relay no longer sends the combined bit mask out to the hardware, and none of the local relay state updates that used to follow that write are emitted.

Finally, the descriptions that tell the software what a piece of equipment is made of are themselves misbehaving. Where a description pins a figure to a constant, that figure no longer reads back: a consumption-measuring socket whose divisor is pinned to 1000 reads back something other than 1000, an unsolicited divisor report from the hardware that used to be quietly ignored is now accepted and raises an update event, and the three pinned figures about a sensor's batteries — the size, the count and the rated voltage — yield nothing at all when read back. Declaring such a sensor with only a size fills in a count and a rated voltage that were never given, and when size, count and a rated voltage of 60 are all supplied, the 60 is replaced by a default figure. An energy meter that must keep its unused three-phase readings hidden now reports them as available, while its single-phase active power reading, which should be available, reports as unavailable. A group of readings declared as belonging to the client side ends up marked as the server side, so the per-hardware configuration pass is applied to the wrong side of it. And a description that drops the second numbered section of a piece of hardware and then declares a fresh empty one in its place now fails to load at all, the whole description rejected with an error rather than yielding the new section.

It worked before a set of undocumented edits to the source of zha-device-handlers. The repository has
no test suite to run: finding out what is wrong, and convincing yourself you have fixed
it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "zhaquirks/adeo/color_controller.py",
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
