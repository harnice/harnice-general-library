import os

from harnice import fileio
from harnice.utils import physical_drawing

# ARGS
# artifact_id = unique instance name for this run
# scale = drawing scale, same meaning as the formboard. 1 is full size.
# hidden_instances = device names to leave out. A list, or one name.
# orientation = "front", "back", "left", "right", "top", or "bottom",
#   or the viewport as alpha, beta, gamma: {"alpha": 0, "beta": 0, "gamma": 0}
#   or [alpha, beta, gamma]. (0, 0, 0) is the front view (look along +Y,
#   +X to the right, +Z up). R = Rx(alpha) · Ry(beta) · Rz(gamma).
#
# Face photos are <image> links to the PNG, relative to the revision.
# pdf_generator embeds those links as raster images in the PDF.
#
# build_utils.run_macro(
#     "physical_model_drawing",
#     "library/macros/system_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="physical-1",
#     scale=1,
#     hidden_instances=[],
#     orientation="front",
# )

artifact_mpn = "physical_model_drawing"

if "scale" not in globals() or scale is None:
    scale = 1
if "hidden_instances" not in globals() or hidden_instances is None:
    hidden_instances = []
if "orientation" not in globals() or orientation is None:
    orientation = "front"


def macro_file_structure():
    return {
        f"{artifact_id}-master.svg": "output svg",
    }


if base_directory is None:
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


os.makedirs(dirpath(None), exist_ok=True)

svg_text = physical_drawing.render_system_drawing(
    artifact_id,
    scale=scale,
    orientation=orientation,
    hidden_instances=hidden_instances,
)
with open(path("output svg"), "w", encoding="utf-8") as handle:
    handle.write(svg_text)
