from harnice import fileio
from harnice.lists import instances_list
from harnice.lists.flattened_network import read_rows, spans_of
from harnice.utils import appearance, cable_utils, svg_utils
import ast
import math
import os
import re

artifact_mpn = "flying_lead_generator"

"""
Drop-in alternative to basic_segment_generator for a segment that ends at a
harness_connector whose mpn is "flying leads" (standard_harnice_formboard picks
this macro for exactly those segments). Every conductor on the segment,
including each conductor inside every cable on it, is drawn at its own outer
diameter and color. All conductors meet at one point at the other end of the
segment and splay apart toward the "flying leads" end, where each one ends on
its own. Terminals are separate "terminal" instances made in the build instructions,
placed on the output csys below, not part of this drawing.

Each splayed conductor gets a 2D output csys named "flying_lead_end" at its tip,
pointing outward. It is written to that conductor's conductor-segment row
({conductor}.{segment}, which is parented to the segment) and to the cavity the
conductor ends in at the "flying leads" connector (e.g. P4.3, which is parented to
the segment origin here). A terminal or flagnote attaches with
parent_csys_instance_name="P4.3" (or "{conductor}.{segment}") and
parent_csys_outputcsys_name="flying_lead_end".

args:

- instance: dict from instances list. one segment instance allowed. requires length
- splay_angle: (optional) degrees between neighboring conductors. default 10 (standard_harnice_formboard passes flying_lead_splay_angle)
- dimension: int, 0 to 100. 0 the dimension is fully transparent (invisible), 100 is fully opaque
- dimension_units: mm, in, or ft
- scale: scale of the formboard, used to correct dimension and outline size
"""

OUTPUT_CSYS_NAME = "flying_lead_end"
FLYING_LEADS_MPN = "flying leads"


# =============== PATHS ===================================================================================
def macro_file_structure():
    return {
        "drawing.svg": "drawing",
    }


if base_directory == None:  # path between cwd and the file structure for this macro
    base_directory = os.path.join("instance_data", "macro", artifact_id)


def path(target_value):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


def dirpath(target_value):
    # target_value = None will return the root of this macro
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


# ==========================================================================================================

# =============== INPUT CHECKS ===============
try:
    instance.get("instance_name")
except:
    raise ValueError(
        "please pass an instance dict as argument 'instance' to this macro"
    )

if instance.get("item_type") != "segment":
    raise ValueError(
        f"flying_lead_generator can only be used to generate segments, not {instance.get('item_type')}"
    )

_g = globals()
_dimension = _g.get("dimension", 50)
_dimension = int(_dimension) if _dimension is not None else 50
_dimension_units = (_g.get("dimension_units") or "in").strip().lower()
_scale = float(_g.get("scale", 1.0)) if _g.get("scale") is not None else 1.0

_splay_angle = _g.get("splay_angle")
_splay_angle = 10.0 if _splay_angle in (None, "") else float(_splay_angle)

segment_name = instance.get("instance_name") or ""
_instances = instances_list.read()
_by_name = {row.get("instance_name"): row for row in _instances}


# =============== HELPERS ===============
def _layout_row(segment_instance):
    """Flattened-network row for this segment, so its end point matches the formboard."""
    name = segment_instance.get("instance_name") or ""
    try:
        for row in read_rows():
            if (row.get("segment_id") or "") == name:
                return row
    except Exception:
        pass
    angle = segment_instance.get("absolute_rotation")
    if angle in ("", None):
        angle = segment_instance.get("angle", 0)
    return {
        "angle": angle or 0,
        "subdivisions": segment_instance.get("subdivisions") or "",
        "angle_constraint": "",
    }


def _fmt(value):
    text = f"{float(value):.4f}".rstrip("0").rstrip(".")
    return text if text not in ("", "-") else "0"


def _xml(text):
    return (
        str(text)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _colors(appearance_value):
    parsed = appearance.parse(appearance_value) or {}
    base = parsed.get("base_color") or parsed.get("outline_color") or "#eeeeee"
    outline = parsed.get("outline_color") or "#000000"
    return base, outline


def _flying_leads_connector_on(node_name):
    """The harness_connector with mpn "flying leads" at this node, or None."""
    node = _by_name.get(node_name) or {}
    group = node.get("connector_group") or ""
    for row in _instances:
        if row.get("item_type") != "harness_connector":
            continue
        if (row.get("mpn") or "").strip().lower() != FLYING_LEADS_MPN:
            continue
        if row.get("parent_csys_instance_name") == node_name or (
            group and row.get("connector_group") == group
        ):
            return row
    return None


def _natural_key(text):
    return [
        (0, int(part), "") if part.isdigit() else (1, 0, part)
        for part in re.split(r"(\d+)", text or "")
        if part != ""
    ]


def _csys_children(row):
    raw = row.get("csys_children")
    if isinstance(raw, dict):
        return dict(raw)
    try:
        parsed = ast.literal_eval(raw) if raw not in ("", None) else {}
    except (ValueError, SyntaxError):
        parsed = {}
    return dict(parsed) if isinstance(parsed, dict) else {}


# =============== WHICH END SPLAYS ===============
node_a = instance.get("node_at_end_a")
node_b = instance.get("node_at_end_b")
connector_a = _flying_leads_connector_on(node_a)
connector_b = _flying_leads_connector_on(node_b)
if bool(connector_a) == bool(connector_b):
    which = "both ends have" if connector_a else "neither end has"
    raise ValueError(
        f"flying_lead_generator: segment '{segment_name}' {which} a connector with mpn "
        f"'{FLYING_LEADS_MPN}' ({node_a}, {node_b}). Flying leads splay toward the one end "
        "with that connector and converge at the other, so exactly one end needs it."
    )
splay_at_a = connector_a is not None
connector = connector_a or connector_b


# =============== CONDUCTORS ===============
# Every conductor-segment hop on this segment, whether or not it is inside a cable.
leads = []
hop_suffix = f".{segment_name}"
for hop in _instances:
    if hop.get("item_type") != "conductor-segment":
        continue
    if hop.get("segment_group") != segment_name:
        continue
    hop_name = hop.get("instance_name") or ""
    if not hop_name.endswith(hop_suffix):
        continue
    conductor = _by_name.get(hop_name[: -len(hop_suffix)])
    if conductor is None or conductor.get("item_type") != "conductor":
        continue

    # Cavity at the connector end, so neighbors in the fan are neighbors in the connector.
    cavity = ""
    cavity_name = None
    for end_node in (conductor.get("node_at_end_a"), conductor.get("node_at_end_b")):
        prefix = f"{connector.get('instance_name')}."
        if (end_node or "").startswith(prefix):
            cavity = end_node[len(prefix):]
            cavity_name = end_node
            break

    leads.append(
        {
            "hop": hop,
            "conductor": conductor,
            "cavity": cavity,
            "cavity_name": cavity_name,
            "diameter_in": cable_utils.conductor_od(conductor, _instances),
            # full engineering appearance; blank draws Harnice's rainbow placeholder
            "appearance": conductor.get("appearance") or hop.get("appearance"),
        }
    )

leads.sort(
    key=lambda lead: (
        _natural_key(lead["cavity"]),
        _natural_key(lead["conductor"].get("instance_name")),
    )
)


# =============== GEOMETRY ===============
# Drawing frame: origin at node A, +X along the segment's first span, SVG Y down.
length_inches = float(instance.get("length", 0) or 0)
length_px = length_inches * 96.0
spans = spans_of(_layout_row(instance))
if len(spans) > 1:
    print(
        f"flying_lead_generator: segment '{segment_name}' has subdivisions; "
        "flying leads splay in a straight line from end to end."
    )
base_angle = spans[0]["angle"]
end_x = end_y = 0.0
for span in spans:
    rel = math.radians(span["angle"] - base_angle)
    end_x += length_px * span["fraction"] * math.cos(rel)
    end_y -= length_px * span["fraction"] * math.sin(rel)

if splay_at_a:  # converge at B, splay back toward A
    converge_x, converge_y = end_x, end_y
    dir_x, dir_y = -end_x, -end_y
else:  # converge at A, splay toward B
    converge_x, converge_y = 0.0, 0.0
    dir_x, dir_y = end_x, end_y
dir_len = math.hypot(dir_x, dir_y)
if dir_len < 1e-9:
    dir_x, dir_y, dir_len = (-1.0 if splay_at_a else 1.0), 0.0, 1.0
dir_x, dir_y = dir_x / dir_len, dir_y / dir_len
center_angle_up = math.degrees(math.atan2(-dir_y, dir_x))  # Y-up, like csys angles

count = len(leads)
for index, lead in enumerate(leads):
    theta_up = center_angle_up + (index - (count - 1) / 2.0) * _splay_angle
    ux = math.cos(math.radians(theta_up))
    uy = -math.sin(math.radians(theta_up))
    lead["ux"], lead["uy"] = ux, uy
    lead["tip_x"] = converge_x + ux * length_px
    lead["tip_y"] = converge_y + uy * length_px
    lead["angle_up"] = theta_up


# =============== DRAW ===============
bounds = [(converge_x, converge_y)]


def _track(x, y):
    bounds.append((x, y))


lead_svg = []
if not leads:
    print(
        f"flying_lead_generator: no conductors are mapped onto segment '{segment_name}'; "
        "drawing one line at the segment diameter."
    )
    seg_base, seg_outline = _colors(instance.get("appearance"))
    width_px = float(instance.get("diameter", 1) or 1) * 96.0
    lead_svg.append(
        f'<line x1="0" y1="0" x2="{_fmt(end_x)}" y2="{_fmt(end_y)}" stroke="{seg_base}" '
        f'stroke-width="{_fmt(width_px)}" stroke-linecap="butt" />'
    )
    _track(end_x, end_y)

for lead in leads:
    name = lead["conductor"].get("instance_name")
    width_px = lead["diameter_in"] * 96.0
    # Same renderer as every other conductor drawing (outline, stripes, bands,
    # twist hatching, rainbow placeholder), with square ends at both end points.
    # draw_styled_path takes Y up; this drawing is Y down.
    parts = []
    svg_utils.draw_styled_path(
        [
            {"x": converge_x, "y": -converge_y, "tangent": lead["angle_up"]},
            {"x": lead["tip_x"], "y": -lead["tip_y"], "tangent": lead["angle_up"]},
        ],
        lead["diameter_in"],
        lead["appearance"],
        parts,
        linecap="butt",
    )
    half_w = width_px / 2.0
    lead_svg.append(f'<g id="{_xml(name)}-flying_lead">{"".join(parts)}</g>')

    for x, y in ((converge_x, converge_y), (lead["tip_x"], lead["tip_y"])):
        _track(x - half_w, y - half_w)
        _track(x + half_w, y + half_w)



# =============== OUTPUT CSYS ===============
# Segment frame in inches, Y up: the same frame the conductor-segment row inherits
# from its parent segment, so calculate_location resolves to the drawn tip.
for lead in leads:
    hop = lead["hop"]
    children = _csys_children(hop)
    children[OUTPUT_CSYS_NAME] = {
        "x": round(lead["tip_x"] / 96.0, 4),
        "y": round(-lead["tip_y"] / 96.0, 4),
        "rotation": round(lead["angle_up"], 4),
    }
    changes = {"csys_children": str(children)}
    if not hop.get("parent_csys_outputcsys_name"):
        changes["parent_csys_outputcsys_name"] = "origin"
    instances_list.modify(hop.get("instance_name"), changes)

    # The same csys on the cavity this conductor ends in (e.g. P4.3), so a terminal
    # can attach to the cavity directly. Parenting the cavity to the segment origin
    # puts it in the same frame as the conductor-segment row.
    cavity_row = _by_name.get(lead["cavity_name"])
    if cavity_row is not None:
        cavity_children = _csys_children(cavity_row)
        cavity_children[OUTPUT_CSYS_NAME] = children[OUTPUT_CSYS_NAME]
        instances_list.modify(
            lead["cavity_name"],
            {
                "csys_children": str(cavity_children),
                "parent_csys_instance_name": segment_name,
                "parent_csys_outputcsys_name": "origin",
            },
        )


# =============== DIMENSION ===============
# Segment length, drawn along the center of the fan, outside the outermost lead.
arrow_size = 4  # px
dim_stroke_width = 1  # px
text_pad = 3  # px
text_font_size = 8  # px
text_font_family = "helvetica"

if _dimension_units == "mm":
    unit_scale, unit_str = 25.4, " mm"
elif _dimension_units == "ft":
    unit_scale, unit_str = 1.0 / 12.0, " ft"
else:
    unit_scale, unit_str = 1.0, " in"

arrow_size_s = arrow_size / _scale
dim_stroke_width_s = dim_stroke_width / _scale
text_font_size_s = text_font_size / _scale
label_height_s = (text_font_size + 2 * text_pad) / _scale
dim_opacity = _dimension / 100.0
dim_color = "#000000"

x1, y1 = converge_x, converge_y
x2, y2 = converge_x + dir_x * length_px, converge_y + dir_y * length_px
ux, uy = dir_x, dir_y
px, py = -uy, ux
widest = max(
    [abs((bx - x1) * px + (by - y1) * py) for bx, by in bounds] + [0.0]
)
dim_offset = widest + 12 / _scale

dim_label_text = f"{length_inches * unit_scale} {instance.get('length_tolerance') or ''}".strip() + unit_str
label_width_s = max(len(dim_label_text) * 6 + 2 * text_pad, 12) / _scale
ox1, oy1 = x1 + px * dim_offset, y1 + py * dim_offset
ox2, oy2 = x2 + px * dim_offset, y2 + py * dim_offset
stroke = f'stroke="{dim_color}" stroke-width="{_fmt(dim_stroke_width_s)}"'
dims = [
    f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(ox1)}" y2="{_fmt(oy1)}" {stroke} />',
    f'<line x1="{_fmt(x2)}" y1="{_fmt(y2)}" x2="{_fmt(ox2)}" y2="{_fmt(oy2)}" {stroke} />',
    f'<line x1="{_fmt(ox1 + ux * arrow_size_s)}" y1="{_fmt(oy1 + uy * arrow_size_s)}" '
    f'x2="{_fmt(ox2 - ux * arrow_size_s)}" y2="{_fmt(oy2 - uy * arrow_size_s)}" {stroke} />',
]
for tip_x, tip_y, sign in ((ox1, oy1, 1), (ox2, oy2, -1)):
    back_x, back_y = tip_x + sign * ux * arrow_size_s, tip_y + sign * uy * arrow_size_s
    dims.append(
        f'<path d="M {_fmt(tip_x)},{_fmt(tip_y)} '
        f'L {_fmt(back_x + px * arrow_size_s / 2)},{_fmt(back_y + py * arrow_size_s / 2)} '
        f'L {_fmt(back_x - px * arrow_size_s / 2)},{_fmt(back_y - py * arrow_size_s / 2)} z" '
        f'fill="{dim_color}" />'
    )
label_rot = math.degrees(math.atan2(uy, ux))
if 90.0 < (label_rot % 360.0 + 360.0) % 360.0 < 270.0:
    label_rot += 180.0
mx, my = (ox1 + ox2) / 2.0, (oy1 + oy2) / 2.0
dims.append(
    f'<g transform="translate({_fmt(mx)},{_fmt(my)}) rotate({_fmt(label_rot)})">'
    f'<rect x="{_fmt(-label_width_s / 2)}" y="{_fmt(-label_height_s / 2)}" '
    f'width="{_fmt(label_width_s)}" height="{_fmt(label_height_s)}" fill="#ffffff" />'
    f'<text x="0" y="0" font-size="{_fmt(text_font_size_s)}px" font-family="{text_font_family}" '
    f'text-anchor="middle" dominant-baseline="middle" fill="{dim_color}" '
    f'id="dim-label-text">{_xml(dim_label_text)}</text></g>'
)
for x, y in ((ox1, oy1), (ox2, oy2)):
    _track(x, y)
_track(mx + px * label_height_s, my + py * label_height_s)
_track(mx - px * label_height_s, my - py * label_height_s)


# =============== WRITE ===============
pad = 2.0
min_x = min(p[0] for p in bounds) - pad
min_y = min(p[1] for p in bounds) - pad
max_x = max(p[0] for p in bounds) + pad
max_y = max(p[1] for p in bounds) + pad
vb_w, vb_h = max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)

svg_content = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(vb_w)}" height="{_fmt(vb_h)}" viewBox="{_fmt(min_x)} {_fmt(min_y)} {_fmt(vb_w)} {_fmt(vb_h)}">
    <g id="{segment_name}-contents-start">
        {"".join(lead_svg)}
        <g opacity="{dim_opacity}">
            {"".join(dims)}
        </g>
    </g>
    <g id="{segment_name}-contents-end"></g>
</svg>
"""

with open(path("drawing"), "w") as svg_file:
    svg_file.write(svg_content)
