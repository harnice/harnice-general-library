from harnice import fileio
from harnice.lists.flattened_network import read_rows, spans_of
from harnice.utils import appearance
import math
import os

artifact_mpn = "basic_segment_generator"

"""
args:

- instance: dict from instances list. one instance allowed. requires length, diameter, optionally uses length_tolerance and subdivisions
- dimension: int, 0 to 100. 0 the dimension is fully transparent (invisible), 100 is fully opaque
- dimension_units: mm, in, or ft
- scale: scale of the formboard, used to correct dimension size
"""


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
        f"basic_segment_generator can only be used to generate segments, not {instance.get('item_type')}"
    )


# =============== CALCULATIONS ===============
# Optional args (dimension opacity 0–100, dimension_units, scale for dimension size)
_g = globals()
_dimension = _g.get("dimension", 50)
_dimension = int(_dimension) if _dimension is not None else 50
_dimension_units = (_g.get("dimension_units") or "in").strip().lower()
_scale = float(_g.get("scale", 1.0)) if _g.get("scale") is not None else 1.0

def _layout_row(segment_instance):
    """Flattened-network row for this segment, so each subdivision can be drawn."""
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
    )


length_inches = float(instance.get("length", 0) or 0)
svg_diameter = float(instance.get("diameter", 1) or 1) * 96
half_svg_diameter = svg_diameter / 2

# Dimension: offset beside each piece; base sizes, then scaled
dim_offset = (half_svg_diameter / _scale) + 24  # px
arrow_size = 4  # px
dim_stroke_width = 1  # px
text_pad = 3  # px
text_font_size = 8  # px
text_font_family = "helvetica"

if _dimension_units == "mm":
    unit_scale = 25.4
    unit_str = " mm"
elif _dimension_units == "ft":
    unit_scale = 1.0 / 12.0
    unit_str = " ft"
else:
    unit_scale = 1.0
    unit_str = " in"

arrow_size_s = arrow_size / _scale
dim_stroke_width_s = dim_stroke_width / _scale
text_font_size_s = text_font_size / _scale
label_height = text_font_size + 2 * text_pad
label_height_s = label_height / _scale
dim_opacity = _dimension / 100.0

segment_stroke = (_parsed := appearance.parse(instance.get("appearance")) or {}).get("base_color") or _parsed.get("outline_color") or "#eeeeee"
_dim_style = {
    "fill_color": "#ffffff",
    "stroke_color": "#000000",
    "text_color": "#000000",
}

spans = spans_of(_layout_row(instance))
base_angle = spans[0]["angle"]
tolerance = "" if len(spans) > 1 else (instance.get("length_tolerance") or "")

pieces = []
cursor_x = 0.0
cursor_y = 0.0
for index, span in enumerate(spans):
    piece_inches = length_inches * span["fraction"]
    piece_px = piece_inches * 96.0
    if piece_px <= 1e-6:
        continue
    rel = math.radians(span["angle"] - base_angle)
    step_x = piece_px * math.cos(rel)
    step_y = -piece_px * math.sin(rel)
    pieces.append(
        {
            "index": index,
            "x1": cursor_x,
            "y1": cursor_y,
            "x2": cursor_x + step_x,
            "y2": cursor_y + step_y,
            "inches": piece_inches,
        }
    )
    cursor_x += step_x
    cursor_y += step_y

if not pieces:
    pieces.append(
        {
            "index": 0,
            "x1": 0.0,
            "y1": 0.0,
            "x2": length_inches * 96.0,
            "y2": 0.0,
            "inches": length_inches,
        }
    )

body = []
dims = []
bounds = []


def _track(x, y):
    bounds.append((x, y))


for piece_number, piece in enumerate(pieces, start=1):
    x1, y1 = piece["x1"], piece["y1"]
    x2, y2 = piece["x2"], piece["y2"]
    dx, dy = x2 - x1, y2 - y1
    dist = math.hypot(dx, dy) or 1.0
    ux, uy = dx / dist, dy / dist
    px, py = -uy, ux  # beside the piece; +Y when the piece runs along +X
    body.append(
        f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(x2)}" y2="{_fmt(y2)}" '
        f'stroke="{segment_stroke}" stroke-width="{_fmt(svg_diameter)}" />'
    )
    _track(x1, y1)
    _track(x2, y2)
    _track(x1 + px * half_svg_diameter, y1 + py * half_svg_diameter)
    _track(x1 - px * half_svg_diameter, y1 - py * half_svg_diameter)
    _track(x2 + px * half_svg_diameter, y2 + py * half_svg_diameter)
    _track(x2 - px * half_svg_diameter, y2 - py * half_svg_diameter)

    dim_value = piece["inches"] * unit_scale
    dim_label_text = f"{dim_value} {tolerance}".strip() + unit_str
    label_width = max(len(dim_label_text) * 6 + 2 * text_pad, 12)
    label_width_s = label_width / _scale
    ox1, oy1 = x1 + px * dim_offset, y1 + py * dim_offset
    ox2, oy2 = x2 + px * dim_offset, y2 + py * dim_offset
    dims.append(
        f'<line x1="{_fmt(x1)}" y1="{_fmt(y1)}" x2="{_fmt(ox1)}" y2="{_fmt(oy1)}" '
        f'stroke="{_dim_style["stroke_color"]}" stroke-width="{_fmt(dim_stroke_width_s)}" />'
    )
    dims.append(
        f'<line x1="{_fmt(x2)}" y1="{_fmt(y2)}" x2="{_fmt(ox2)}" y2="{_fmt(oy2)}" '
        f'stroke="{_dim_style["stroke_color"]}" stroke-width="{_fmt(dim_stroke_width_s)}" />'
    )
    dims.append(
        f'<line x1="{_fmt(ox1 + ux * arrow_size_s)}" y1="{_fmt(oy1 + uy * arrow_size_s)}" '
        f'x2="{_fmt(ox2 - ux * arrow_size_s)}" y2="{_fmt(oy2 - uy * arrow_size_s)}" '
        f'stroke="{_dim_style["stroke_color"]}" stroke-width="{_fmt(dim_stroke_width_s)}" />'
    )
    dims.append(
        f'<path d="M {_fmt(ox1)},{_fmt(oy1)} '
        f'L {_fmt(ox1 + ux * arrow_size_s + px * arrow_size_s / 2)},{_fmt(oy1 + uy * arrow_size_s + py * arrow_size_s / 2)} '
        f'L {_fmt(ox1 + ux * arrow_size_s - px * arrow_size_s / 2)},{_fmt(oy1 + uy * arrow_size_s - py * arrow_size_s / 2)} z" '
        f'fill="{_dim_style["stroke_color"]}" />'
    )
    dims.append(
        f'<path d="M {_fmt(ox2)},{_fmt(oy2)} '
        f'L {_fmt(ox2 - ux * arrow_size_s + px * arrow_size_s / 2)},{_fmt(oy2 - uy * arrow_size_s + py * arrow_size_s / 2)} '
        f'L {_fmt(ox2 - ux * arrow_size_s - px * arrow_size_s / 2)},{_fmt(oy2 - uy * arrow_size_s - py * arrow_size_s / 2)} z" '
        f'fill="{_dim_style["stroke_color"]}" />'
    )
    label_rot = math.degrees(math.atan2(dy, dx))
    if 90.0 < (label_rot % 360.0 + 360.0) % 360.0 < 270.0:
        label_rot += 180.0
    mx, my = (ox1 + ox2) / 2.0, (oy1 + oy2) / 2.0
    label_id = "dim-label-text" if piece_number == 1 else f"dim-label-text-{piece_number}"
    dims.append(
        f'<g transform="translate({_fmt(mx)},{_fmt(my)}) rotate({_fmt(label_rot)})">'
        f'<rect x="{_fmt(-label_width_s / 2)}" y="{_fmt(-label_height_s / 2)}" '
        f'width="{_fmt(label_width_s)}" height="{_fmt(label_height_s)}" fill="{_dim_style["fill_color"]}" />'
        f'<text x="0" y="0" font-size="{_fmt(text_font_size_s)}px" font-family="{text_font_family}" '
        f'text-anchor="middle" dominant-baseline="middle" fill="{_dim_style["text_color"]}" '
        f'id="{label_id}">{_xml(dim_label_text)}</text></g>'
    )
    _track(ox1, oy1)
    _track(ox2, oy2)
    _track(mx + px * label_height_s, my + py * label_height_s)
    _track(mx - px * label_height_s, my - py * label_height_s)

for earlier, later in zip(pieces, pieces[1:]):
    body.append(
        f'<circle cx="{_fmt(later["x1"])}" cy="{_fmt(later["y1"])}" r="{_fmt(half_svg_diameter)}" '
        f'fill="{segment_stroke}" />'
    )

straight = (
    len(pieces) == 1
    and abs(pieces[0]["y2"]) < 1e-6
    and pieces[0]["x2"] >= -1e-6
)
if straight:
    svg_length = length_inches * 96.0
    vb_x, vb_y = 0.0, -half_svg_diameter
    vb_w, vb_h = svg_length, svg_diameter + 2
else:
    pad = 2.0
    min_x = min(p[0] for p in bounds) - pad
    min_y = min(p[1] for p in bounds) - pad
    max_x = max(p[0] for p in bounds) + pad
    max_y = max(p[1] for p in bounds) + pad
    vb_x, vb_y = min_x, min_y
    vb_w, vb_h = max(max_x - min_x, 1.0), max(max_y - min_y, 1.0)

instance_name = instance.get("instance_name")
svg_content = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="{_fmt(vb_w)}" height="{_fmt(vb_h)}" viewBox="{_fmt(vb_x)} {_fmt(vb_y)} {_fmt(vb_w)} {_fmt(vb_h)}">
    <g id="{instance_name}-contents-start">
        {"".join(body)}
        <g opacity="{dim_opacity}">
            {"".join(dims)}
        </g>
    </g>
    <g id="{instance_name}-contents-end"></g>
</svg>
"""

with open(path("drawing"), "w") as svg_file:
    svg_file.write(svg_content)
