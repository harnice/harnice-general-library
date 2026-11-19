"""Rewrites this family's SKUs. Run by hand when the catalog changes.

Library maintenance only. Harness and system scripts never import this
file; they import ferrule.py. The catalog's one source of truth is
ferrule.csv: edit a row there, then run this.

Writes revision history, attributes.json, drawing.svg, and model.step for
each row and builds it with `harnice -b`.

    python3 ferrule_generator.py [--step-only] [--svg-only] [--no-build]
"""
import csv
import json
import math
import os
import subprocess
import sys

from harnice import fileio, state
from harnice.lists import rev_history
from harnice.utils import step_utils

FAMILY_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, FAMILY_DIR)
from ferrule import LIBRARY_REPO, LIBRARY_SUBPATH  # noqa: E402

REVISION = "1"
DATE_STARTED = "11/18/26"
MANUFACTURER = ""

PX_PER_IN = 96.0
FLAGNOTE_DISTANCE_IN = 3.0
FLAGNOTE_ANGLES = [0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90]
TUBE_HEX = "#B9BDC2"  # bare tinned copper
TUBE_HIGHLIGHT_HEX = "#E9EBED"
OUTLINE_HEX = "#1A1A1A"


def read_catalog():
    """One dict per row of ferrule.csv, with the numbers as floats."""
    with open(os.path.join(FAMILY_DIR, "ferrule.csv"), newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for row in rows:
        for key in ("overall_length_mm", "tube_length_mm", "tube_od_mm", "collar_od_mm"):
            row[key] = float(row[key])
        row["insulation"] = f"#{row['insulation_hex']}"
    return rows


def mix_with_white(hex_color, amount):
    r, g, b = (int(hex_color[i : i + 2], 16) for i in (1, 3, 5))
    r, g, b = (round(c + (255 - c) * amount) for c in (r, g, b))
    return f"#{r:02X}{g:02X}{b:02X}"


def stations(row):
    """Named x stations and radii in mm, in the drawing frame.

    Origin is the open end of the metal tube, on the axis, as marked on the
    reference picture: where the wire ends. +X points out of the tube, away
    from the wire, so the whole ferrule sits in -X. The wire enters the
    collar rear at x_rear. The reference picture has the collar on the left
    and the tube tip on the right, the same as this frame.
    """
    r_tube = row["tube_od_mm"] / 2  # ferrule.csv (estimate, see its notes)
    r_collar = row["collar_od_mm"] / 2  # ferrule.csv (estimate, see its notes)
    r_collar_front = 0.95 * r_collar  # estimate: reference picture, collar narrows toward the tube
    r_lip = 1.15 * r_tube  # estimate: reference picture, collar lip around the tube
    taper_mm = 1.2 * (r_collar_front - r_lip)  # estimate: reference picture taper proportion

    x_tip = 0.0  # origin: open end of the tube
    x_tube_rear = -row["tube_length_mm"]  # ferrule.csv: exposed tube length
    x_taper = x_tube_rear - taper_mm  # estimate: start of the collar taper
    x_rear = -row["overall_length_mm"]  # ferrule.csv: overall length
    assert x_rear < x_taper < x_tube_rear < x_tip
    return {
        "x_rear": x_rear, "x_taper": x_taper, "x_tube_rear": x_tube_rear, "x_tip": x_tip,
        "r_tube": r_tube, "r_collar": r_collar, "r_collar_front": r_collar_front, "r_lip": r_lip,
    }


def envelope(s):
    """(x_mm, radius_mm) stations, rear to tip. The SVG and the STEP both use this."""
    return [
        (s["x_rear"], s["r_collar"]),
        (s["x_taper"], s["r_collar_front"]),
        (s["x_tube_rear"], s["r_lip"]),
        (s["x_tube_rear"], s["r_tube"]),
        (s["x_tip"], s["r_tube"]),
    ]


def silhouette_mm(env):
    """Closed side-view outline in mm (part frame, +Y up)."""
    return list(env) + [(x, -r) for x, r in reversed(env)]


# The only place mm turns into SVG px and the only place y flips.
def px(mm):
    return mm / 25.4 * PX_PER_IN


def svg_point(x_mm, y_mm):
    return f"{px(x_mm):.3f},{-px(y_mm):.3f}"


def svg_rect(x0, x1, y0, y1, fill):
    return (
        f'<rect x="{px(x0):.3f}" y="{-px(y1):.3f}" '
        f'width="{px(x1 - x0):.3f}" height="{px(y1 - y0):.3f}" fill="{fill}"/>'
    )


def svg_polygon(points, fill, stroke=None, stroke_width=0.0):
    pts = " ".join(svg_point(x, y) for x, y in points)
    stroke_attr = f' stroke="{stroke}" stroke-width="{stroke_width}"' if stroke else ""
    return f'<polygon points="{pts}" fill="{fill}"{stroke_attr}/>'


def svg_line(x0, y0, x1, y1, stroke, stroke_width):
    return (
        f'<line x1="{px(x0):.3f}" y1="{-px(y0):.3f}" x2="{px(x1):.3f}" y2="{-px(y1):.3f}" '
        f'stroke="{stroke}" stroke-width="{stroke_width:.3f}" stroke-linecap="round"/>'
    )


def ferrule_svg(row):
    pn = row["library_pn"]
    s = stations(row)
    env = envelope(s)
    collar_hex = row["insulation"]
    shapes = []

    # Tube, with the two light bands the reference picture shows.
    shapes.append(svg_rect(s["x_tube_rear"], s["x_tip"], -s["r_tube"], s["r_tube"], TUBE_HEX))
    for sign in (1, -1):
        y0, y1 = sorted((sign * 0.2 * s["r_tube"], sign * 0.6 * s["r_tube"]))
        shapes.append(svg_rect(s["x_tube_rear"], s["x_tip"], y0, y1, TUBE_HIGHLIGHT_HEX))

    # Collar: the rear part of the same envelope.
    collar = env[:3]
    shapes.append(svg_polygon(collar + [(x, -r) for x, r in reversed(collar)], collar_hex))

    # Two lengthwise sheen stripes on the collar, as on the reference picture.
    stripe_x0 = s["x_rear"] + 0.08 * (s["x_taper"] - s["x_rear"])
    stripe_x1 = s["x_taper"] - 0.05 * (s["x_taper"] - s["x_rear"])
    for sign in (1, -1):
        y = sign * 0.38 * s["r_collar_front"]
        shapes.append(
            svg_line(stripe_x0, y, stripe_x1, y, mix_with_white(collar_hex, 0.22), px(0.22 * s["r_collar_front"]))
        )

    # Outer outline last.
    shapes.append(svg_polygon(silhouette_mm(env), "none", OUTLINE_HEX, 0.6))

    body = "\n    ".join(shapes)
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="400" height="400">\n'
        f'  <g id="{pn}-drawing-contents-start">\n'
        f"    {body}\n"
        "  </g>\n"
        f'  <g id="{pn}-drawing-contents-end">\n'
        "  </g>\n"
        "</svg>\n"
    )


def build_csys_children(row):
    """3d-mate at the tube tip (the origin). Cartesian flagnotes.

    The ferrule sits wholly in -X, so rays about the origin would all end on
    the tip. Rays start at leader_center, the middle of the part on the
    axis, and each leader lands where its ray last leaves the silhouette.
    """
    s = stations(row)
    outline = [(x / 25.4, y / 25.4) for x, y in silhouette_mm(envelope(s))]
    cx = (s["x_rear"] + s["x_tip"]) / 2 / 25.4

    def farthest_crossing(angle_deg):
        dx, dy = math.cos(math.radians(angle_deg)), math.sin(math.radians(angle_deg))
        best = 0.0
        for (x1, y1), (x2, y2) in zip(outline, outline[1:] + outline[:1]):
            ex, ey = x2 - x1, y2 - y1
            denom = dx * ey - dy * ex
            if abs(denom) < 1e-12:
                continue
            t = ((x1 - cx) * ey - y1 * ex) / denom
            u = ((x1 - cx) * dy - y1 * dx) / denom
            if t > 0 and -1e-9 <= u <= 1 + 1e-9:
                best = max(best, t)
        return best

    children = {
        "3d-mate": {"x": 0.0, "y": 0.0, "z": 0.0, "rx": 0.0, "ry": 0.0, "rz": 0.0},
        "leader_center": {"x": round(cx, 4), "y": 0.0, "rotation": 0},
    }
    for i, angle in enumerate(FLAGNOTE_ANGLES, start=1):
        dx, dy = math.cos(math.radians(angle)), math.sin(math.radians(angle))
        t = farthest_crossing(angle)
        children[f"flagnote-{i}"] = {
            "x": round(cx + FLAGNOTE_DISTANCE_IN * dx, 4),
            "y": round(FLAGNOTE_DISTANCE_IN * dy, 4),
            "rotation": 0,
        }
        children[f"flagnote-{i}-leader_dest"] = {
            "x": round(cx + t * dx, 4),
            "y": round(t * dy, 4),
            "rotation": 0,
        }
    return children


def compile_part_attributes(row):
    return {
        "datasheet": row["source"],
        "wire_gauge_awg": row["wire_gauge_awg"],
        "wire_size_mm2": row["wire_size_mm2"],
        "insulation_color": row["insulation"],
        "insulated": True,
        "overall_length": round(row["overall_length_mm"] / 25.4, 4),
        "width": round(row["collar_od_mm"] / 25.4, 4),
        "tube_length": round(row["tube_length_mm"] / 25.4, 4),
        "tube_od": round(row["tube_od_mm"] / 25.4, 4),
        "collar_od": round(row["collar_od_mm"] / 25.4, 4),
        "tools": ["generic ferrule crimp tool 22awg-7awg"],
        "build_notes": [],
        "csys_children": build_csys_children(row),
    }


def revision_history_row(row):
    return {
        "project_type": "part",
        "mfg": MANUFACTURER,
        "pn": row["library_pn"],
        "rev": REVISION,
        "desc": (
            f"FERRULE, INSULATED, {row['wire_gauge_awg']} AWG ({row['wire_size_mm2']} MM2), "
            f"{row['insulation_color'].upper()}, {row['overall_length_mm']:g} MM LONG, "
            f"{row['tube_length_mm']:g} MM TUBE"
        ),
        "status": "",
        "datestarted": DATE_STARTED,
        "library_repo": LIBRARY_REPO,
        "library_subpath": LIBRARY_SUBPATH,
    }


def progress_bar(i, n, width=30):
    done = round(width * i / n)
    return f"[{'#' * done}{'.' * (width - done)}] {i}/{n}"


def main(step_only=False, svg_only=False, build=True):
    state.set_rev(REVISION)
    state.set_project_type("part")

    # part_family_append asks git and drawnby.json on every SKU. Ask once.
    harnice_version = fileio.harnice_version()
    drawnby = fileio.drawnby()
    fileio.harnice_version = lambda: harnice_version
    fileio.drawnby = lambda: drawnby

    rows = read_catalog()
    for i, row in enumerate(rows, start=1):
        pn = row["library_pn"]
        part_dir = os.path.join(FAMILY_DIR, pn)
        rev_dir = os.path.join(part_dir, f"rev{REVISION}")
        os.makedirs(rev_dir, exist_ok=True)

        if not step_only:
            with open(os.path.join(rev_dir, "drawing.svg"), "w", encoding="utf-8") as f:
                f.write(ferrule_svg(row))
        if not svg_only:
            step_utils.write_revolution_step(os.path.join(rev_dir, "model.step"), pn, envelope(stations(row)))
        if not (step_only or svg_only):
            rev_history.part_family_append(
                revision_history_row(row),
                os.path.join(part_dir, f"{pn}-revision_history.tsv"),
            )
            with open(os.path.join(rev_dir, "attributes.json"), "w", encoding="utf-8") as f:
                json.dump(compile_part_attributes(row), f, indent=2)
                f.write("\n")
            if build:
                # Always harnice -b from the revision folder. Errors stop the run.
                subprocess.run(["harnice", "-b"], cwd=rev_dir, check=True)
        print(progress_bar(i, len(rows)))


if __name__ == "__main__":
    main(
        step_only="--step-only" in sys.argv,
        svg_only="--svg-only" in sys.argv,
        build="--no-build" not in sys.argv,
    )
