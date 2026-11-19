"""Rewrites this family's SKUs. Run by hand when the catalog changes.

Library maintenance only. Harness and system scripts never import this
file; they import spade_terminal.py. The catalog's one source of truth is
the tables below: this file writes spade_terminal.csv from them, and the
chooser reads that CSV.

Writes revision history, attributes.json, drawing.svg, and model.step for
each SKU and builds it with `harnice -b`.

    python3 spade_terminal_generator.py [--no-build]

Frame: origin is on the axis where the barrel ends and the neck widens to
the fork, which is where the insulation sleeve ends. The barrel and sleeve
sit in -X, the fork in +X. 3d-mate sits where the stud goes: the center of
the slot's round end, X along the screw into the plate (part -Z), Y along
the body back toward the barrel (part -X), Z across the fork (part +Y). The
drawing is the flat face of the terminal, like the ring drawings.
"""
import csv
import json
import math
import os
import subprocess
import sys

from harnice import fileio, state
from harnice.lists import rev_history
from harnice.utils import cad, step_utils

FAMILY_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FAMILY_DIR)
from spade_terminal import LIBRARY_REPO, LIBRARY_SUBPATH  # noqa: E402

REVISION = "1"
DATE_STARTED = "11/19/26"
MANUFACTURER = ""

# ---------------------------------------------------------------------------
# Catalog: the one source of truth for this family.
# ---------------------------------------------------------------------------

# Wire gauges and the vinyl insulation color sold for each gauge band.
# Every gauge is also sold bare.
GAUGE_BANDS = [
    (["22", "20", "18"], "red", "#FF0000"),
    (["16", "14"], "blue", "#0000FF"),
    (["12", "10"], "yellow", "#FFFF00"),
]

# Studs this family is sold for.
STUDS = ["#4", "#6", "#8", "#10", "1/4"]

# Stud clearance (slot width), inches. estimate: the same values
# generic_ring_terminals uses, typical vinyl and bare copper terminals.
# https://www.mcmaster.com/products/ring-terminals/
STUD_CLEARANCE_IN = {"#4": 0.119, "#6": 0.145, "#8": 0.171, "#10": 0.197, "1/4": 0.265}

# Bare copper wire OD by AWG, inches (ASTM B258 nominal).
AWG_OD_IN = {
    "22": 0.025347, "20": 0.031961, "18": 0.040303, "16": 0.050821,
    "14": 0.064084, "12": 0.080808, "10": 0.101897,
}

PX_PER_IN = 96.0
FLAGNOTE_RADIUS_IN = 3.0
FLAGNOTE_ANGLES = [0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90]
METAL_HEX = "#898989"
CRIMP_SHADE = "rgba(0,0,0,0.15)"
EDGE_HEX = "#777777"


def iter_part_configurations():
    """Yield one dict per legal SKU, with its estimated envelope in inches."""
    for gauges, color, hex_code in GAUGE_BANDS:
        for gauge in gauges:
            for stud in STUDS:
                for insulation in (hex_code, None):
                    stud_id = STUD_CLEARANCE_IN[stud]
                    # estimate: the ring family's formulas, with the ring OD
                    # as the fork width. Replace with a vendor table when one
                    # is used.
                    fork_width = 0.2 * stud_id * stud_id + stud_id + 0.2
                    barrel_od = AWG_OD_IN[gauge] + 0.15
                    yield {
                        "wire_gauge": gauge,
                        "stud_size": stud,
                        "insulation": insulation,
                        "insulation_color": color if insulation else "",
                        "stud_id": stud_id,
                        "fork_width": fork_width,
                        "barrel_od": barrel_od,
                        "overall_length": 2 * barrel_od + fork_width,
                    }


def make_part_number(cfg):
    """SPADE_TERMINAL-{awg}-{stud}[-{insulation hex}], e.g. SPADE_TERMINAL-22-8-FF0000."""
    stud = cfg["stud_size"].lstrip("#").replace("/", "_")
    insulation = f"-{cfg['insulation'].lstrip('#')}" if cfg["insulation"] else ""
    return f"SPADE_TERMINAL-{cfg['wire_gauge']}-{stud}{insulation}"


def description_from_cfg(cfg):
    desc = f"SPADE TERMINAL, {cfg['wire_gauge']} AWG, {cfg['stud_size']} STUD"
    if cfg["insulation"]:
        desc += f", {cfg['insulation_color'].upper()}"
    return desc


# ---------------------------------------------------------------------------
# Geometry, in inches in the part frame (+Y up).
# ---------------------------------------------------------------------------

def stations(cfg):
    """Named x stations along the axis, rear (wire end) to tip."""
    barrel_len = cfg["overall_length"] - cfg["fork_width"]
    x_neck = 0.0  # origin: barrel ends and the neck widens (sleeve end), as marked
    x_rear = -0.75 * barrel_len  # estimate: barrel (wire) end
    x_fork = 0.25 * barrel_len  # fork plate starts
    x_slot = x_rear + cfg["overall_length"] - cfg["fork_width"] / 2  # stud center, where a ring's hole would be
    x_tip = x_rear + cfg["overall_length"]  # fork tip
    assert x_rear < x_neck < x_fork < x_slot < x_tip
    return {"x_rear": x_rear, "x_neck": x_neck, "x_fork": x_fork, "x_slot": x_slot, "x_tip": x_tip}


def shapes_in(cfg):
    """Every filled shape as a closed polygon, in drawing order."""
    s = stations(cfg)
    half_w = cfg["fork_width"] / 2
    barrel_r = cfg["barrel_od"] / 2
    slot_r = cfg["stud_id"] / 2
    chamfer = 0.15 * cfg["fork_width"]  # estimate: rounded-off tine corners

    barrel = [(s["x_rear"], barrel_r), (s["x_neck"], barrel_r), (s["x_neck"], -barrel_r), (s["x_rear"], -barrel_r)]
    slot_bottom = [
        (s["x_slot"] + slot_r * math.cos(math.radians(a)), slot_r * math.sin(math.radians(a)))
        for a in range(90, 271, 10)
    ]
    # Neck and fork are one plate, so no seam shows where they meet.
    plate = (
        [(s["x_neck"], barrel_r), (s["x_fork"], half_w), (s["x_tip"] - chamfer, half_w),
         (s["x_tip"], half_w - chamfer), (s["x_tip"], slot_r)]
        + slot_bottom
        + [(s["x_tip"], -slot_r), (s["x_tip"], -half_w + chamfer), (s["x_tip"] - chamfer, -half_w),
           (s["x_fork"], -half_w), (s["x_neck"], -barrel_r)]
    )
    shapes = [("barrel", barrel), ("plate", plate)]
    if cfg["insulation"]:
        pad = 0.025  # estimate: sleeve wall, as on the ring drawings
        x0, x1 = s["x_rear"] - 0.04, s["x_neck"]  # sleeve overhangs the barrel end, as on the rings
        shapes.append(("sleeve", [(x0, barrel_r + pad), (x1, barrel_r + pad), (x1, -barrel_r - pad), (x0, -barrel_r - pad)]))
    return shapes


PLATE_THICKNESS_IN = 0.03  # estimate: typical stamped copper spade


def write_model(path, pn, cfg):
    """model.step from the same outline the drawing uses.

    The drawing is the flat face, so the plate (neck and fork, slot
    included) is that outline extruded through its thickness, centered on
    the axis. The barrel, or the sleeve on an insulated part, is the barrel
    revolved about +X. Pieces are combined the way cad.save_step combines
    device bodies.
    """
    triangles = []
    for name, points in shapes_in(cfg):
        if name == "plate":
            model = cad.new()
            cad.sketch(
                model,
                "plate",
                "right",
                {f"p{i}": point for i, point in enumerate(points)},
                [(f"p{i}", f"p{(i + 1) % len(points)}") for i in range(len(points))],
            )
            body = cad.extrude(model, "plate", PLATE_THICKNESS_IN)
            half = PLATE_THICKNESS_IN / 2
            triangles += [
                tuple((x * 25.4, y * 25.4, (z - half) * 25.4) for x, y, z in tri) for tri in body.triangles
            ]
        elif name == "sleeve" or (name == "barrel" and not cfg["insulation"]):
            x0 = min(x for x, _ in points)
            x1 = max(x for x, _ in points)
            radius = max(y for _, y in points)
            triangles += step_utils.revolution_triangles([(x0 * 25.4, radius * 25.4), (x1 * 25.4, radius * 25.4)])
    step_utils.write_step_file(path, pn, triangles)


# The only place inches turn into SVG px and the only place y flips.
def svg_points(points):
    return " ".join(f"{x * PX_PER_IN:.3f},{-y * PX_PER_IN:.3f}" for x, y in points)


def spade_terminal_svg(pn, cfg):
    s = stations(cfg)
    barrel_r = cfg["barrel_od"] / 2
    els = []
    for name, points in shapes_in(cfg):
        fill = cfg["insulation"] if name == "sleeve" else METAL_HEX
        els.append(f'<polygon points="{svg_points(points)}" fill="{fill}"/>')
    if not cfg["insulation"]:
        # Crimp bands and the open barrel end, as on the bare ring terminals.
        barrel_len = s["x_neck"] - s["x_rear"]
        band = 0.15 * barrel_len
        for x0 in (s["x_rear"] + 0.1 * barrel_len, s["x_rear"] + 0.9 * barrel_len - band):
            box = [(x0, barrel_r), (x0 + band, barrel_r), (x0 + band, -barrel_r), (x0, -barrel_r)]
            els.append(f'<polygon points="{svg_points(box)}" fill="{CRIMP_SHADE}"/>')
            for y in (barrel_r, -barrel_r):
                els.append(f'<polyline points="{svg_points([(x0, y), (x0 + band, y)])}" fill="none" stroke="{EDGE_HEX}" stroke-width="0.8"/>')
        els.append(
            f'<ellipse cx="{s["x_rear"] * PX_PER_IN:.3f}" cy="0" rx="2" ry="{barrel_r * PX_PER_IN:.3f}" '
            f'fill="#6a6a6a" stroke="{EDGE_HEX}" stroke-width="0.5"/>'
        )
    content = "\n    ".join(els)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="400" height="400">\n'
        f'  <g id="{pn}-drawing-contents-start">\n'
        f"    {content}\n"
        "  </g>\n"
        f'  <g id="{pn}-drawing-contents-end">\n'
        "  </g>\n"
        "</svg>\n"
    )


def build_csys_children(cfg):
    """3d-mate where the stud goes. Polar flagnotes about the origin.

    Each leader lands where its ray from the origin last leaves any shape,
    which is the outline of the whole terminal.
    """
    edges = []
    for _, points in shapes_in(cfg):
        edges += list(zip(points, points[1:] + points[:1]))

    def farthest_crossing(angle_deg):
        dx, dy = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
        best = 0.0
        for (x1, y1), (x2, y2) in edges:
            ex, ey = x2 - x1, y2 - y1
            denom = dx * ey - dy * ex
            if abs(denom) < 1e-12:
                continue
            t = (x1 * ey - y1 * ex) / denom
            u = (x1 * dy - y1 * dx) / denom
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = max(best, t)
        return best

    children = {
        # Center of the slot's round end. R = Rx(-90)·Ry(0)·Rz(90) turns the
        # mate's X down the screw axis into the plate (part -Z), its Y along
        # the body back toward the barrel (part -X), and its Z across the
        # fork (part +Y).
        "3d-mate": {"x": round(stations(cfg)["x_slot"], 4), "y": 0.0, "z": 0.0, "rx": -90.0, "ry": 0.0, "rz": 90.0},
    }
    for i, angle in enumerate(FLAGNOTE_ANGLES, start=1):
        children[f"flagnote-{i}"] = {"angle": angle, "distance": FLAGNOTE_RADIUS_IN, "rotation": 0}
        children[f"flagnote-{i}-leader_dest"] = {
            "angle": angle, "distance": round(farthest_crossing(angle), 4), "rotation": 0,
        }
    return children


def compile_part_attributes(cfg):
    return {
        "wire_gauge_awg": cfg["wire_gauge"],
        "stud_size": cfg["stud_size"],
        "insulation_color": cfg["insulation"],
        "insulated": cfg["insulation"] is not None,
        "stud_hole_id": round(cfg["stud_id"], 4),
        "fork_width": round(cfg["fork_width"], 4),
        "width": round(cfg["fork_width"], 4),
        "barrel_od": round(cfg["barrel_od"], 4),
        "overall_length": round(cfg["overall_length"], 4),
        "barrel_material": "copper",
        "plating": "tin",
        "insulation_material": "vinyl" if cfg["insulation"] else None,
        "tools": ["generic spade terminal crimp tool 10awg-22awg"],
        "build_notes": [],
        "csys_children": build_csys_children(cfg),
    }


CSV_COLUMNS = (
    "library_pn",
    "wire_gauge_awg",
    "stud_size",
    "insulated",
    "insulation_color",
    "insulation_hex",
    "stud_hole_id_in",
    "fork_width_in",
    "barrel_od_in",
    "overall_length_in",
    "notes",
)


def catalog_row(cfg):
    return {
        "library_pn": make_part_number(cfg),
        "wire_gauge_awg": cfg["wire_gauge"],
        "stud_size": cfg["stud_size"],
        "insulated": cfg["insulation"] is not None,
        "insulation_color": cfg["insulation_color"],
        "insulation_hex": (cfg["insulation"] or "").lstrip("#"),
        "stud_hole_id_in": round(cfg["stud_id"], 4),
        "fork_width_in": round(cfg["fork_width"], 4),
        "barrel_od_in": round(cfg["barrel_od"], 4),
        "overall_length_in": round(cfg["overall_length"], 4),
        "notes": "estimate: dimensions from the generic_ring_terminals formulas",
    }


def progress_bar(i, n, width=30):
    done = round(width * i / n)
    return f"[{'#' * done}{'.' * (width - done)}] {i}/{n}"


def main(build=True):
    state.set_rev(REVISION)
    state.set_project_type("part")

    # part_family_append asks git and drawnby.json on every SKU. Ask once.
    harnice_version = fileio.harnice_version()
    drawnby = fileio.drawnby()
    fileio.harnice_version = lambda: harnice_version
    fileio.drawnby = lambda: drawnby

    variants = list(iter_part_configurations())
    with open(os.path.join(FAMILY_DIR, "spade_terminal.csv"), "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(catalog_row(cfg) for cfg in variants)

    for i, cfg in enumerate(variants, start=1):
        pn = make_part_number(cfg)
        part_dir = os.path.join(FAMILY_DIR, pn)
        rev_dir = os.path.join(part_dir, f"rev{REVISION}")
        os.makedirs(rev_dir, exist_ok=True)
        rev_history.part_family_append(
            {
                "project_type": "part",
                "mfg": MANUFACTURER,
                "pn": pn,
                "rev": REVISION,
                "desc": description_from_cfg(cfg),
                "status": "",
                "datestarted": DATE_STARTED,
                "library_repo": LIBRARY_REPO,
                "library_subpath": LIBRARY_SUBPATH,
            },
            os.path.join(part_dir, f"{pn}-revision_history.tsv"),
        )
        with open(os.path.join(rev_dir, "attributes.json"), "w", encoding="utf-8") as f:
            json.dump(compile_part_attributes(cfg), f, indent=2)
            f.write("\n")
        with open(os.path.join(rev_dir, "drawing.svg"), "w", encoding="utf-8") as f:
            f.write(spade_terminal_svg(pn, cfg))
        write_model(os.path.join(rev_dir, "model.step"), pn, cfg)
        if build:
            # Always harnice -b from the revision folder. Errors stop the run.
            subprocess.run(["harnice", "-b"], cwd=rev_dir, check=True)
        print(progress_bar(i, len(variants)))


if __name__ == "__main__":
    main(build="--no-build" not in sys.argv)
