import os

from harnice import fileio
from harnice.utils import cad

# Rack chassis, in inches. Saved with fileio.path("body"), which is the
# device's body.step, not a file in this macro's folder.
#
# +X is right, +Z is up, and the front face is y = 0. That matches the
# viewer's view cube: Right is +X, Top is +Z, Front is -Y.
#
# The sketch is on "right". That plane's normal is [0, 0, 1], u is [1, 0, 0]
# (width, +X) and v is [0, 1, 0] (depth, +Y). The sketch uuid is "bottom":
# the face at z = 0. extrude grows the solid along +Z by u * 1.75.
#
# The front ears are 19 inches wide and 1/16 inch thick. The chassis behind
# them is 17 inches wide. A depth shallower than the ear is just that plate.
# Width is centered on X. Depth starts at the front face and grows along +Y.
#
# images maps a surface uuid to a file. The front ears are also stored as
# the surface "front", which is the face the viewer paints. The orientation
# passed to attach_png is degrees.
#
# Each rack unit gets a mate connector on the front face, centered on that
# unit. U1 is the bottom unit. x is the center of the width, y is 0, and z
# is the middle of that 1.75 inch band. Angles stay 0. A mate already saved
# under another id, such as a signals-list connector, is kept. An older U
# mate this chassis no longer has is dropped.

if "params" not in globals() or not isinstance(params, dict):
    raise ValueError("params is required")
if "images" not in globals() or images is None:
    images = {}
elif not isinstance(images, dict):
    raise ValueError("images must be a dict of surface uuid to image path")

for name in ("u", "depth"):
    if name not in params:
        raise ValueError(f"params is missing {name}")
u_count = float(params["u"])
depth = float(params["depth"])
if not (0 < u_count < float("inf") and 0 < depth < float("inf")):
    raise ValueError("u and depth must be greater than zero")

height = u_count * 1.75
ear = 1.0 / 16.0
if depth < ear:
    ear = depth
half_ear = 19.0 / 2.0
half_body = 17.0 / 2.0

if depth <= ear:
    vertices = {
        "a": (-half_ear, 0.0),
        "b": (half_ear, 0.0),
        "c": (half_ear, depth),
        "d": (-half_ear, depth),
    }
    edges = [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")]
else:
    vertices = {
        "a": (-half_ear, 0.0),
        "b": (half_ear, 0.0),
        "c": (half_ear, ear),
        "d": (half_body, ear),
        "e": (half_body, depth),
        "f": (-half_body, depth),
        "g": (-half_body, ear),
        "h": (-half_ear, ear),
    }
    edges = [
        ("a", "b"), ("b", "c"), ("c", "d"), ("d", "e"),
        ("e", "f"), ("f", "g"), ("g", "h"), ("h", "a"),
    ]

model = cad.new()
cad.sketch(model, "bottom", "right", vertices, edges)
cad.extrude(model, "bottom", height)
# Edge a-b is the front face: y = 0, the ears, the full 19 inch width.
front_edge = model.surfaces["bottom-a-b"]
model.surfaces["front"] = {
    "plane": front_edge["plane"],
    "png": None,
    "orientation": None,
}
for surface, image_path in images.items():
    cad.attach_png(model, surface, image_path, 0)
cad.save_step(model, fileio.path("body"))

unit = 1.75
band_start = 0.0
index = 1
while band_start < height:
    band = unit if band_start + unit <= height else height - band_start
    cad.mate(model, f"U{index}", [0, 0, band_start + band / 2])
    band_start += unit
    index += 1

mates_path = fileio.path("mates")
if os.path.isfile(mates_path):
    from harnice.utils import physical_body

    have = {mate["id"] for mate in model.mates}
    for saved in physical_body.load_body(mates_path)["mate_connectors"]:
        name = saved["id"]
        if name in have:
            continue
        if len(name) > 1 and name[0] == "U" and name[1:].isdigit():
            continue
        cad.mate(
            model,
            name,
            saved["location"],
            saved["alpha"],
            saved["beta"],
            saved["gamma"],
        )
cad.save_mates(model, mates_path)
