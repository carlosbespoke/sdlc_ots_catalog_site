# bdwgc: repairing a garbage collector without a test suite

The repository has received 27 separate undocumented edits.

This project is a library that hands out storage to a running program and later takes back whatever that program can no longer reach, along with a facility for building up long pieces of text out of smaller fragments. Both sides of it now misbehave. Simple programs abort before they do any work, longer-running ones crash or quietly hand the same storage to two owners at once, and several ordinary calls refuse requests they used to serve.

The trouble starts with the simplest thing a program can ask for. Requesting one small block and doing nothing else aborts inside that call, with the library reporting that one of its own internal consistency checks failed. Building it in the mode that keeps extra bookkeeping beside every object, and allocating through the entry points that go with that mode, aborts too, on a different internal check, this one raised for ordinary small requests. Asking for a block of zero bytes aborts rather than coming back with memory. Handing an object back explicitly and then asking for a fresh block of the same size yields storage that still holds the bytes written into the object just given up, rather than zeros. Passing a null pointer to the call that gives an object back crashes instead of returning without doing anything. Growing an object that was allocated with a description of where its pointer fields lie, by asking for a bigger block through the call that resizes, yields storage whose description no longer spans the new size, so pointers written beyond the old end are dropped and their targets handed out again. Asking for an array of typed elements by giving a count and an element size yields storage whose pointer fields go untraced, so objects reachable only from that array are taken away while still in use. Composing a description for an array out of the description of its element type and allocating with the result loses referenced objects in the same way. The query that reports both which flavour of allocation an object came from and how large it is either crashes or leaves the size it was asked to fill untouched.

Programs that use more than one thread run into failures of their own. They abort the moment the first collection runs, complaining that an internal lock could not be given up. When threads are let go again at the end of a collection, the library complains that the number it started again differs from the number it halted, and the run hangs or dies there. A thread created through the library's own creation wrapper is handed the wrong argument: the pointer its start routine receives is not the one supplied at creation. A program that pauses one of its threads through the public call for that, and then asks whether that thread is currently paused, is told it is not.

Letting a program run long enough for storage to be taken back brings more failures. Programs that allocate enough to trigger a collection die with a segmentation fault partway through it. Workloads that keep a large number of objects reachable across repeated collections either die inside a collection or come back holding references to storage that has already been handed out to a later request. Switching on the mode that collects in small steps and then building a large linked structure crashes soon after the structure grows. Programs that attach a cleanup callback to their objects crash once collections begin. Pointers held only in the global variables of libraries loaded at run time are not treated as roots, so the objects they refer to are taken away and their storage reissued while those globals still point at them.

The calls a program makes to check itself behave wrongly too. The checked operation that confirms two pointers lie within one object prints a complaint and refuses pairs that do lie within one object. The check applied to a pointer that is being moved along by an offset crashes when the pointer does not refer to storage this library handed out at all. Objects allocated with a cleanup callback attached come back with the first word of the caller's own data overwritten, so values stored in them read back as something else, and when such an object is finally swept the callback is given the wrong field to work from, so the tally of cleanups does not match the number of objects allocated. The setup call for the allocation scheme that takes a caller-supplied tracing routine aborts the program, rejecting the routine it was handed.

Text assembled from joined fragments is mishandled as well. Searching such a value for a single character returns the position of the last occurrence rather than the first. Searching it for a run of several characters reports no match for runs that are present. Stepping through a deeply joined value one position at a time yields characters taken from the wrong places. Formatted printing into one of these values mishandles a field width written with more than one digit, padding the output to a width unrelated to the number given.

It worked before a set of undocumented edits to the source of bdwgc. This checkout has
no test suite.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "/workspace/repo/extra/msvc_dbg.c",
      "function": "enclosing_function_name"
    },
    {
      "file": "/workspace/repo/extra/msvc_dbg.c",
      "function": "Type.method_name"
    }
  ]
}
```

Each entry is an object with a `file` and a `function`; anything in `causes` that is not
an object counts as a wrong entry. `file` is the absolute path of the file, in the
repository checked out at `/workspace/repo`, written exactly as it appears in the tree.
A file inside a directory keeps its directories: the example above is
`/workspace/repo/extra/msvc_dbg.c`, not `msvc_dbg.c`. The same path relative to the
repository root, such as `extra/msvc_dbg.c`, is accepted too. A path outside
`/workspace/repo`, or a path with a `..` segment, does not name a file in the repository
and counts as a wrong entry.

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
