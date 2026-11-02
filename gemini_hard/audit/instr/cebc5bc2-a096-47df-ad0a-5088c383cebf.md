# fzf misreads keys, miscounts rows and misorders matches — diagnosing it without a test suite

This is an interactive filter: you hand it a list of lines, it draws them on the screen, and as you type it narrows the list and hands back what you picked. A fresh build of it misbehaves in a startling number of unrelated places, so this is everything I could pin down from the outside, entirely by using it. The repository has received 30 separate undocumented edits.

Start it up and the trouble begins before anything is drawn. It asks the screen where the cursor sits, then whether bracketed paste is on, then where the cursor sits again; even when all three replies come back promptly and in order, the row and column it settles on are the ones you would see if nothing had been read at all. The clearing it does afterwards is off too: the number of erase sequences it writes to wipe out a reply the screen echoed back does not match how far that echo actually reached. Once it is drawing, printing two coloured words followed by two plain ones produces a byte stream with the ordinary printable letters missing, as though each of them were an unprintable control code. Colours are mistranslated as well — one given as six digits in base sixteen comes out with its red, green and blue taken from the wrong digits, so a request for pure red is not red — and when a colour state is turned back into an escape sequence, the reverse-video attribute is always tacked on, so even a plain foreground change, red over the default background, carries an attribute nobody asked for.

Laying entries out on the screen is wrong in two ways that both concern how much room something takes. A run of text that exactly fills the room available is pushed onto a second row rather than left alone, while genuinely over-long text still breaks where you would expect. And any entry with line breaks inside it is measured as narrower than it really is, so the number of rows reported for it, with breaking across rows switched off and switched on at assorted widths, is lower than the number it actually occupies, and the width at which it begins reporting an overflow shifts to match.

Telling it which keys to listen for is broken in two independent ways, and both land on keys that are a single symbol. A comma-separated list of keys now refuses every one-symbol entry — @, !, J, g, a bare comma — complaining that the key is not supported, while ctrl-z, f2, alt-a, shift-left and all the named synonyms are still accepted. Separately, when an action is attached to a key, an entry whose key is exactly one symbol long is split in the wrong place, so attaching a sorting toggle to a letter leaves the toggle off and attaching a command to a digit never fires, whereas entries keyed by f1 or ctrl-a still attach. On top of that, the readable name reported for a key that was pressed comes out mangled for essentially every key, and the same mangling shows up in the text substituted for the name of the action currently running when it is pasted into a command line.

Loading entries into it fails from both directions. Drawing them from an external command yields nothing at all: a command that prints two lines produces zero entries, though the finished-reading notification still arrives and a command that does not exist is still reported as finished with nothing read. Pushing them in from memory instead, the two ways of asking how many are loaded disagree — one reports roughly twice the number that went in — and they keep disagreeing after the list is trimmed down to a tail.

Saying which part of each line you care about no longer works when you bound it at both ends. Asking for third through fifth, or minus-third through minus-fifth, or everything up to third, is turned away, while the open-ended third-and-onwards, a bare pair of dots and a lone number still work; the knock-on effect is that command templates and the pulling out of individual fields built on such a span produce the wrong text or drop pieces entirely. Separately, when a template asks for the selections to reach the command through a scratch file on disk, the spot where the filename belongs comes back empty and there is no file to read, even though creating and writing that file did not fail.

Typing a query goes wrong in a whole cluster of ways. With accents treated as their plain equivalents, the whole-string equality test returns the opposite verdict from every other mode: an accented word against its unaccented spelling is reported as unequal, while checking for a prefix, a suffix or a contained piece all agree that it matches. Searching text held as code points rather than bytes finds the wrong offsets whenever three-byte symbols such as CJK, Hangul, Thai or kana are present, because one of the two search paths rebuilds those symbols from too few bytes, and the slower of the two backwards searches reports hits at positions that hold some other symbol entirely. Hunting for a single plain Latin letter inside such text is wrong in three further ways: a case-blind forward search for the letter a behaves unlike the same search for e and misses the uppercase form; a backwards search disregards what was asked about case, so a case-sensitive search for a lowercase letter also returns uppercase hits; and the faster backwards search looks for a code point thirty-two above the letter rather than its uppercase form, so it lands on punctuation-like code points and never on the uppercase letter. Two more surface once text outside that plain range is involved: asking whether an entry's text could be reduced to plain unaccented Latin answers yes for text that plainly cannot — pure Hangul, CJK, Cyrillic or emoji — and yes for Hangul mixed with plain letters too, and the screening step that decides whether an accented or non-Latin query letter may be used to reject entries cheaply now admits letters that some other letter lowercases onto, so a search with such a letter in the query gives a different score and different marked positions than the very same search with the shortcut turned off, and entries that do contain the query are thrown away.

What comes back is then ordered wrongly in three ways. Asking whether one hit sorts ahead of another gives the wrong answer when the two carry identical scores and the same position in the input, including when a hit is asked about against itself. The fast ordering used once there are more than a hundred or so hits no longer agrees with a plain comparison sort: entries come back in a different order, both normally and with the list reversed. And with sorting switched off, when the outcomes of several workers are brought together, fetching the nth entry returns the wrong one at some positions even though the reported total is right.

Typing a second query over the same data no longer reuses any of the first one's work. After a query has been run over a block of entries, storing the outcome under the query text and immediately asking for it back returns nothing, so every keystroke redoes the whole job. When stored per-block information does get consulted, the entries it points at are the opposite ones, so running a query a second time over the same data reports a different number of hits than running it fresh. And the judgement about whether a multi-term query's outcome may be reused at all comes out the wrong way round for several shapes of query — a term next to an alternative, or next to an exclusion — while the short string derived from the query for lookup purposes stays as it was.

Two last oddities turn up no matter what you are doing. On the way out, the cleanup callbacks run in reverse of the order they were registered in, but the earliest-registered one never runs, and asking for the shutdown a second time does not rescue it. And a shared true/false flag reports true no matter what it holds: one created as false reads back true, and storing false into it and reading it again still says true — the number written for true is not the number anything looking at it expects either.

It worked before a set of undocumented edits to the source of fzf. Finding out what is
wrong, and convincing yourself you have fixed it, is part of the task.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "src/actiontype_string.go",
      "function": "enclosing_function_name"
    },
    {
      "file": "src/actiontype_string.go",
      "function": "Type.method_name"
    }
  ]
}
```

`file` is the path of the file relative to the repository root, written exactly as it
appears in the tree. A file inside a directory keeps its directory prefix: the example
above is `src/actiontype_string.go`, not `actiontype_string.go`.

`function` is the function name. A class or receiver prefix, written `Type.name`, is
accepted anywhere and is required when two functions in the same file share a name: the
bare name cannot tell them apart. When an edit sits inside a function nested in another
function, either name is accepted. Name every function one of the undocumented edits is
in, and only those. Where you wrote the fix does not matter: if you restored the behavior
from a caller or from a helper of your own, name the function the edit is in rather than
the one you wrote. If you suspect a function but found no edit in it, leave it out.


Before you edit any code, write your research and your plan to /app/RESEARCH_AND_PLANNING.md. Cover what you learned about the existing code and the constraints that shape the change, then how you intend to carry it out and why, including how you will know it works. Be concrete - the files, names and decisions specific to this codebase, not generalities. Complete the document before you touch any code: it is the record of your up-front investigation and decisions, and it should not be rewritten to match whatever the implementation turns into afterwards. Once it is done, implement the plan.
