"""Emit generic ring-terminal SKUs as Harnice parts.

The catalog, legality filter and part-number grammar live in ring_terminal.py.
This file only writes folders. Do not import it from a harness.

Origin is the barrel (cable) end on the axis; +X toward the ring / stud.
Same cable-side convention as the aerospace library. csys_children["3d-mate"]
sits on the ring tip.

Ring OD and overall length are estimates (see ring_od_from_stud /
overall_length_from_wire), not manufacturer callouts.
"""

from __future__ import annotations

import csv
import json
import math
import os
import sys

from harnice import fileio, state
from harnice.lists import rev_history
import harnice.project_types.part as part

_FAMILY_DIR = os.path.dirname(os.path.abspath(__file__))
if _FAMILY_DIR not in sys.path:
    sys.path.insert(0, _FAMILY_DIR)

import ring_terminal  # noqa: E402

REVISION = "1"
DATE_STARTED = "2/16/26"
LIBRARY_REPO = ring_terminal.LIBRARY_REPO
LIBRARY_SUBPATH = ring_terminal.LIBRARY_SUBPATH
MANUFACTURER = ring_terminal.MANUFACTURER

PX_PER_IN = 96.0
MM_PER_IN = 25.4
FLAGNOTE_RADIUS_IN = 3.0
FLAGNOTE_PADDING_IN = 0.04
FLAGNOTE_ANGLES_DEG = (
    0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90
)
delete_pngs = True


def _load_step_utils():
    try:
        from harnice.utils import step_utils as module
        return module
    except ImportError:
        pass
    import importlib.util

    sibling = os.path.normpath(
        os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "..",
            "..",
            "..",
            "Harnice",
            "src",
            "harnice",
            "utils",
            "step_utils.py",
        )
    )
    spec = importlib.util.spec_from_file_location("harnice_step_utils", sibling)
    if spec is None or spec.loader is None:
        raise ImportError(
            "Generating STEP envelopes requires harnice.utils.step_utils "
            "(Harnice src/harnice/utils/step_utils.py)."
        )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


step_utils = _load_step_utils()


def csys_6dof(x, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
    """Child csys pose in inches/degrees relative to the part origin."""
    return {
        "x": round(float(x), 4),
        "y": round(float(y), 4),
        "z": round(float(z), 4),
        "rx": round(float(rx), 4),
        "ry": round(float(ry), 4),
        "rz": round(float(rz), 4),
    }


def mate_csys_3d(overall_length: float):
    """Ring tip in the part frame. Origin is the barrel (cable) end."""
    return csys_6dof(overall_length)


# estimate: typical vinyl / bare copper tongue, not a manufacturer table.
def ring_od_from_stud(stud_id: float) -> float:
    return 0.2 * stud_id * stud_id + stud_id + 0.2


# estimate: barrel length ~ 2x shank OD plus the ring.
def overall_length_from_wire(barrel_od: float, ring_od: float) -> float:
    return 2 * barrel_od + ring_od


def dimensions_from_cfg(cfg: dict) -> dict:
    stud_id = ring_terminal.STUD_SIZES[cfg["stud_size"]]
    wire_od = ring_terminal.AWG_OD[cfg["wire_gauge"]]
    ring_od = ring_od_from_stud(stud_id)
    barrel_od = wire_od + 0.15  # estimate: shank over wire
    length = overall_length_from_wire(barrel_od, ring_od)
    return {
        "stud_hole_id": round(stud_id, 4),
        "ring_od": round(ring_od, 4),
        "barrel_od": round(barrel_od, 4),
        "overall_length": round(length, 4),
    }


def part_perimeter_inches(ring_od: float, barrel_od: float, overall_length: float):
    """Side-view silhouette; origin at the barrel end, +X toward the ring."""
    ring_r = ring_od / 2.0
    barrel_r = barrel_od / 2.0
    barrel_len = max(0.0, overall_length - ring_od)
    rcx = overall_length - ring_r
    attach = math.atan2(barrel_r, ring_r)
    n_arc = 16
    pts = [
        (0.0, -barrel_r),
        (0.0, barrel_r),
        (barrel_len, barrel_r),
        (rcx - ring_r * math.cos(attach), ring_r * math.sin(attach)),
    ]
    span = 2.0 * (math.pi - attach)
    for i in range(1, n_arc):
        ang = (math.pi - attach) - span * i / n_arc
        pts.append((rcx + ring_r * math.cos(ang), ring_r * math.sin(ang)))
    pts += [
        (rcx - ring_r * math.cos(attach), -ring_r * math.sin(attach)),
        (barrel_len, -barrel_r),
        (0.0, -barrel_r),
    ]
    return pts


def _ray_edge_intersection_t(origin, angle_rad, p0, p1, eps=1e-9):
    ox, oy = origin
    dx, dy = math.cos(angle_rad), math.sin(angle_rad)
    ex, ey = p1[0] - p0[0], p1[1] - p0[1]
    det = dx * ey - dy * ex
    if abs(det) < eps:
        return None
    rx, ry = p0[0] - ox, p0[1] - oy
    t = (rx * ey - ry * ex) / det
    u = (rx * dy - ry * dx) / det
    if t < -eps or u < -eps or u > 1 + eps:
        return None
    return max(0.0, t)


def _ray_perimeter_exit_distance(origin, angle_deg, perimeter):
    if perimeter[0] != perimeter[-1]:
        perimeter = perimeter + [perimeter[0]]
    angle_rad = math.radians(angle_deg)
    hits = []
    for i in range(len(perimeter) - 1):
        t = _ray_edge_intersection_t(origin, angle_rad, perimeter[i], perimeter[i + 1])
        if t is not None and t > 1e-6:
            hits.append(t)
    if not hits:
        return None
    return max(hits)


def build_csys_children(ring_od, overall_length, barrel_od):
    """Polar flagnotes about the cable-end origin; 3d-mate at the ring tip."""
    perimeter = part_perimeter_inches(ring_od, barrel_od, overall_length)
    note_r = max(FLAGNOTE_RADIUS_IN, overall_length + 0.5)
    children = {"3d-mate": mate_csys_3d(overall_length)}
    for i, angle in enumerate(FLAGNOTE_ANGLES_DEG, start=1):
        dest = _ray_perimeter_exit_distance((0.0, 0.0), angle, perimeter)
        if dest is None:
            dest = overall_length
        children[f"flagnote-{i}"] = {
            "angle": angle,
            "distance": round(note_r, 4),
            "rotation": 0,
        }
        children[f"flagnote-{i}-leader_dest"] = {
            "angle": angle,
            "distance": round(dest + FLAGNOTE_PADDING_IN, 4),
            "rotation": 0,
        }
    return children


def compile_part_attributes(cfg: dict) -> dict:
    dims = dimensions_from_cfg(cfg)
    color_name = ring_terminal.insulation_color_name(cfg["insulation"])
    return {
        "tools": ["crimp tool"],
        "build_notes": [],
        "csys_children": build_csys_children(
            dims["ring_od"], dims["overall_length"], dims["barrel_od"]
        ),
        "wire_gauge_awg": cfg["wire_gauge"],
        "stud_size": cfg["stud_size"],
        "insulation_color": color_name,
        "insulated": color_name is not None,
        "stud_hole_id": dims["stud_hole_id"],
        "ring_od": dims["ring_od"],
        "barrel_od": dims["barrel_od"],
        "overall_length": dims["overall_length"],
        "barrel_material": "copper",
        "plating": "tin",
        "insulation_material": "vinyl" if color_name else None,
    }


def envelope_stations_mm(dims: dict):
    """(x_mm, radius_mm) stations from the cable end. estimate: mushroom envelope."""
    barrel_r = dims["barrel_od"] / 2.0 * MM_PER_IN
    ring_r = dims["ring_od"] / 2.0 * MM_PER_IN
    barrel_len = max(0.0, dims["overall_length"] - dims["ring_od"]) * MM_PER_IN
    overall = dims["overall_length"] * MM_PER_IN
    return [
        (0.0, barrel_r),
        (barrel_len, barrel_r),
        (barrel_len, ring_r),
        (overall, ring_r),
    ]


def write_part_step(rev_dir, part_number, dims):
    path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-model.step")
    step_utils.write_revolution_step(
        path,
        part_number,
        envelope_stations_mm(dims),
        description=f"{part_number} low-fidelity envelope",
    )
    return path


def ring_terminal_svg(part_number: str, dims: dict, insulation: str | None) -> str:
    """Side view. Origin is the barrel (cable) end; +X toward the ring tip.

    400x400, 96 px = 1 inch; store +Y up; emit SVG y as -y via the part build.
    """
    stud_id = dims["stud_hole_id"]
    ring_od = dims["ring_od"]
    barrel_od = dims["barrel_od"]
    overall_length = dims["overall_length"]
    ring_r = ring_od / 2
    hole_r = stud_id / 2
    barrel_r = barrel_od / 2
    barrel_len = overall_length - ring_od
    scale = PX_PER_IN

    rcx = (overall_length - ring_r) * scale
    rcy = 0
    bx1 = 0
    bx2 = barrel_len * scale
    by1 = -barrel_r * scale
    bh = barrel_od * scale
    crimp_w = barrel_len * 0.15
    c1x = barrel_len * scale * 0.1
    c2x = bx2 - barrel_len * scale * 0.1 - crimp_w * scale
    ang = math.atan2(barrel_r, ring_r)
    taper_dx = ring_r * scale * math.cos(ang)
    taper_dy = ring_r * scale * math.sin(ang)

    els: list[str] = []
    els.append(
        f'<rect x="{bx1:.2f}" y="{by1:.2f}" '
        f'width="{bx2 - bx1 + 2:.2f}" height="{bh:.2f}" '
        f'fill="#898989" rx="2"/>'
    )
    pts = (
        f"{rcx - taper_dx:.2f},{rcy - taper_dy:.2f} "
        f"{bx2:.2f},{by1:.2f} "
        f"{bx2:.2f},{by1 + bh:.2f} "
        f"{rcx - taper_dx:.2f},{rcy + taper_dy:.2f}"
    )
    els.append(f'<polygon points="{pts}" fill="#898989"/>')
    els.append(
        f'<circle cx="{rcx:.2f}" cy="{rcy:.2f}" '
        f'r="{ring_r * scale:.2f}" fill="#898989"/>'
    )
    if insulation is not None:
        ins_pad = 0.15 * scale / 6
        ins_x = bx1 - 4
        ins_y = by1 - ins_pad
        ins_h = bh + ins_pad * 2
        ins_w = (c2x + crimp_w * scale / 2) - ins_x
        els.append(
            f'<rect x="{ins_x:.2f}" y="{ins_y:.2f}" '
            f'width="{ins_w:.2f}" height="{ins_h:.2f}" '
            f'fill="{insulation}"/>'
        )
    els.append(
        f'<circle cx="{rcx:.2f}" cy="{rcy:.2f}" '
        f'r="{hole_r * scale:.2f}" fill="#ffffff" '
        f'stroke="#666666" stroke-width="0.5"/>'
    )
    if insulation is None:
        for cx in (c1x, c2x):
            cw = crimp_w * scale
            els.append(
                f'<rect x="{cx:.2f}" y="{by1:.2f}" '
                f'width="{cw:.2f}" height="{bh:.2f}" '
                f'fill="rgba(0,0,0,0.15)" rx="1"/>'
            )
            for y in (by1, by1 + bh):
                els.append(
                    f'<line x1="{cx:.2f}" y1="{y:.2f}" '
                    f'x2="{cx + cw:.2f}" y2="{y:.2f}" '
                    f'stroke="#777777" stroke-width="0.8"/>'
                )
        els.append(
            f'<ellipse cx="{bx1:.2f}" cy="{rcy:.2f}" '
            f'rx="2" ry="{barrel_r * scale:.2f}" '
            f'fill="#6a6a6a" stroke="#777777" stroke-width="0.5"/>'
        )
    for dx, dy in [(3, 0), (0, 3)]:
        els.append(
            f'<line x1="{rcx - dx:.2f}" y1="{rcy - dy:.2f}" '
            f'x2="{rcx + dx:.2f}" y2="{rcy + dy:.2f}" '
            f'stroke="#bbbbbb" stroke-width="0.5"/>'
        )
    content = "\n    ".join(els)
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>\n'
        f'<svg xmlns="http://www.w3.org/2000/svg" version="1.1"'
        f' width="400" height="400">\n'
        f'<g id="{part_number}-drawing-contents-start">\n'
        f'    {content}\n'
        f'</g>\n'
        f'<g id="{part_number}-drawing-contents-end">\n'
        f'</g>\n'
        f'</svg>'
    )


def revision_history_row(cfg):
    return {
        "project_type": state.project_type,
        "mfg": MANUFACTURER,
        "pn": ring_terminal.make_part_number(cfg),
        "rev": REVISION,
        "desc": ring_terminal.description_from_cfg(cfg),
        "status": "",
        "datestarted": DATE_STARTED,
        "library_repo": LIBRARY_REPO,
        "library_subpath": LIBRARY_SUBPATH,
    }


def write_catalog_csv(path=None):
    if path is None:
        path = os.path.join(_FAMILY_DIR, "ring_terminal.csv")
    rows = [
        ring_terminal.catalog_row(cfg)
        for cfg in ring_terminal.iter_part_configurations()
    ]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle, fieldnames=ring_terminal.CATALOG_COLUMNS, lineterminator="\n"
        )
        writer.writeheader()
        writer.writerows(rows)
    return path


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


def build_part(part_number, rev_dir):
    cwd = os.getcwd()
    os.chdir(rev_dir)
    try:
        state.set_pn(part_number)
        state.set_rev(REVISION)
        state.set_file_structure(part.file_structure())
        part.generate_structure()
        part.build()
    finally:
        os.chdir(cwd)


def main(step_only=False, svg_only=False, csv_only=False, build=True):
    state.set_rev(REVISION)
    state.set_project_type("part")

    csv_path = write_catalog_csv()
    print(f"Wrote catalog: {csv_path}")
    if csv_only:
        return

    variants = list(ring_terminal.iter_part_configurations())
    total = len(variants)
    if not (step_only or svg_only):
        cache_run_constant_lookups()

    for i, cfg in enumerate(variants, start=1):
        pn = ring_terminal.make_part_number(cfg)
        print(f"Preparing part number: {pn}")
        dims = dimensions_from_cfg(cfg)
        attributes = compile_part_attributes(cfg)

        part_dir = os.path.join(_FAMILY_DIR, pn)
        os.makedirs(part_dir, exist_ok=True)
        rev_dir = os.path.join(part_dir, f"{pn}-rev{REVISION}")
        rev_hist = os.path.join(part_dir, f"{pn}-revision_history.tsv")
        json_path = os.path.join(rev_dir, f"{pn}-rev{REVISION}-attributes.json")
        svg_path = os.path.join(rev_dir, f"{pn}-rev{REVISION}-drawing.svg")

        if step_only or svg_only:
            os.makedirs(rev_dir, exist_ok=True)
            if not os.path.exists(rev_hist):
                rev_history.part_family_append(revision_history_row(cfg), rev_hist)
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(attributes, f, indent=2)
                f.write("\n")
            if svg_only:
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(ring_terminal_svg(pn, dims, cfg["insulation"]))
            if step_only:
                write_part_step(rev_dir, pn, dims)
            print(_progress_bar(i, total))
            continue

        rev_history.part_family_append(revision_history_row(cfg), rev_hist)
        if os.path.exists(rev_dir):
            for item in os.listdir(rev_dir):
                item_path = os.path.join(rev_dir, item)
                if os.path.isfile(item_path):
                    os.remove(item_path)
        else:
            os.makedirs(rev_dir)

        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(attributes, f, indent=2)
            f.write("\n")
        with open(svg_path, "w", encoding="utf-8") as f:
            f.write(ring_terminal_svg(pn, dims, cfg["insulation"]))
        write_part_step(rev_dir, pn, dims)

        if build:
            build_part(pn, rev_dir)
            if delete_pngs:
                for item in os.listdir(rev_dir):
                    if item.endswith(".png"):
                        os.remove(os.path.join(rev_dir, item))
        print(_progress_bar(i, total))

    print(f"Finished rendering all {total} parts in family.")


if __name__ == "__main__":
    main(
        step_only="--step-only" in sys.argv,
        svg_only="--svg-only" in sys.argv,
        csv_only="--csv-only" in sys.argv,
        build="--no-build" not in sys.argv,
    )
