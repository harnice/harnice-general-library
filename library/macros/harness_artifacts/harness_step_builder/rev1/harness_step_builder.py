import os

from harnice import fileio
from harnice.lists import flattened_network, instances_list
from harnice.utils import bundle_network_utils, cable_utils, step_utils

artifact_mpn = "harness_step_builder"

# describe your args here. comment them out and do not officially define because they are called via runpy,
# for example, the caller build instructions should define the arguments like this:
# build_utils.run_macro(
#    "harness_step_builder",
#    "library/macros/harness_artifacts",
#    "https://github.com/harnice/harnice-general-library",
#    artifact_id="harness-step-1",
#    chosen_network=bundle_network,
#    input_instances=instances_list.read(),
# )

# chosen_network: required. The chosen (solved) 3D network dict with "segments"
# and "nodes". Default harness build passes bundle_network.
# input_instances: optional. Which instances to write into the STEP. Defaults
# to instances_list.read(). Omit parents if you like; placement still walks
# the full instances list.

INCH_TO_MM = step_utils.INCH_TO_MM
SKIP_MODEL_ITEM_TYPES = {
    "segment",
    "macro",
    "note",
    "flagnote",
    "cable",
    "conductor",
    "cable-segment",
    "conductor-segment",
}
_JOIN_EPS_IN = 1e-6


def macro_file_structure():
    return {
        f"{artifact_id}.step": "harness step",
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
    return fileio.dirpath(
        target_value,
        structure_dict=macro_file_structure(),
        base_directory=base_directory,
    )


try:
    chosen_network
except NameError:
    raise ValueError(
        "harness_step_builder requires argument 'chosen_network' "
        "(pass the chosen network dict from harness build instructions)"
    )

if not isinstance(chosen_network, dict):
    raise ValueError(
        "harness_step_builder argument 'chosen_network' must be a network dict"
    )

try:
    input_instances
except NameError:
    input_instances = None
if input_instances in ("", None):
    input_instances = instances_list.read()
if not isinstance(input_instances, (list, tuple)):
    raise ValueError(
        "harness_step_builder argument 'input_instances' must be a list of instance dicts"
    )

world_instances = instances_list.read()


def _positive_float(value):
    if value in ("", None):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return number


def _instance_model_path(instance):
    item_type = instance.get("item_type")
    name = instance.get("instance_name")
    if item_type in ("", None) or name in ("", None):
        return None
    return os.path.join(
        fileio.dirpath(None),
        "instance_data",
        item_type,
        name,
        f"{name}-model.step",
    )


def _diameter_lookup(instances):
    lookup = {}
    for instance in instances:
        if instance.get("item_type") != "segment":
            continue
        diameter = _positive_float(instance.get("diameter"))
        if diameter is None:
            continue
        name = instance.get("instance_name")
        group = instance.get("segment_group")
        if name not in ("", None):
            lookup[name] = diameter
        if group not in ("", None):
            lookup[group] = diameter
    return lookup


def _near(a, b, eps=_JOIN_EPS_IN):
    return (
        abs(a[0] - b[0]) <= eps
        and abs(a[1] - b[1]) <= eps
        and abs(a[2] - b[2]) <= eps
    )


def _points_mm(points_in):
    return [
        (x * INCH_TO_MM, y * INCH_TO_MM, z * INCH_TO_MM) for x, y, z in points_in
    ]


def _tube_from_points_in(points_in, diameter_in):
    points_mm = _points_mm(points_in)
    radius_mm = (diameter_in / 2.0) * INCH_TO_MM
    radii = [radius_mm] * len(points_mm)
    return step_utils.sweep_triangles(points_mm, radii)


def _segment_tube(segment, diameter_in):
    return _tube_from_points_in(flattened_network.spline_points(segment), diameter_in)


def _centerline_inches(hops, segments_by_id):
    points = []
    for seg_name, direction in hops:
        segment = segments_by_id.get(seg_name)
        if segment is None:
            continue
        pts = list(flattened_network.spline_points(segment))
        if direction == "ba":
            pts.reverse()
        if not pts:
            continue
        if points and _near(points[-1], pts[0]):
            pts = pts[1:]
        points.extend(pts)
    return points


def _append_trace_tube(bodies, name, hops, segments_by_id, diameter_in):
    if diameter_in is None or diameter_in <= 0:
        return
    points_in = _centerline_inches(hops, segments_by_id)
    if len(points_in) < 2:
        return
    try:
        triangles = _tube_from_points_in(points_in, diameter_in)
    except ValueError:
        return
    bodies.append({"name": str(name), "triangles": triangles})


include_segment_ids = set()
for instance in input_instances:
    if instance.get("item_type") != "segment":
        continue
    name = instance.get("instance_name")
    group = instance.get("segment_group")
    if name not in ("", None):
        include_segment_ids.add(name)
    if group not in ("", None):
        include_segment_ids.add(group)

diameters = _diameter_lookup(world_instances)
segments_by_id = {
    segment.get("segment_id"): segment
    for segment in (chosen_network.get("segments") or [])
    if segment.get("segment_id") not in ("", None)
}
bodies = []

for segment in chosen_network.get("segments") or []:
    segment_id = segment.get("segment_id")
    if segment_id in ("", None):
        continue
    if segment_id not in include_segment_ids:
        continue
    diameter = diameters.get(segment_id)
    if diameter is None:
        continue
    try:
        triangles = _segment_tube(segment, diameter)
    except ValueError:
        continue
    bodies.append({"name": str(segment_id), "triangles": triangles})

for instance in input_instances:
    item_type = instance.get("item_type")
    name = instance.get("instance_name")
    if name in ("", None):
        continue
    if item_type == "cable":
        hops = cable_utils.mapped_segment_hops(name, "cable-segment", world_instances)
        if not hops:
            continue
        try:
            diameter = cable_utils.cable_jacket_od(name, instance)
        except ValueError:
            continue
        _append_trace_tube(bodies, name, hops, segments_by_id, diameter)
    elif item_type == "conductor":
        hops = cable_utils.mapped_segment_hops(name, "conductor-segment", world_instances)
        if not hops:
            continue
        try:
            diameter = cable_utils.conductor_od(instance, world_instances)
        except ValueError:
            continue
        _append_trace_tube(bodies, name, hops, segments_by_id, diameter)

for instance in input_instances:
    if instance.get("item_type") in SKIP_MODEL_ITEM_TYPES:
        continue
    model_path = _instance_model_path(instance)
    if model_path is None or not os.path.isfile(model_path):
        continue
    shape = step_utils.read_step_shape(model_path)
    if shape is None:
        continue
    x, y, z, alpha, beta, gamma = bundle_network_utils.calculate_location_3d(
        instance, world_instances
    )
    placed = step_utils.transform_shape(
        shape,
        x * INCH_TO_MM,
        y * INCH_TO_MM,
        z * INCH_TO_MM,
        alpha,
        beta,
        gamma,
    )
    bodies.append({"name": instance.get("instance_name"), "shape": placed})

if not bodies:
    raise ValueError(
        "harness_step_builder found no segment tubes or component STEP bodies to write"
    )

step_utils.write_assembly_step(
    path("harness step"),
    f"{artifact_id}",
    bodies,
    description="harness assembly",
)
