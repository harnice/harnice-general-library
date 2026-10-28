import os
from harnice import fileio
from harnice.lists import flattened_network, instances_list
from harnice.utils import appearance, svg_utils

artifact_mpn = "trace_layout_visualizer"
# artifact_id: intentionally NOT defined here — injected externally by runpy

"""
Draws conductor and/or cable routing paths across the harness bundles, using the same
trace geometry as the Analyze circuits/cable overlays but laid out in formboard space
so `scale` means what it means on standard_harnice_formboard.

Args:
artifact_id : "unique identifier for this instance of the macro (cable_layout-1)"
trace_item_types : (optional) list of item_types to draw, in back-to-front order.
    Defaults to ["conductor", "cable"]. A single string is also accepted.
input_instances : (optional) restrict the drawing to these instances. Instances that
    are not conductors or cables are ignored, so formboard-style lists can be reused.
    Omit to draw every conductor/cable in the project.
scale : (optional) scale factor for the drawing, same meaning as on the formboard
    (1 is full size). Defaults to 1.
"""

try:
    trace_item_types
except NameError:
    trace_item_types = ["conductor", "cable"]

if isinstance(trace_item_types, str):
    trace_item_types = [trace_item_types]

try:
    input_instances
except NameError:
    input_instances = None

try:
    scale
except NameError:
    scale = 1


# ==========================================================================================================
#               GLOBAL SETTINGS
# ==========================================================================================================
PX_PER_INCH = 96  # formboard drawing space

TRACE_WIDTH_IN = 0.05  # drawn width of one wire, scales with the drawing
TRACE_SPACING_IN = 0.2  # lateral spread between parallel wires at a shared node
LABEL_PRINT_SIZE_PX = 8  # label height on the sheet, held constant across scales


# ==========================================================================================================
#               PATHS
# ==========================================================================================================
def macro_file_structure():
    return {
        f"{artifact_id}-master.svg": "output svg",
    }


if base_directory is None:  # path between cwd and the file structure for this macro
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


os.makedirs(dirpath(None), exist_ok=True)


def appearance_for_print(appearance_val):
    """White fill with no outline is invisible on paper; add a gray outline."""
    parsed = appearance.parse(appearance_val)
    if not parsed or not parsed.get("base_color"):
        return parsed if parsed is not None else appearance_val
    if appearance.to_rgb(parsed.get("base_color")) != (255, 255, 255):
        return parsed
    if parsed.get("outline_color") not in [None, ""]:
        return parsed
    parsed["outline_color"] = "#888888"
    return parsed


# ==========================================================================================================
#               MAIN RUNTIME LOGIC
# ==========================================================================================================
# Build the bundle network the way the formboard does: node/segment instances placed by
# their coordinate systems, inches → pixels, Y negated to match the SVG convention.
# The whole instances list is used regardless of input_instances, because
# calculate_location has to walk each node's full parent chain.
instances = instances_list.read()

network_nodes = {}
network_segments = {}
for instance in instances:
    if instance.get("item_type") == "node":
        x, y, _ = flattened_network.calculate_location(instance, instances)
        network_nodes[instance.get("instance_name")] = {
            "x": x * PX_PER_INCH,
            "y": y * -PX_PER_INCH,
        }
    elif instance.get("item_type") == "segment":
        node_a = instance.get("node_at_end_a")
        node_b = instance.get("node_at_end_b")
        if node_a and node_b:
            network_segments[instance.get("instance_name")] = {
                "node_at_end_a": node_a,
                "node_at_end_b": node_b,
                "diameter": float(instance.get("diameter") or 1),
            }

network_2D = {"nodes": network_nodes, "segments": network_segments}

source_instances = input_instances if input_instances is not None else instances
print_instances = []
for inst in source_instances:
    row = dict(inst)
    row["appearance"] = appearance_for_print(inst.get("appearance"))
    print_instances.append(row)

# Stroke, spacing, and label size follow svg_utils.trace_overlay_style when the
# script has changed them. A key still at the overlay default keeps the sheet
# number above, so an untouched build matches older drawings. stroke_width is
# inches. segment_spacing is px in this pixel network. label_font_size is the
# printed px size, divided by scale because the text sits in the scale group.
stroke_width = svg_utils.trace_overlay_sheet_value("stroke_width", TRACE_WIDTH_IN)
segment_spacing = svg_utils.trace_overlay_sheet_value(
    "segment_spacing", TRACE_SPACING_IN * PX_PER_INCH
)
label_print_px = svg_utils.trace_overlay_sheet_value(
    "label_font_size", LABEL_PRINT_SIZE_PX
)

content_lines = []
for item_type in trace_item_types:
    layer_markup = flattened_network.trace_layer_markup(
        network_2D,
        item_type,
        input_instances=print_instances,
        stroke_width=stroke_width,
        segment_spacing=segment_spacing,
        # Labels sit inside the scale group, so pre-divide to print at a fixed size.
        label_font_size=label_print_px / scale,
        min_label_segment_length=svg_utils.trace_overlay_style[
            "min_label_segment_length"
        ],
    )
    layer_id = f"{artifact_id}-{item_type}_traces"
    content_lines.append(f'    <g id="{layer_id}" inkscape:label="{layer_id}">')
    if layer_markup.strip():
        content_lines.extend(
            f"      {line}" for line in layer_markup.strip().split("\n")
        )
    content_lines.append("    </g>")


# ==========================================================================================================
# write the svg file
with open(path("output svg"), "w", encoding="utf-8") as f:
    f.write('<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n')
    f.write(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
        'version="1.1" width="1000" height="1000">\n'
    )
    f.write(f'  <g id="{artifact_id}-contents-start">\n')
    f.write(f'    <g id="{artifact_id}-scale_group" transform="scale({scale})">\n')
    f.writelines(line + "\n" for line in content_lines)
    f.write("    </g>\n")
    f.write("  </g>\n")
    f.write(f'  <g id="{artifact_id}-contents-end">\n')
    f.write("  </g>\n")
    f.write("</svg>\n")
