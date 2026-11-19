"""Generic ferrule chooser. Harness and system build scripts import this file.

Call choose_part(wire_gauge) to get a library part number that exists.
ferrule_generator.py is for rewriting the library only. Never import it.
The catalog's one source of truth is ferrule.csv, next to this file.

    import os
    import sys

    from harnice.lists import instances_list
    from harnice.utils import library_utils

    LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
    LIBRARY_SUBPATH = "parts/generic_ferrules/"
    sys.path.append(
        os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH)
    )
    import ferrule

    for instance in instances_list.read():
        if instance.get("item_type") != "terminal":
            continue
        gauge = instance.get("wire_gauge_awg")
        if not gauge:
            continue
        instances_list.modify(
            instance.get("instance_name"),
            {
                "mpn": ferrule.choose_part(gauge),
                "lib_repo": LIBRARY_REPO,
                "lib_subpath": LIBRARY_SUBPATH,
            },
        )
"""
import csv
import os

LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "parts/generic_ferrules/"


def choose_part(wire_gauge, insulation=None):
    """Library part number of the ferrule for one wire gauge.

    wire_gauge is 18, "18", "18AWG", or "#18". insulation is optional: a
    color name or hex such as "red", "FF0000", or "#FF0000". Each gauge is
    sold in one collar color, so a different color raises. Raises ValueError
    naming the legal values when nothing matches.
    """
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "ferrule.csv"),
        newline="",
        encoding="utf-8",
    ) as f:
        rows = list(csv.DictReader(f))

    gauge = str(wire_gauge).strip().upper().lstrip("#").removesuffix("AWG").strip()
    matches = [row for row in rows if gauge.isdigit() and row["wire_gauge_awg"] == str(int(gauge))]
    if not matches:
        raise ValueError(
            f"No ferrule for {wire_gauge!r} AWG. Legal AWG: "
            f"{', '.join(row['wire_gauge_awg'] for row in rows)}."
        )

    if insulation is not None:
        wanted = str(insulation).strip().lstrip("#").upper()
        legal = ", ".join(f"{row['insulation_color']} ({row['insulation_hex']})" for row in matches)
        matches = [row for row in matches if wanted in (row["insulation_hex"], row["insulation_color"].upper())]
        if not matches:
            raise ValueError(f"The {gauge} AWG ferrule is sold in {legal}, not {insulation!r}.")

    return matches[0]["library_pn"]
