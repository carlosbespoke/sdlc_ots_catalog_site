# libexpat: diagnosing four real defects without a test suite

I set a maximum tolerated amplification factor and an activation threshold on a parser, then created a child parser for external entity content and handed that child a lone parameter entity declaration longer than the threshold I had chosen. Parsing came back successful every time; no limit breach was ever reported, however far below the length of the declaration I pushed the threshold.

I registered a comment handler that records the comment text and then asks the parser to stop, parsed a document whose element content references an entity that in turn expands to two further levels of nested entities, and looped calling resume until parsing finished. The recorded comments stopped partway: the text following the innermost entity reference, including the trailing comments of the two enclosing entities and the material after them, never arrived.

After feeding the parser one short chunk in a non-final call, I prepared to feed it a next chunk whose length is close to the largest value a signed int can hold. The parser agreed to take it and gave me room for it, instead of refusing with an out-of-memory indication, although a request that large cannot be met.

I fed the parser a document whose declaration carries a version pseudo-attribute with nothing at all between the quotes. The parser took it without complaint and carried on to the root element, instead of stopping and reporting an error about the declaration.

There are four separate defects in the source of libexpat behind the behaviour above,
each in a different function. This checkout has no test suite.

Fix the behaviour described above.

Record the functions that contain those defects in `/app/rca.json`, one entry each:

```json
{
  "causes": [
    {
      "file": "expat/lib/xmlrole.c",
      "function": "enclosing_function_name"
    }
  ]
}
```

`file` is the path of the file relative to the repository root, written exactly as it
appears in the tree. A file inside a directory keeps its directory prefix: the example
above is `expat/lib/xmlrole.c`, not `xmlrole.c`. An absolute path, or a path with a `..`
segment, does not name a file in the repository and counts as a wrong entry.

`function` is the name of the C function whose code is wrong: the function a fix of that
defect belongs in. A function defined through a macro may be named by the name the macro
expands to or by the name passed to the macro. Name every function one of the defects is
in, and only those, once each: a second entry for a function another entry already names,
or an entry for a function that holds none of the defects, counts as a wrong entry. Where
you wrote your fix does not matter: if you worked around a defect from a caller or from a
helper of your own, name the function that holds the wrong code rather than the one you
changed. If you suspect a function but found nothing wrong in it, leave it out.
