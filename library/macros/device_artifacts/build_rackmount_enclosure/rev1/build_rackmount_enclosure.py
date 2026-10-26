import os

from harnice import fileio
from harnice.utils import cad

# Rack enclosure, in inches. Saved with fileio.path("body"), which is the
# device's body.step, not a file in this macro's folder.
#
# +X is right, +Z is up, and the front face is y = 0. That matches the
# viewer's view cube: Right is +X, Top is +Z, Front is -Y.
#
# The footprint sketch is on "right". That plane's normal is [0, 0, 1],
# u is [1, 0, 0] (width, +X) and v is [0, 1, 0] (depth, +Y). The sketch
# uuid is "shell". It is 21 inches wide, which is 19 inches plus 1 inch on
# each side, and `depth` deep with no extra margin. Width is centered on X.
# Depth starts at the front face and grows along +Y. extrude grows the
# solid along +Z by units * 1.75, plus 1 inch of wall on the top and the
# bottom.
#
# The opening sketch is on "front". That plane's normal is [0, 1, 0],
# u is [0, 0, 1] (height, +Z) and v is [1, 0, 0] (width, +X). The sketch
# uuid is "opening". It is exactly units * 1.75 tall and 17 inches wide.
# The ears belong to the rack, so this is 17 inches, not 19. It sits 1 inch
# above z = 0, centered in the 21 inch width. extrude grows that prism
# along +Y by the same depth. boolean_subtract cuts it out of the shell,
# so the front and the back are both open.
#
# Each rack unit gets a mate connector on the front face, centered on that
# unit of the opening. U1 is the bottom unit. x is 0, y is 0, and z is the
# middle of that 1.75 inch band, starting 1 inch above the bottom of the
# shell. Angles stay 0. A mate already saved under another id, such as a
# signals-list connector, is kept. An older U mate this enclosure no longer
# has is dropped.

if "depth" not in globals() or "units" not in globals():
    raise ValueError("depth and units are required")
depth = float(depth)
units = float(units)
if depth <= 0 or units <= 0:
    raise ValueError("depth and units must be greater than 0")

unit = 1.75
opening_height = units * unit
outer_height = opening_height + 2.0
half_outer = 10.5
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
