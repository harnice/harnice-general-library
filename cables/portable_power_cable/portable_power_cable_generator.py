"""Emit portable-power-cable SKUs as Harnice cables.

The catalog and part-number grammar live in portable_power_cable.py.
This file only writes folders. Do not import it from a harness.
"""
import csv
import json
import os
import sys

from harnice import state
from harnice.lists import rev_history

_FAMILY_DIR = os.path.dirname(os.path.abspath(__file__))
if _FAMILY_DIR not in sys.path:
    sys.path.insert(0, _FAMILY_DIR)

import portable_power_cable as ppc

REVISION = "1"
DATE_STARTED = "8/18/26"


def compile_cable_attributes(cfg):
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

    jacket_properties = {
        "voltage": spec["voltage"],
    }
    if spec["jacket_material"]:
        jacket_properties["material"] = spec["jacket_material"]
    if spec["jacket_color"]:
        jacket_properties["color"] = spec["jacket_color"]
    if jacket_in:
        jacket_properties["diameter"] = ppc.fmt_in(jacket_in)

    mcmaster = ppc.mcmaster_part(spec["code"], gauge, n)
    if mcmaster:
        jacket_properties["mcmaster pn"] = mcmaster

    jacket = {"properties": jacket_properties}
    jacket.update(conductors)
    return {"jacket": jacket}


def main():
    def write_family_csv(path=None):
        if path is None:
            path = os.path.join(_FAMILY_DIR, "portable_power_cable.csv")
        rows = [ppc.catalog_row(cfg) for cfg in ppc.iter_part_configurations()]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=ppc.CSV_COLUMNS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    def write_conductor_list(attrs, path):
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
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=headers, delimiter="\t", lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        return len(rows)

    state.set_rev(REVISION)
    state.set_project_type("cable")

    configs = list(ppc.iter_part_configurations())
    print(f"Building {len(configs)} portable power cables in {_FAMILY_DIR}")

    for cfg in configs:
        pn = ppc.make_part_number(cfg)
        mcmaster = ppc.mcmaster_part(cfg["spec"]["code"], cfg["gauge"], cfg["n_conductors"])
        print(f"Preparing cable: {pn}")

        part_dir = os.path.join(_FAMILY_DIR, pn)
        os.makedirs(part_dir, exist_ok=True)

        rev_dir = os.path.join(part_dir, f"rev{REVISION}")
        if os.path.exists(rev_dir):
            for item in os.listdir(rev_dir):
                item_path = os.path.join(rev_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
        else:
            os.makedirs(rev_dir)

        rev_history.part_family_append(
            {
                "project_type": state.project_type,
                "mfg": "McMaster-Carr" if mcmaster else ppc.MANUFACTURER,
                "pn": pn,
                "rev": REVISION,
                "desc": ppc.description_from_cfg(cfg),
                "status": "",
                "datestarted": DATE_STARTED,
                "library_repo": ppc.LIBRARY_REPO,
                "library_subpath": ppc.LIBRARY_SUBPATH,
                "revisionupdates": "INITIAL RELEASE",
            },
            os.path.join(part_dir, f"{pn}-revision_history.tsv"),
        )

        attributes = compile_cable_attributes(cfg)
        json_path = os.path.join(rev_dir, "attributes.json")
        with open(json_path, "w", encoding="utf-8") as handle:
            json.dump(attributes, handle, indent=4)
            handle.write("\n")

        write_conductor_list(attributes, os.path.join(rev_dir, "conductors.tsv"))

    csv_path = write_family_csv()
    print(f"Finished building {len(configs)} portable power cables.")
    print(f"Wrote family catalog: {csv_path}")


if __name__ == "__main__":
    main()
