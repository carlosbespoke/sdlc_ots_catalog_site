# libsodium: 26 injected one-line faults to diagnose without a test suite

The repository has received 26 separate undocumented edits.

An application calls this library to keep data secret, to prove where data came from, and to turn passwords and arbitrary bytes into keys, and it now gets a great many of those jobs wrong. Nothing about the algorithms changed and nothing about the callers changed. Calls that used to return correct answers now return wrong ones, and several of them stop the program outright.

Proving a message came from you, and checking that proof. A message that is signed and then handed straight back to be checked is reported as not verifying, so the check throws out signatures the library itself has just produced, while byte strings far too short to hold a signature at all are let through into processing rather than being turned away. For many messages the signature bytes produced do not agree with the published vectors for the same key and message, so no other implementation accepts them either.

Working with the mathematical elements those keys are built from. Asking whether a byte string names an element of the prime-order subgroup answers yes for byte strings that name elements lying outside it. Multiplying an element by an all-zero scalar reports success and writes out a result instead of returning the error that signals a degenerate scalar. Mapping an arbitrary byte string onto an element yields elements that disagree with the standard vectors, and both of the two kinds of element that offer this mapping behave that way.

Boiling a message down to a short fingerprint. The small keyed fingerprint whose output is 128 bits returns values unrelated to the published vectors, for messages of any length. Asking for a fingerprint computed with a salt and a personalisation string gives a digest that disagrees with the published vectors, as if the salt bytes had never been handed over, and asking for that same fingerprint with no salt at all crashes. Asking for a keyed fingerprint with a key length of zero gives a digest different from the one the same message gives when no key is supplied. Feeding a message in a single call into any of the three interfaces that soak up input and then let you squeeze out as many bytes as you want, and then squeezing, returns bytes that do not match the published output for that message; when the message is shorter than the amount soaked up at a time the result varies with whatever memory happens to lie past the end of the input buffer, and all three of those interfaces behave the same way.

Keeping a message secret between two parties. One of the combined secrecy-and-authenticity interfaces halts the program on every call that encrypts, even for a short message and short extra authenticated data. Another returns ciphertext and a tag that do not agree with the published vectors and that will not decrypt back to the message they came from. Asking for a detached decryption with no output buffer supplied, so that only the authentication tag is checked, crashes instead of returning the verification result, and it does this both for the form that takes a short nonce and for the form that takes an extended one. Pushing a long run of messages into a continuous encrypted stream gives output that stops agreeing with known-good output once enough of them have gone in, and a known-good stream produced elsewhere can no longer be decrypted past that same point. Decapsulating a post-quantum encapsulation with the secret key belonging to the public key it was made for gives back a shared secret different from the one the encapsulation step produced, so the two sides never agree on a key.

Turning a password into a key, and checking a password later. Checking a password against a stored hash string that is truncated or otherwise not well formed crashes instead of reporting that the password does not match. A stored hash string carrying a version marker other than the one this build writes is accepted and verified rather than turned down. Asking whether a stored hash string ought to be recomputed under a different operations limit and memory limit answers that no recomputation is needed, even when those limits differ from the ones the string records. Deriving a key from a password through the call that takes an operations limit and a memory limit returns bytes that do not match the published vectors for those inputs. Deriving bytes through the call that takes cost, block size and parallelism as explicit numbers returns output matching no published vector even when the password and the salt have the same length, and giving a password and a salt of differing lengths changes the result again in a way the vectors do not predict.

Carrying a network address through a transformation and writing it back out as text. Encrypting an IPv4 address in the mode that is supposed to keep shared leading bits intact returns a result that disagrees with the published vectors and does not keep the leading bits that two such values share. Turning a binary address back into its text form writes long runs of zero groups out in full instead of using the shortened notation, so the string produced is not the standard text form of that address.

And after a handler has been installed to be run when the library catches an improper use of its own interfaces, provoking such a use kills the program without the handler ever being called.

It worked before a set of undocumented edits to the source of libsodium. This checkout has
no test suite.

Restore the behavior described above.

Record the functions that contain those edits in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "/workspace/repo/src/libsodium/crypto_aead/aegis256/aegis256_aesni.c",
      "function": "enclosing_function_name"
    },
    {
      "file": "/workspace/repo/src/libsodium/crypto_aead/aegis256/aegis256_aesni.c",
      "function": "Type.method_name"
    }
  ]
}
```

Each entry is an object with a `file` and a `function`; anything in `causes` that is not
an object counts as a wrong entry. `file` is the absolute path of the file, in the
repository checked out at `/workspace/repo`, written exactly as it appears in the tree.
A file inside a directory keeps its directories: the example above is
`/workspace/repo/src/libsodium/crypto_aead/aegis256/aegis256_aesni.c`, not
`aegis256_aesni.c`. The same path relative to the repository root, such as
`src/libsodium/crypto_aead/aegis256/aegis256_aesni.c`, is accepted too. A path outside
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
