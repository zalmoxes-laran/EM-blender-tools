'''
Parser autonomo per il formato shift.txt del 3D Survey Collection.

Formato atteso (singola riga, spazi come separatore):
    EPSG::NNNN X Y Z
    EPSG::NNNN X Y        (senza z: z = 0)

Regola di E.D. sulla quota (23 ott 2026): **lo shift Z è 0 per progetto** — le
quote assolute stanno nei vertici dei modelli. Uno shift.txt senza z è quindi
uno shift con z 0, non un file malformato.

Non dipende da 3D-survey-collection installato — parser locale di EMTools.
'''

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ShiftRecord:
    epsg: str
    x: float
    y: float
    z: float

    def format_line(self) -> str:
        return f"EPSG::{self.epsg} {self.x} {self.y} {self.z}\n"


def parse_shift_file(path: str) -> ShiftRecord:
    with open(path, 'r') as f:
        line = f.readline().strip()
    if not line:
        raise ValueError(f"Empty shift file: {path}")
    parts = line.split()
    if len(parts) < 3:
        raise ValueError(
            f"Malformed shift file {path!r}: expected 'EPSG::NNNN X Y [Z]', got {line!r}"
        )
    epsg_token = parts[0].replace('EPSG::', '').replace('EPSG:', '').strip()
    return ShiftRecord(
        epsg=epsg_token,
        x=float(parts[1]),
        y=float(parts[2]),
        # no z: 0, the project rule (heights in the vertices)
        z=float(parts[3]) if len(parts) > 3 else 0.0,
    )


def write_shift_file(path: str, record: ShiftRecord) -> None:
    with open(path, 'w') as f:
        f.write(record.format_line())
