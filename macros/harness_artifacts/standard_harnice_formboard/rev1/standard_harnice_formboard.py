import re
import os
import math
from collections import defaultdict
from harnice import fileio
from harnice.utils import library_utils, svg_utils, build_utils
from harnice.lists import flattened_network

artifact_mpn = "standard_harnice_formboard"

"""
Args:
artifact_id : "unique identifier for this instance of the macro (drawing-1)"
input_instances : instances that you want to plot on the formboard. include notes, connectors, etc
scale : scale factor for the drawing
rotation : (optional) rotation of the drawing in degrees
trace_path_item_types: (optional) item_type that should not be plotted but instead paths should be drawn along the bundles
- dimension: int, 0 to 100. (optional) 0 the dimension is fully transparent (invisible), 100 is fully opaque
"""

try:
    trace_path_item_types
except NameError:
    trace_path_item_types = []

try:
    dimension
except NameError:
    dimension = 100

# ==================================================================================================
#               PATHS
# ==================================================================================================
def macro_file_structure(instance_name=None, item_type=None):
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


# ==================================================================================================
#               HELPER FUNCTIONS
# ==================================================================================================
def make_new_flagnote_drawing(instance, location):
    if instance.get("item_type") != "flagnote":
        raise ValueError(
            f"you just tried to make a flagnote drawing without specifying flagnote type by 'mpn' field on '{instance.get('instance_name')}'"
        )

    # === Pull drawing into this macro ===
    # Flagnotes can appear on multiple formboard artifacts (overview + detail) with the
    # same instance_name; do not record them in project library history or the second
    # pull raises "already been imported".
    library_utils.pull(
        instance,
        destination_directory=location,
        update_instances_list=False,
        record_library_history=False,
    )
    flagnote_drawing_path = os.path.join(location, "drawing.svg")

    # === Perform text replacement on known drawing path ===
    with open(flagnote_drawing_path, "r", encoding="utf-8") as f:
        svg = f.read()

    new_text = svg_utils.escape_svg_text(instance.get("print_name") or "")
    svg, n = re.subn(r">flagnote-text<", f">{new_text}<", svg)
    if n == 0:
        svg = re.sub(
            r'(<text\b[^>]*\bid="flagnote-text"[^>]*>)[^<]*',
            rf"\1{new_text}",
            svg,
            count=1,
        )

    with open(flagnote_drawing_path, "w", encoding="utf-8") as f:
        f.write(svg)


def make_new_segment_drawing(instance, location, dimension, dimension_units):
    if instance.get("item_type") != "segment":
        raise ValueError(
            f"you just tried to make a segment drawing out of a non-segment instance '{instance.get('instance_name')}'"
        )

    build_utils.run_macro(
        "basic_segment_generator",
        "macros/harness_artifacts",
        "https://github.com/harnice/harnice-general-library",
        scale=scale,
        dimension=dimension,
        dimension_units=dimension_units,
        artifact_id=f"{artifact_id}-{instance.get('instance_name')}",
        instance=instance,
        base_directory=location,
    )


def bundle_border(
    network_2D,
    stroke_width=10,
    junction_radius=20,
    appearance_dict=None,
):
    """
    Draws the harness bundle boundary by walking the outer perimeter using a
    left-wall-follower (half-edge) traversal and calling
    draw_filleted_styled_path once per endpoint-to-endpoint segment.

    Algorithm:
      • Start at any degree-1 (endpoint) node, on its left departure border.
      • Traverse toward the interior; at each junction take the CCW-next
        half-edge (first edge CCW from the reverse of the incoming direction).
      • At each junction, compute the virtual sharp corner — the intersection
        of the incoming and outgoing border lines — and record it with the
        requested junction_radius.
      • When an endpoint node is reached, terminate the chain there and call
        draw_filleted_styled_path, which inserts a circular fillet of the given
        radius at every interior corner.
      • Start a fresh chain from the opposite-side cap point at that endpoint
        and continue until the traversal returns to the start node.

    Geometry:
      Each border line runs parallel to its segment, offset laterally by
      seg_radius = diameter / 2.  At junctions the two adjacent border lines
      are extended to their intersection — the virtual sharp corner.
      draw_filleted_styled_path trims each straight segment back by
      R * tan(alpha / 2) and inserts a Bezier arc of radius junction_radius,
      giving consistent, tightly defined curves at every node.

    Coordinate convention:
      graph["nodes"] x/y  — SVG pixels, y increases downward.
      Chain point y       — math convention: −y_svg (negated).

    Args:
        network_2D       dict   {"nodes": {id: {x, y}},
                                 "segments": {id: {node_at_end_a, node_at_end_b,
                                                   (opt) diameter (inches)}}}
        stroke_width     px     Stroke width of the border lines.
        junction_radius  px     Fillet radius applied at every junction corner.
                                Clamped automatically if segments are too short.
        appearance_dict         Passed to draw_filleted_styled_path.
                                Default: solid black line.

    Returns:
        str  Raw SVG markup (no <svg> wrapper).
    """
    if appearance_dict is None:
        appearance_dict = {"base_color": "black"}

    graph = network_2D

    # ------------------------------------------------------------------ helpers

    adj = defaultdict(list)
    for seg_uuid, seg_info in graph["segments"].items():
        na = seg_info["node_at_end_a"]
        nb = seg_info["node_at_end_b"]
        adj[na].append((seg_uuid, nb))
        adj[nb].append((seg_uuid, na))

    def point_theta(origin, target):
        return math.degrees(math.atan2(target["y"] - origin["y"], target["x"] - origin["x"]))

    def dep_svg(from_id, to_id):
        return point_theta(graph["nodes"][from_id], graph["nodes"][to_id])

    def departure_target(node_id, seg_uuid):
        """First point along a segment when leaving a node, including a bend."""
        seg = graph["segments"][seg_uuid]
        waypoints = seg.get("waypoints") or []
        if node_id == seg.get("node_at_end_a") and waypoints:
            return waypoints[0]
        if node_id == seg.get("node_at_end_b") and waypoints:
            return waypoints[-1]
        other_id = (
            seg.get("node_at_end_b")
            if node_id == seg.get("node_at_end_a")
            else seg.get("node_at_end_a")
        )
        return graph["nodes"][other_id]

    def directed_waypoints(seg_uuid, from_id, to_id):
        seg = graph["segments"][seg_uuid]
        waypoints = list(seg.get("waypoints") or [])
        if from_id == seg.get("node_at_end_b") and to_id == seg.get("node_at_end_a"):
            waypoints.reverse()
        return waypoints

    def seg_radius(seg_uuid):
        return graph["segments"][seg_uuid].get("diameter", 1) * 96 / 2

    def perpendicular_endpoint(node_id, theta_svg, seg_r):
        """
        Cap point for a degree-1 (endpoint) node.

        The border runs parallel to the segment (direction theta) offset by
        seg_r.  The cap is the perpendicular through the node; their
        intersection is node + seg_r * (theta + 90°).
        """
        nc = graph["nodes"][node_id]
        cx, cy = nc["x"], nc["y"]
        a = math.radians(theta_svg + 90)
        return {
            "x": cx + seg_r * math.cos(a),
            "y": -(cy + seg_r * math.sin(a)),
        }

    def border_corner_at(cx, cy, theta_in, seg_r_in, theta_out, seg_r_out):
        """
        Virtual sharp corner at a junction node.

        Computes the intersection of the incoming border line (left of theta_in,
        offset by seg_r_in) with the outgoing border line (left of theta_out,
        offset by seg_r_out).  Falls back to the midpoint of the two border
        points if the lines are parallel.

        Returns {"x": float, "y": float, "radius": junction_radius} with y
        negated to match the math convention used by draw_filleted_styled_path.
        """
        p_in_rad = math.radians(theta_in + 90)
        p_out_rad = math.radians(theta_out + 90)

        px_in = cx + seg_r_in * math.cos(p_in_rad)
        py_in = cy + seg_r_in * math.sin(p_in_rad)
        px_out = cx + seg_r_out * math.cos(p_out_rad)
        py_out = cy + seg_r_out * math.sin(p_out_rad)

        dx_in = math.cos(math.radians(theta_in))
        dy_in = math.sin(math.radians(theta_in))
        dx_out = math.cos(math.radians(theta_out))
        dy_out = math.sin(math.radians(theta_out))

        det = dx_in * dy_out - dy_in * dx_out
        if abs(det) < 1e-9:
            vx, vy = (px_in + px_out) / 2, (py_in + py_out) / 2
        else:
            dpx, dpy = px_out - px_in, py_out - py_in
            t = (dpx * dy_out - dpy * dx_out) / det
            vx = px_in + t * dx_in
            vy = py_in + t * dy_in

        return {"x": vx, "y": -vy, "radius": junction_radius}

    def border_corner(node_id, theta_in, seg_r_in, theta_out, seg_r_out):
        nc = graph["nodes"][node_id]
        return border_corner_at(
            nc["x"], nc["y"], theta_in, seg_r_in, theta_out, seg_r_out
        )

    # ------------------------------------------------------------------ traversal

    def bfs_component(seed):
        comp, q = set(), [seed]
        while q:
            n = q.pop()
            if n in comp:
                continue
            comp.add(n)
            for _, nb in adj[n]:
                if nb not in comp:
                    q.append(nb)
        return comp

    local_group = []
    processed = set()

    for seed in graph["nodes"]:
        if seed in processed:
            continue
        comp = bfs_component(seed)
        processed.update(comp)

        endpoints = [n for n in comp if len(adj[n]) == 1]
        if not endpoints:
            continue  # pure cycle — skip for now

        start_node = endpoints[0]
        start_seg, start_nbr = adj[start_node][0]
        start_theta = point_theta(
            graph["nodes"][start_node],
            departure_target(start_node, start_seg),
        )
        start_seg_r = seg_radius(start_seg)

        chain = [perpendicular_endpoint(start_node, start_theta, start_seg_r)]

        cur_node = start_node
        cur_seg = start_seg
        cur_nbr = start_nbr
        prev_node = None

        n_segs_comp = sum(
            1
            for s in graph["segments"].values()
            if s["node_at_end_a"] in comp or s["node_at_end_b"] in comp
        )

        for _ in range(2 * n_segs_comp + 4):
            prev_node = cur_node
            cur_node = cur_nbr
            cur_seg_r = seg_radius(cur_seg)
            bend_points = directed_waypoints(cur_seg, prev_node, cur_node)
            if bend_points:
                span_pts = (
                    [graph["nodes"][prev_node]]
                    + bend_points
                    + [graph["nodes"][cur_node]]
                )
                for i in range(len(bend_points)):
                    theta_in = point_theta(span_pts[i], span_pts[i + 1])
                    theta_out = point_theta(span_pts[i + 1], span_pts[i + 2])
                    chain.append(
                        border_corner_at(
                            span_pts[i + 1]["x"],
                            span_pts[i + 1]["y"],
                            theta_in,
                            cur_seg_r,
                            theta_out,
                            cur_seg_r,
                        )
                    )
                theta = point_theta(bend_points[-1], graph["nodes"][cur_node])
            else:
                theta = dep_svg(prev_node, cur_node)

            if len(adj[cur_node]) == 1:
                chain.append(perpendicular_endpoint(cur_node, theta, cur_seg_r))
                svg_utils.draw_filleted_styled_path(
                    chain, stroke_width / 96, appearance_dict, local_group
                )

                if cur_node == start_node:
                    break

                chain = [perpendicular_endpoint(cur_node, theta + 180, cur_seg_r)]
                cur_nbr = prev_node

            else:
                # CCW-next half-edge.
                candidates = [(s, nb) for s, nb in adj[cur_node] if s != cur_seg]
                here = graph["nodes"][cur_node]
                candidates.sort(
                    key=lambda x: (
                        theta + 180 - point_theta(here, departure_target(cur_node, x[0]))
                    )
                    % 360
                )
                next_seg, next_nbr = candidates[0]
                theta_next = point_theta(here, departure_target(cur_node, next_seg))
                next_seg_r = seg_radius(next_seg)

                chain.append(
                    border_corner(cur_node, theta, cur_seg_r, theta_next, next_seg_r)
                )
                cur_seg = next_seg
                cur_nbr = next_nbr

    return "\n".join(local_group)


# ==================================================================================================
#               MAIN RUNTIME LOGIC
# ==================================================================================================
unprintable_item_types = {
    "origin",
    "node",
}

# Group instances by item_type
grouped_instances = defaultdict(list)
trace_path_instances = []
for instance in input_instances:
    if instance.get("item_type") not in unprintable_item_types:
        if instance.get("item_type") not in trace_path_item_types:
            grouped_instances[instance.get("item_type")].append(instance)
        else:
            trace_path_instances.append(instance)

# Layer ordering: front to back. SVG renders the last written group on top,
# so groups are written in reverse of this order (back first, front last).
layer_order = [
    "flagnote",
    "device_connector",
    "backshell",
    "other",
    "bundle_boundary",
    "cable_layout",
    "segment",
]

# Prepare lines for SVG content
group_content = {}
printable_instances = set()
flagnote_position_counter = {}
known_instance_types = set(layer_order) - {"other", "bundle_boundary", "cable_layout"}

# ==================================================================================================
# Step through each item_type and add relevant group backbone content to the SVG
for item_type, items in grouped_instances.items():
    lines = []
    lines.append(f'    <g id="{item_type}" inkscape:label="{item_type}">')

    for instance in items:
        if instance.get("item_type") in unprintable_item_types:
            continue

        instance_name = instance.get("instance_name")
        printable_instances.add(instance_name)

        x, y, angle = flattened_network.calculate_location(instance, input_instances)
        svg_px_x = x * 96
        svg_px_y = y * -96

        if item_type == "flagnote":
            leader_dest_temp_instance = instance
            leader_dest_temp_instance["parent_csys_outputcsys_name"] = (
                f"{instance.get('parent_csys_outputcsys_name')}-leader_dest"
            )
            x_leader_dest, y_leader_dest, angle_leader_dest = (
                flattened_network.calculate_location(
                    leader_dest_temp_instance, input_instances
                )
            )

            # translate, then scale, then replace
            lines.append(
                svg_utils.draw_clean_line(
                    [x, y], [x_leader_dest, y_leader_dest], scale=scale
                )
            )
            lines.append(
                f'      <g id="{instance_name}-translate" transform="translate({svg_px_x},{svg_px_y}) rotate({-1 * angle})">'
            )
            lines.append(
                f'      <g id="{instance_name}-scale" transform="scale({1 / scale})">'
            )
            lines.append(
                f'      <g id="{instance_name}-contents-start" inkscape:label="{instance_name}-contents-start">'
            )
            lines.append("      </g>")
            lines.append(
                f'      <g id="{instance_name}-contents-end" inkscape:label="{instance_name}-contents-end"></g>'
            )
            lines.append("      </g>")
            lines.append("      </g>")

        else:
            # just replace, no scale
            lines.append(
                f'      <g id="{instance_name}-contents-start" inkscape:label="{instance_name}-contents-start" transform="translate({svg_px_x},{svg_px_y}) rotate({-1 * angle})">'
            )
            lines.append("      </g>")
            lines.append(
                f'      <g id="{instance_name}-contents-end" inkscape:label="{instance_name}-contents-end"></g>'
            )

    lines.append("    </g>")
    if item_type in known_instance_types:
        group_content[item_type] = lines
    else:
        group_content.setdefault("other", [])
        group_content["other"].extend(lines)


# ==================================================================================================
# Draw routing paths for cable instances
#
# draw_segments_across_paths needs a network_2D dict with:
#   nodes    — {node_id: {x, y}}  (positions in inches)
#   segments — {seg_id: {node_at_end_a, node_at_end_b}}
#
# Cable instances carry node_at_end_a / node_at_end_b, which we pass directly
# via from_node_id_field / to_node_id_field so no field-name translation is needed.

if trace_path_instances not in [None, []]:
    # build the network
    network_nodes = {}
    network_segments = {}
    for instance in input_instances:
        if instance.get("item_type") == "node":
            name = instance.get("instance_name")
            x, y, _ = flattened_network.calculate_location(instance, input_instances)
            network_nodes[name] = {
                "x": x * 96,
                "y": y * -96,
            }  # inches → pixels, Y negated to match SVG convention

        if instance.get("item_type") == "segment":
            node_a = instance.get("node_at_end_a")
            node_b = instance.get("node_at_end_b")
            if node_a and node_b:
                network_segments[instance.get("instance_name")] = {
                    "node_at_end_a": node_a,
                    "node_at_end_b": node_b,
                    "diameter": float(instance.get("diameter", 1)),
                }

    flat_rows = {}
    try:
        for row in flattened_network.read_rows():
            flat_rows[row.get("segment_id") or ""] = row
    except Exception:
        flat_rows = {}
    for seg_id, seg in network_segments.items():
        row = flat_rows.get(seg_id)
        node_a = seg.get("node_at_end_a")
        if not row or node_a not in network_nodes:
            continue
        origin_x = network_nodes[node_a]["x"] / 96.0
        origin_y = -network_nodes[node_a]["y"] / 96.0
        poly = flattened_network.polyline_points(origin_x, origin_y, row)
        seg["waypoints"] = [
            {"x": px * 96.0, "y": -py * 96.0} for px, py in poly[1:-1]
        ]

    network_2D = {"nodes": network_nodes, "segments": network_segments}

    # Network coordinates are in pixels, so spacing/stroke are also in pixels.
    cable_svg = svg_utils.draw_segments_across_paths(
        trace_path_instances,
        network_2D,
        stroke_width=10,
        segment_spacing=20,
        label_font_size=8,
        from_node_id_field="node_at_end_a",
        to_node_id_field="node_at_end_b",
    )

    cable_lines = []
    cable_lines.append('    <g id="cable-paths">')
    cable_lines.append(cable_svg)
    cable_lines.append("    </g>")
    group_content["cable_layout"] = cable_lines

    bundle_border_svg = bundle_border(
        network_2D,
        stroke_width=5,
        junction_radius=20,
    )

    bundle_lines = []
    bundle_lines.append('    <g id="bundle-border">')
    bundle_lines.append(bundle_border_svg)
    bundle_lines.append("    </g>")
    group_content["bundle_boundary"] = bundle_lines


# Assemble content_lines in SVG write order (back to front = reverse of layer_order)
content_lines = []
for layer in reversed(layer_order):
    if layer in group_content:
        content_lines.extend(group_content[layer])


# ==================================================================================================
# write the svg file with group structure backbone
with open(path("output svg"), "w") as f:
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


# ==================================================================================================
# copy in instance content
# pull() does not overwrite existing editable drawings, so drop last build's
# flagnotes and recopy from the library template (print names, BOM bubbles, etc).
fileio.silentremove(os.path.join(dirpath(None), "instance_data", "flagnote"))
for instance in input_instances:
    item_type = instance.get("item_type", "").strip()
    if instance.get("instance_name") in printable_instances:
        # === handle flagnotes ===
        if instance.get("item_type") == "flagnote":
            flagnote_location = os.path.join(
                dirpath(None),
                "instance_data",
                "flagnote",
                instance.get("instance_name"),
            )
            make_new_flagnote_drawing(instance, flagnote_location)
            svg_utils.find_and_replace_svg_group(
                os.path.join(flagnote_location, "drawing.svg"),
                instance.get("instance_name"),
                path("output svg"),
                instance.get("instance_name"),
            )

        # === handle segments ===
        elif instance.get("item_type") in ["segment", "flagnote"]:
            # make as needed, edit this section to reference other segment drawings
            generated_instance_location = os.path.join(
                dirpath(None),
                "instance_data",
                "macro",
                f"{artifact_id}-{instance.get('instance_name')}",
            )
            if instance.get("item_type") == "segment":
                make_new_segment_drawing(
                    instance,
                    generated_instance_location,
                    dimension=dimension,
                    dimension_units="in",
                )

            svg_utils.find_and_replace_svg_group(
                os.path.join(generated_instance_location, "drawing.svg"),
                instance.get("instance_name"),
                path("output svg"),
                instance.get("instance_name"),
            )

        else:  # pull from project-level instance_data
            svg_utils.find_and_replace_svg_group(
                os.path.join(
                    fileio.dirpath(None),  # project root
                    "instance_data",
                    instance.get("item_type"),
                    instance.get("instance_name"),
                    "drawing.svg",
                ),
                instance.get("instance_name"),
                path("output svg"),
                instance.get("instance_name"),
            )
