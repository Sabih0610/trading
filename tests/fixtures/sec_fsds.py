"""Owned SEC FSDS-shaped fixtures (fictional values only)."""

from __future__ import annotations

import zipfile
from pathlib import Path

SUB_HEADER = (
    "adsh cik name sic countryba stprba cityba zipba bas1 bas2 baph countryma stprma cityma zipma "
    "mas1 mas2 countryinc stprinc ein former changed afs wksi fye form period fy fp filed accepted "
    "prevrpt detail instance nciks aciks"
).split()
NUM_HEADER = "adsh tag version ddate qtrs uom segments coreg value footnote".split()


def sub_row(adsh: str, cik: int, sic: str, form: str, period: str, filed: str) -> str:
    values = dict.fromkeys(SUB_HEADER, "")
    values.update(adsh=adsh, cik=str(cik), name="OWNED TEST CO", sic=sic, form=form)
    values.update(
        period=period, filed=filed, accepted=f"{filed[:4]}-{filed[4:6]}-{filed[6:]} 06:00:00.0"
    )
    return "\t".join(values[c] for c in SUB_HEADER)


def num_row(adsh: str, tag: str, ddate: str, qtrs: int, value: str, **extra: str) -> str:
    values = dict.fromkeys(NUM_HEADER, "")
    values.update(
        adsh=adsh,
        tag=tag,
        version="us-gaap/2024",
        ddate=ddate,
        qtrs=str(qtrs),
        uom="USD",
        value=value,
    )
    values.update(extra)
    return "\t".join(values[c] for c in NUM_HEADER)


def make_zip(path: Path, subs: list[str], nums: list[str]) -> Path:
    with zipfile.ZipFile(path, "w") as z:
        z.writestr("sub.txt", "\n".join(["\t".join(SUB_HEADER), *subs]) + "\n")
        z.writestr("num.txt", "\n".join(["\t".join(NUM_HEADER), *nums]) + "\n")
    return path
