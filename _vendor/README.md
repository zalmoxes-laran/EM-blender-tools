# _vendor — code carried as source

| file | from | commit | sha256 |
|---|---|---|---|
| `dtcstamp.py` | `ExtendedMatrix/dtcstamp` | `c05bb1f` (*Align canonical .3tz with NFC names*) | `fe871cfc00b000bca4e856f470910ee7f99bb5e892b430c75acf3c5384d012f9` |

**Why vendored and not a wheel.** EMtools needs `dtcstamp.content_digest` and
`members_digest` (the identity of a tree, the same for a folder and its `.3tz`;
the identity of a resource of several files). Measured on 1 Oct 2026: the
dtcstamp on PyPI is **0.1.1**, which does not have them, and the s3dgraphy dev25
wheel does not carry dtcstamp. A wheel built here from the checkout would
declare 0.1.1 while holding other code — the same lie `rebundle_s3dgraphy.py`
exists to prevent. A copy with its commit and its digest says exactly what it is.

`resource_digest.py` prefers an installed `dtcstamp` that has the two
functions, and falls back to this copy. `tests/test_resource_digest.py`
reproduces conformance cases 20 and 23 of dtcstamp on whichever is used, and
compares this file with the sibling checkout when there is one.

**Never edit it here.** Update it by copying the file from a newer dtcstamp
commit and rewriting the row above; drop it when a dtcstamp with
`content_digest` is on PyPI and bundled as a wheel.
