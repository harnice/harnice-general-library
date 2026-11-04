"""Emit generic ring-terminal SKUs.

The catalog and part-number grammar live in ring_terminal.py. This file
writes the drawing, attributes, and STEP-side metadata. Do not import it
from a harness.

Origin is the barrel (cable) end on the axis, +X toward the ring / stud.
csys_children["3d-mate"] sits on the ring tip.
"""
import csv
import json
import math
import os
import subprocess
import sys

from harnice import state
from harnice.lists import rev_history

_FAMILY_DIR = os.path.dirname(os.path.abspath(__file__))
if _FAMILY_DIR not in sys.path:
    sys.path.insert(0, _FAMILY_DIR)

import ring_terminal as rt

REVISION = "1"
DATE_STARTED = "2/16/26"
FLAGNOTE_RADIUS_IN = 3.0
FLAGNOTE_PADDING_IN = 0.04


def compile_part_attributes(cfg):
    """Build the attributes dict for a single ring terminal configuration."""

    def build_csys_children(ring_od, overall_length):
        """Polar flagnotes about the cable-end origin; 3d-mate at the ring tip."""

        def terminal_outline_distance(angle_deg):
            """Distance from the cable-end origin to the ring silhouette.

            The barrel is narrower than the ring, so a ray from the origin
            hits the barrel first and leaves the arrowhead short of the ring.
            Land on the ring instead: its far intersection, or the crown
            line at the ring radius when that line still lies over the ring.
            """
            ring_r = ring_od / 2.0
            rcx = overall_length - ring_r
            ang = math.radians(abs(angle_deg))
            hits = []
            if ang > 1e-9:
                crown = ring_r / math.sin(ang)
                if 0 <= crown * math.cos(ang) <= rcx:
                    hits.append(crown)
            cosine = math.cos(ang)
            disc = (2 * cosine * rcx) ** 2 - 4 * (rcx * rcx - ring_r * ring_r)
            if disc >= 0:
                root = math.sqrt(disc)
                span = 2 * cosine * rcx
                for t in ((span - root) / 2, (span + root) / 2):
                    if t > 1e-6:
                        hits.append(t)
            if ang < 1e-9:
                hits.append(overall_length)
            if not hits:
                hits.append(overall_length)
            return max(hits) + FLAGNOTE_PADDING_IN

        angles = [0]
        step = 15
        a = step
        while len(angles) < 13:
            angles.append(a)
            if len(angles) < 13:
                angles.append(-a)
            a += step

        children = {
            "3d-mate": {
                "x": round(float(overall_length), 4),
                "y": 0.0,
                "z": 0.0,
                "rx": 0.0,
                "ry": 0.0,
                "rz": 0.0,
            },
        }
        for i, angle in enumerate(angles, start=1):
            dest_dist = terminal_outline_distance(angle)
            children[f"flagnote-{i}"] = {
                "angle": angle, "distance": FLAGNOTE_RADIUS_IN, "rotation": 0,
            }
            children[f"flagnote-{i}-leader_dest"] = {
                "angle": angle, "distance": round(dest_dist, 4), "rotation": 0,
            }
        return children

    wire_gauge = cfg["wire_gauge"]
    stud_size_label = cfg["stud_size"]
    insulation = cfg["insulation"]

    stud_id = rt.STUD_SIZES[stud_size_label]
    wire_od = rt.AWG_OD[wire_gauge]
    # Estimated envelope. Replace with a manufacturer table when one is used.
    ring_od = 0.2 * stud_id * stud_id + stud_id + 0.2
    barrel_od = wire_od + 0.15
    length = 2 * barrel_od + ring_od

    attributes = {
        "wire_gauge_awg": wire_gauge,
        "stud_size": stud_size_label,
        "insulation_color": insulation,
        "insulated": insulation is not None,
        "stud_hole_id": round(stud_id, 4),
        "ring_od": round(ring_od, 4),
        "barrel_od": round(barrel_od, 4),
        "overall_length": round(length, 4),
        "barrel_material": "copper",
        "plating": "tin",
        "insulation_material": "vinyl" if insulation else None,
    }
    molex = rt.molex_part(wire_gauge, stud_size_label, insulation)
    mcmaster = rt.mcmaster_part(wire_gauge, stud_size_label, insulation)
    if molex:
        attributes["molex_pn"] = molex
    if mcmaster:
        attributes["mcmaster_pn"] = mcmaster
    if wire_gauge in ("22", "20", "18", "16", "14", "12", "10"):
        tool = "generic ring terminal crimp tool 10awg-22awg"
    else:
        tool = f"ring terminal crimp tool for {wire_gauge}awg terminals"
    attributes["tools"] = [tool]
    attributes["build_notes"] = []
    attributes["csys_children"] = build_csys_children(ring_od, length)
    return attributes


# ---------------------------------------------------------------------------
# SVG generation
# ---------------------------------------------------------------------------

def ring_terminal_svg(
    part_number: str,
    stud_id: float,
    ring_od: float,
    barrel_od: float,
    overall_length: float,
    insulation: str | None = None,
) -> str:
    """Generate an SVG drawing of a ring terminal.

    Origin is the barrel (cable) end; +X toward the ring tip.
    All dimensions are in inches.

    Args:
        part_number: Part number used in group IDs.
        stud_id: Stud hole inner diameter.
        ring_od: Ring outer diameter.
        barrel_od: Barrel / shank outer diameter.
        overall_length: Overall length from barrel end to ring tip.
        insulation: Hex colour string (e.g. "#e03030") or None for bare.

    Returns:
        SVG markup string.
    """
    ring_r = ring_od / 2
    hole_r = stud_id / 2
    barrel_r = barrel_od / 2
    barrel_len = overall_length - ring_od

    scale = 96   # pixels per inch

    # Ring center
    rcx = (overall_length - ring_r) * scale
    rcy = 0

    # Barrel rectangle
    bx1 = 0
    bx2 = barrel_len * scale
    by1 = -barrel_r * scale
    bh = barrel_od * scale

    # Crimp bands
    crimp_w = barrel_len * 0.15
    c1x = barrel_len * scale * 0.1
    c2x = bx2 - barrel_len * scale * 0.1 - crimp_w * scale

    # Taper from barrel to ring
    ang = math.atan2(barrel_r, ring_r)
    taper_dx = ring_r * scale * math.cos(ang)
    taper_dy = ring_r * scale * math.sin(ang)

    svg_w = overall_length * scale
    svg_h = max(ring_od, barrel_od) * scale

    els: list[str] = []

    # Barrel body
    els.append(
        f'<rect x="{bx1:.2f}" y="{by1:.2f}" '
        f'width="{bx2 - bx1 + 2:.2f}" height="{bh:.2f}" '
        f'fill="#898989" rx="2"/>'
    )

    # Taper transition
    pts = (
        f"{rcx - taper_dx:.2f},{rcy - taper_dy:.2f} "
        f"{bx2:.2f},{by1:.2f} "
        f"{bx2:.2f},{by1 + bh:.2f} "
        f"{rcx - taper_dx:.2f},{rcy + taper_dy:.2f}"
    )
    els.append(f'<polygon points="{pts}" fill="#898989"/>')

    # Ring outer disc
    els.append(
        f'<circle cx="{rcx:.2f}" cy="{rcy:.2f}" '
        f'r="{ring_r * scale:.2f}" fill="#898989"/>'
    )

    # Insulation sleeve
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

    # Stud hole
    els.append(
        f'<circle cx="{rcx:.2f}" cy="{rcy:.2f}" '
        f'r="{hole_r * scale:.2f}" fill="#ffffff" '
        f'stroke="#666666" stroke-width="0.5"/>'
    )

    # Crimp bands (bare terminals only)
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

        # Barrel end opening (bare terminals only)
        els.append(
            f'<ellipse cx="{bx1:.2f}" cy="{rcy:.2f}" '
            f'rx="2" ry="{barrel_r * scale:.2f}" '
            f'fill="#6a6a6a" stroke="#777777" stroke-width="0.5"/>'
        )

    # Center crosshair
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
        f' width="{svg_w:.0f}" height="{svg_h:.0f}">\n'
        f'<g id="{part_number}-drawing-contents-start">\n'
        f'    {content}\n'
        f'</g>\n'
        f'<g id="{part_number}-drawing-contents-end">\n'
        f'</g>\n'
        f'</svg>'
    )


def main(skip_render=False, attributes_only=False):
    def write_catalog_csv(path=None):
        if path is None:
            path = os.path.join(_FAMILY_DIR, "ring_terminal.csv")
        rows = [rt.catalog_row(cfg) for cfg in rt.iter_part_configurations()]
        with open(path, "w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(
                handle, fieldnames=rt.CSV_COLUMNS, lineterminator="\n"
            )
            writer.writeheader()
            writer.writerows(rows)
        return path

    state.set_rev(REVISION)
    state.set_project_type("part")

    family_dir = _FAMILY_DIR
    csv_path = write_catalog_csv()
    print(f"Wrote family catalog: {csv_path}")
    configs = list(rt.iter_part_configurations())
    for cfg in configs:
        pn = rt.make_part_number(cfg)
        print(f"Preparing part number: {pn}")

        # ---- directory structure ----
        part_dir = os.path.join(family_dir, pn)
        os.makedirs(part_dir, exist_ok=True)

        rev_dir = os.path.join(part_dir, f"rev{REVISION}")
        if not attributes_only:
            if os.path.exists(rev_dir):
                for item in os.listdir(rev_dir):
                    p = os.path.join(rev_dir, item)
                    if os.path.isfile(p):
                        os.remove(p)
            else:
                os.makedirs(rev_dir)

            # ---- revision history ----
            rev_history.part_family_append(
                {
                    "project_type": state.project_type,
                    "mfg": "mil spec",
                    "pn": pn,
                    "rev": REVISION,
                    "desc": rt.description_from_cfg(cfg),
                    "status": "",
                    "datestarted": DATE_STARTED,
                    "library_repo": rt.LIBRARY_REPO,
                    "library_subpath": rt.LIBRARY_SUBPATH,
                },
                os.path.join(part_dir, f"{pn}-revision_history.tsv"),
            )
        else:
            os.makedirs(rev_dir, exist_ok=True)

        # ---- attributes JSON ----
        attributes = compile_part_attributes(cfg)
        json_path = os.path.join(rev_dir, "attributes.json")
        with open(json_path, "w") as f:
            json.dump(attributes, f, indent=2)
            f.write("\n")

        if attributes_only:
            continue

        # ---- SVG drawing ----
        svg_content = ring_terminal_svg(
            part_number=pn,
            stud_id=attributes["stud_hole_id"],
            ring_od=attributes["ring_od"],
            barrel_od=attributes["barrel_od"],
            overall_length=attributes["overall_length"],
            insulation=cfg["insulation"],
        )
        svg_path = os.path.join(rev_dir, "drawing.svg")
        with open(svg_path, "w") as f:
            f.write(svg_content)

        # ---- render ----
        if not skip_render:
            subprocess.run(["harnice", "-r"], cwd=rev_dir, check=True)
            for item in os.listdir(rev_dir):
                if item.endswith(".png"):
                    os.remove(os.path.join(rev_dir, item))

    print("Finished rendering all parts in family.")


if __name__ == "__main__":
    main(
        skip_render="--skip-render" in sys.argv,
        attributes_only="--attributes-only" in sys.argv,
    )