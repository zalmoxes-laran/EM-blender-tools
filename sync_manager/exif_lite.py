"""L1 · who took a photo and when: its EXIF header, read without a library.

The lot rule (E.D., 3 October 2026, evening) proposes a lot only for the photos
of ONE SESSION — same camera, contiguous EXIF times — so the inventory needs the
camera and the time of every photo it lists. Blender's Python carries no Pillow,
and the frozen bridge of EMStudio neither: this reads the two places a camera
writes them (a JPEG's APP1 segment, the first IFDs of a TIFF-based raw — DNG,
CR2, NEF, ARW…), never the image. The same reader as EMStudio's
`tools/em_bridge.py::_photo_exif`.

Pure: no `bpy`. Measured by `tests/test_inventory.py` on photos whose EXIF was
written by Pillow.
"""

_EXIF_PHOTO_EXT = (".jpg", ".jpeg", ".tif", ".tiff", ".dng", ".cr2", ".nef",
                   ".arw", ".orf", ".rw2", ".raf")


def photo_exif(path):
    """L1 · a photo's camera and time from its EXIF, without a library.

    → ``{"camera": "<make> <model>[ #<serial>]", "taken_at": "YYYY:MM:DD HH:MM:SS"}``
    with None where the file says nothing, or None for a file that is not a
    photo this reads (JPEG's APP1, or a TIFF-based raw: DNG, CR2, NEF, ARW…).
    Reads the header only, never the image."""
    import struct

    if not str(path).lower().endswith(_EXIF_PHOTO_EXT):
        return None
    try:
        with open(path, "rb") as fh:
            head = fh.read(4)
            if head[:2] == b"\xff\xd8":
                fh.seek(2)
                tiff = None
                for _ in range(64):
                    marker = fh.read(2)
                    if len(marker) < 2 or marker[0] != 0xFF or marker[1] in (0xDA, 0xD9):
                        break
                    size = struct.unpack(">H", fh.read(2))[0]
                    data = fh.read(size - 2)
                    if marker[1] == 0xE1 and data[:6] == b"Exif\x00\x00":
                        tiff = data[6:]
                        break
                if tiff is None:
                    return None
            elif head in (b"II*\x00", b"MM\x00*"):
                fh.seek(0)
                tiff = fh.read(1 << 20)
            else:
                return None
    except OSError:
        return None
    if len(tiff) < 8 or tiff[:2] not in (b"II", b"MM"):
        return None
    end = "<" if tiff[:2] == b"II" else ">"

    def ifd(offset):
        out = {}
        if offset <= 0 or offset + 2 > len(tiff):
            return out
        count = struct.unpack(end + "H", tiff[offset:offset + 2])[0]
        for k in range(min(count, 512)):
            at = offset + 2 + 12 * k
            if at + 12 > len(tiff):
                break
            tag, kind, n = struct.unpack(end + "HHI", tiff[at:at + 8])
            raw = tiff[at + 8:at + 12]
            if kind == 2:                                   # ASCII
                if n > 4:
                    ptr = struct.unpack(end + "I", raw)[0]
                    raw = tiff[ptr:ptr + n]
                out[tag] = raw[:n].split(b"\x00", 1)[0].decode("latin-1").strip()
            elif kind == 4:                                 # LONG
                out[tag] = struct.unpack(end + "I", raw)[0]
        return out

    zero = ifd(struct.unpack(end + "I", tiff[4:8])[0])
    sub = ifd(zero[0x8769]) if isinstance(zero.get(0x8769), int) else {}
    make, model = str(zero.get(0x010F) or ""), str(zero.get(0x0110) or "")
    if make and model.lower().startswith(make.lower()):
        make = ""                                  # «Canon Canon EOS R5»
    camera = " ".join(x for x in (make, model) if x).strip()
    serial = str(sub.get(0xA431) or "").strip()
    if camera and serial:
        camera = f"{camera} #{serial}"
    taken = str(sub.get(0x9003) or zero.get(0x0132) or "").strip()
    return {"camera": camera or None, "taken_at": taken or None}
