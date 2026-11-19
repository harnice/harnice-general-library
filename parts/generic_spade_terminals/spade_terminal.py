"""Generic spade terminal chooser. Harness and system build scripts import this file.

Call choose_part(wire_gauge, stud_size, insulation) to get a library part
number that exists. spade_terminal_generator.py is for rewriting the
library only. Never import it. This file reads spade_terminal.csv, which
the generator writes from its tables, the family's one source of truth.

Attach a spade at a flying-lead end the same way as a ring terminal:

    import os
    import sys

    from harnice.lists import instances_list
    from harnice.utils import library_utils

    LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
    LIBRARY_SUBPATH = "parts/generic_spade_terminals/"
    sys.path.append(
        os.path.join(library_utils.get_local_path(LIBRARY_REPO), LIBRARY_SUBPATH)
    )
    import spade_terminal

    for instance in instances_list.read():
        if instance.get("item_type") != "terminal":
            continue
        gauge = instance.get("wire_gauge_awg")
        stud = instance.get("stud_size")
        if not gauge or not stud:
            continue
        instances_list.modify(
            instance.get("instance_name"),
            {
                "mpn": spade_terminal.choose_part(gauge, stud, insulation=True),
                "lib_repo": LIBRARY_REPO,
                "lib_subpath": LIBRARY_SUBPATH,
            },
        )
"""
import csv
import os

LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "parts/generic_spade_terminals/"


def choose_part(wire_gauge, stud_size, insulation=None):
    """Library part number of a spade terminal that exists in this library.

    wire_gauge is 18, "18", "18AWG", or "#18". stud_size is "#8", 8, "No. 8",
    "1/4", "1_4", or "1/4in". insulation is None, False, or "bare" for a bare
    terminal; True for the vinyl color of that gauge band (red 22-18, blue
    16-14, yellow 12-10); or a color name or hex such as "red" or "#FF0000".
    Raises ValueError naming the legal values when nothing matches.
    """
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "spade_terminal.csv"),
        newline="",
        encoding="utf-8",
    ) as f:
        rows = list(csv.DictReader(f))

    gauge = str(wire_gauge).strip().upper().lstrip("#").removesuffix("AWG").strip()
    gauge = str(int(gauge)) if gauge.isdigit() else gauge
    matches = [row for row in rows if row["wire_gauge_awg"] == gauge]
    if not matches:
        legal = sorted({row["wire_gauge_awg"] for row in rows}, key=int, reverse=True)
        raise ValueError(f"No spade terminal for {wire_gauge!r} AWG. Legal AWG: {', '.join(legal)}.")

    stud = str(stud_size).strip().upper().replace(" ", "").replace("_", "/").removesuffix("IN")
    stud = stud.removeprefix("NO.").removeprefix("NO")
    stud = f"#{int(stud.lstrip('#'))}" if stud.lstrip("#").isdigit() else stud
    legal_studs = ", ".join(dict.fromkeys(row["stud_size"] for row in matches))
    matches = [row for row in matches if row["stud_size"] == stud]
    if not matches:
        raise ValueError(f"No spade terminal for {gauge} AWG on a {stud_size!r} stud. Legal studs: {legal_studs}.")

    if insulation is None or insulation is False or str(insulation).strip().lower() in ("bare", "none", ""):
        matches = [row for row in matches if row["insulated"] == "False"]
    elif insulation is True:
        matches = [row for row in matches if row["insulated"] == "True"]
    else:
        wanted = str(insulation).strip().lstrip("#").upper()
        legal = ", ".join(f"{row['insulation_color']} ({row['insulation_hex']})" for row in matches if row["insulated"] == "True")
        matches = [row for row in matches if wanted in (row["insulation_hex"], row["insulation_color"].upper())]
        if not matches:
            raise ValueError(f"The {gauge} AWG spade terminal is sold bare or in {legal}, not {insulation!r}.")

    return matches[0]["library_pn"]
