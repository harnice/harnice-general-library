from harnice import fileio
from harnice.utils import cad

# Copies a STEP file onto the device at fileio.path("body").
# import_step does not build a cad model, so there is no surface to attach
# an image to. Bytes are copied unchanged.

if "path_to_step" not in globals() or not path_to_step:
    raise ValueError("path_to_step is required")

cad.import_step(path_to_step, fileio.path("body"))
