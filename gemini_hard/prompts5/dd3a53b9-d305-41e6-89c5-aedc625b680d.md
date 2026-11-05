# Diagnosing 30 injected faults in capstone without a test suite

The repository has received 30 separate undocumented edits.

Software that hands this project a buffer of machine code, one instruction at a time, gets back a printed line and a structured description of the operands, and both of those now come out wrong in a great many places. The bytes being fed in have not changed and neither have the callers.

Walking a buffer instruction by instruction, some byte sequences no longer come back as an instruction at all. A vector shift-left-long-by-immediate encoding is refused outright and its bytes are reported as undecodable. The bitwise-and arithmetic operation of one small register machine yields nothing. An encoding occupying six bytes resolves to something unrelated to the bytes handed in, or fails to resolve. The first of the push-an-immediate opcodes of one stack machine arrives without its immediate and reports a length one byte short, so the following instruction is taken from the middle of it.

Elsewhere an instruction does come back, but not the one the bytes denote. A compare-and-branch encoding whose two source register fields hold the same number comes back as the two-register comparison mnemonic carrying an extra register operand, in place of the single-register form. A short-form encoding whose one register serves as both source and destination comes back with that register operand missing entirely. Three-operand encodings come back with wrong register numbers. An instruction written with the four-byte vector encoding introducer and its operand-width bit set comes back as the narrow variant, with wrong operand width and wrong register selection. An addressing form pairing a zero-page address with a branch displacement comes back with no operands whatsoever. A load or store belonging to an auxiliary processing unit reports a register mask where a direct data register access belongs. A single-operand encoding that should render as a no-operation prints a mnemonic and an operand instead, while encodings that should keep their operands render as a no-operation and lose one. Register operands appear under names belonging to other registers, or with no name at all. An operand listing the tiles of a matrix unit states the wrong number of tiles. A four-element structure load to one lane with its alignment bit set shows its memory operand without the alignment.

The text of the line is damaged in ways of its own. The division between the mnemonic and the operand text is taken at the wrong space, so part of the operand text ends up inside the mnemonic. A write to the status register prints without the field-selection letters that should follow the underscore, while the case that selects no fields prints a stray underscore. A vector compare using the always-true unsigned-signalling predicate prints without its predicate suffix. A rotate-and-mask instruction prints its simplified form with a wrong immediate. An instruction that folds its second operand into the mnemonic prints that operand a second time afterwards. A branch carrying a modifier prints the wrong modifier text.

The numbers attached to an instruction are wrong too. A compressed load-upper-immediate whose immediate stands for a negative value reads as a large positive number. A four-byte immediate with its top bit set prints as a large positive quantity rather than the negative value it denotes. A multi-byte variable-length integer embedded in an instruction comes out wrong once it spans more than one byte, so a branch table's entry count is far too small and the instruction length with it. Targets worked out for a 32-bit setting print as enormous 64-bit addresses instead of wrapping into 32 bits. An instruction addressing memory by an absolute offset prints a wrong number in place of that offset. An operand holding a floating point constant in the widest format prints a number of completely wrong magnitude.

Leaning on the structured description handed back alongside each instruction is no better. Asking whether a recorded operand holds a literal number answers yes exactly when it does not, so the printed text and the recorded operand kinds both describe the wrong thing over a broad range of instructions. Detail derived from a pair of describing values attaches them in reverse order, giving operand entries built from the wrong one. Memory-referencing instructions report base and displacement as separate plain operands rather than as one memory operand. Setting an option on an open handle comes back with a failure code instead of success.

It worked before a set of undocumented edits to the source of capstone. This checkout has
no test suite.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "/workspace/repo/arch/AArch64/AArch64BaseInfo.c",
      "function": "enclosing_function_name"
    },
    {
      "file": "/workspace/repo/arch/AArch64/AArch64BaseInfo.c",
      "function": "Type.method_name"
    }
  ]
}
```

Each entry is an object with a `file` and a `function`; anything in `causes` that is not
an object counts as a wrong entry. `file` is the absolute path of the file, in the
repository checked out at `/workspace/repo`, written exactly as it appears in the tree.
A file inside a directory keeps its directories: the example above is
`/workspace/repo/arch/AArch64/AArch64BaseInfo.c`, not `AArch64BaseInfo.c`. The same path
relative to the repository root, such as `arch/AArch64/AArch64BaseInfo.c`, is accepted
too. A path outside `/workspace/repo`, or a path with a `..` segment, does not name a
file in the repository and counts as a wrong entry.

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
