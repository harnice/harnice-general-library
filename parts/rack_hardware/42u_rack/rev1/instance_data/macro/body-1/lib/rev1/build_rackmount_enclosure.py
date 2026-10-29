import os

from harnice import fileio
from harnice.utils import cad

# Rack enclosure, in inches. Saved with fileio.path("body"), which is the
# device's body.step, not a file in this macro's folder.
#
# The front of the rack is the front of the model: the face at y = 0, which
# is the viewer's front (minimum Y, normal -Y). +Z is up. +X is to the right
# when looking at that front. The shell extends along +Y by `depth`. Width
# is centered on X. Height grows along +Z.
#
# The footprint sketch is on "right". That plane's normal is [0, 0, 1],
# u is [1, 0, 0] (width, +X) and v is [0, 1, 0] (depth, +Y). The sketch
# uuid is "shell". It is 19 inches wide and `depth` deep. The front edge is
# v = 0. extrude grows the solid along +Z by units * 1.75, plus 1 inch of
# wall on the top and the bottom.
#
# The opening sketch is on "front". That plane's normal is [0, 1, 0], u is
# [0, 0, 1] (height, +Z) and v is [1, 0, 0] (width, +X). The sketch uuid is
# "opening". It is exactly units * 1.75 tall and 17 inches wide. The ears
# belong to the rack, so this is 17 inches, not 19. It sits 1 inch above
# z = 0, centered in the 19 inch width. extrude grows that prism along +Y
# through the shell. boolean_subtract cuts it out, so the front and the
# back are both open.
#
# Each rack unit gets two mate connectors, one on the front and one on the
# back, centered on that unit of the opening. F1 and B1 are the bottom unit.
# Front mates are at y = 0 with gamma -90, so +X points out the front (-Y)
# and +Z points up. Back mates are at y = depth with gamma 90, so +X points
# out the back (+Y) and +Z still points up. Each of these mates has source
# "build", so the next build places them again. A mate with source "gui"
# keeps the pose saved in attributes.json. A gui mate with the same id
# replaces the build mate. Other attributes in that file stay.

if "depth" not in globals() or "units" not in globals():
    raise ValueError("depth and units are required")
depth = float(depth)
units = float(units)
if depth <= 0 or units <= 0:
    raise ValueError("depth and units must be greater than 0")

unit = 1.75
opening_height = units * unit
outer_height = opening_height + 2.0
half_outer = 9.5
half_opening = 8.5
z0 = 1.0
z1 = z0 + opening_height

model = cad.new()
cad.sketch(
    model,
    "shell",
    "right",
    {
        "a": (-half_outer, 0.0),
        "b": (half_outer, 0.0),
        "c": (half_outer, depth),
        "d": (-half_outer, depth),
    },
    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")],
)
shell = cad.extrude(model, "shell", outer_height)
cad.sketch(
    model,
    "opening",
    "front",
    {
        "a": (z0, -half_opening),
        "b": (z1, -half_opening),
        "c": (z1, half_opening),
        "d": (z0, half_opening),
    },
    [("a", "b"), ("b", "c"), ("c", "d"), ("d", "a")],
)
opening = cad.extrude(model, "opening", depth)
cad.boolean_subtract(opening, shell)
cad.save_step(model, fileio.path("body"))

band_start = z0
index = 1
while band_start < z1:
    band = unit if band_start + unit <= z1 else z1 - band_start
    center = band_start + band / 2
    cad.mate(model, f"F{index}", [0, 0, center], gamma=-90)
    cad.mate(model, f"B{index}", [0, depth, center], gamma=90)
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
