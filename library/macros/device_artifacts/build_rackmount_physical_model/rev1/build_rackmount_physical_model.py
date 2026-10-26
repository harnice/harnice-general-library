import os

from harnice import fileio
from harnice.utils import cad

# Rack chassis, in inches. Saved with fileio.path("body"), which is the
# device's body.step, not a file in this macro's folder.
#
# The faceplate is the front of the model: the plane y = 0, which is the
# viewer's front (minimum Y, normal -Y). +Z is up. +X is to the right when
# looking at that front. The chassis extends along +Y by `depth`. Width is
# centered on X. Height grows along +Z.
#
# The sketch is on "right". That plane's normal is [0, 0, 1], u is [1, 0, 0]
# (width, +X) and v is [0, 1, 0] (depth, +Y). The sketch uuid is "bottom":
# the face at z = 0. The front edge is v = 0. extrude grows the solid along
# +Z by u * 1.75.
#
# The faceplate ears are 19 inches wide and 1/16 inch thick. The chassis
# behind them is 17 inches wide. A depth shallower than the ear is just that
# plate.
#
# images maps a surface name to a file. "front" is the faceplate, and the
# viewer paints that y = 0 face under the same name. "back" is the face at
# y = depth. "bottom" stays the sketch face at z = 0. The orientation passed
# to attach_png is degrees.
#
# Each rack unit gets a mate connector on the faceplate, centered on that
# unit. F1 is the bottom unit. x is 0, y is 0, and z is the middle of that
# 1.75 inch band. gamma is -90, so the mate's +X points out of the front
# and its +Z points up. Each of these mates has source "build", so the next
# build places them again. A mate with source "gui" keeps the pose saved in
# attributes.json. A gui mate with the same id replaces the build mate.
# Other attributes in that file stay.

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
    back_edge = "bottom-c-d"
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
    back_edge = "bottom-e-f"

model = cad.new()
cad.sketch(model, "bottom", "right", vertices, edges)
cad.extrude(model, "bottom", height)
# Edge a-b is the faceplate: y = 0, the ears, the full 19 inch width.
# The viewer calls this minimum-Y face "front".
faceplate = model.surfaces["bottom-a-b"]
model.surfaces["front"] = {
    "plane": faceplate["plane"],
    "png": None,
    "orientation": None,
}
back = model.surfaces[back_edge]
model.surfaces["back"] = {
    "plane": back["plane"],
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
    cad.mate(model, f"F{index}", [0, 0, band_start + band / 2], gamma=-90)
    band_start += unit
    index += 1

mates_path = fileio.path("attributes")
saved_body = None
if os.path.isfile(mates_path):
    from harnice.utils import physical_body

    saved_body = physical_body.load_body(mates_path)
if saved_body:
    cad.keep_gui_mates(model, saved_body["mate_connectors"])
cad.save_mates(model, mates_path)
