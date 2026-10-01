"""The stamp: the immutable record of one step of a chain.

A stamp attests **one step**. An agent, with a process and its parameters,
consumes one or more inputs and produces **one** artifact; the stamp is the
record of that, written to stand on its own. The **chain** is the whole; a
**step** is the single transformation; a **stamp** is the file that records it.

**This is not a distributed ledger.** No consensus, no global ordering, no
network, no tokens, nothing to mine and nobody to agree with. «Chain» plus
«hash» plus «immutable» reads *blockchain* and the question will arrive every
time, so here is the answer first: a stamp is a JSON file somebody writes next
to a file they made, and a chain is what you get when you follow the digests
backwards. Two people can write contradicting stamps for the same artifact and
**both are kept**, because a contradiction is a discovery and this library has
no opinion about who is right.

## Why one file

Whoever writes an add-on for Blender, or a script for Metashape, will not add a
dependency on a large library to write two kilobytes of JSON. So this is **one
module, standard library only**: copy it next to your code and import it. That
constraint is the design, not an accident, and there is a test that copies this
file into an empty directory and runs the conformance corpus against it.

## What is here, and what is deliberately not

Here: the **format** (read, write, validate), the **identity** of an artifact
and how strong it is, the **hints**, **comparing** two stamps for the same
artifact, and **walking** a chain backwards.

Not here: anything that knows where files live. The walk takes a **resolver**
from the caller — the file system for a Blender plugin, an object store for a
server, a graph for s3Dgraphy, an index for a catalogue — and this module knows
none of the four. Also not here: building a stamp *from a graph*, which needs a
graph and therefore belongs to whoever has one.

## Reading rule that matters more than it looks

**Keep the fields you do not understand.** An implementation that drops the
unknown destroys provenance on the first round trip, silently, and the loss is
discovered years later by somebody who needed exactly that field. Everything
here copies whole objects rather than rebuilding them from known keys.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
import re
import struct
import unicodedata
import zipfile
import zlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (Any, Callable, Dict, Iterable, List, Optional, Sequence,
                    Tuple, Union)

#: The name of this package, in **one place**. It appears in `pyproject.toml`
#: and in this line, and nowhere else — never inside a field of the format, so
#: renaming it costs a `sed` over a small repository and changes no file anyone
#: has already written.
PACKAGE = "dtcstamp"

__version__ = "0.1.1"

#: The stamp format version. A record that declares another one is not broken:
#: it is from another epoch, and is refused with that word.
STAMP_VERSION = 1

#: The hints format version, separate on purpose: two files with two lives —
#: one never changes, the other changes all the time.
HINTS_VERSION = 1

STAMP_SUFFIX = ".stamp.json"
HINTS_SUFFIX = ".hints.json"


# ═════════════════════════════════════════════════════════════════════════════
# IDENTITY — and how strong it is, which is a separate question
# ═════════════════════════════════════════════════════════════════════════════
#
# A chain is strong at the published end and soft at the authoring end. A glTF
# file in a store has canonical bytes and its `sha256:` **proves it is the one**;
# a datablock inside a `.blend` has no canonical bytes — the file changes for
# reasons that have nothing to do with that mesh — and what can be computed is a
# structural fingerprint, enough to **notice that it changed**, not to verify
# that it is the same one.
#
# The format says so with the prefix. But a consumer deciding by looking inside
# the string — `digest.startswith(...)` in five places — is five places where the
# rule can drift, and one of those five will eventually treat a structural
# fingerprint as proof. So: one function.

#: Fingerprints that **prove**: there is a canonical byte sequence and anybody
#: can redo the arithmetic and get the same value.
VERIFIABLE_SCHEMES = ("sha256",)

#: Fingerprints that **compare**: they say whether it changed, not that it is the
#: same one. The `1` in `emstruct1` is in the name because the day a different
#: one is computed that one is `emstruct2`, and an old stamp goes on saying which
#: rule its own was taken by.
COMPARABLE_SCHEMES = ("emstruct1",)

VERIFIABLE = "verifiable"
COMPARABLE = "comparable"
UNKNOWN = "unknown"


def split_identity(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """``("sha256", "6e4a…")`` — the scheme and the value, or ``(None, …)``.

    Separate from :func:`identity_strength` because whoever writes a stamp has to
    be able to put the two halves back together, and recomposing them with a
    hand-written ``:`` in two different places is how one of the two eventually
    loses its prefix.
    """
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if ":" not in text:
        return None, text
    scheme, _, rest = text.partition(":")
    scheme = scheme.strip().lower()
    rest = rest.strip()
    if not scheme or not rest:
        # `:abc` or `abc:` are not a scheme and a value: they are a malformed
        # string, and reading half of it would be worse than not reading it.
        return None, text
    return scheme, rest


def identity_strength(value: Any) -> Optional[str]:
    """``verifiable``, ``comparable``, ``unknown`` — or ``None`` if there is none.

    Three answers and not two, and the third is the important one. Bare digests
    exist in the real corpus: sixty-four hex characters and nothing else. Calling
    that ``verifiable`` would be **guessing the algorithm** and then asserting it.

    An absence is not ``unknown``: it is ``None``. There is no identity whose
    strength could be measured, and returning a word where there is no string
    would make a reader believe something had been said.
    """
    scheme, rest = split_identity(value)
    if rest is None:
        return None
    if scheme in VERIFIABLE_SCHEMES:
        return VERIFIABLE
    if scheme in COMPARABLE_SCHEMES:
        return COMPARABLE
    return UNKNOWN


def is_verifiable(value: Any) -> bool:
    """Whether anybody can **redo the arithmetic** and prove these are the bytes.

    False for an absence and false for an ``unknown``: the question has one safe
    answer, and without it the answer is no.
    """
    return identity_strength(value) == VERIFIABLE


def is_comparable(value: Any) -> bool:
    """Whether it is enough to notice a change — verifiable included.

    **A verifiable one is also comparable**, and that line is why this function
    exists instead of being ``strength == "comparable"`` written by the caller:
    somebody asking «can I at least notice an edit?» must get ``True`` from a
    sha256 too, and the opposite question is :func:`is_verifiable`.
    """
    return identity_strength(value) in (VERIFIABLE, COMPARABLE)


def describe_identity(value: Any) -> Dict[str, Any]:
    """What an interface has the right to say, in a dictionary.

    ``claim`` is the sentence, and it is not a courtesy: the whole point is that
    a panel must not write «verified» next to a structural fingerprint, and
    handing it the right words works better than hoping it will derive them.
    """
    scheme, rest = split_identity(value)
    strength = identity_strength(value)
    claim = {
        VERIFIABLE: "these are those bytes, and anyone can check",
        COMPARABLE: "this tells you if it changed, not that it is the same one",
        UNKNOWN: "an identity with no stated algorithm: not checkable",
        None: "no identity recorded",
    }[strength]
    return {"scheme": scheme, "value": rest, "strength": strength,
            "verifiable": strength == VERIFIABLE, "claim": claim}


# ═════════════════════════════════════════════════════════════════════════════
# THE STAMP — validate, read, write
# ═════════════════════════════════════════════════════════════════════════════

class BadStamp(ValueError):
    """This is not readable as a stamp."""


def validate_stamp(stamp: Any) -> Dict[str, Any]:
    """The minimum for it to be a stamp, and the sentences for when it is not.

    The **version** and the **identity of the output** are checked, and nothing
    else: a validator that demanded ``how`` would refuse the empty step, which is
    half of the real world.

    Returns the stamp itself, unchanged — **not a copy rebuilt from known keys**.
    Whatever it carries that this version does not understand travels on.
    """
    if not isinstance(stamp, dict):
        raise BadStamp(f"a stamp is a JSON object, got {type(stamp).__name__}")
    version = stamp.get("stamp")
    if version is None:
        raise BadStamp(
            "no `stamp` version key: this may be an em.json fragment, which is a "
            "different species — a stamp is a record and not a document to merge, "
            "edit and version")
    if version != STAMP_VERSION:
        raise BadStamp(
            f"stamp version {version!r}: this build reads version "
            f"{STAMP_VERSION}")
    itself = stamp.get("self")
    if not isinstance(itself, dict) or not str(itself.get("resource_id") or "").strip():
        raise BadStamp(
            "a stamp with no `self.resource_id` names no artifact: it is the "
            "output that gives the record its identity")
    return stamp


def clean_stamp(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """The stamp **without the notes**, which is what leaves.

    Notes are for whoever emitted it. A file leaving the perimeter must not carry
    the doubts of its writer disguised as content. Keys are dropped only when
    they start with ``_``: everything else survives, including what this version
    does not understand.
    """
    return {k: v for k, v in stamp.items() if not str(k).startswith("_")}


def stamp_filename(stamp: Dict[str, Any], *, asset: Optional[str] = None) -> str:
    """``<asset>.stamp.json``.

    The asset's name when there is one, otherwise the resource id: never
    ``em.json`` (a different species — it would invite merging, editing and
    versioning a record) and never ``dtc.json`` (it would promise a chain and
    deliver one link).
    """
    base = str(asset or (stamp.get("self") or {}).get("resource_id") or "stamp")
    return _safe_name(base) + STAMP_SUFFIX


def stamp_identity(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """How strong this stamp's identity is — see :func:`describe_identity`.

    Here, rather than left to the reader, because it is the question an interface
    has to ask **before** writing «verified» next to a row.
    """
    return describe_identity((stamp.get("self") or {}).get("digest"))


def is_verifiable_stamp(stamp: Dict[str, Any]) -> bool:
    return is_verifiable((stamp.get("self") or {}).get("digest"))


def declared_origin(stamp: Dict[str, Any]) -> bool:
    """Whether ``from: []`` means «born here» or «I do not know how».

    The two are written the same way and mean opposite things, and the format
    warns about exactly this: an empty parent list **with** a ``how`` that signs
    it is a complete declaration, **without** one it says nothing was declared.
    Asked here so that no caller has to remember the rule.
    """
    parents = stamp.get("from")
    if parents:
        return False
    return bool(stamp.get("how"))


# ── the title and the description — a courtesy, like every label ─────────────
#
# Added 04-10-2026 (E.D., 29-09): the receipt a shelf keeps for a stamped file
# shows a title and a description, and the stamp had neither — every reader
# fell back to the resource id or the file name. Both OPTIONAL, both in `self`
# (they are about the artifact), and both a courtesy for a human, never
# identity: two stamps that name the same bytes differently have not
# contradicted each other about where the bytes came from, so neither is part
# of :func:`substance`. The title is spelled `label`, the word `from[]` already
# uses, so a child copies its parent's `self.label` into its own `from[].label`
# without translating it. A stamp without them is exactly as valid as before.

#: A description is SHORT: a line or two for a list or a receipt, not the
#: documentation of the artifact (that is the graph's). A reader may shorten a
#: longer one for display; none refuses it — refusing would lose a record.
DESCRIPTION_HINT_CHARS = 280


def _own_text(value: Any, resource_id: str) -> Optional[str]:
    """A label worth showing: a non-empty string that does not merely repeat
    the id (the rule of every label in the format)."""
    if not isinstance(value, str):
        return None
    text = value.strip()
    if not text:
        return None
    rid = str(resource_id or "")
    tail = rid.rsplit(":", 1)[-1].rsplit("/", 1)[-1]
    if text in (rid, tail):
        return None
    return text


def stamp_title(stamp: Dict[str, Any]) -> Optional[str]:
    """``self.label``, when it says something the id does not; else None."""
    itself = stamp.get("self") or {}
    return _own_text(itself.get("label"), itself.get("resource_id"))


def stamp_description(stamp: Dict[str, Any]) -> Optional[str]:
    """``self.description``, when there is one; else None. Never shortened here:
    :data:`DESCRIPTION_HINT_CHARS` is advice for writers and displays."""
    value = (stamp.get("self") or {}).get("description")
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def receipt(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """What a shelf keeps for a stamped file: the stamp's identity and the
    words a person reads, **as a copy**.

    ``{id, checksum, stamp, parents, title, description}``: ``id`` is
    ``self.resource_id``; ``checksum`` is ``self.digest`` (the shelf's word for
    it); ``stamp`` is the format version the record was written in; ``parents``
    lists ``from`` by identity only (``resource_id``, and ``digest`` / ``kind``
    when present — never the label, which is the parent's own courtesy);
    ``title`` / ``description`` are copied from ``self`` and absent when the
    stamp has none. A copy and not a reference: the receipt outlives the file
    beside it, and the stamp — being immutable — cannot drift from it.
    """
    validate_stamp(stamp)
    itself = stamp.get("self") or {}
    out: Dict[str, Any] = {"id": str(itself.get("resource_id"))}
    if itself.get("digest"):
        out["checksum"] = str(itself["digest"])
    out["stamp"] = stamp.get("stamp")
    parents = []
    for parent in stamp.get("from") or []:
        if not isinstance(parent, dict):
            continue
        entry = {k: parent[k] for k in ("resource_id", "digest", "kind")
                 if parent.get(k)}
        if entry:
            parents.append(entry)
    out["parents"] = parents
    title = stamp_title(stamp)
    if title:
        out["title"] = title
    description = stamp_description(stamp)
    if description:
        out["description"] = description
    return out


# ── the filesystem, kept to three functions on purpose ───────────────────────
#
# Everything above is pure: given a dictionary it answers. These three are the
# only ones that touch a disk, and they are separate so the rest can be tested
# without one — and so a caller whose bytes come from an object store or a
# database never goes near them.

def read_stamp(path: str) -> Dict[str, Any]:
    """Read ``<asset>.stamp.json`` from a path and validate it."""
    with open(path, "r", encoding="utf-8") as handle:
        return validate_stamp(json.load(handle))


def parse_stamp(raw: Union[str, bytes, bytearray]) -> Dict[str, Any]:
    """The same, from bytes somebody else fetched — a store, a socket, a row.

    Exists so that a caller with the bytes in hand does not have to write them to
    a temporary file to use this library, which is what an object-store client
    would otherwise do.
    """
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return validate_stamp(json.loads(raw))


def write_stamp(stamp: Dict[str, Any], path: str) -> str:
    """Write the stamp to disk.

    ``indent=1`` and ``ensure_ascii=False``: **the reader of last resort is a
    human with a text editor, thirty years from now**, and that is also why it is
    not written compact.
    """
    return _write_json(clean_stamp(stamp), path)


def _safe_name(base: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(base))


def _write_json(payload: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def now_iso() -> str:
    """The current instant, UTC, second precision, ISO-8601 with a ``Z``.

    Second precision on purpose: these instants order observations, and
    microseconds would only add noise to every diff.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z")


# ═════════════════════════════════════════════════════════════════════════════
# COMPARING — two stamps for the same artifact, and never a winner
# ═════════════════════════════════════════════════════════════════════════════
#
# Two stamps for the same output digest that contradict each other in substance —
# different parents, a different process — **are not an error, they are a
# discovery**, and they are made to surface. Two that differ only in the instant
# are the same fact recorded twice, and deduplicate.
#
# Nothing here chooses. Choosing is a decision somebody makes with a reason,
# and a library that quietly picked one would make that decision invisible.

@dataclass
class Disagreement:
    """One point where two stamps do not agree. **Without a winner.**"""

    path: str
    mine: Any
    theirs: Any

    def as_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "mine": self.mine, "theirs": self.theirs}


def substance(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """The facts of the stamp, reduced to a comparable shape.

    Lists with no meaningful order — the parents, the software — become
    **canonically sorted sets**: a tileset coming out of N meshes is not a
    different fact because the meshes are listed in another order, and calling
    that a disagreement would be noise.
    """
    itself = dict(stamp.get("self") or {})
    how = dict(stamp.get("how") or {})
    by = dict(stamp.get("by") or {})
    declared = dict(stamp.get("declared") or {})

    out: Dict[str, Any] = {}
    out["self.digest"] = itself.get("digest")
    out["self.digest_covers"] = itself.get("digest_covers")
    out["self.media_type"] = itself.get("media_type")
    out["self.format"] = itself.get("format")
    out["self.packaging"] = itself.get("packaging")
    out["self.tier"] = itself.get("tier")
    out["self.measures"] = itself.get("measures")
    # the identity of the CONTENT of a tree: two stamps for the same bytes that
    # name two contents contradict each other. `computed_by` and `files` are
    # not substance — the digest already says everything they could.
    out["self.content_digest"] = (itself.get("content_digest") or {}).get("digest") \
        if isinstance(itself.get("content_digest"), dict) else None
    # NOT `self.label` nor `self.description`: a title is a courtesy, and two
    # people naming the same bytes differently have not disagreed about them.

    # The parents by identity, never by label: a `label` is a courtesy.
    parents = stamp.get("from")
    if isinstance(parents, list):
        out["from"] = sorted(
            _parent_key(p) for p in parents if isinstance(p, dict))
    else:
        out["from"] = None

    out["how.process_id"] = how.get("process_id")
    out["how.technique"] = how.get("technique")
    out["how.dtc_kind"] = how.get("dtc_kind")
    out["how.parameters"] = how.get("parameters")
    out["how.acquisition"] = how.get("acquisition")
    software = how.get("software")
    out["how.software"] = (sorted(_canonical(s) for s in software)
                           if isinstance(software, list) else None)

    operator = by.get("operator")
    out["by.operator"] = _canonical(operator) if operator else None

    out["declared.license"] = declared.get("license")
    out["declared.embargo_until"] = declared.get("embargo_until")
    return out


def _parent_key(parent: Dict[str, Any]) -> str:
    return "|".join([str(parent.get("resource_id") or ""),
                     str(parent.get("digest") or ""),
                     str(parent.get("kind") or "")])


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def compare_stamps(mine: Dict[str, Any], theirs: Dict[str, Any]
                   ) -> List[Disagreement]:
    """The points where two stamps about the same artifact do not agree.

    **Silence is not a disagreement**: both have to speak. The one exception is
    ``from`` when a ``how`` signs it — there the empty list IS a declaration
    («born here») and saying nothing is a different thing.
    """
    a, b = substance(mine), substance(theirs)
    mine_claims_origin = bool(mine.get("how"))
    theirs_claims_origin = bool(theirs.get("how"))
    out: List[Disagreement] = []
    for path in a:
        left, right = a.get(path), b.get(path)
        if path == "from":
            # an empty list speaks only when a `how` signs it
            left_speaks = left is not None and (left or mine_claims_origin)
            right_speaks = right is not None and (right or theirs_claims_origin)
            if not (left_speaks and right_speaks):
                continue
        elif left in (None, "", {}, []) or right in (None, "", {}, []):
            continue
        if left != right:
            out.append(Disagreement(path=path, mine=left, theirs=right))
    return out


def stamps_agree(mine: Dict[str, Any], theirs: Dict[str, Any]) -> bool:
    """Whether the two say the same thing about the same artifact.

    Differing only in ``by.at`` is not a disagreement and never reaches here:
    the instant is not part of :func:`substance`, because the same fact recorded
    twice at two moments is one fact.
    """
    return not compare_stamps(mine, theirs)


# ═════════════════════════════════════════════════════════════════════════════
# THE WALK — one rung at a time, and it says where it could not get to
# ═════════════════════════════════════════════════════════════════════════════
#
# **This library does not know where things are.** It knows how to walk: given a
# stamp and a function «give me the stamp (or the bytes) for this digest», it
# goes back one rung at a time and **stops saying where it did not arrive** —
# «there was a parent with this id and this digest, and I do not have it» is a
# RESULT, not an error.
#
# The caller supplies the resolver: the file system for a Blender plugin, an
# object store for a server, a graph for s3Dgraphy, an index for a catalogue.
# None of the four is in here, and a test asserts it by reading the source of
# these functions.

#: What the caller passes: given a parent's digest, return its stamp (a dict), or
#: the bytes/text of its `.stamp.json`, or ``None`` for «I do not have it».
Resolver = Callable[[str], Union[None, Dict[str, Any], str, bytes]]

#: Why a rung is where the walk stopped. Each one is a different fact, and a
#: single «missing» would have flattened four different situations into one.
NOT_RESOLVED = "not resolved"
NOT_A_FILE = "not a file"
ALREADY_WALKED = "already walked"
CEILING = "ceiling reached"
UNREADABLE = "unreadable"


@dataclass
class Rung:
    """One rung of the ascent: a parent, and whether it was reached."""

    resource_id: Optional[str] = None
    digest: Optional[str] = None
    #: ``"acquisition"`` when the input is a campaign rather than a file
    kind: Optional[str] = None
    label: Optional[str] = None
    #: how many links away from the artifact the walk started at
    depth: int = 1
    stamp: Optional[Dict[str, Any]] = None
    reached: bool = False
    #: when it was not reached, WHICH of the reasons above
    why: Optional[str] = None
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        out = {"resource_id": self.resource_id, "digest": self.digest,
               "depth": self.depth, "reached": self.reached}
        for key in ("kind", "label", "why", "detail"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


@dataclass
class Walk:
    """What the ascent found, and what it did not.

    ``unreached`` is not an error list: it is the edge of what this caller can
    see from where it is standing. The same walk run on a machine that holds the
    archive reaches further, and the difference between the two is exactly the
    useful information.
    """

    root: Dict[str, Any] = field(default_factory=dict)
    rungs: List[Rung] = field(default_factory=list)
    #: true when the ceiling stopped the walk rather than the data
    truncated: bool = False

    @property
    def reached(self) -> List[Rung]:
        return [r for r in self.rungs if r.reached]

    @property
    def unreached(self) -> List[Rung]:
        return [r for r in self.rungs if not r.reached]

    @property
    def depth(self) -> int:
        return max((r.depth for r in self.rungs), default=0)

    def as_dict(self) -> Dict[str, Any]:
        return {"root": (self.root.get("self") or {}).get("digest"),
                "truncated": self.truncated,
                "rungs": [r.as_dict() for r in self.rungs]}


def walk_chain(stamp: Dict[str, Any], resolve: Resolver, *,
               max_rungs: int = 512) -> Walk:
    """Walk backwards from one stamp, one rung at a time.

    ``resolve(digest)`` may return a stamp, the bytes or text of one, or ``None``
    for «I do not have it». Returning ``None`` is an ordinary answer and the walk
    records it as a rung that was not reached.

    **It terminates on a cycle.** Two stamps citing each other must not spin
    forever — a thing that should not exist in reality, which is exactly why it
    is tested. Each digest is walked once; a second sighting is a rung with
    ``why=ALREADY_WALKED``. ``max_rungs`` is the second net, for a chain that is
    long rather than circular, and when it bites the walk says ``truncated``
    instead of pretending it finished.
    """
    walk = Walk(root=stamp)
    root_digest = (stamp.get("self") or {}).get("digest")
    seen = {root_digest} if root_digest else set()
    # the frontier, as (stamp-to-expand, depth of its parents)
    frontier: List[Tuple[Dict[str, Any], int]] = [(stamp, 1)]

    while frontier:
        current, depth = frontier.pop(0)
        for parent in current.get("from") or []:
            if not isinstance(parent, dict):
                continue
            rung = Rung(resource_id=_text(parent.get("resource_id")),
                        digest=_text(parent.get("digest")),
                        kind=_text(parent.get("kind")),
                        label=_text(parent.get("label")),
                        depth=depth)
            walk.rungs.append(rung)

            if len(walk.rungs) >= max_rungs:
                rung.why = CEILING
                walk.truncated = True
                return walk

            # An input that is not a file has no bytes to hash and nothing to
            # resolve: an acquisition campaign is a legitimate parent and the
            # missing digest is not a defect. Asking the resolver for it would
            # make every caller invent an answer for a question with none.
            if not rung.digest:
                rung.why = NOT_A_FILE if rung.kind else NOT_RESOLVED
                continue

            if rung.digest in seen:
                rung.why = ALREADY_WALKED
                continue
            seen.add(rung.digest)

            answer = resolve(rung.digest)
            if answer is None:
                rung.why = NOT_RESOLVED
                continue
            try:
                parent_stamp = (validate_stamp(answer)
                                if isinstance(answer, dict)
                                else parse_stamp(answer))
            except (BadStamp, ValueError) as exc:
                # BadStamp and ValueError, not Exception: a malformed or foreign
                # file is this, and it is a fact about the data. Anything else is
                # a defect in the resolver and must reach whoever wrote it.
                rung.why = UNREADABLE
                rung.detail = str(exc)
                continue
            rung.stamp = parent_stamp
            rung.reached = True
            frontier.append((parent_stamp, depth + 1))
    return walk


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ═════════════════════════════════════════════════════════════════════════════
# HINTS — «I saw this digest in this place, at this moment»
# ═════════════════════════════════════════════════════════════════════════════
#
# A mutable, plural, non-authoritative register, in a separate file
# (`<asset>.hints.json`) and **never covered by any digest**. The file is
# separate out of necessity and not for tidiness: an immutable record cannot
# contain a mutable field, because rewriting it would change its content.
#
# The gain is the opposite of what it looks like: **a wrong hint is harmless.**
# You follow it, recompute the fingerprint, and either it is the right thing or
# you find out immediately. A system that points by NAME hands you the wrong file
# in silence, which is the worst way there is to be wrong.

#: Who may travel and who may not. **Two values and not three**: «maybe» is not
#: an answer to a question about privacy.
SCOPES = ("public", "private")

#: How that place is reached. Open vocabulary — a `kind` that is not here is
#: recorded anyway, because a hint is an observation and not a declaration of
#: conformance — but these four write themselves.
KNOWN_KINDS = ("s3", "http", "local", "blend")

#: Which kinds are public when nobody says. A store URI is an address;
#: **everything else is private by default**, and the direction of this default
#: is the decision: erring towards «private» costs a hint that does not travel,
#: erring towards «public» costs somebody's user name.
_PUBLIC_BY_DEFAULT = ("s3", "http")


def new_hints(digest: str) -> Dict[str, Any]:
    """An empty register for this digest."""
    return {"hints": HINTS_VERSION, "digest": str(digest), "seen": []}


def kind_for(locator: str) -> str:
    """How that place is reached, read off the shape of the locator."""
    text = str(locator or "")
    if text.startswith("s3://"):
        return "s3"
    if text.startswith(("http://", "https://")):
        return "http"
    if text.startswith("blend://"):
        return "blend"
    return "local"


def scope_for(locator: str, kind: Optional[str] = None) -> str:
    """``public`` or ``private`` when nobody has said.

    The direction of the doubt is towards ``private``, always.
    """
    guessed = kind or kind_for(locator)
    return "public" if guessed in _PUBLIC_BY_DEFAULT else "private"


def note_seen(hints: Dict[str, Any], locator: str, *,
              kind: Optional[str] = None,
              scope: Optional[str] = None,
              machine: Optional[str] = None,
              when: Optional[str] = None) -> Dict[str, Any]:
    """Note «seen here, now». **Updates, does not duplicate, does not delete.**

    The same locator on the same machine is **the same hint re-observed**: its
    ``when`` is updated and it stays where it was. A row per glance would grow
    the file without adding a fact.

    ``when`` can be passed — and it needs to be, because a function that asks the
    clock cannot be tested twice with the same outcome. Absent, it is now: the
    clock belongs here, because **observing is an act that happens at a moment**,
    unlike emitting a stamp, which is a reading.

    **Hints are not deleted, they age.** There is nothing here, and there will be
    nothing here, that asks a person to tidy up a path: a moved file is not an
    error to correct, it is a fact to re-observe.
    """
    if scope is not None and scope not in SCOPES:
        raise ValueError(f"scope must be one of {list(SCOPES)}, got {scope!r}")
    seen = hints.setdefault("seen", [])
    resolved_kind = kind or kind_for(locator)
    entry = {
        "locator": str(locator),
        "kind": resolved_kind,
        "scope": scope or scope_for(locator, resolved_kind),
        "when": when or now_iso(),
    }
    if machine:
        entry["machine"] = machine
    for existing in seen:
        if existing.get("locator") == entry["locator"] \
                and existing.get("machine") == entry.get("machine"):
            existing.update(entry)
            return existing
    seen.append(entry)
    return entry


def for_export(hints: Dict[str, Any]) -> Dict[str, Any]:
    """The hints that may travel: **only ``public``**.

    The one door outwards, and **it has no switch**: a door that can be opened
    halfway is a door somebody opens halfway one day. Returns a well-formed
    register even when it stays empty — «I know no public place for this digest»
    is an honest answer, while no file at all would suggest the register does not
    exist.
    """
    out = {"hints": HINTS_VERSION, "digest": hints.get("digest"), "seen": []}
    for entry in hints.get("seen") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("scope") != "public":
            continue
        # `machine` does not leave even in a public hint: the name of somebody's
        # computer is not part of an address, and in a file that travels it is
        # just one more thing that is known about them.
        out["seen"].append({k: v for k, v in entry.items() if k != "machine"})
    return out


def private_locators(hints: Dict[str, Any]) -> List[str]:
    """The locators that must not leave. To **prove** it, not to use them."""
    return [str(e.get("locator") or "") for e in hints.get("seen") or []
            if isinstance(e, dict) and e.get("scope") != "public"]


def hints_filename(digest: str, *, asset: Optional[str] = None) -> str:
    """``<asset>.hints.json``, beside the stamp and by the same naming rule."""
    return _safe_name(str(asset or digest or "hints")) + HINTS_SUFFIX


def write_hints(hints: Dict[str, Any], path: str) -> str:
    """Write the **whole** register, private hints included: it is the home file."""
    return _write_json(hints, path)


def write_public_hints(hints: Dict[str, Any], path: str) -> str:
    """Write **only** what may travel. No parameter disables the filter."""
    return _write_json(for_export(hints), path)


def read_hints(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def file_digest(path: str, *, chunk: int = 1024 * 1024) -> str:
    """``sha256:<hex>`` of a file's bytes, read in blocks.

    In blocks because a point cloud does not fit in memory, and a digest that
    works on small files and dies on large ones is worse than no digest: it fails
    on exactly the data that was worth identifying.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def scan_directory(root: str, *, machine: Optional[str] = None,
                   when: Optional[str] = None,
                   suffixes: Optional[Iterable[str]] = None,
                   into: Optional[Dict[str, Dict[str, Any]]] = None
                   ) -> Dict[str, Any]:
    """Scan a directory and note where it saw what.

    Returns ``{"found": {digest: hints}, "unreadable": [...]}`` — **two keys and
    not one dictionary**, because a file that could not be read has no digest to
    live under, and slipping it into the same map with a fake key would put a
    word among the addresses of whoever iterates.

    ``into`` continues a register that already existed, because a scan **adds
    to** previous observations rather than replacing them: a file that is not
    there today does not stop having been seen elsewhere yesterday.

    The ``scope`` is not a parameter: a path on a disk is ``local``, and ``local``
    is ``private``. Letting the caller choose would mean somebody one day passes
    ``public`` for a scan of their own laptop.
    """
    base = pathlib.Path(root)
    if not base.is_dir():
        raise NotADirectoryError(f"{root} is not a directory to scan")
    found: Dict[str, Dict[str, Any]] = into if into is not None else {}
    unreadable: List[str] = []
    wanted = tuple(s.lower() for s in suffixes) if suffixes else None
    host = machine if machine is not None else _this_machine()
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if wanted and path.suffix.lower() not in wanted:
            continue
        try:
            digest = file_digest(str(path))
        except OSError as exc:
            # OSError and not Exception: a denied permission or a broken link is
            # this; anything else is a defect and must reach the reader instead
            # of ending up in a list of warnings.
            unreadable.append(f"{path}: {exc}")
            continue
        register = found.setdefault(digest, new_hints(digest))
        note_seen(register, str(path), kind="local", scope="private",
                  machine=host, when=when)
    return {"found": found, "unreadable": unreadable}


def _this_machine() -> Optional[str]:
    """The name of this machine, when the system says.

    It lives in a ``private`` hint and never leaves (:func:`for_export` strips it
    even from a public one): it tells «I saw it on the laptop» from «I saw it on
    the desktop», which is the only reason two hints to the same path are two
    hints.
    """
    uname = getattr(os, "uname", None)
    return uname().nodename if callable(uname) else None



# ═════════════════════════════════════════════════════════════════════════════
# THE RESOURCE OF MORE THAN ONE FILE — the list of its members is its identity
# ═════════════════════════════════════════════════════════════════════════════
#
# Decided by E.D. on 30 Sep 2026: a resource is the SET, each file is a member
# of it. An OBJ is not a file: it is the obj, the mtl it calls, and the
# textures the mtl calls — and the digest of the obj alone would say «these are
# those bytes» about a third of the thing. So the digest of a resource of more
# than one file is the digest of the SORTED LIST of its members (role, path,
# checksum), in one canonical form fixed here byte for byte, because two
# implementations that disagree on a separator disagree on every identity.
#
# A tileset has TWO identities, and they are not in competition: the sha256 of
# the `.3tz` names that file; the digest of the list (path, sha256) of what is
# inside names the CONTENT, and a folder and its `.3tz` share it. Whoever
# produces the tileset computes it — they have the files in hand anyway.

#: What ``self.packaging`` says, measured on s3Dgraphy (``PACKAGINGS`` of the
#: resource, 30 Sep 2026) and on the corpus (``file``, ``datablock``). A value
#: that is not here is kept, not refused: the vocabulary is enumerated so that
#: writers agree, not so that a reader can throw a record away.
PACKAGINGS = ("file", "file_set", "directory", "archive", "datablock")

#: What ``self.digest_covers`` says. ``members``: the digest is the sha256 of
#: the canonical list of the members (:func:`members_canonical`), not of any
#: file's bytes.
DIGEST_COVERS = ("artifact", "payload", "members")

#: The role of a member, as s3Dgraphy's ``has_file`` spells it.
ENTRY_POINT = "entry_point"
MEMBER = "member"
MEMBER_ROLES = (ENTRY_POINT, MEMBER)

#: Who computed a ``content_digest``: the producer at export, or whoever
#: stamped the tree afterwards. Two words, because the second one read bytes
#: that may already have been moved or edited, and a reader has the right to
#: know which.
COMPUTED_BY = ("producer", "stamper")

#: The field separator of the canonical list: NUL, the one character no path on
#: any file system can contain — so a path can hold a tab, a space or even a
#: newline and the list still reads back one way only.
MEMBERS_SEPARATOR = "\x00"
#: The end of every line, the last one included.
MEMBERS_EOL = "\n"

#: A ``file_set`` lists its members inside the stamp, so it must stay small.
#: MEASURED on TempluMare: 3 members at LOD1/LOD2, 6 at LOD0; a glTF with a
#: full PBR material per part rarely passes twenty. Over this ceiling it is a
#: tree, and a tree is identified by :func:`content_digest` without a list.
MAX_FILE_SET_MEMBERS = 64

#: Never members of a tree: what a file browser leaves behind. The same list as
#: the 3tz profile's, and it MUST be the same — otherwise a folder and its
#: archive could not share a content digest.
SKIP_NAMES = (".DS_Store", "Thumbs.db")

_SHA256_HEX = re.compile(r"^[0-9a-f]{64}$")


class BadMembers(ValueError):
    """This list of members has no canonical form."""


def member_path(path: str) -> str:
    """The path of a member as the canonical list writes it.

    Forward slashes, no leading slash, Unicode NFC (a name typed on a Mac and
    the same name typed on Windows are the same name). Refused — not repaired —
    an empty path, an empty, ``.`` or ``..`` segment, and a control character:
    each of those is a path that means two things.
    """
    text = unicodedata.normalize("NFC", str(path)).replace("\\", "/").lstrip("/")
    if not text:
        raise BadMembers("an empty path is not a member")
    if any(ord(c) < 0x20 or c == "\x7f" for c in text):
        raise BadMembers(f"{text!r}: a control character in a path")
    for segment in text.split("/"):
        if segment in ("", ".", ".."):
            raise BadMembers(
                f"{text!r}: a path with an empty, '.' or '..' segment names "
                f"more than one place")
    return text


def _member_digest(member: Dict[str, Any]) -> str:
    value = member.get("digest") or member.get("checksum")
    scheme, rest = split_identity(value)
    if scheme != "sha256" or not rest or not _SHA256_HEX.match(rest.lower()):
        raise BadMembers(
            f"{member.get('path')!r}: a member needs `sha256:<64 hex>`, got "
            f"{value!r}")
    return "sha256:" + rest.lower()


def canonical_members(members: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """The members normalised and sorted: ``[{role, path, digest}]``, plus
    ``size_bytes`` when it was given.

    Sorted by the UTF-8 bytes of the NFC path. At most one ``entry_point``; no
    path twice (after normalisation, so ``a\\b`` and ``a/b`` collide as they
    should).
    """
    out, seen, entries = [], set(), 0
    for member in members:
        if not isinstance(member, dict):
            raise BadMembers(f"a member is an object, got {type(member).__name__}")
        role = member.get("role") or MEMBER
        if role not in MEMBER_ROLES:
            raise BadMembers(f"role {role!r}: one of {list(MEMBER_ROLES)}")
        path = member_path(member.get("path") or "")
        if path in seen:
            raise BadMembers(f"{path!r} is listed twice")
        seen.add(path)
        entries += role == ENTRY_POINT
        row = {"role": role, "path": path, "digest": _member_digest(member)}
        size = member.get("size_bytes")
        if isinstance(size, int) and not isinstance(size, bool) and size >= 0:
            row["size_bytes"] = size
        out.append(row)
    if entries > 1:
        raise BadMembers(f"{entries} entry points: a resource has one door")
    out.sort(key=lambda r: r["path"].encode("utf-8"))
    return out


def members_canonical(members: Iterable[Dict[str, Any]]) -> bytes:
    """The canonical list, byte for byte — what :func:`members_digest` hashes.

    One line per member, in path order::

        <role> NUL <path> NUL sha256:<hex> LF

    UTF-8, NFC paths, lower-case hex, and a LF after every line including the
    last. ``size_bytes`` is not in it: the size follows from the bytes.
    """
    lines = [MEMBERS_SEPARATOR.join((m["role"], m["path"], m["digest"]))
             + MEMBERS_EOL for m in canonical_members(members)]
    return "".join(lines).encode("utf-8")


def members_digest(members: Iterable[Dict[str, Any]]) -> str:
    """``sha256:<hex>`` of :func:`members_canonical` — the identity of a
    resource of more than one file, and the ``content_digest`` of a tree."""
    return "sha256:" + hashlib.sha256(members_canonical(members)).hexdigest()


# ── a tree: a folder, or the same folder packed in a .3tz ────────────────────

#: The 3tz index entry (3D Tiles Archive Format v1.3): never a member.
INDEX_NAME_3TZ = "@3dtilesIndex1@"
MEDIA_TYPE_3TZ = "application/vnd.maxar.archive.3tz+zip"
_BLOCK = 1024 * 1024
_LFH = struct.Struct("<IHHHHHIIIHH")
_LFH_SIGNATURE = 0x04034B50



def _directory_members(root: str, entry_point: Optional[str]) -> List[Dict[str, Any]]:
    base = os.path.abspath(root)
    out = []
    for folder, dirs, files in os.walk(base):
        dirs.sort()
        for name in sorted(files):
            if name in SKIP_NAMES:
                continue
            full = os.path.join(folder, name)
            rel = os.path.relpath(full, base).replace(os.sep, "/")
            out.append({"path": rel, "digest": file_digest(full),
                        "size_bytes": os.path.getsize(full)})
    return _with_entry_point(out, entry_point)


def _with_entry_point(rows, entry_point):
    door = member_path(entry_point) if entry_point else None
    for row in rows:
        row["role"] = ENTRY_POINT if door and member_path(row["path"]) == door \
            else MEMBER
    return rows


def _index_records(fh, zf: zipfile.ZipFile) -> List[Tuple[bytes, int]]:
    infos = zf.infolist()
    if not infos or infos[-1].filename != INDEX_NAME_3TZ:
        raise ValueError(f"not a 3tz: the last entry is not {INDEX_NAME_3TZ!r}")
    if infos[-1].compress_type != zipfile.ZIP_STORED:
        raise ValueError(f"not a 3tz: {INDEX_NAME_3TZ} is compressed")
    raw = zf.read(infos[-1])
    if len(raw) % 24:
        raise ValueError(f"not a 3tz: an index of {len(raw)} bytes is not "
                         f"24-byte records")
    return [(raw[i:i + 16], struct.unpack_from("<Q", raw, i + 16)[0])
            for i in range(0, len(raw), 24)]


def _archive_members(path: str, entry_point: Optional[str]) -> List[Dict[str, Any]]:
    """The members of a 3tz read THROUGH ITS INDEX, nothing extracted.

    The index gives the offset of each local header; the central directory,
    matched by that offset, gives the method, the compressed size and the CRC;
    the bytes are streamed in blocks from the data that follows the header and
    their CRC is checked on the way. An entry the index does not reach, or a
    record that points at no entry, is an archive that is not a 3tz, and says
    so.
    """
    out = []
    with open(path, "rb") as fh, zipfile.ZipFile(fh) as zf:
        records = _index_records(fh, zf)
        by_offset = {i.header_offset: i for i in zf.infolist()
                     if i.filename != INDEX_NAME_3TZ}
        reached = set()
        for md5, offset in records:
            info = by_offset.get(offset)
            if info is None:
                raise ValueError(f"not a 3tz: an index record points at offset "
                                 f"{offset}, where no entry starts")
            name = info.filename.replace("\\", "/").lstrip("/")
            if hashlib.md5(name.encode("utf-8")).digest() != md5:
                raise ValueError(f"not a 3tz: the index record of {name!r} "
                                 f"carries another MD5")
            reached.add(offset)
            fh.seek(offset)
            head = fh.read(_LFH.size)
            fields = _LFH.unpack(head)
            if fields[0] != _LFH_SIGNATURE:
                raise ValueError(f"no local file header at offset {offset}")
            fh.seek(fields[9] + fields[10], os.SEEK_CUR)
            out.append({"path": name,
                        **_stream_member(fh, info)})
        missing = sorted(i.filename for o, i in by_offset.items()
                         if o not in reached)
        if missing:
            raise ValueError(f"not a 3tz: {len(missing)} entries the index does "
                             f"not reach, e.g. {missing[:3]}")
    return _with_entry_point(out, entry_point)


def _stream_member(fh, info: zipfile.ZipInfo) -> Dict[str, Any]:
    method, left = info.compress_type, info.compress_size
    digest, crc, size = hashlib.sha256(), 0, 0
    if method == zipfile.ZIP_STORED:
        inflate = None
    elif method == zipfile.ZIP_DEFLATED:
        inflate = zlib.decompressobj(-15)
    elif method == 93:
        # Zstandard is allowed by the 3tz spec and is not standard library.
        raise ValueError(f"{info.filename!r} is Zstandard-compressed: this "
                         f"module reads stored and deflated entries only")
    else:
        raise ValueError(f"{info.filename!r}: compression method {method} is "
                         f"not one a 3tz allows")
    while left:
        block = fh.read(min(_BLOCK, left))
        if not block:
            raise ValueError(f"{info.filename!r} is truncated")
        left -= len(block)
        if inflate is not None:
            block = inflate.decompress(block)
        digest.update(block)
        crc = zlib.crc32(block, crc)
        size += len(block)
    if inflate is not None:
        tail = inflate.flush()
        digest.update(tail)
        crc = zlib.crc32(tail, crc)
        size += len(tail)
    if crc != info.CRC or size != info.file_size:
        raise ValueError(f"{info.filename!r}: CRC or size do not match the "
                         f"central directory")
    return {"digest": "sha256:" + digest.hexdigest(), "size_bytes": size}


def tree_members(path: str, *, entry_point: Optional[str] = "tileset.json"
                 ) -> List[Dict[str, Any]]:
    """Every file of a tree — a folder, or a ``.3tz`` — as members, sorted.

    ``entry_point`` (``tileset.json`` by default, at the root) gets the role
    ``entry_point``; every other file is a ``member``. ``.DS_Store`` and
    ``Thumbs.db`` are never members, and neither is the 3tz index.
    """
    if os.path.isdir(path):
        rows = _directory_members(path, entry_point)
    elif zipfile.is_zipfile(path):
        rows = _archive_members(path, entry_point)
    else:
        raise ValueError(f"{path} is neither a folder nor a 3tz")
    return canonical_members(rows)


def content_digest(path: str, *, entry_point: Optional[str] = "tileset.json") -> str:
    """The identity of the CONTENT of a tree: :func:`members_digest` of
    :func:`tree_members`. A folder and its ``.3tz`` give the same value,
    whatever the archive's dates, attributes or compression."""
    return members_digest(tree_members(path, entry_point=entry_point))


def content_digest_block(path: str, *, computed_by: str = "stamper",
                         entry_point: Optional[str] = "tileset.json"
                         ) -> Dict[str, Any]:
    """``self.content_digest`` for a stamp: ``{digest, files, computed_by}``.

    The list is NOT in the stamp — a tileset has thousands of files; the digest
    and the count are, and whoever needs the list recomputes it from the tree.
    """
    if computed_by not in COMPUTED_BY:
        raise ValueError(f"computed_by must be one of {list(COMPUTED_BY)}")
    rows = tree_members(path, entry_point=entry_point)
    return {"digest": members_digest(rows), "files": len(rows),
            "computed_by": computed_by}


# ── the one .3tz profile: 3DSC's ─────────────────────────────────────────────

#: The canonical 3tz — the archive 3DSC writes (``3D-survey-collection/
#: cesium_exporter/archive_3tz.py``, commit ``1430128``, ``write_3tz`` with
#: ``compress=False``, plus the NFC names it writes from 22 Oct 2026), the
#: same as s3Dgraphy's ``CANONICAL_3TZ_PROFILE``, aligned that day on flag
#: 0x800 and NFC. See ``profiles/3tz.md``.
CANONICAL_3TZ = {
    "source": "3D-survey-collection/cesium_exporter/archive_3tz.py",
    "source_commit": "1430128",
    "date_time": (1980, 1, 1, 0, 0, 0),
    "compress_type": zipfile.ZIP_STORED,
    "create_system": 3,
    "external_attr": 0o100644 << 16,
    "skip_names": SKIP_NAMES,
    "name_form": "NFC",
}

#: The general-purpose flag Python's zipfile — and so 3DSC — sets on an entry
#: whose name is not ASCII (bit 11, «the name is UTF-8»). MEASURED 30 Sep 2026:
#: 3DSC writes it for ``Data/città.b3dm``. Deterministic, so allowed: exactly
#: on the non-ASCII names, and nowhere else.
_UTF8_FLAG = 0x800


def _expected_flags(name: str) -> int:
    return _UTF8_FLAG if any(ord(c) > 0x7F for c in name) else 0


def is_canonical_3tz(path: str) -> Dict[str, Any]:
    """Whether the archive follows :data:`CANONICAL_3TZ`, criterion by
    criterion, with the reasons when it does not.

    Canonical means: the sha256 of the file names its content and not the
    moment it was packed. A non-canonical 3tz is still a 3tz, and its
    :func:`content_digest` is the canonical one's; only its file digest is
    unstable.
    """
    prof = CANONICAL_3TZ
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
    members = [i for i in infos if i.filename != INDEX_NAME_3TZ]
    names = [i.filename for i in members]
    index_last = bool(infos) and infos[-1].filename == INDEX_NAME_3TZ
    index_sorted = False
    if index_last and infos[-1].compress_type == zipfile.ZIP_STORED:
        with open(path, "rb") as fh, zipfile.ZipFile(fh) as zf:
            try:
                keys = [struct.unpack("<QQ", md5) for md5, _ in
                        _index_records(fh, zf)]
                index_sorted = keys == sorted(keys)
            except ValueError:
                pass
    checks = {
        "entries_in_order": [n.encode("utf-8") for n in names]
                            == sorted(n.encode("utf-8") for n in names),
        "index_last": index_last,
        "index_sorted": index_sorted,
        "fixed_dates": all(i.date_time == prof["date_time"] for i in infos),
        "stored": all(i.compress_type == prof["compress_type"] for i in infos),
        "create_system": all(i.create_system == prof["create_system"] for i in infos),
        "external_attr": all(i.external_attr == prof["external_attr"] for i in infos),
        "no_extra_fields": all(not i.extra or max(i.file_size, i.compress_size,
                                                  i.header_offset) >= 0xFFFFFFFF
                               for i in infos),
        "flags": all(i.flag_bits == _expected_flags(i.filename) for i in infos),
        "names_nfc": all(unicodedata.normalize(prof["name_form"], i.filename)
                         == i.filename for i in infos),
        "tileset_at_root": "tileset.json" in names,
        "no_3tz_paths": not any(".3tz" in n.lower() for n in names),
        "no_skipped_names": not any(n.rsplit("/", 1)[-1] in prof["skip_names"]
                                    for n in names),
    }
    why = {
        "entries_in_order": "members are not in path order",
        "index_last": f"{INDEX_NAME_3TZ} is not the last entry",
        "index_sorted": "the index is not stored or not sorted by MD5",
        "fixed_dates": "entries carry a date other than 1980-01-01 00:00:00 "
                       "(the time of writing: the digest names the moment of "
                       "packing, not the content)",
        "stored": "entries are compressed",
        "create_system": "create_system is not 3 (unix)",
        "external_attr": "file attributes are not 0o100644",
        "no_extra_fields": "entries carry extra fields",
        "flags": "general purpose flags other than 0 on an ASCII name and "
                 "0x800 on a non-ASCII one",
        "names_nfc": "names are not in Unicode NFC (a name as macOS gives it, "
                     "NFD: the same folder would give another sha256 elsewhere)",
        "tileset_at_root": "no tileset.json at the root",
        "no_3tz_paths": "a path contains '.3tz'",
        "no_skipped_names": ".DS_Store / Thumbs.db are packed",
    }
    reasons = []
    for key, ok in checks.items():
        if ok:
            continue
        text = why[key]
        if key == "fixed_dates":
            text += f": {sorted({i.date_time for i in infos} - {prof['date_time']})[:3]}"
        if key == "external_attr":
            seen = sorted({hex(i.external_attr) for i in infos}
                          - {hex(prof["external_attr"])})
            text += f": {seen[:3]}, not {hex(prof['external_attr'])}"
        if key == "names_nfc":
            text += ": " + str([i.filename for i in infos
                                if unicodedata.normalize("NFC", i.filename)
                                != i.filename][:3])
        if key == "flags":
            text += ": " + str([(i.filename, hex(i.flag_bits)) for i in infos
                                if i.flag_bits != _expected_flags(i.filename)][:3])
        reasons.append(text)
    return {**checks, "canonical": not reasons, "reasons": reasons,
            "members": len(members),
            "create_versions": sorted({i.create_version for i in infos})}


# ── a file set: an entry point and the files it calls ────────────────────────
#
# The members of a file set are FOUND, not listed by hand: from the entry
# point one follows `mtllib` and `map_*` (OBJ) or `buffers` and `images`
# (glTF), into subfolders too. What nobody calls stays out, and is named. The
# folder does not delimit the asset: a LOD folder holds eleven tiles.

_ABSOLUTE = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\/]|[A-Za-z][A-Za-z0-9+.-]*://)")

#: MTL statements that name a file, besides every `map_*`.
_MTL_FILE_KEYS = ("bump", "disp", "decal", "refl", "norm")
#: MTL options and how many arguments each takes (`-o`/`-s`/`-t` take one to
#: three numbers, read greedily).
_MTL_OPTIONS = {"-blendu": 1, "-blendv": 1, "-boost": 1, "-mm": 2, "-o": 3,
                "-s": 3, "-t": 3, "-texres": 1, "-clamp": 1, "-bm": 1,
                "-imfchan": 1, "-type": 1, "-cc": 1}


def _is_number(token: str) -> bool:
    try:
        float(token)
        return True
    except ValueError:
        return False


def _mtl_file(tokens: List[str]) -> Optional[str]:
    i = 0
    while i < len(tokens) and tokens[i].startswith("-") \
            and tokens[i].lower() in _MTL_OPTIONS:
        count = _MTL_OPTIONS[tokens[i].lower()]
        i += 1
        taken = 0
        while taken < count and i < len(tokens) - 1:
            if count == 3 and not _is_number(tokens[i]):
                break
            i += 1
            taken += 1
    rest = " ".join(tokens[i:]).strip()
    return rest or None


def _text_lines(path: str) -> List[str]:
    with open(path, "rb") as handle:
        return handle.read().decode("utf-8", errors="replace").splitlines()


def _obj_refs(path: str) -> List[str]:
    refs, here = [], os.path.dirname(path)
    for line in _text_lines(path):
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and parts[0] == "mtllib":
            whole = parts[1].strip()
            # one name with spaces (Blender) or several names (the spec)
            if os.path.isfile(os.path.join(here, whole)) or " " not in whole:
                refs.append(whole)
            else:
                refs.extend(whole.split())
    return refs


def _mtl_refs(path: str) -> List[str]:
    refs = []
    for line in _text_lines(path):
        tokens = line.strip().split()
        if not tokens:
            continue
        key = tokens[0].lower()
        if key.startswith("map_") or key in _MTL_FILE_KEYS:
            name = _mtl_file(tokens[1:])
            if name:
                refs.append(name)
    return refs


def _gltf_json(path: str) -> Dict[str, Any]:
    with open(path, "rb") as handle:
        raw = handle.read()
    if raw[:4] == b"glTF":
        length = struct.unpack_from("<I", raw, 12)[0]
        kind = raw[16:20]
        if kind != b"JSON":
            raise ValueError(f"{path}: the first glb chunk is not JSON")
        raw = raw[20:20 + length]
    return json.loads(raw.decode("utf-8"))


def _gltf_refs(path: str) -> List[str]:
    from urllib.parse import unquote
    doc = _gltf_json(path)
    refs = []
    for key in ("buffers", "images"):
        for item in doc.get(key) or []:
            uri = (item or {}).get("uri")
            if isinstance(uri, str) and uri and not uri.startswith("data:"):
                refs.append(unquote(uri))
    return refs


def _refs_of(path: str) -> List[str]:
    suffix = os.path.splitext(path)[1].lower()
    if suffix == ".obj":
        return _obj_refs(path)
    if suffix == ".mtl":
        return _mtl_refs(path)
    if suffix in (".gltf", ".glb"):
        return _gltf_refs(path)
    return []


def follow_references(entry_point: str) -> Dict[str, Any]:
    """The members of a file set, found by following its references.

    Returns ``{"members": [{role, path, digest, size_bytes}], "warnings": […],
    "missing": [paths], "outside": [refs]}``. Paths are relative to the entry
    point's folder. A reference that is absolute, or climbs out of that folder
    with ``../``, is not followed and is a warning; a reference to a file that
    is not there is ``missing`` (a stamp made from this would leave it out, and
    the verification of an existing stamp names it).
    """
    entry = os.path.abspath(entry_point)
    base = os.path.dirname(entry)
    found: Dict[str, str] = {}          # relative path → absolute path
    order = [entry]
    found[member_path(os.path.basename(entry))] = entry
    warnings, missing, outside = [], [], []
    i = 0
    while i < len(order):
        current = order[i]
        i += 1
        try:
            refs = _refs_of(current)
        except (OSError, ValueError) as exc:
            warnings.append(f"{os.path.relpath(current, base)}: unreadable "
                            f"({exc})")
            continue
        for ref in refs:
            caller = os.path.relpath(current, base).replace(os.sep, "/")
            if _ABSOLUTE.match(ref):
                outside.append(ref)
                warnings.append(f"{caller}: absolute reference {ref!r} not "
                                f"followed")
                continue
            target = os.path.normpath(os.path.join(os.path.dirname(current),
                                                   ref.replace("\\", "/")))
            rel = os.path.relpath(target, base).replace(os.sep, "/")
            if rel == ".." or rel.startswith("../"):
                outside.append(ref)
                warnings.append(f"{caller}: {ref!r} leaves the folder of the "
                                f"entry point, not followed")
                continue
            key = member_path(rel)
            if key in found or key in missing:
                continue
            if not os.path.isfile(target):
                missing.append(key)
                warnings.append(f"{caller}: calls {ref!r}, which is not there")
                continue
            found[key] = target
            order.append(target)
    door = member_path(os.path.basename(entry))
    members = [{"role": ENTRY_POINT if rel == door else MEMBER, "path": rel,
                "digest": file_digest(full), "size_bytes": os.path.getsize(full)}
               for rel, full in found.items()]
    return {"members": canonical_members(members), "warnings": warnings,
            "missing": sorted(missing), "outside": outside}


def new_file_set_stamp(entry_point: str, resource_id: str, **blocks: Any
                       ) -> Dict[str, Any]:
    """A stamp for the file set whose door is ``entry_point``.

    ``self`` carries ``packaging: file_set``, ``digest_covers: members``, the
    members digest and the list itself (``self.members``). ``blocks`` are the
    other top-level blocks as they are (``from``, ``how``, ``by``, …).
    The warnings of the walk ride along as the note ``_followed``, which
    :func:`write_stamp` drops: they are for the writer, not for the record.

    Refused over :data:`MAX_FILE_SET_MEMBERS`: that is a tree, and a tree is
    identified by :func:`content_digest`.
    """
    followed = follow_references(entry_point)
    members = followed["members"]
    if len(members) > MAX_FILE_SET_MEMBERS:
        raise BadMembers(
            f"{len(members)} members, over the ceiling of "
            f"{MAX_FILE_SET_MEMBERS} for a file_set: stamp it as a tree "
            f"(packaging directory, content_digest)")
    itself = {"resource_id": str(resource_id),
              "digest": members_digest(members),
              "digest_covers": "members",
              "packaging": "file_set",
              "members": members,
              "measures": {"size_bytes": sum(m["size_bytes"] for m in members),
                           "files": len(members)}}
    stamp = {"stamp": STAMP_VERSION, "self": itself}
    stamp.update(blocks)
    stamp["self"] = {**itself, **(blocks.get("self") or {}), **itself}
    stamp["_followed"] = {k: followed[k] for k in ("warnings", "missing", "outside")}
    return stamp


def file_set_stamp_path(entry_point: str) -> str:
    """The sidecar: ONE, beside the door — ``OB_PODIO_LOD1.obj.stamp.json`` —
    by the rule every stamp already follows (:func:`stamp_filename`)."""
    return os.path.join(os.path.dirname(os.path.abspath(entry_point)),
                        stamp_filename({}, asset=os.path.basename(entry_point)))


def verify_members(stamp: Dict[str, Any], entry_point: str) -> Dict[str, Any]:
    """Check a ``file_set`` stamp against the files beside its door.

    ``{"ok", "missing", "changed", "extra", "list_consistent", "warnings"}``:
    a member that is not there, a member whose bytes changed, a file the entry
    point now calls and the stamp does not list; and whether ``self.members``
    still hashes to ``self.digest`` (a hand-edited list does not). A member
    shared with another file set is checked here like any other: each stamp is
    verified on its own, and a change to the shared file breaks both.
    """
    itself = stamp.get("self") or {}
    listed = canonical_members(itself.get("members") or [])
    base = os.path.dirname(os.path.abspath(entry_point))
    missing, changed = [], []
    for member in listed:
        full = os.path.join(base, *member["path"].split("/"))
        if not os.path.isfile(full):
            missing.append(member["path"])
        elif file_digest(full) != member["digest"]:
            changed.append(member["path"])
    now = follow_references(entry_point) if os.path.isfile(entry_point) else \
        {"members": [], "warnings": [f"{entry_point}: the entry point is gone"]}
    stamped = {m["path"] for m in listed}
    extra = sorted(m["path"] for m in now["members"] if m["path"] not in stamped)
    consistent = members_digest(listed) == itself.get("digest")
    return {"ok": consistent and not (missing or changed or extra),
            "missing": missing, "changed": changed, "extra": extra,
            "list_consistent": consistent, "warnings": now["warnings"]}


def unclaimed_files(root: str, file_sets: Iterable[Dict[str, Any]], *,
                    base: Optional[str] = None) -> List[str]:
    """Files under ``root`` that no file set calls — named, never swept in.

    ``file_sets`` are results of :func:`follow_references` (or stamps), their
    paths relative to ``base`` (``root`` by default). Stamps and hints are not
    listed: they are records, not data.
    """
    base = os.path.abspath(base or root)
    claimed = set()
    for item in file_sets:
        rows = item.get("members") or (item.get("self") or {}).get("members") or []
        claimed.update(member_path(m["path"]) for m in rows)
    out = []
    for folder, dirs, files in os.walk(root):
        dirs.sort()
        for name in sorted(files):
            if name in SKIP_NAMES or name.endswith((STAMP_SUFFIX, HINTS_SUFFIX)):
                continue
            rel = os.path.relpath(os.path.join(folder, name), base)
            rel = member_path(rel.replace(os.sep, "/"))
            if rel not in claimed:
                out.append(rel)
    return out


# ── a tree stamp, and the link between two forms of one content ──────────────

def new_tree_stamp(path: str, resource_id: str, *, computed_by: str = "stamper",
                   entry_point: Optional[str] = "tileset.json", **blocks: Any
                   ) -> Dict[str, Any]:
    """A stamp for a tree: a folder (``packaging: directory``) or a ``.3tz``
    (``packaging: archive``).

    The folder has no bytes of its own: its ``self.digest`` IS the content
    digest (``digest_covers: members``). The archive has: ``self.digest`` is
    the sha256 of the file (``digest_covers: artifact``) and
    ``self.content_digest`` names the content. Two stamps with the same
    ``content_digest.digest`` are **two forms of one thing** — the word EMtools
    uses for its ``_link`` (the tree served) and ``_archive`` (the zip that
    travels) — and nothing else links them: the equality is the link.
    """
    block = content_digest_block(path, computed_by=computed_by,
                                 entry_point=entry_point)
    if os.path.isdir(path):
        itself = {"resource_id": str(resource_id), "digest": block["digest"],
                  "digest_covers": "members", "packaging": "directory",
                  "content_digest": block}
    else:
        itself = {"resource_id": str(resource_id), "digest": file_digest(path),
                  "digest_covers": "artifact", "packaging": "archive",
                  "media_type": MEDIA_TYPE_3TZ, "content_digest": block,
                  "measures": {"size_bytes": os.path.getsize(path)}}
    stamp = {"stamp": STAMP_VERSION}
    stamp.update(blocks)
    stamp["self"] = {**(blocks.get("self") or {}), **itself}
    return stamp


def same_content(mine: Dict[str, Any], theirs: Dict[str, Any]) -> bool:
    """Whether two stamps name two forms of the same content: equal
    ``self.content_digest.digest`` (for a folder, its ``self.digest``)."""
    def key(stamp):
        itself = stamp.get("self") or {}
        block = itself.get("content_digest") or {}
        if block.get("digest"):
            return block["digest"]
        if itself.get("digest_covers") == "members":
            return itself.get("digest")
        return None
    a, b = key(mine), key(theirs)
    return bool(a) and a == b


def verify_tree(stamp: Dict[str, Any], path: str) -> Dict[str, Any]:
    """Recompute a tree's content digest (and, for an archive, the file's
    sha256) and compare: ``{"ok", "content", "file"}`` — ``file`` is None for
    a folder, which has no bytes of its own."""
    itself = stamp.get("self") or {}
    expected = (itself.get("content_digest") or {}).get("digest") \
        or itself.get("digest")
    content = content_digest(path) == expected
    file_ok = None
    if not os.path.isdir(path):
        file_ok = file_digest(path) == itself.get("digest")
    return {"ok": content and file_ok is not False, "content": content,
            "file": file_ok}


# ── a datablock: an object inside a .blend, which has no bytes of its own ────

BLEND_SCHEME = "blend://"


def blend_locator(blend_path: str, datablock_type: str, name: str) -> str:
    """``blend://<path>#<Type>/<name>``, percent-encoded — the form of
    s3Dgraphy's ``make_blend_locator`` (``resources/resolver.py``), copied and
    pinned by a conformance case so the two cannot drift."""
    from urllib.parse import quote
    if not blend_path or not name:
        return ""
    return (BLEND_SCHEME + quote(str(blend_path), safe="/")
            + "#" + quote(str(datablock_type or "Object"), safe="")
            + "/" + quote(str(name), safe=""))


def parse_blend_locator(locator: str) -> Optional[Tuple[str, str, str]]:
    """``(path, type, name)`` from a ``blend://`` locator, or None."""
    from urllib.parse import unquote
    text = (locator or "").strip()
    if not text.lower().startswith(BLEND_SCHEME):
        return None
    rest = text[len(BLEND_SCHEME):]
    if "#" not in rest:
        return None
    path, fragment = rest.split("#", 1)
    if "/" not in fragment:
        return None
    kind, name = fragment.split("/", 1)
    if not path or not name:
        return None
    return unquote(path), unquote(kind), unquote(name)


def new_datablock_stamp(resource_id: str, blend_path: str, name: str, *,
                        datablock_type: str = "Object",
                        structural_digest: Optional[str] = None,
                        machine: Optional[str] = None, when: Optional[str] = None,
                        **blocks: Any) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """A stamp and its hints for a datablock (``packaging: datablock``).

    **There is no digest of bytes**, and the stamp says so the way the format
    already does: ``self.digest`` is an ``emstruct1:`` fingerprint when the
    caller computed one (comparable, never verifiable), or absent. The
    ``blend://`` locator is a PATH, so it does not go in the stamp: it is a
    private hint, keyed by the fingerprint (or by the resource id when there is
    none).
    """
    itself: Dict[str, Any] = {"resource_id": str(resource_id),
                              "packaging": "datablock"}
    if structural_digest:
        scheme, _ = split_identity(structural_digest)
        if scheme not in COMPARABLE_SCHEMES:
            raise ValueError(f"a datablock's digest is structural "
                             f"({'/'.join(COMPARABLE_SCHEMES)}:…), got "
                             f"{structural_digest!r}")
        itself["digest"] = structural_digest
        itself["digest_covers"] = "artifact"
    stamp = {"stamp": STAMP_VERSION}
    stamp.update(blocks)
    stamp["self"] = {**(blocks.get("self") or {}), **itself}
    hints = new_hints(structural_digest or str(resource_id))
    note_seen(hints, blend_locator(blend_path, datablock_type, name),
              kind="blend", scope="private", machine=machine, when=when)
    return stamp, hints


__all__ = [
    "ALREADY_WALKED", "BadStamp", "CEILING", "COMPARABLE", "COMPARABLE_SCHEMES",
    "DESCRIPTION_HINT_CHARS", "Disagreement", "HINTS_SUFFIX", "HINTS_VERSION", "KNOWN_KINDS", "NOT_A_FILE",
    "NOT_RESOLVED", "PACKAGE", "Resolver", "Rung", "SCOPES", "STAMP_SUFFIX",
    "STAMP_VERSION", "UNKNOWN", "UNREADABLE", "VERIFIABLE", "VERIFIABLE_SCHEMES",
    "Walk", "__version__", "clean_stamp", "compare_stamps", "declared_origin",
    "describe_identity", "file_digest", "for_export", "hints_filename",
    "identity_strength", "is_comparable", "is_verifiable", "is_verifiable_stamp",
    "kind_for", "new_hints", "note_seen", "now_iso", "parse_stamp",
    "private_locators", "read_hints", "read_stamp", "receipt", "scan_directory",
    "scope_for", "split_identity", "stamp_description", "stamp_filename",
    "stamp_identity", "stamp_title",
    "stamps_agree", "substance", "validate_stamp", "walk_chain", "write_hints",
    "write_public_hints", "write_stamp",
    # the resource of more than one file (21-10-2026)
    "BLEND_SCHEME", "BadMembers", "COMPUTED_BY", "CANONICAL_3TZ", "DIGEST_COVERS",
    "ENTRY_POINT", "INDEX_NAME_3TZ", "MAX_FILE_SET_MEMBERS", "MEDIA_TYPE_3TZ",
    "MEMBER", "MEMBER_ROLES", "MEMBERS_EOL", "MEMBERS_SEPARATOR", "PACKAGINGS",
    "SKIP_NAMES", "blend_locator", "canonical_members", "content_digest",
    "content_digest_block", "file_set_stamp_path", "follow_references",
    "is_canonical_3tz", "member_path", "members_canonical", "members_digest",
    "new_datablock_stamp", "new_file_set_stamp", "new_tree_stamp",
    "parse_blend_locator", "same_content", "tree_members", "unclaimed_files",
    "verify_members", "verify_tree",
]
