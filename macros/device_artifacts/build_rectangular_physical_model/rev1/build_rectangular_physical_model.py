from harnice import fileio
from harnice.utils import cad

# Rectangular solid, in inches. Saved with fileio.path("body"), which is the
# device's body.step, not a file in this macro's folder.
#
# cad.new() writes three datum planes:
#   top    normal [1, 0, 0]    u [0, 1, 0]    v [0, 0, 1]
#   front  normal [0, 1, 0]    u [0, 0, 1]    v [1, 0, 0]
#   right  normal [0, 0, 1]    u [1, 0, 0]    v [0, 1, 0]
#
# +X is right, +Z is up, and the front face is y = 0. The sketch is on
# "front", so u is +Z (height) and v is +X (width). Its uuid is "front":
# the face at y = 0. extrude grows the solid along +Y by depth. Width and
# height are centered on the origin.
#
# extrude also adds the far face "front-end" (y = depth) and one side per
# edge: "front-a-b", "front-b-c", "front-c-d", "front-d-a". images maps one of
# those surface uuids to a file. The orientation is degrees.

if "params" not in globals() or not isinstance(params, dict):
    raise ValueError("params is required")
if "images" not in globals() or images is None:
    images = {}
elif not isinstance(images, dict):
    raise ValueError("images must be a dict of surface uuid to image path")

for name in ("width", "height", "depth"):
    if name not in params:
        raise ValueError(f"params is missing {name}")
width = float(params["width"])
height = float(params["height"])
depth = float(params["depth"])
if not (0 < width < float("inf") and 0 < height < float("inf") and 0 < depth < float("inf")):
    raise ValueError("width, height, and depth must be greater than zero")

half_w = width / 2
half_h = height / 2
model = cad.new()
cad.sketch(
    model,
    "front",
    "front",
    {
        "a": (-half_h, -half_w),
        "b": (half_h, -half_w),
        "c": (half_h, half_w),
        "d": (-half_h, half_w),
    },
    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")],
)
cad.extrude(model, "front", depth)
for surface, image_path in images.items():
    cad.attach_png(model, surface, image_path, 0)
cad.save_step(model, fileio.path("body"))
