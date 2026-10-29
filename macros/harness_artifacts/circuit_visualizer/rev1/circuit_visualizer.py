import os
from harnice import fileio
from harnice.lists import instances_list
from harnice.utils import circuit_utils, svg_utils

artifact_mpn = "circuit_visualizer"
# artifact_id: intentionally NOT defined here — injected externally by runpy


# ==========================================================================================================
# PATHS
# ==========================================================================================================


def macro_file_structure():
    return {
        f"{artifact_id}-circuit-visualizer-master.svg": "circuit visualizer svg",
    }


if base_directory is None:  # Provided externally, not defined here
    base_directory = os.path.join("instance_data", "macro", artifact_id)


def path(target_value):
    return fileio.path(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


def dirpath(target_value):
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


# ==========================================================================================================
# GLOBAL SETTINGS
# ==========================================================================================================

node_pointsize = 6
circuit_length = 800
whitespace_length = 24

FONT_FAMILY = "Arial"
FONT_SIZE = 7
FONT_COLOR = "black"
line_spacing = 7

HEADER_HEIGHT = 16
ROW_HEIGHT = 30
COL1_HEADER = "CIRCUIT ID"
COL1_WIDTH = 72
TABLE_STROKE = "black"
TABLE_FILL = "white"

NODE_MARGIN_X = 5
NODE_MARGIN_Y = 3
NODE_WIDTH = 84  # fixed width for all nodes

COL2_WIDTH = circuit_length + 2 * whitespace_length
COL2_HEADER = "SCHEMATIC"
VISUALIZATION_INSET_X = whitespace_length

SVG_HEADER = """<?xml version="1.0" encoding="UTF-8" standalone="no"?>
<svg xmlns="http://www.w3.org/2000/svg" version="1.1">
"""
SVG_FOOTER = "</svg>\n"

svg_elements = []


# ==========================================================================================================
# TEXT RENDERING
# ==========================================================================================================


def plot_text_lines(lines, center_x, center_y, text_group, background=False):
    # Normalize: turn None into empty strings
    norm_lines = [(t if t is not None else "") for t in lines]

    total_text_height = len(norm_lines) * line_spacing
    start_y = center_y - (total_text_height / 2) + (FONT_SIZE / 2)

    text_template = (
        f'<text x="{{x}}" y="{{y}}" fill="{FONT_COLOR}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE}">{{text}}</text>'
    )

    # Safe width calculation
    max_chars = max(len(t) for t in norm_lines) if norm_lines else 0

    if background:
        if max_chars > 0:
            est_width = max_chars * (FONT_SIZE * 0.6)
            box_height = total_text_height
            box_x = center_x - est_width / 2 - 2
            box_y = start_y - FONT_SIZE / 2
            text_group.append(
                f'<rect x="{box_x:.2f}" y="{box_y:.2f}" '
                f'width="{est_width+4:.2f}" height="{box_height:.2f}" '
                f'fill="white" stroke="none"/>'
            )

    # Render text lines
    for i, text in enumerate(norm_lines):
        ty = start_y + i * line_spacing
        text_group.append(
            text_template.format(
                x=center_x, y=ty, text=svg_utils.escape_svg_text(text)
            )
        )


# ==========================================================================================================
# SHAPE DRAWING (no text)
# ==========================================================================================================


def plot_node_shape(node_instance, x_left, y_center, width, node_group):
    """Draw a rectangular node box. x_left is LEFT edge, NOT center."""
    box_height = ROW_HEIGHT - 2 * NODE_MARGIN_Y
    box_y = y_center - box_height / 2

    rect = (
        f'<rect x="{x_left}" y="{box_y}" width="{width}" height="{box_height}" '
        f'fill="white" stroke="black" stroke-width="1"/>'
    )
    node_group.append(rect)


def plot_segment_shape(segment_instance, x_left, y_center, length, segment_group):
    """Draw a straight segment. Returns (center_x, center_y) for labels."""
    y_for_path = -y_center  # svg_utils flips Y internally

    spline_points = [
        {"x": x_left, "y": y_for_path, "tangent": 0},
        {"x": x_left + length, "y": y_for_path, "tangent": 0},
    ]

    svg_utils.draw_styled_path(
        spline_points, 0.02, segment_instance.get("appearance"), segment_group
    )

    return (x_left + length / 2, y_center)


# ==========================================================================================================
# HEADER
# ==========================================================================================================


def build_header():
    header_group = []
    y0 = 0

    header_group.append(
        f'<rect x="0" y="{y0}" width="{COL1_WIDTH}" height="{HEADER_HEIGHT}" '
        f'fill="#E0E0E0" stroke="{TABLE_STROKE}" />'
    )
    header_group.append(
        f'<rect x="{COL1_WIDTH}" y="{y0}" width="{COL2_WIDTH}" height="{HEADER_HEIGHT}" '
        f'fill="#E0E0E0" stroke="{TABLE_STROKE}" />'
    )

    header_group.append(
        f'<text x="{COL1_WIDTH/2}" y="{y0 + HEADER_HEIGHT/2}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE+1}" font-weight="bold">{COL1_HEADER}</text>'
    )

    header_group.append(
        f'<text x="{COL1_WIDTH + COL2_WIDTH/2}" y="{y0 + HEADER_HEIGHT/2}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE+1}" font-weight="bold">{COL2_HEADER}</text>'
    )

    return header_group


# ==========================================================================================================
# MAIN RENDER LOOP
# ==========================================================================================================

row_index = 0
y_offset = HEADER_HEIGHT

# Harnesses use conductors (circuits are system-level).
try:
    _input_rows = input_instances
except NameError:
    _input_rows = []


def _instance_named(name):
    if not name:
        return None
    for inst in instances_list.read():
        if inst.get("instance_name") == name:
            return inst
    return None


for instance in _input_rows:
    if instance.get("item_type") != "conductor":
        continue

    circuit_id = instance.get("circuit_id")
    print_name = "" if circuit_id in (None, "") else str(circuit_id)

    zero_port, max_port = circuit_utils.end_ports_of_circuit(circuit_id)
    end_a = _instance_named(instance.get("node_at_end_a")) or zero_port or {}
    end_b = _instance_named(instance.get("node_at_end_b")) or max_port or {}
    end_a_name = end_a.get("instance_name")
    end_b_name = end_b.get("instance_name")

    # Mid-path items on the same circuit_id (contacts, etc.), excluding ends/conductors.
    mids = []
    for p in circuit_utils.instances_of_circuit(circuit_id):
        if p.get("item_type") in ("conductor", "cable", "circuit"):
            continue
        if "-segment" in (p.get("item_type") or ""):
            continue
        if p.get("instance_name") in (end_a_name, end_b_name):
            continue
        mids.append(p)
    mids.sort(key=lambda x: int(x.get("circuit_port_number") or 0))

    # Path left→right: end A, mid nodes, conductor segment, end B
    ports = []
    if end_a:
        ports.append(end_a)
    ports.extend(mids)
    ports.append(instance)
    if end_b:
        ports.append(end_b)

    # Correct node/segment split
    nodes = []
    for p in ports:
        if p.get("location_type") == "node":
            nodes.append(p)

    segments = []
    for p in ports:
        if p.get("location_type") == "segment":
            segments.append(p)

    # ---- Determine layout widths ----
    usable_width = COL2_WIDTH - 2 * NODE_MARGIN_X
    total_node_width = len(nodes) * NODE_WIDTH

    if len(segments) > 0:
        segment_length = (usable_width - total_node_width) / len(segments)
    else:
        segment_length = 0

    # ---- SVG group origins ----
    y_row_top = y_offset + row_index * ROW_HEIGHT
    group_x = COL1_WIDTH
    group_y = y_row_top
    row_center_y = ROW_HEIGHT / 2

    table_group = []
    segment_group = []
    node_group = []
    text_group = []

    # ---- Table cells ----
    table_group.append(
        f'<rect x="0" y="{y_row_top}" width="{COL1_WIDTH}" height="{ROW_HEIGHT}" '
        f'stroke="{TABLE_STROKE}" fill="{TABLE_FILL}" />'
    )
    table_group.append(
        f'<rect x="{COL1_WIDTH}" y="{y_row_top}" width="{COL2_WIDTH}" height="{ROW_HEIGHT}" '
        f'stroke="{TABLE_STROKE}" fill="{TABLE_FILL}" />'
    )

    # ---- Left Column Text ----
    text_group.append(
        f'<text x="{COL1_WIDTH/2}" y="{y_row_top + ROW_HEIGHT/2}" '
        f'text-anchor="middle" dominant-baseline="middle" '
        f'font-family="{FONT_FAMILY}" font-size="{FONT_SIZE}">'
        f"{svg_utils.escape_svg_text(print_name)}</text>"
    )

    # ---- Schematic Layout ----

    left = NODE_MARGIN_X  # local coordinates only
    right = left

    for port in ports:

        loc = port.get("location_type", "")

        # --------------------------------------------
        # Update left/right
        # --------------------------------------------
        if loc == "segment":
            left = right
            right = left + segment_length

        else:  # node
            left = right
            right = left + NODE_WIDTH  # <-- Nodes must advance

        # --------------------------------------------
        # Draw NODE (local coords)
        # --------------------------------------------
        if loc == "node":
            center_x = (left + right) / 2
            x_left = center_x - NODE_WIDTH / 2

            plot_node_shape(
                port,
                x_left,
                row_center_y,
                NODE_WIDTH,
                node_group,
            )

            text_lines = []
            if port.get("item_type") not in [None, ""]:
                if port.get("item_type") in ["device_connector_cavity"]:
                    pass
                else:
                    text_lines.append(port.get("item_type"))
            connector_print_name = ""
            if port.get("connector_group"):
                conn = instances_list.instance_in_connector_group_with_item_type(
                    port.get("connector_group"), "device_connector"
                )
                if conn:
                    connector_print_name = conn.get("print_name") or ""
                if not connector_print_name:
                    conn = instances_list.instance_in_connector_group_with_item_type(
                        port.get("connector_group"), "harness_connector"
                    )
                    if conn:
                        connector_print_name = (
                            conn.get("print_name")
                            or conn.get("harness_side_connector_id")
                            or conn.get("instance_name")
                            or ""
                        )
            if connector_print_name not in [None, ""]:
                text_lines.append(connector_print_name)
            if port.get("print_name") not in [None, ""]:
                text_lines.append(port.get("print_name"))
            elif port.get("instance_name") not in [None, ""]:
                text_lines.append(str(port.get("instance_name")).rsplit(".", 1)[-1])

            plot_text_lines(
                text_lines,
                group_x + center_x,
                group_y + row_center_y,
                text_group,
            )

        # --------------------------------------------
        # Draw SEGMENT (local coords)
        # --------------------------------------------
        if loc == "segment":
            center_x = (left + right) / 2

            svg_utils.draw_styled_path(
                [
                    {"x": left, "y": -row_center_y, "tangent": 0},
                    {"x": right, "y": -row_center_y, "tangent": 0},
                ],
                0.02,
                port.get("appearance"),
                segment_group,
            )

            plot_text_lines(
                [
                    port.get("print_name", ""),
                ],
                group_x + center_x,  # <-- labels include group_x
                group_y + row_center_y,
                text_group,
                background=True,
            )

    # ---- Output row ----
    svg_elements.extend(table_group)
    svg_elements.append(f'<g transform="translate({group_x},{group_y})">')
    svg_elements.extend(f"  {s}" for s in segment_group)
    svg_elements.extend(f"  {n}" for n in node_group)
    svg_elements.append("</g>")
    svg_elements.extend(text_group)

    row_index += 1


# ==========================================================================================================
# WRITE SVG
# ==========================================================================================================

with open(path("circuit visualizer svg"), "w", encoding="utf-8") as f:
    f.write(SVG_HEADER)
    f.write(f'<g id="{artifact_id}-circuit-visualizer-contents-start">\n')

    for h in build_header():
        f.write(f"  {h}\n")

    for element in svg_elements:
        f.write(f"  {element}\n")

    f.write("</g>\n")
    f.write(f'<g id="{artifact_id}-circuit-visualizer-contents-end"/>\n')
    f.write(SVG_FOOTER)
