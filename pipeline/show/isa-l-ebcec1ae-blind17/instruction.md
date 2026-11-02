# isa-l: locating 17 injected faults without a test suite

The repository has received 17 separate undocumented edits.

This library is used to pack a buffer into fewer bytes and get the original back, to boil a
buffer down to a short value a reader can use to tell it arrived intact, and to spread
stored bytes over several pieces so the original survives losing some of them. All three
now hand back wrong answers for material they used to handle.

Packing a buffer and then unpacking it no longer returns what went in. At the cheapest
setting the result matches until the very end, where bytes near the tail come back wrong,
as if a single byte had been picked up one step out of order. Where more effort is spent
spotting repeated runs and pointing back at earlier copies of them, the restored output
instead diverges in the middle of long repeated stretches and contains bytes that were
never in the input, and material whose repeat sits a long way from its earlier occurrence
comes back with the repeated stretch copied from the wrong place. Other buffers pack into
something that cannot be unpacked at all, reporting corruption instead of returning bytes,
and larger inputs, for which the packer works out its own symbol tables instead of reusing
a fixed set, likewise produce output that is rejected or that restores into garbage.

How the caller drives the work matters as much as the setting. Handing over a whole buffer
in one self-contained call, with the result written into an area the caller supplied, comes
back with a failure status or with an output length that disagrees with the bytes actually
written. Feeding the same material a piece at a time and marking the last piece as the end
never reaches completion: the call returns with the input consumed, the stream unterminated
and the output short. Asking part-way through for whatever has been produced so far leaves
it equally stuck, with no usable prefix handed back and no further progress on later calls.

Going the other way under the same drip feed, handing over only a few bytes of input per
call, returns an error or stops with part of the material missing, and a descriptive field
near the front of the stream that happens to span one of those call boundaries comes back
truncated or mangled. Asking only what the opening description of an enveloped stream says,
when it carries an optional extra field, hands back extra bytes taken from the wrong place
and with the wrong length, and the signal that the caller's area for that field was too
small is raised for the wrong sizes.

Boiling a buffer down to a short value for checking is off too. Among the 32-bit variants,
one goes wrong on essentially any input longer than a single byte, and another returns
values unlike the reference too. Two of the 64-bit variants are wrong as well: the value
handed back for a buffer matches the reference for neither of them, whether the bytes are
passed in one call or in pieces.

Spreading stored bytes over extra pieces so loss can be survived is wrong in several ways.
Computing the pair of extra pieces that protect a set of stored ones yields a second extra
piece that fails verification against the material it was computed from. Preparing the
lookup used to multiply a run of bytes by a single coefficient and then applying it gives
wrong products for some coefficients, so anything written out with those coefficients
cannot be rebuilt afterwards. Computing redundancy for one particular number of
simultaneous outputs leaves those outputs filled with wrong bytes, and recovering lost
material from them fails.

It worked before a set of undocumented edits to the source of isa-l. This checkout has
no test suite.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "/workspace/repo/crc/aarch64/crc_aarch64_dispatcher.c",
      "function": "enclosing_function_name"
    },
    {
      "file": "/workspace/repo/crc/aarch64/crc_aarch64_dispatcher.c",
      "function": "Type.method_name"
    }
  ]
}
```

Each entry is an object with a `file` and a `function`; anything in `causes` that is not
an object counts as a wrong entry. `file` is the absolute path of the file, in the
repository checked out at `/workspace/repo`, written exactly as it appears in the tree.
A file inside a directory keeps its directories: the example above is
`/workspace/repo/crc/aarch64/crc_aarch64_dispatcher.c`, not `crc_aarch64_dispatcher.c`.
The same path relative to the repository root, such as
`crc/aarch64/crc_aarch64_dispatcher.c`, is accepted too. A path outside
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
