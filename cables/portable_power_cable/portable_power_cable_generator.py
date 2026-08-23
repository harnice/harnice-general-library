"""Emit portable-power-cable SKUs as Harnice cables.

The catalog, legality filter and part-number grammar live in
portable_power_cable.py. This file only writes folders. Do not import it
from a harness.

Cables have no drawing/STEP. Each SKU is attributes JSON plus a conductor
list walked from the nested jacket -> conductor tree.
"""

from __future__ import annotations

import csv
import json
import os
import sys

from harnice import fileio, state
from harnice.lists import rev_history

_FAMILY_DIR = os.path.dirname(os.path.abspath(__file__))
if _FAMILY_DIR not in sys.path:
    sys.path.insert(0, _FAMILY_DIR)

import portable_power_cable as ppc  # noqa: E402

REVISION = "1"
DATE_STARTED = "8/18/26"
LIBRARY_REPO = ppc.LIBRARY_REPO
LIBRARY_SUBPATH = ppc.LIBRARY_SUBPATH


def compile_cable_attributes(cfg: dict) -> dict:
    spec = cfg["spec"]
    gauge = cfg["gauge"]
    n = cfg["n_conductors"]
    insulation_in = spec["insulation_in"](gauge)
    jacket_in = spec["jacket_in"](gauge)

    conductors = {}
    for color in ppc.CONDUCTOR_COLORS[n]:
        conductors[color] = {
            "conductor": True,
            "properties": {
                "insulation material": spec["insulation_material"],
                "od": ppc.insulated_od(gauge, insulation_in),
                "gauge": f"{gauge}AWG",
                "construction": ppc.CLASS_K_STRANDING[gauge],
                "material": "copper",
            },
            "appearance": ppc.conductor_appearance(color),
        }
        if spec.get("oil_resistant_insulation"):
            conductors[color]["properties"]["oil resistant"] = True

    jacket_properties = {
        "construction": spec["construction"],
        "voltage": spec["voltage"],
        "usage": spec["usage"],
        "type": spec["code"],
        "jacketed": spec["jacketed"],
    }
    if spec["jacket_material"]:
        jacket_properties["material"] = spec["jacket_material"]
    if spec["jacket_color"]:
        jacket_properties["color"] = spec["jacket_color"]
    if jacket_in:
        jacket_properties["thickness"] = ppc.fmt_in(jacket_in)
    for flag in (
        "oil_resistant_jacket",
        "oil_resistant_insulation",
        "weather_resistant",
    ):
        if spec.get(flag):
            jacket_properties[flag.replace("_", " ")] = True

    mcmaster = ppc.mcmaster_part(spec["code"], gauge, n)
    if mcmaster:
        jacket_properties["mcmaster pn"] = mcmaster["pn"]
        jacket_properties["mcmaster designation"] = mcmaster["designation"]
        jacket_properties["mcmaster url"] = mcmaster["url"]

    return {"jacket": {**{"properties": jacket_properties}, **conductors}}


def write_catalog_csv(path=None):
    if path is None:
        path = os.path.join(_FAMILY_DIR, "portable_power_cable.csv")
    rows = [ppc.catalog_row(cfg) for cfg in ppc.iter_part_configurations()]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=ppc.CATALOG_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


def write_conductor_list(attrs: dict, path: str) -> int:
    """Walk the attributes tree the same way harnice.project_types.cable.build does."""
    rows = []
    all_headers = {"appearance"}

    def recurse(obj, parent_chain=None):
        if parent_chain is None:
            parent_chain = []
        if isinstance(obj, dict):
            if obj.get("conductor") is True:
                props = obj.get("properties", {})
                appearance = obj.get("appearance", {})
                container = parent_chain[-2] if len(parent_chain) >= 2 else ""
                identifier = parent_chain[-1] if len(parent_chain) >= 1 else ""
                row = {"container": container, "identifier": identifier}
                for k, v in props.items():
                    row[k] = v
                    all_headers.add(k)
                row["appearance"] = (
                    json.dumps(
                        appearance, separators=(",", ":"), ensure_ascii=False
                    ).replace('"', "'")
                    if appearance
                    else ""
                )
                rows.append(row)
            for k, v in obj.items():
                if isinstance(v, (dict, list)):
                    recurse(v, parent_chain + [k])
        elif isinstance(obj, list):
            for item in obj:
                recurse(item, parent_chain)

    recurse(attrs)
    headers = ["container", "identifier"] + sorted(all_headers)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=headers, delimiter="\t", lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return len(rows)


def revision_history_row(cfg, mcmaster):
    return {
        "project_type": state.project_type,
        "mfg": "McMaster-Carr" if mcmaster else ppc.MANUFACTURER,
        "pn": ppc.make_part_number(cfg),
        "rev": REVISION,
        "desc": ppc.description_from_cfg(cfg),
        "status": "",
        "datestarted": DATE_STARTED,
        "library_repo": LIBRARY_REPO,
        "library_subpath": LIBRARY_SUBPATH,
        "revisionupdates": "INITIAL RELEASE",
    }


def _progress_bar(done, total, width=25):
    if total <= 0:
        filled = width
        pct = 100
    else:
        filled = min(width, max(0, round(width * done / total)))
        pct = round(100.0 * done / total)
    cells = ["x"] * filled + ["."] * (width - filled)
    return "[ " + " ".join(cells) + f" ] ({pct}%)"


def cache_run_constant_lookups():
    git_hash = fileio.get_git_hash_of_harnice_src()
    drawnby = fileio.drawnby()
    fileio.get_git_hash_of_harnice_src = lambda: git_hash
    fileio.drawnby = lambda: drawnby


def main(csv_only=False):
    state.set_rev(REVISION)
    state.set_project_type("cable")

    csv_path = write_catalog_csv()
    print(f"Wrote catalog: {csv_path}")
    if csv_only:
        return

    cache_run_constant_lookups()
    configs = list(ppc.iter_part_configurations())
    total = len(configs)
    with_mcmaster = 0
    print(f"Building {total} portable power cables in {_FAMILY_DIR}")

    for i, cfg in enumerate(configs, start=1):
        pn = ppc.make_part_number(cfg)
        mcmaster = ppc.mcmaster_part(
            cfg["spec"]["code"], cfg["gauge"], cfg["n_conductors"]
        )
        print(f"Preparing cable: {pn}" + (f" ({mcmaster['pn']})" if mcmaster else ""))
        if mcmaster:
            with_mcmaster += 1

        part_dir = os.path.join(_FAMILY_DIR, pn)
        os.makedirs(part_dir, exist_ok=True)
        rev_dir = os.path.join(part_dir, f"{pn}-rev{REVISION}")
        if os.path.exists(rev_dir):
            for item in os.listdir(rev_dir):
                item_path = os.path.join(rev_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
        else:
            os.makedirs(rev_dir)

        rev_history.part_family_append(
            revision_history_row(cfg, mcmaster),
            os.path.join(part_dir, f"{pn}-revision_history.tsv"),
        )

        attributes = compile_cable_attributes(cfg)
        json_path = os.path.join(rev_dir, f"{pn}-rev{REVISION}-attributes.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(attributes, f, indent=4)
            f.write("\n")

        tsv_path = os.path.join(rev_dir, f"{pn}-rev{REVISION}-conductor_list.tsv")
        write_conductor_list(attributes, tsv_path)
        print(_progress_bar(i, total))

    print(
        f"Finished building {total} portable power cables "
        f"({with_mcmaster} with McMaster-Carr part numbers)."
    )


if __name__ == "__main__":
    main(csv_only="--csv-only" in sys.argv)
