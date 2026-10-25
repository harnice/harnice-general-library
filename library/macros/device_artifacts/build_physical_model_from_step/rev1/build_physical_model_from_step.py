from harnice.utils import physical_body

# Copies a STEP file onto the device as body.step. Call from the device
# build instructions:
# build_utils.run_macro(
#     "build_physical_model_from_step",
#     "library/macros/device_artifacts",
#     "https://github.com/harnice/harnice-general-library",
#     artifact_id="body-1",
#     path_to_step="vendor/chassis.step",
# )
#
# Bytes are copied unchanged, so image links already in that file stay.

if "path_to_step" not in globals() or not path_to_step:
    raise ValueError("path_to_step is required")

physical_body.build_physical_model_from_step(path_to_step)
