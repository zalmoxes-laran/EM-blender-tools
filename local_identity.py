"""The local identity of EM Tools: an ORCID iD DECLARED in the preferences.

E.D. (1 Oct 2026, decision 17): EM Tools has a local identity, with the same
model as EMStudio — an iD typed in the preferences, «dichiarato, non
verificato» — so that a stamp born in Blender outside a room says who made it
(``by.operator``) instead of naming nobody.

The model, from EMStudio's ``identity.ts`` (measured and reused, not
reinvented):

* the iD is normalised the way people paste it (``https://orcid.org/…``,
  spaces, a lower-case ``x``) down to ``dddd-dddd-dddd-dddX``;
* it is refused when its shape is wrong or its **check digit** fails — the
  last character is a MOD 11-2 (ISO/IEC 7064) over the first fifteen digits.
  A transposed pair of digits passes any shape test and names a REAL OTHER
  PERSON: an identity validated only by its shape is not validated;
* a declared iD is checked by nobody, and the record says so: the signature's
  access mode is ``declared`` (s3Dgraphy dev28 ``editorial.AUTH_MODES``;
  dtcstamp 0.1.3 ``by.operator.auth``).

No ``bpy`` here: the preferences read it, pytest measures it.
"""

from __future__ import annotations

import re
from typing import Dict, Optional

_SHAPE = re.compile(r"^(\d{4})-(\d{4})-(\d{4})-(\d{3}[\dX])$")

#: the problems an iD can have, as EMStudio names them
EMPTY, SHAPE, CHECKSUM = "empty", "shape", "checksum"

#: the access mode a declared identity signs with
DECLARED = "declared"


def normalize_orcid(value: Optional[str]) -> str:
    """Whatever was pasted, down to the 19 characters that matter (or the
    stripped input when it is not 16 digits: then it is not an iD)."""
    raw = re.sub(r"^https?://(www\.)?orcid\.org/", "", str(value or "").strip(), flags=re.I)
    raw = re.sub(r"[\s‐-―]", "-", raw)
    raw = re.sub(r"[^0-9Xx-]", "", raw).upper()
    digits = raw.replace("-", "")
    if len(digits) != 16:
        return raw
    return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"


def is_valid_orcid(value: Optional[str]) -> bool:
    """Shape AND check digit (MOD 11-2) — ``identity.ts isValidOrcid``."""
    orcid = normalize_orcid(value)
    if not _SHAPE.match(orcid):
        return False
    digits = orcid.replace("-", "")
    total = 0
    for ch in digits[:15]:
        total = (total + int(ch)) * 2
    result = (12 - total % 11) % 11
    expected = "X" if result == 10 else str(result)
    return digits[15] == expected


def orcid_problem(value: Optional[str]) -> Optional[str]:
    """``empty`` · ``shape`` · ``checksum`` · None (a good iD)."""
    orcid = normalize_orcid(value)
    if not orcid:
        return EMPTY
    if not _SHAPE.match(orcid):
        return SHAPE
    return None if is_valid_orcid(orcid) else CHECKSUM


PROBLEM_TEXT = {
    EMPTY: "",
    SHAPE: "not an ORCID iD: 16 digits, the last may be X (0000-0002-1825-0097)",
    CHECKSUM: "the check digit does not match: a digit is wrong or two are swapped, "
              "and this iD would name somebody else",
}


def declared_operator(orcid: Optional[str], name: Optional[str] = None
                      ) -> Optional[Dict[str, object]]:
    """``by.operator`` for a stamp made under the local identity, or None.

    ``{"id": "https://orcid.org/<iD>", "label": <name>, "auth": {"mode":
    "declared"}}`` — the form dtcstamp 0.1.3 admits (``label`` a courtesy,
    omitted when empty; ``auth`` says how strong the name is). An iD with a
    problem gives None: a stamp is not signed with an identifier that belongs
    to somebody else or to nobody."""
    if orcid_problem(orcid) is not None:
        return None
    operator: Dict[str, object] = {"id": f"https://orcid.org/{normalize_orcid(orcid)}"}
    label = str(name or "").strip()
    if label:
        operator["label"] = label
    operator["auth"] = {"mode": DECLARED}
    return operator
