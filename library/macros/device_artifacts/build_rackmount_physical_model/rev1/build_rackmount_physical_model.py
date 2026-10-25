from harnice.utils import physical_body

# Writes the device's body.step. Call from the device build instructions:
# build_utils.run_macro(
#     "build_rackmount_physical_model",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     params={"u": 2, "depth": 10},
#     images={
#         "front": os.path.join(fileio.dirpath("body_images"), "front.png"),
#     },
# )
#
# params keys: u (rack units) and depth (inches). Height is u * 1.75.
# The front ears are 19 inches wide and 1/16 inch thick. The body behind
# them is 17 inches wide. images is the same face-to-path dict as
# build_rectangular_physical_model.

if "params" not in globals() or params is None:
    raise ValueError("params is required")
if "images" not in globals() or images is None:
    images = {}

physical_body.build_rackmount_physical_model(params, images)
