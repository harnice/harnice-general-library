"""
nema_plugs_generator.py
=======================

NEMA WD-6 cord-cap plugs (P) and cord connectors (R).

PRIMARY SOURCES
---------------
    ANSI/NEMA WD 6-2002, Wiring Devices — Dimensional Specifications.
    Face geometry (blade/slot size, spacing, clocking) and flanged-inlet
    diameters A/B/C come from the cited WD-6 figures in nema_geometry.py.
    Rear nylon housings are typical Hubbell Insulgrip cord caps
    (HBL5266C, HBL2311, HBL2611, HBL9431C, HBL9451C); WD-6 does not
    specify the rear body.

WHAT IS MODELLED
----------------
    Drawing and STEP share a cable-side origin (same convention as the
    aerospace library): x = 0 is the strain-relief / cable face, +X
    toward the mating face. Body is the Hubbell envelope; plug blades
    are the WD-6 contacts projected onto the XZ plane (G at the top).
    STEP: cylindrical housing + WD-6 face cylinder, then (plugs) blades
    extruded +X from the face. csys_children["3d-mate"] sits on that
    mating face (blade tips on P, face on R).

LIMITATIONS
-----------
    Locking series other than L5 use the L5 pitch/blade size of that
    amp class with a series clocking offset so the faces are not
    interchangeable; exact WD-6 angles for L6–L26 are not all encoded.
    Wall-plate duplex 5-15R/5-20R is not this part; R here is a cord
    connector.
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

import nema_geometry
import nema_plugs

REVISION = "1"
DATE_STARTED = "8/18/26"
LIBRARY_REPO = "https://github.com/harnice/harnice-general-library"
LIBRARY_SUBPATH = "connectors/nema_plugs/"
delete_pngs = True

PX_PER_IN = 96.0
MM_PER_IN = 25.4

BODY_HEX = "#1C1C1C"
RING_HEX = "#2A2A2A"
BLADE_HEX = "#C4A35A"
GROUND_HEX = "#7A8B73"
SLOT_HEX = "#0A0A0A"

FLAGNOTE_RADIUS_IN = 3.0
FLAGNOTE_ANGLES_DEG = (
    0, 15, -15, 30, -30, 45, -45, 60, -60, 75, -75, 90, -90
)


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


# ---------------------------------------------------------------------------
# Envelopes
# ---------------------------------------------------------------------------

def connector_length_in(spec: dict, gender: str) -> float:
    return nema_geometry.overall_length(spec, gender)


# ---------------------------------------------------------------------------
# Side-view silhouette (inches, math coords, +Y up = part +Z)
# ---------------------------------------------------------------------------

def envelope_stations_in(spec: dict, gender: str):
    """Stepped (x, radius) stations from the cable end to the mating face."""
    house = nema_geometry.housing(spec, gender)
    body_l = house["length"]
    body_r = house["diameter"] / 2.0
    face_r = house["face"] / 2.0
    ring_r = face_r * 1.06 if spec["locking"] else face_r
    face_start = max(0.0, body_l - house["face_length"])
    stations = [(0.0, body_r)]
    if face_start > 0.05:
        stations.append((face_start, body_r))
        stations.append((face_start, ring_r))
    stations.append((body_l, ring_r))
    if gender == "P":
        blade_r = _blade_side_radius_in(spec)
        longest = max(nema_geometry.blade_length(spec, n) for n in spec["contacts"])
        stations.append((body_l, blade_r))
        stations.append((body_l + longest, blade_r))
    return stations


def _blade_side_radius_in(spec: dict) -> float:
    zs = []
    for feat in nema_geometry.face_features(spec, "P"):
        z0, z1 = _feature_z_span(feat)
        zs.extend((abs(z0), abs(z1)))
    return max(zs) if zs else nema_geometry.face_diameter(spec) / 2.0


def _feature_z_span(feat: dict):
    zs = [z for poly in nema_geometry.feature_polygons_yz(feat) for _, z in poly]
    return (min(zs), max(zs)) if zs else (0.0, 0.0)


def part_perimeter_inches(spec: dict, gender: str):
    stations = envelope_stations_in(spec, gender)
    pts = [(x, r) for x, r in stations]
    pts += [(x, -r) for x, r in reversed(stations)]
    if pts[0] != pts[-1]:
        pts.append(pts[0])
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


def csys_6dof(x, y=0.0, z=0.0, rx=0.0, ry=0.0, rz=0.0):
    """Child csys pose in inches/degrees relative to the STEP (part) origin."""
    return {
        "x": round(float(x), 4),
        "y": round(float(y), 4),
        "z": round(float(z), 4),
        "rx": round(float(rx), 4),
        "ry": round(float(ry), 4),
        "rz": round(float(rz), 4),
    }


def mate_csys_3d(spec: dict, gender: str):
    """Mating face in the STEP frame (inches), identity orientation.

    Origin is the cable-side strain relief; this output sits on the
    mating face (blade tips on a plug, nylon face on a connector).
    """
    return csys_6dof(nema_geometry.overall_length(spec, gender))


def flagnote_csys_children(spec: dict, gender: str):
    """Polar flagnotes about the cable-end origin; leaders on the silhouette."""
    perimeter = part_perimeter_inches(spec, gender)
    overall = nema_geometry.overall_length(spec, gender)
    note_r = max(FLAGNOTE_RADIUS_IN, overall + 0.5)
    children = {}
    for i, angle in enumerate(FLAGNOTE_ANGLES_DEG, start=1):
        r_leader = _ray_perimeter_exit_distance((0.0, 0.0), angle, perimeter)
        if r_leader is None:
            continue
        children[f"flagnote-{i}"] = {
            "angle": angle,
            "distance": note_r,
            "rotation": 0,
        }
        children[f"flagnote-{i}-leader_dest"] = {
            "angle": angle,
            "distance": round(r_leader, 4),
            "rotation": 0,
        }
    return children


# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def _px_in(inches):
    return inches * PX_PER_IN


def _mm_in(inches):
    return inches * MM_PER_IN


def _poly(points, fill="#C0C0C0"):
    pts = " ".join(f"{x:.2f},{y:.2f}" for x, y in points)
    return f'<polygon points="{pts}" fill="{fill}" stroke="black" stroke-width="1"/>'


def _rect(x, y, w, h, fill, stroke="black"):
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{w:.2f}" height="{h:.2f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def _circle(cx, cy, r, fill, stroke="black"):
    return (
        f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{r:.2f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1"/>'
    )


def _circle_yz(cy, cz, radius_mm, n=24):
    return [
        (
            cy + radius_mm * math.cos(2.0 * math.pi * i / n),
            cz + radius_mm * math.sin(2.0 * math.pi * i / n),
        )
        for i in range(n)
    ]


def _blade_color(name: str) -> str:
    return GROUND_HEX if name == "G" else BLADE_HEX


# ---------------------------------------------------------------------------
# SVG — side elevation (D38999 convention)
# ---------------------------------------------------------------------------

def connector_svg(part_number: str, spec: dict, gender: str) -> str:
    house = nema_geometry.housing(spec, gender)
    body_l = house["length"]
    body_r = house["diameter"] / 2.0
    face_r = house["face"] / 2.0
    ring_r = face_r * 1.06 if spec["locking"] else face_r
    face_start = max(0.0, body_l - house["face_length"])
    clamp = min(0.35, body_l * 0.18)

    x0 = 0.0
    x_clamp = _px_in(clamp)
    x_face0 = _px_in(face_start)
    x_face = _px_in(body_l)
    r_body = _px_in(body_r)
    r_ring = _px_in(ring_r)
    r_cable = r_body * 0.55

    parts = []
    # Strain-relief taper into the nylon body, then the WD-6 face cylinder.
    body_outline = [
        (x0, -r_cable),
        (x_clamp, -r_body),
        (x_face0, -r_body),
        (x_face0, -r_ring),
        (x_face, -r_ring),
        (x_face, r_ring),
        (x_face0, r_ring),
        (x_face0, r_body),
        (x_clamp, r_body),
        (x0, r_cable),
    ]
    parts.append(_poly(body_outline, fill=BODY_HEX))
    if spec["locking"]:
        ring_w = min(_px_in(0.28), _px_in(body_l) * 0.18)
        parts.append(
            _rect(x_face - ring_w, -r_ring, ring_w, 2.0 * r_ring, RING_HEX)
        )
    parts.append(_circle(x0 + _px_in(0.08), 0.0, _px_in(0.16), "#111111"))

    if gender == "P":
        for feat in nema_geometry.face_features(spec, "P"):
            z0, z1 = _feature_z_span(feat)
            blade_l = nema_geometry.blade_length(spec, feat["name"])
            y_top = -_px_in(z1)
            h = _px_in(z1 - z0)
            if h < 2.0:
                h = 2.0
                y_top = -_px_in((z0 + z1) / 2.0) - h / 2.0
            parts.append(
                _rect(x_face, y_top, _px_in(blade_l), h, _blade_color(feat["name"]))
            )
    else:
        # Cord connector: shallow slot pockets at the face, no protruding blades.
        for feat in nema_geometry.face_features(spec, "R"):
            z0, z1 = _feature_z_span(feat)
            slot_w = _px_in(0.12)
            y_top = -_px_in(z1)
            h = max(2.0, _px_in(z1 - z0))
            parts.append(_rect(x_face - slot_w, y_top, slot_w, h, SLOT_HEX))

    return f'''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1" width="400" height="400">
<g id="{part_number}-drawing-contents-start">
{chr(10).join(parts)}
</g>
<g id="{part_number}-drawing-contents-end">
</g>
</svg>'''


# ---------------------------------------------------------------------------
# STEP — housing along +X, blades from the face
# ---------------------------------------------------------------------------

def envelope_prisms_mm(spec: dict, gender: str):
    house = nema_geometry.housing(spec, gender)
    body_l = _mm_in(house["length"])
    body_r = _mm_in(house["diameter"] / 2.0)
    face_r = _mm_in(house["face"] / 2.0)
    face_len = _mm_in(house["face_length"])
    face_start = max(0.0, body_l - face_len)

    segments = []
    if face_start > 0.05:
        segments.append((0.0, face_start, _circle_yz(0.0, 0.0, body_r)))
    ring_r = face_r * 1.06 if spec["locking"] else face_r
    segments.append((face_start, body_l, _circle_yz(0.0, 0.0, ring_r)))

    if gender == "P":
        for feat in nema_geometry.face_features(spec, "P"):
            x1 = body_l + _mm_in(nema_geometry.blade_length(spec, feat["name"]))
            for poly_in in nema_geometry.feature_polygons_yz(feat):
                poly_mm = [(_mm_in(y), _mm_in(z)) for y, z in poly_in]
                segments.append((body_l, x1, poly_mm))
    return segments


def write_part_step(rev_dir, part_number, spec, gender):
    path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-model.step")
    step_utils.write_prism_segments_step(
        path,
        part_number,
        envelope_prisms_mm(spec, gender),
        description=f"NEMA {spec['config']}{gender} low-fidelity envelope",
    )
    return path


# ---------------------------------------------------------------------------
# Attributes / catalog
# ---------------------------------------------------------------------------

# Commercial cross-references for the cord-cap (P) / cord connector (R).
# Hubbell Insulgrip nylon plug (…1 / …66C / …20C) and connector body
# (…3 / …69C / …29C). Where Hubbell only tools an angled plug, that PN is
# used. Wall-plate receptacles are omitted.
# Keys with no verified PN are left out of the attributes JSON.
_HUBBELL_PNS = {
    # straight 15/20 A Insulgrip
    ("5-15", "P"): "HBL5266C",
    ("5-15", "R"): "HBL5269C",
    ("5-20", "P"): "HBL5366C",
    ("5-20", "R"): "HBL5369C",
    ("6-15", "P"): "HBL5666C",
    ("6-15", "R"): "HBL5669C",
    ("6-20", "P"): "HBL5466C",
    ("6-20", "R"): "HBL5469C",
    # straight 30/50/60 A
    ("5-30", "P"): "HBL9309",
    ("6-30", "P"): "HBL9331",
    ("5-50", "P"): "HBL9361",
    ("6-50", "P"): "HBL9368",
    ("10-30", "P"): "HBL9333",
    ("14-20", "P"): "HBL8411C",
    ("14-30", "P"): "HBL9431C",
    ("14-50", "P"): "HBL9451C",
    ("14-60", "P"): "HBL9461C",
    ("15-30", "P"): "HBL8431C",
    ("15-60", "P"): "HBL8461C",
    ("TT-30", "P"): "HBLTT30P",
    # locking 15 A Insulgrip
    ("L5-15", "P"): "HBL4720C",
    ("L5-15", "R"): "HBL4729C",
    ("L6-15", "P"): "HBL4570C",
    ("L6-15", "R"): "HBL4579C",
    ("L7-15", "P"): "HBL4770C",
    ("L7-15", "R"): "HBL4779C",
    # locking 20 A 2P3W
    ("L5-20", "P"): "HBL2311",
    ("L5-20", "R"): "HBL2313",
    ("L6-20", "P"): "HBL2321",
    ("L6-20", "R"): "HBL2323",
    ("L7-20", "P"): "HBL2331",
    ("L7-20", "R"): "HBL2333",
    ("L8-20", "P"): "HBL2341",
    ("L8-20", "R"): "HBL2343",
    ("L9-20", "P"): "HBL2351",
    ("L9-20", "R"): "HBL2353",
    # locking 30 A 2P3W
    ("L5-30", "P"): "HBL2611",
    ("L5-30", "R"): "HBL2613",
    ("L6-30", "P"): "HBL2621",
    ("L6-30", "R"): "HBL2623",
    ("L7-30", "P"): "HBL2631",
    ("L7-30", "R"): "HBL2633",
    ("L8-30", "P"): "HBL2641",
    ("L8-30", "R"): "HBL2643",
    ("L9-30", "P"): "HBL2651",
    ("L9-30", "R"): "HBL2653",
    # locking 20 A 3P4W
    ("L14-20", "P"): "HBL2411",
    ("L14-20", "R"): "HBL2413",
    ("L15-20", "P"): "HBL2421",
    ("L15-20", "R"): "HBL2423",
    ("L16-20", "P"): "HBL2431",
    ("L16-20", "R"): "HBL2433",
    # locking 30 A 3P4W
    ("L14-30", "P"): "HBL2711",
    ("L14-30", "R"): "HBL2713",
    ("L15-30", "P"): "HBL2721",
    ("L15-30", "R"): "HBL2723",
    ("L16-30", "P"): "HBL2731",
    ("L16-30", "R"): "HBL2733",
    ("L17-30", "P"): "HBL2741",
    ("L17-30", "R"): "HBL2743",
    # locking 20 A 4P5W
    ("L21-20", "P"): "HBL2511",
    ("L21-20", "R"): "HBL2513",
    ("L22-20", "P"): "HBL2521",
    ("L22-20", "R"): "HBL2523",
    ("L23-20", "P"): "HBL2531",
    ("L23-20", "R"): "HBL2533",
    # locking 30 A 4P5W
    ("L21-30", "P"): "HBL2811",
    ("L21-30", "R"): "HBL2813",
    ("L22-30", "P"): "HBL2821",
    ("L22-30", "R"): "HBL2823",
    ("L23-30", "P"): "HBL2831",
    ("L23-30", "R"): "HBL2833",
}


def _vendor_attributes(config: str, gender: str) -> dict:
    hubbell = _HUBBELL_PNS.get((config, gender))
    if not hubbell:
        return {}
    return {"hubbell pn": hubbell}


def compile_part_attributes(cfg: dict) -> dict:
    spec = cfg["spec"]
    gender = cfg["gender"]
    contacts = [
        {"name": name, "size": spec["max_wire_awg"]}
        for name in spec["contacts"]
    ]
    attrs = {
        "tools": ["flathead screwdriver"],
        "build_notes": [],
        "csys_children": {
            "3d-mate": mate_csys_3d(spec, gender),
            **flagnote_csys_children(spec, gender),
        },
        "contacts": contacts,
        "nema_config": spec["config"],
        "gender": gender,
        "voltage": spec["voltage"],
        "current_a": spec["amps"],
        "locking": spec["locking"],
        "poles": spec["poles"],
        "wires": spec["wires"],
        "grounded": spec["grounded"],
        "system": spec["system"],
    }
    attrs.update(_vendor_attributes(spec["config"], gender))
    return attrs


CATALOG_COLUMNS = (
    "library_pn",
    "official_pin",
    "spec",
    "common_name",
    "config",
    "series",
    "gender",
    "contacts_type",
    "locking",
    "voltage",
    "current_a",
    "poles",
    "wires",
    "grounded",
    "system",
    "contact_letters",
    "pin_count",
    "max_wire_awg",
    "mates",
    "library_subpath",
)


def catalog_row(cfg: dict) -> dict:
    spec = cfg["spec"]
    gender = cfg["gender"]
    g = nema_plugs.GENDERS[gender]
    pn = nema_plugs.make_part_number(cfg["config"], gender)
    mates = nema_plugs.compatible_mates(pn)
    return {
        "library_pn": pn,
        "official_pin": nema_plugs.official_name(cfg["config"], gender),
        "spec": "ANSI/NEMA WD 6",
        "common_name": f"{spec['common_name']}, {g['name'].lower()}",
        "config": spec["config"],
        "series": spec["series"],
        "gender": g["name"],
        "contacts_type": g["contacts"],
        "locking": spec["locking"],
        "voltage": spec["voltage"],
        "current_a": spec["amps"],
        "poles": spec["poles"],
        "wires": spec["wires"],
        "grounded": spec["grounded"],
        "system": spec["system"],
        "contact_letters": " ".join(spec["contacts"]),
        "pin_count": len(spec["contacts"]),
        "max_wire_awg": spec["max_wire_awg"],
        "mates": ", ".join(mates),
        "library_subpath": LIBRARY_SUBPATH,
    }


def write_catalog_csv(path=None):
    if path is None:
        path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "nema_plugs.csv"
        )
    rows = [catalog_row(cfg) for cfg in nema_plugs.iter_part_configurations()]
    with open(path, "w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CATALOG_COLUMNS)
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


def make_part(cfg, render=True, attributes_only=False):
    spec = cfg["spec"]
    gender = cfg["gender"]
    part_number = nema_plugs.make_part_number(cfg["config"], gender)
    print("Preparing part number: ", part_number)

    family_dir = os.path.dirname(os.path.abspath(__file__))
    part_dir = os.path.join(family_dir, part_number)
    os.makedirs(part_dir, exist_ok=True)

    rev_dir = os.path.join(part_dir, f"{part_number}-rev{REVISION}")
    if attributes_only:
        os.makedirs(rev_dir, exist_ok=True)
        json_path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-attributes.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(compile_part_attributes(cfg), f, indent=2)
            f.write("\n")
        return part_number

    rev_history.part_family_append(
        {
            "project_type": state.project_type,
            "mfg": "NEMA",
            "pn": part_number,
            "rev": REVISION,
            "desc": nema_plugs.description_from_cfg(cfg),
            "status": "",
            "datestarted": DATE_STARTED,
            "library_repo": LIBRARY_REPO,
            "library_subpath": LIBRARY_SUBPATH,
            "revisionupdates": "INITIAL RELEASE",
        },
        os.path.join(part_dir, f"{part_number}-revision_history.tsv"),
    )

    rev_dir = os.path.join(part_dir, f"{part_number}-rev{REVISION}")
    if os.path.exists(rev_dir):
        for item in os.listdir(rev_dir):
            item_path = os.path.join(rev_dir, item)
            if os.path.isfile(item_path):
                os.remove(item_path)
    else:
        os.makedirs(rev_dir)

    json_path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-attributes.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(compile_part_attributes(cfg), f, indent=2)
        f.write("\n")

    svg_path = os.path.join(rev_dir, f"{part_number}-rev{REVISION}-drawing.svg")
    with open(svg_path, "w", encoding="utf-8") as f:
        f.write(connector_svg(part_number, spec, gender))

    write_part_step(rev_dir, part_number, spec, gender)

    if render:
        build_part(part_number, rev_dir)
        if delete_pngs:
            for item in os.listdir(rev_dir):
                if item.endswith(".png"):
                    os.remove(os.path.join(rev_dir, item))

    return part_number


def main(csv_only=False, skip_render=False, attributes_only=False):
    state.set_rev(REVISION)
    state.set_project_type("part")

    if not attributes_only:
        csv_path = write_catalog_csv()
        print(f"Wrote catalog: {csv_path}")
        if csv_only:
            return

    if not skip_render and not attributes_only:
        cache_run_constant_lookups()

    configs = list(nema_plugs.iter_part_configurations())
    total = len(configs)
    print(f"Building {total} NEMA plugs in {os.path.dirname(os.path.abspath(__file__))}")
    for i, cfg in enumerate(configs, start=1):
        make_part(cfg, render=not skip_render, attributes_only=attributes_only)
        print(_progress_bar(i, total))

    print(f"Finished rendering {total} parts in family.")


if __name__ == "__main__":
    main(
        csv_only="--csv-only" in sys.argv,
        skip_render="--skip-render" in sys.argv,
        attributes_only="--attributes-only" in sys.argv,
    )
