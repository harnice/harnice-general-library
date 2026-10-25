from harnice.utils import physical_body

# Writes the device's body.step. Call from the device build instructions:
# build_utils.run_macro(
#     "build_rectangular_physical_model",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     params={"width": 4, "height": 2, "depth": 6},
#     images={
#         "front": os.path.join(fileio.dirpath("body_images"), "front.png"),
#     },
# )
#
# params keys, inches: width (X), height (Y), depth (Z).
# images maps front, back, left, right, top, or bottom to an image path.
# The origin is the center of the front face.

if "params" not in globals() or params is None:
    raise ValueError("params is required")
if "images" not in globals() or images is None:
    images = {}

physical_body.build_rectangular_physical_model(params, images)
